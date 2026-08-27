#!/usr/bin/env python3
"""Offline audit of the current M4LegacyWifiDecoder assumptions."""

import argparse
import binascii
import json
from pathlib import Path

import numpy as np


BARKER = np.asarray([1, -1, 1, 1, -1, 1, 1, 1, -1, -1, -1], dtype=np.float64)
STAGES = [
    "admission", "barker_correlation", "symbol_timing", "differential_decode",
    "descramble", "plcp_header", "payload", "mac_type", "beacon_probe",
    "ssid", "final_ap",
]


def bits_lsb(data):
    return [(value >> bit) & 1 for value in data for bit in range(8)]


def bits_value(bits, start, count):
    return sum(int(bits[start + bit]) << bit for bit in range(count))


def management_psdu(subtype, ssid=b"FIX8DSSS", channel=7, length=96):
    bssid = bytes.fromhex("02d055aa7711")
    frame = bytearray()
    frame += ((subtype & 15) << 4).to_bytes(2, "little") + b"\x00\x00"
    frame += b"\xff" * 6 + bssid + bssid + b"\x10\x00"
    frame += b"\x00" * 8 + (100).to_bytes(2, "little") + b"\x01\x04"
    frame += bytes((0, len(ssid))) + ssid + bytes((3, 1, channel))
    frame += bytes((1, 4, 0x82, 0x84, 0x8B, 0x96))
    if len(frame) < length - 4:
        frame += bytes(length - 4 - len(frame))
    frame = frame[:length - 4]
    frame += (binascii.crc32(frame) & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(frame)


def scramble(bits, seed=0x5D):
    # Generate the transmitted sequence in the exact self-synchronizing form
    # inverted by M4LegacyWifiDecoder: plain[n]=s[n]^s[n-4]^s[n-7].
    out = [((seed >> (6 - n)) & 1) for n in range(min(7, len(bits)))]
    for n in range(7, len(bits)):
        out.append((int(bits[n]) & 1) ^ out[n - 4] ^ out[n - 7])
    return out


def dbpsk_chips(bits, phase=1.0 + 0j):
    chips = []
    current = phase
    for bit in bits:
        if bit:
            current = -current
        chips.extend(current * BARKER)
    return chips, current


def dqpsk_chips(bits, phase=1.0 + 0j):
    # Differential dibit mapping is sufficient for the audit because the
    # current decoder rejects SIGNAL=0x14 before attempting a 2 Mbit/s payload.
    rotation = {
        (0, 0): 1.0 + 0j,
        (0, 1): 0.0 + 1j,
        (1, 1): -1.0 + 0j,
        (1, 0): 0.0 - 1j,
    }
    chips = []
    current = phase
    for offset in range(0, len(bits) - 1, 2):
        current *= rotation[(bits[offset], bits[offset + 1])]
        chips.extend(current * BARKER)
    return chips, current


def generate_ppdu(rate_mbps=1, subtype=8, short_preamble=False, timing_offset=0,
                  sample_count=20000, scale=60.0):
    psdu = management_psdu(subtype)
    if short_preamble:
        preamble = [0] * 56 + bits_lsb((0x05CF).to_bytes(2, "little"))
    else:
        preamble = [1] * 128 + bits_lsb((0xF3A0).to_bytes(2, "little"))
    signal = 0x0A if rate_mbps == 1 else 0x14
    length_us = len(psdu) * 8 // rate_mbps
    header = bits_lsb(bytes((signal, 0))) + bits_lsb(length_us.to_bytes(2, "little")) + [0] * 16
    all_plain = preamble + header + bits_lsb(psdu)
    all_scrambled = scramble(all_plain)
    header_bits = len(preamble) + len(header)
    chips, phase = dbpsk_chips(all_scrambled[:header_bits])
    if rate_mbps == 1:
        payload_chips, _ = dbpsk_chips(all_scrambled[header_bits:], phase)
    else:
        payload_chips, _ = dqpsk_chips(all_scrambled[header_bits:], phase)
    chips = np.asarray(chips + payload_chips, dtype=np.complex128)
    result = np.zeros(sample_count, dtype=np.complex128)
    n = np.arange(max(0, sample_count - timing_offset))
    chip_index = (n * 11) // 20
    valid = chip_index < len(chips)
    result[timing_offset + n[valid]] = chips[chip_index[valid]] * scale
    return result, psdu


def parse_prefix(frame):
    if len(frame) < 36:
        return {"mac_type": False, "beacon_probe": False, "ssid": False}
    fc = int.from_bytes(frame[:2], "little")
    frame_type = (fc >> 2) & 3
    subtype = (fc >> 4) & 15
    result = {
        "fc": f"0x{fc:04x}",
        "frame_type": frame_type,
        "frame_subtype": subtype,
        "mac_type": frame_type == 0,
        "beacon_probe": frame_type == 0 and subtype in (8, 5),
        "ssid": False,
        "ssid_value": None,
    }
    if not result["beacon_probe"]:
        return result
    p = 36
    while p + 2 <= len(frame):
        element, size = frame[p], frame[p + 1]
        p += 2
        if p + size > len(frame):
            break
        if element == 0:
            result["ssid"] = True
            result["ssid_value"] = frame[p:p + size].decode("utf-8", "replace")
            break
        p += size
    return result


def decode_like_firmware(samples):
    count = len(samples)
    reached = {name: False for name in STAGES}
    reached["admission"] = count >= 5000
    result = {"stages": reached, "failure": "admission"}
    if count < 5000:
        return result
    max_chips = count * 11 // 20
    best_barker = 0.0
    for phase in range(20):
        for symbol_offset in range(11):
            starts = np.arange(symbol_offset, max_chips - 10, 11, dtype=np.int64)
            if len(starts) < 257:
                continue
            chip_offsets = starts[:, None] + np.arange(11, dtype=np.int64)[None, :]
            indices = (chip_offsets * 20 + phase + 5) // 11
            valid_rows = np.all(indices < count, axis=1)
            indices = indices[valid_rows]
            if len(indices) < 257:
                continue
            corr = samples[indices] @ BARKER
            best_barker = max(best_barker, float(np.max(np.abs(corr))))
            reached["barker_correlation"] = best_barker > 0
            reached["symbol_timing"] = True
            dot = np.real(corr[1:] * np.conj(corr[:-1]))
            scrambled = (dot < 0).astype(np.uint8)[:2048]
            if len(scrambled) < 256:
                continue
            reached["differential_decode"] = True
            plain = np.zeros_like(scrambled)
            plain[7:] = scrambled[7:] ^ scrambled[3:-4] ^ scrambled[:-7]
            reached["descramble"] = True
            for p in range(64, len(plain) - (16 + 48 + 36 * 8)):
                if bits_value(plain, p, 16) != 0xF3A0:
                    continue
                header = p + 16
                signal = bits_value(plain, header, 8)
                result.update(sfd_position=int(p), plcp_signal=f"0x{signal:02x}")
                reached["plcp_header"] = True
                if signal != 0x0A:
                    result["failure"] = "unsupported_plcp_rate"
                    continue
                length_us = bits_value(plain, header + 16, 16)
                result["plcp_length_us"] = int(length_us)
                if not length_us or length_us & 7:
                    result["failure"] = "plcp_length"
                    continue
                expected = length_us // 8
                payload = header + 48
                available = (len(plain) - payload) // 8
                nbytes = min(expected, available, 96)
                if nbytes < 36:
                    result["failure"] = "payload_short"
                    continue
                frame = bytes(bits_value(plain, payload + byte * 8, 8) for byte in range(nbytes))
                reached["payload"] = True
                mac = parse_prefix(frame)
                result.update(mac)
                reached["mac_type"] |= mac["mac_type"]
                reached["beacon_probe"] |= mac["beacon_probe"]
                reached["ssid"] |= mac["ssid"]
                if mac["ssid"]:
                    reached["final_ap"] = True
                    result["failure"] = None
                    result["best_barker"] = best_barker
                    return result
    result["best_barker"] = best_barker
    if result["failure"] == "admission":
        result["failure"] = "sfd_or_plcp"
    return result


def audit_cases():
    cases = []
    for rate in (1, 2):
        for subtype, label in ((8, "beacon"), (5, "probe_response")):
            samples, _ = generate_ppdu(rate_mbps=rate, subtype=subtype)
            row = decode_like_firmware(samples)
            row.update(name=f"long_{rate}M_{label}", rate_mbps=rate, subtype=subtype, short_preamble=False)
            cases.append(row)
    samples, _ = generate_ppdu(rate_mbps=1, subtype=8, short_preamble=True)
    row = decode_like_firmware(samples)
    row.update(name="short_1M_beacon", rate_mbps=1, subtype=8, short_preamble=True)
    cases.append(row)
    timing_pass = 0
    for offset in range(20):
        samples, _ = generate_ppdu(rate_mbps=1, subtype=8, timing_offset=offset)
        timing_pass += decode_like_firmware(samples)["stages"]["final_ap"]
    return cases, timing_pass


def render(cases, timing_pass):
    out = [
        "# Fix8w DSSS fallback audit",
        "",
        "| Case | admission | Barker | timing | differential | descramble | PLCP | payload | MAC | Beacon/Probe | SSID | final AP | failure |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in cases:
        s = row["stages"]
        out.append(
            f"| {row['name']} | {s['admission']} | {s['barker_correlation']} | {s['symbol_timing']} | "
            f"{s['differential_decode']} | {s['descramble']} | {s['plcp_header']} | {s['payload']} | "
            f"{s['mac_type']} | {s['beacon_probe']} | {s['ssid']} | {s['final_ap']} | {row.get('failure')} |"
        )
    out += [
        "",
        f"Long-preamble 1 Mbit/s timing sweep: {timing_pass}/20 sample phases pass.",
        "",
        "## Audit findings",
        "",
        "- The current fallback is long-preamble, 1 Mbit/s DBPSK only.",
        "- SIGNAL must equal `0x0A`; a valid long-preamble 2 Mbit/s (`0x14`) frame is rejected before payload.",
        "- Short preamble/SFD and its 2 Mbit/s header modulation are unsupported.",
        "- PLCP CRC is not checked. LENGTH is assumed to be a 1 Mbit/s microsecond count and divided by eight.",
        "- The Fix8v baseline exposed only attempted/success. The Fix8w diagnostic patch adds all eleven stage counters over a new diagnostic subtype without changing WireApReport layout.",
        "- The self-synchronizing descrambler and payload offset are correct for generated long-preamble 1 Mbit/s Beacon and Probe Response frames.",
    ]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    cases, timing_pass = audit_cases()
    one_m = [row for row in cases if row["rate_mbps"] == 1 and not row["short_preamble"]]
    two_m = [row for row in cases if row["rate_mbps"] == 2]
    assert all(row["stages"]["final_ap"] for row in one_m), one_m
    assert all(not row["stages"]["final_ap"] and row["failure"] == "unsupported_plcp_rate" for row in two_m), two_m
    assert timing_pass == 20, timing_pass
    report = render(cases, timing_pass)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "fix8w_dsss_audit.json").write_text(json.dumps({"cases": cases, "timing_pass": timing_pass}, indent=2) + "\n")
        (args.output / "fix8w_dsss_audit.md").write_text(report)
    print(report)
    print("FIX8W_DSSS_REFERENCE=PASS long_1M=2/2 timing_phases=20/20 unsupported_2M_confirmed=2/2")


if __name__ == "__main__":
    main()
