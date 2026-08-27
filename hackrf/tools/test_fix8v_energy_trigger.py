#!/usr/bin/env python3
"""Fix8v offline reliability profiler for the unchanged Fix8u energy trigger."""

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fix8u_sync_geometry import make_packet
from wifi_aim_offline import RATES, load_c8, metadata


BLOCK = 2048
SUBBLOCKS = (256, 128)
RATE_ORDER = (0xB, 0xF, 0xA, 0xE, 0x9, 0xD, 0x8, 0xC)
OFFSETS = tuple(range(0, BLOCK, 128))
BASE_NOISE_SIGMA = 1.5
BASE_SIGNAL_RMS = (3.0, 4.5, 6.0, 9.0, 12.0, 18.0, 24.0)
GAINS = (0.5, 1.0, 2.0, 4.0, 8.0)


def power(x):
    return float(np.mean(x.real * x.real + x.imag * x.imag))


def max_subblock_power(x, width):
    return max(power(x[p:p + width]) for p in range(0, len(x), width))


def quantize(x):
    i = np.clip(np.rint(x.real), -127, 127)
    q = np.clip(np.rint(x.imag), -127, 127)
    clipped = int(np.count_nonzero(np.abs(i) >= 127) + np.count_nonzero(np.abs(q) >= 127))
    return i + 1j * q, clipped


def threshold(noise_power):
    return noise_power + noise_power / 4.0 + 32.0


def block_metrics(block):
    return (power(block), max_subblock_power(block, 256), max_subblock_power(block, 128))


def packet_detection(rng, gain, signal_rms):
    hits = np.zeros(3, dtype=np.int64)
    clipping = 0
    components = 0
    total = 0
    noise_sigma = BASE_NOISE_SIGMA * gain
    # The firmware learns the digitized background. Estimate it independently
    # from packet trials, as Warmup does before entering Waiting.
    learned = []
    for _ in range(64):
        z, _ = quantize((rng.normal(0, noise_sigma, BLOCK) +
                         1j * rng.normal(0, noise_sigma, BLOCK)))
        learned.append(power(z))
    gate = threshold(float(np.mean(learned)))

    for rate in RATE_ORDER:
        packet = make_packet(rate)
        packet /= math.sqrt(power(packet))
        packet *= signal_rms * gain
        for offset in OFFSETS:
            block_count = math.ceil((BLOCK + offset + len(packet)) / BLOCK) + 1
            x = (rng.normal(0, noise_sigma, block_count * BLOCK) +
                 1j * rng.normal(0, noise_sigma, block_count * BLOCK))
            x[BLOCK + offset:BLOCK + offset + len(packet)] += packet
            x, clip = quantize(x)
            clipping += clip
            components += 2 * len(x)
            maxima = np.zeros(3)
            for b in range(block_count):
                maxima = np.maximum(maxima, block_metrics(x[b * BLOCK:(b + 1) * BLOCK]))
            hits += maxima >= gate
            total += 1
    return hits / total, clipping / components, gate


