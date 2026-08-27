#!/usr/bin/env python3
"""Compare Fix8t hardware captures with deterministic golden Wi-Fi IQ."""

import argparse
import math
from pathlib import Path

import numpy as np

from wifi_aim_offline import FS, LONG, load_c8, metadata
from test_fix8u_sync_geometry import RATES, find_sync, q16_at, trigger_capture


def corr(ref, value):
    den = np.vdot(ref, ref).real * np.vdot(value, value).real
    return 0.0 if den <= 1.0 else float(abs(np.vdot(ref, value)) ** 2 / den)


def ltf_pair_at(x, pos, cfo_hz):
    if pos < 0 or pos + 128 > len(x):
        return 0.0
    n = np.arange(128)
    y = x[pos:pos+128] * np.exp(-2j*np.pi*cfo_hz*n/FS)
    ref = np.fft.ifft(LONG)
    return min(corr(ref, y[:64]), corr(ref, y[64:]))


def max_stf(x, limit=5000):
    end = min(limit, len(x)-80)
    values = np.array([q16_at(x, d) for d in range(end)])
    at = int(np.argmax(values))
    return float(values[at]), at


def spectrum_metrics(x, center):
    start = max(0, min(len(x)-1024, center-192))
    y = x[start:start+1024]
    window = np.hanning(len(y))
    p = np.abs(np.fft.fftshift(np.fft.fft(y*window)))**2 + 1e-12
    p /= p.sum()
    n = len(p)
    flatness = float(np.exp(np.mean(np.log(p))) / np.mean(p))
    peak_median_db = float(10*np.log10(p.max()/np.median(p)))
    dc_median_db = float(10*np.log10(p[n//2]/np.median(p)))
    # Narrowest contiguous FFT interval containing 90% of power.
    c = np.concatenate(([0.0], np.cumsum(p)))
    best = n
    j = 0
    for i in range(n):
        if j < i: j = i
        while j < n and c[j+1]-c[i] < 0.90: j += 1
        if j < n: best = min(best, j-i+1)
    return {
        "flatness": flatness,
        "peak_median_db": peak_median_db,
        "dc_median_db": dc_median_db,
        "bw90_mhz": best * FS / n / 1e6,
    }


def power_db(a, b):
    return float(10*np.log10(max(a,1e-12)/max(b,1e-12)))


def row_for(name, x, ltf, cfo, channel):
    stf, stf_at = max_stf(x)
    loose = find_sync(x, stf_threshold=0.30, ltf_threshold=0.0)
    p = np.abs(x)**2
    pre = float(p[:2048].mean())
    trig = float(p[2048:4096].mean())
    boundary_before = float(p[1920:2048].mean())
    boundary_after = float(p[2048:2176].mean())
    spec = spectrum_metrics(x, ltf)
    return {
        "name": name,
        "channel": channel,
        "ltf": ltf,
        "delta2048": ltf-2048,
        "cfo_hz": cfo,
        "stf": stf,
        "stf_at": stf_at,
        "ltf_reported_pair": ltf_pair_at(x, ltf, cfo),
        "ltf_loose_best": 0.0 if loose is None else loose["ltf_score"],
        "ltf_loose_at": None if loose is None else loose["ltf"],
        "trigger_vs_pre_db": power_db(trig, pre),
        "boundary_step_db": power_db(boundary_after, boundary_before),
        **spec,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    rows=[]
    for c8 in sorted(args.directory.glob("WAIM_00*.C8")):
        txt=c8.with_suffix(".TXT")
        if not txt.exists(): continue
        m=metadata(txt)
        rows.append(row_for(c8.name,load_c8(c8),m["ltf_position"],m["cfo_hz"],m["channel"]))

    golden=[]
    positions=(1800,2048,2200,2500,3000,3500,4096,4500)
    for rate,pos in zip(RATES,positions):
        x=trigger_capture(rate,pos)
        golden.append(row_for(f"golden-{RATES[rate][3]}M",x,pos,180000,6))

    def line(r):
        return (
            f"| {r['name']} | {r['channel']} | {r['ltf']} | {r['delta2048']:+d} | "
            f"{100*r['stf']:.1f}% @{r['stf_at']} | {100*r['ltf_reported_pair']:.1f}% | "
            f"{100*r['ltf_loose_best']:.1f}% | {r['trigger_vs_pre_db']:+.1f} | "
            f"{r['boundary_step_db']:+.1f} | {r['bw90_mhz']:.1f} | "
            f"{r['flatness']:.3f} | {r['peak_median_db']:.1f} |"
        )

    admitted = [r for r in rows if r["stf"] >= 0.75 and r["ltf_loose_best"] >= 0.30]
    rejected = [r for r in rows if r["stf"] < 0.75 and r["ltf_loose_best"] < 0.30]
    ambiguous = [r for r in rows if r not in admitted and r not in rejected]

    def names(items):
        return ", ".join(r["name"] for r in items)

    verdict = [
        "The old 2200-sample limit is a search-geometry defect. Golden packets "
        "with LTF at 2500, 3000, 3500, 4096, and 4500 are valid but cannot be "
        "reached by the old search.",
    ]
    if admitted:
        verdict.append(
            f"- Synchronization evidence passes for {names(admitted)}: sustained "
            "STF is at least 75% and the absolute LTF pair is at least 30%."
        )
    if rejected:
        verdict.append(
            f"- Synchronization evidence rejects {names(rejected)}: both STF and "
            "absolute LTF are below their admission thresholds."
        )
    if ambiguous:
        verdict.append(
            f"- Mixed synchronization evidence remains for {names(ambiguous)}; "
            "inspect the capture before classifying it."
        )
    if not rows:
        verdict.append("- No matching WAIM_00*.C8/TXT pairs were found.")

    out=[
        "# Fix8u RAW IQ comparison",
        "",
        "| Capture | CH | LTF | LTF-2048 | max STF | reported LTF pair | loose best LTF | trigger/pre dB | boundary dB | BW90 MHz | flatness | peak/median dB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[line(r) for r in rows],
        "",
        "## Golden IQ",
        "",
        "| Capture | CH | LTF | LTF-2048 | max STF | reported LTF pair | loose best LTF | trigger/pre dB | boundary dB | BW90 MHz | flatness | peak/median dB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[line(r) for r in golden],
        "",
        "Thresholds: sustained STF >= 75%; weaker absolute LTF pair >= 30%.",
        "",
        "## Verdict",
        "",
        *verdict,
    ]
    text="\n".join(out)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
