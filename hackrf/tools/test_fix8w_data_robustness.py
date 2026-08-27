#!/usr/bin/env python3
"""Golden regression for the Fix8w hard/soft full-PSDU harness."""

import numpy as np

from analyze_fix8w_data import collect_data
from test_fix8u_sync_geometry import trigger_capture
from wifi_aim_offline import RATES, decode


def config(name, bits, normalized, traceback_zero):
    return {
        "name": name,
        "cpe": True,
        "amplitude_normalize": False,
        "noise_weight": False,
        "decision_phase": False,
        "polarity_period": 127,
        "cfo_delta_hz": 0,
        "quant_bits": bits,
        "normalized_llr": normalized,
        "traceback_zero": traceback_zero,
        "timing_delta": 0,
        "channel_alpha": 0.0,
    }


def main():
    failures = []
    configs = [
        config("q3-raw", 3, False, False),
        config("q4-normalized", 4, True, False),
        config("q5-tail-zero", 5, True, True),
    ]
    q3_fcs = 0
    for index, rate_raw in enumerate(RATES):
        ltf = 2500 + index * 173
        cfo = -120000 + index * 31000
        x = trigger_capture(rate_raw, ltf, cfo_hz=cfo, noise_sigma=1.0, scale=260.0)
        baseline = decode(x, ltf, cfo)
        if baseline.get("stage", 0) < 7:
            failures.append((rate_raw, "baseline", baseline))
            continue
        for cfg in configs:
            row = collect_data(x, ltf, cfo, rate_raw, baseline["length"], cfg)
            if row["hard"].get("fcs_valid") is not True:
                failures.append((rate_raw, cfg["name"], "hard", row["hard"]))
            if cfg["name"] == "q3-raw":
                q3_fcs += row["soft"].get("fcs_valid") is True
            elif row["soft"].get("fcs_valid") is not True:
                failures.append((rate_raw, cfg["name"], "soft", row["soft"]))
    assert not failures, failures[:3]
    # Three-bit raw quantization is deliberately retained as an experiment,
    # not a requirement: low-resolution 64-QAM can lose information even in a
    # clipped synthetic capture. Four/five-bit normalized paths must be exact.
    assert q3_fcs >= 6, q3_fcs
    print(
        "FIX8W_DATA_ROBUSTNESS=PASS rates=8/8",
        f"q3_raw_fcs={q3_fcs}/8",
        "q4_q5_full_psdu_fcs=8/8",
    )


if __name__ == "__main__":
    main()
