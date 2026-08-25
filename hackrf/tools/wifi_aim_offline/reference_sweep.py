#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import pathlib
import random
import subprocess
import sys

import numpy as np


def beacon_mpdu(ssid=b"WAIM-REFERENCE", channel=6):
    # Minimal legacy beacon MPDU sufficient for WiFi AIM's prefix parser.
    bssid = bytes.fromhex("021122334455")
    p = bytearray()
    p += bytes.fromhex("8000")                  # Beacon frame control
    p += bytes.fromhex("0000")                  # Duration
    p += b"\xff" * 6                            # DA
    p += bssid                                   # SA
    p += bssid                                   # BSSID
    p += bytes.fromhex("0000")                  # Sequence control
    p += b"\x00" * 8                            # Timestamp
    p += bytes.fromhex("6400")                  # Beacon interval
    p += bytes.fromhex("0100")                  # Capabilities
    p += bytes([0, len(ssid)]) + ssid            # SSID IE
    p += bytes([3, 1, channel])                  # DS parameter set IE
    return bytes(p)


def quantize_iq8(sig, target_peak=100.0):
    x = np.asarray(sig, dtype=np.complex64)
    peak = max(float(np.max(np.abs(x.real))), float(np.max(np.abs(x.imag))), 1e-9)
    scale = target_peak / peak
    i = np.clip(np.rint(x.real * scale), -127, 127).astype(np.int8)
    q = np.clip(np.rint(x.imag * scale), -127, 127).astype(np.int8)
    out = np.empty(i.size * 2, dtype=np.int8)
    out[0::2] = i
    out[1::2] = q
    return out


def add_awgn(sig, snr_db, rng):
    x = np.asarray(sig, dtype=np.complex64)
    p = float(np.mean(np.abs(x) ** 2))
    if p <= 0:
        return x
    npow = p / (10.0 ** (snr_db / 10.0))
    n = (rng.normal(size=x.size) + 1j * rng.normal(size=x.size)) * math.sqrt(npow / 2.0)
    return (x + n).astype(np.complex64)


def add_multipath(sig, delay, gain):
    x = np.asarray(sig, dtype=np.complex64)
    y = x.copy()
    if delay > 0 and delay < x.size:
        y[delay:] += np.complex64(gain) * x[:-delay]
    return y


def run_decoder(exe, iq8, tmp_path):
    iq8.tofile(tmp_path)
    cp = subprocess.run([exe, str(tmp_path)], text=True, capture_output=True, check=True)
    return json.loads(cp.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decoder", required=True)
    ap.add_argument("--reference-tools", required=True)
    ap.add_argument("--out", default="wifi_aim_offline_results")
    args = ap.parse_args()

    ref_tools = pathlib.Path(args.reference_tools).resolve()
    sys.path.insert(0, str(ref_tools))
    import phy80211
    import phy80211header as p8h

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    tmp = outdir / "vector.iq8"
    rows = []
    rng = np.random.default_rng(0x5741494D)
    mpdu = beacon_mpdu()

    # Reference project's legacy MCS 0..7 corresponds to 6/9/12/18/24/36/48/54 Mb/s.
    rates = [6, 9, 12, 18, 24, 36, 48, 54]

    def generate(mcs, cfo_hz=0.0):
        phy = phy80211.phy80211(ifDebug=False)
        mod = p8h.modulation(phyFormat=p8h.F.L, mcs=mcs, bw=p8h.BW.BW20, nSTS=1, shortGi=False)
        phy.genFromMpdu(mpdu, mod)
        streams = phy.genFinalSig(multiplier=1.0, cfoHz=float(cfo_hz), num=1, gap=True, gapLen=512)
        if not streams or not streams[0]:
            raise RuntimeError("reference generator returned no samples")
        return np.asarray(streams[0], dtype=np.complex64)

    def test(name, mcs, sig, impairment, value):
        iq8 = quantize_iq8(sig)
        r = run_decoder(args.decoder, iq8, tmp)
        row = {
            "name": name,
            "mcs": mcs,
            "expected_rate_mbps": rates[mcs],
            "impairment": impairment,
            "value": value,
            **r,
        }
        rows.append(row)
        print(json.dumps(row, sort_keys=True))

    # A. Golden clean vectors for every legacy rate.
    clean_by_mcs = {}
    for mcs in range(8):
        sig = generate(mcs, 0.0)
        clean_by_mcs[mcs] = sig
        test(f"clean_mcs{mcs}", mcs, sig, "clean", 0)

    # B. CFO sweep focused on the 6 Mb/s beacon. Includes integer-bin and adjacent-channel offsets.
    for cfo in [-5_000_000, -1_000_000, -625_000, -312_500, -156_250, -100_000,
                -50_000, 50_000, 100_000, 156_250, 312_500, 625_000, 1_000_000, 5_000_000]:
        test(f"cfo_{cfo:+d}", 0, generate(0, cfo), "cfo_hz", cfo)

    # C. Noise robustness on the exact same independently generated clean vector.
    base = clean_by_mcs[0]
    for snr in [30, 20, 15, 10, 7, 5]:
        test(f"awgn_{snr}dB", 0, add_awgn(base, snr, rng), "snr_db", snr)

    # D. Simple delayed echo, within and beyond the 16-sample legacy OFDM GI.
    for delay, gain in [(1, 0.25), (4, 0.35), (8, 0.35), (12, 0.35), (16, 0.35), (20, 0.35)]:
        test(f"echo_d{delay}_g{gain}", 0, add_multipath(base, delay, gain), "echo", f"d={delay},g={gain}")

    csv_path = outdir / "results.csv"
    json_path = outdir / "results.json"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    clean = [r for r in rows if r["impairment"] == "clean"]
    clean_ok = sum(bool(r["ok"]) and r["rate_mbps"] == r["expected_rate_mbps"] for r in clean)
    stage_hist = {}
    for r in rows:
        stage_hist[str(r["stage"])] = stage_hist.get(str(r["stage"]), 0) + 1
    summary = {
        "reference": "cloud9477/gr-ieee80211 Python PHY generator",
        "clean_exact_pass": clean_ok,
        "clean_total": len(clean),
        "stage_histogram": stage_hist,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