def false_trigger_rates(rng, gain, trials=20000):
    noise_sigma = BASE_NOISE_SIGMA * gain
    learned = []
    for _ in range(128):
        z, _ = quantize(rng.normal(0, noise_sigma, BLOCK) +
                        1j * rng.normal(0, noise_sigma, BLOCK))
        learned.append(power(z))
    gate = threshold(float(np.mean(learned)))
    pure = np.zeros(3, dtype=np.int64)
    impulsive = np.zeros(3, dtype=np.int64)
    impulse_trials = max(2000, trials // 5)
    for n in range(trials):
        z, _ = quantize(rng.normal(0, noise_sigma, BLOCK) +
                        1j * rng.normal(0, noise_sigma, BLOCK))
        pure += np.asarray(block_metrics(z)) >= gate
        if n < impulse_trials:
            start = int(rng.integers(0, BLOCK - 128 + 1))
            burst = np.zeros(BLOCK, dtype=np.complex128)
            burst[start:start + 128] = ((6.0 * gain) *
                                        np.exp(1j * rng.uniform(-math.pi, math.pi, 128)))
            zi, _ = quantize(z + burst)
            impulsive += np.asarray(block_metrics(zi)) >= gate
    return pure / trials, impulsive / impulse_trials, gate


def hardware_rows(directory):
    rows = []
    if not directory:
        return rows
    root = Path(directory)
    for c8 in sorted(root.glob("WAIM_00*.C8")):
        txt = c8.with_suffix(".TXT")
        if not txt.exists():
            continue
        x = load_c8(c8)
        m = metadata(txt)
        pre = x[:BLOCK]
        trigger = x[BLOCK:2 * BLOCK]
        clip = int(np.count_nonzero(np.abs(x.real) >= 127) +
                   np.count_nonzero(np.abs(x.imag) >= 127))
        full, p256, p128 = block_metrics(trigger)
        rows.append((c8.name, m["channel"], m["SQ"], full, p256, p128,
                     power(pre), clip, 100.0 * clip / (2 * len(x))))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--false-trials", type=int, default=20000)
    args = ap.parse_args()

    rng = np.random.default_rng(0x8A0F1E)
    false_rows = []
    for gain in GAINS:
        pure, impulse, gate = false_trigger_rates(rng, gain, args.false_trials)
        false_rows.append((gain, gate, pure, impulse))

    detection_rows = []
    for gain in GAINS:
        for amplitude in BASE_SIGNAL_RMS:
            rates, clip, gate = packet_detection(rng, gain, amplitude)
            detection_rows.append((gain, amplitude, gate, rates, clip))

    # Regression verdict: the full-block average must demonstrably lose a
    # useful weak-packet region, while the same-threshold 128-sample maximum
    # must also demonstrate why it cannot be deployed blindly at high gain.
    improvements = [r for r in detection_rows if r[3][1] >= r[3][0] + 0.20]
    assert improvements, "synthetic placement sweep did not expose full-block dilution"
    high_gain_false = false_rows[-1][2]
    assert high_gain_false[2] > high_gain_false[0], "128-window false-trigger risk not exposed"
    assert all(r[3][1] + 1e-12 >= r[3][0] for r in detection_rows)

    out = [
        "# Fix8v energy-trigger regression",
        "",
        "The production trigger remains unchanged: full 2,048-sample DMA-block mean "
        "with threshold `noise*1.25 + 32`. The 256/128 columns are shadow candidates only.",
        "",
        "## Packet detection over all 8 rates and 16 start offsets",
        "",
        "| Gain | Packet RMS before gain | Threshold | Full block | Max/256 | Max/128 | Clipped components |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for gain, amplitude, gate, rates, clip in detection_rows:
        out.append(f"| {gain:.1f}x | {amplitude:.1f} | {gate:.1f} | "
                   f"{100*rates[0]:.1f}% | {100*rates[1]:.1f}% | {100*rates[2]:.1f}% | "
                   f"{100*clip:.3f}% |")

    out += [
        "",
        "## False-trigger comparison",
        "",
        "Rates are per DMA block. At 20 MS/s and 2,048 samples, 0.1% means about 9.8 "
        "false triggers/s before STF rejection.",
        "",
        "| Gain | Threshold | Full noise | Max/256 noise | Max/128 noise | Full 128-sample impulse | Max/256 impulse | Max/128 impulse |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for gain, gate, pure, impulse in false_rows:
        out.append(f"| {gain:.1f}x | {gate:.1f} | {100*pure[0]:.4f}% | "
                   f"{100*pure[1]:.4f}% | {100*pure[2]:.4f}% | "
                   f"{100*impulse[0]:.2f}% | {100*impulse[1]:.2f}% | {100*impulse[2]:.2f}% |")

    hw = hardware_rows(args.captures)
    if hw:
        out += [
            "",
            "## Hardware C8 block-power evidence",
            "",
            "| Capture | CH | SQ | Trigger full | Trigger max/256 | Trigger max/128 | Pretrigger mean | Clip count | Clip % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in hw:
            out.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]:.1f} | "
                       f"{row[4]:.1f} | {row[5]:.1f} | {row[6]:.1f} | "
                       f"{row[7]} | {row[8]:.3f}% |")

    out += [
        "",
        "## Verdict",
        "",
        "- Full-block averaging has a real offset/amplitude blind region, especially for short high-rate packets.",
        "- Max/256 recovers much of that region at low cost in the synthetic sweep.",
        "- Max/128 is more sensitive, but the unchanged threshold increases high-gain noise and short-impulse triggers.",
        "- No subblock trigger is enabled in Fix8v. Hardware profiler counters must measure the candidate/false-reject ratio first.",
    ]
    text = "\n".join(out) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(f"FIX8V_ENERGY_TRIGGER=PASS placements={len(OFFSETS)} rates={len(RATE_ORDER)} "
          f"gains={len(GAINS)} amplitudes={len(BASE_SIGNAL_RMS)} improvements={len(improvements)}")
    if args.output:
        print(args.output)


if __name__ == "__main__":
    main()
