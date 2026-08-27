#!/usr/bin/env python3
"""Fix8w offline OFDM DATA robustness profiler.

This tool intentionally does not change firmware.  It compares the existing
hard-decision path with max-log soft Viterbi variants and records enough
per-symbol evidence to distinguish synchronization/phase/channel problems from
FEC/descrambler failures.
"""

import argparse
import binascii
import csv
import json
import math
from pathlib import Path

import numpy as np

from analyze_fix8u_c8 import ltf_pair_at, max_stf
from wifi_aim_offline import (
    DATA_K,
    FS,
    LONG,
    PILOT_BASE,
    PILOT_K,
    RATES,
    decode,
    load_c8,
    metadata,
    parity,
    viterbi,
)


# IEEE 802.11 pilot polarity sequence, period 127. The recurrence is the
# x^7+x^4+1 sequence in binary form (0 -> +1, 1 -> -1). The Fix8v firmware
# currently stores only the first 64 entries and indexes with &63.
_pilot_bits = [0, 0, 0, 0, 1, 1, 1]
for _pilot_n in range(120):
    _pilot_bits.append(_pilot_bits[_pilot_n] ^ _pilot_bits[_pilot_n + 3])
PILOT_POL_127 = np.asarray([1 if bit == 0 else -1 for bit in _pilot_bits], dtype=np.float64)
assert len(PILOT_POL_127) == 127


def deinterleave_values(values, n_cbps, n_bpsc):
    values = np.asarray(values)
    out = np.zeros(n_cbps, dtype=values.dtype)
    s = max(n_bpsc // 2, 1)
    for k in range(n_cbps):
        first = s * (k // s) + ((k + (16 * k) // n_cbps) % s)
        second = 16 * first - (n_cbps - 1) * ((16 * first) // n_cbps)
        out[second] = values[k]
    return out


def depuncture_values(values, mode, erasure):
    values = np.asarray(values)
    if mode == 0:
        return values.copy()
    pattern = [1, 1, 1, 0] if mode == 1 else [1, 1, 1, 0, 0, 1]
    out = []
    ii = 0
    pi = 0
    while ii < len(values) or pi != 0:
        if pattern[pi]:
            if ii >= len(values):
                return None
            out.append(values[ii])
            ii += 1
        else:
            out.append(erasure)
        pi = (pi + 1) % len(pattern)
    return np.asarray(out, dtype=values.dtype)


def constellation_axes(n_bpsc):
    if n_bpsc <= 2:
        return [(-1.0, (0,)), (1.0, (1,))]
    if n_bpsc == 4:
        scale = math.sqrt(10.0)
        return [
            (-3 / scale, (0, 0)), (-1 / scale, (0, 1)),
            (1 / scale, (1, 1)), (3 / scale, (1, 0)),
        ]
    scale = math.sqrt(42.0)
    return [
        (-7 / scale, (0, 0, 0)), (-5 / scale, (0, 0, 1)),
        (-3 / scale, (0, 1, 1)), (-1 / scale, (0, 1, 0)),
        (1 / scale, (1, 1, 0)), (3 / scale, (1, 1, 1)),
        (5 / scale, (1, 0, 1)), (7 / scale, (1, 0, 0)),
    ]


def slice_axis(value, axes):
    return min(axes, key=lambda q: (value - q[0]) ** 2)


def maxlog_axis(value, axes):
    width = len(axes[0][1])
    result = []
    for bit in range(width):
        d0 = min((value - level) ** 2 for level, label in axes if label[bit] == 0)
        d1 = min((value - level) ** 2 for level, label in axes if label[bit] == 1)
        result.append(d0 - d1)  # positive supports bit 1
    return result


def build_ltf_channel(x, ltf, cfo_hz):
    n0 = np.arange(ltf, ltf + 64)
    n1 = np.arange(ltf + 64, ltf + 128)
    a = np.fft.fft(x[ltf:ltf + 64] * np.exp(-2j * np.pi * cfo_hz * (n0 - ltf) / FS))
    b = np.fft.fft(x[ltf + 64:ltf + 128] * np.exp(-2j * np.pi * cfo_hz * (n1 - ltf) / FS))
    h = np.zeros(64, dtype=np.complex128)
    used = LONG != 0
    h[used] = 0.5 * (a[used] + b[used]) * LONG[used]
    # Equalized half-difference estimates per-subcarrier LTF noise.
    noise = np.ones(64, dtype=np.float64)
    noise[used] = np.abs(0.5 * (a[used] - b[used]) / np.maximum(np.abs(h[used]), 1e-9)) ** 2
    floor = max(float(np.median(noise[used])) * 0.05, 1e-8)
    noise[used] = np.maximum(noise[used], floor)
    return h, noise


def equalized_fft(x, fft_start, origin, cfo_hz, h):
    n = np.arange(fft_start, fft_start + 64)
    y = np.fft.fft(x[fft_start:fft_start + 64] * np.exp(-2j * np.pi * cfo_hz * (n - origin) / FS))
    z = np.zeros(64, dtype=np.complex128)
    used = np.abs(h) > 1e-9
    z[used] = y[used] / h[used]
    return y, z


def demap_symbol(x, fft_start, origin, cfo_hz, h, ltf_noise, pilot_index,
                 n_bpsc, cpe=True, amplitude_normalize=False,
                 noise_weight=False, decision_phase=False, polarity_period=127):
    if fft_start < 0 or fft_start + 64 > len(x):
        return None
    y, z = equalized_fft(x, fft_start, origin, cfo_hz, h)
    pol_table = PILOT_POL_127
    if polarity_period == 64:
        pol = pol_table[pilot_index & 63]
    else:
        pol = pol_table[pilot_index % 127]
    pilot_expected = PILOT_BASE * pol
    pilots = z[PILOT_K % 64]
    cpe_vector = np.sum(pilots * pilot_expected)
    cpe_angle = float(np.angle(cpe_vector)) if abs(cpe_vector) > 1e-12 else 0.0
    pilot_coherence = float(abs(cpe_vector) / max(float(np.sum(np.abs(pilots))), 1e-12))
    rot = np.exp(-1j * cpe_angle) if cpe else 1.0 + 0j
    data = z[DATA_K % 64] * rot
    axes = constellation_axes(n_bpsc)

    if amplitude_normalize:
        nearest = np.array([slice_axis(v.real, axes)[0] + 1j * slice_axis(v.imag, axes)[0]
                            for v in data])
        if n_bpsc == 1:
            nearest = np.array([slice_axis(v.real, axes)[0] + 0j for v in data])
        den = float(np.vdot(nearest, nearest).real)
        gain = float(np.vdot(nearest, data).real / den) if den > 1e-9 else 1.0
        if gain > 0.1:
            data = data / gain

    nearest = []
    labels = []
    for value in data:
        re_level, re_bits = slice_axis(value.real, axes)
        if n_bpsc == 1:
            nearest.append(complex(re_level, 0.0))
            labels.extend(re_bits)
        else:
            im_level, im_bits = slice_axis(value.imag, axes)
            nearest.append(complex(re_level, im_level))
            labels.extend(re_bits + im_bits)
    nearest = np.asarray(nearest, dtype=np.complex128)

    residual_phase = float(np.angle(np.vdot(nearest, data))) if len(nearest) else 0.0
    if decision_phase:
        data = data * np.exp(-1j * residual_phase)
        nearest = []
        labels = []
        for value in data:
            re_level, re_bits = slice_axis(value.real, axes)
            if n_bpsc == 1:
                nearest.append(complex(re_level, 0.0))
                labels.extend(re_bits)
            else:
                im_level, im_bits = slice_axis(value.imag, axes)
                nearest.append(complex(re_level, im_level))
                labels.extend(re_bits + im_bits)
        nearest = np.asarray(nearest, dtype=np.complex128)

    error = data - nearest
    evm = float(np.sqrt(np.vdot(error, error).real / max(np.vdot(nearest, nearest).real, 1e-12)))
    symbol_noise = max(float(np.mean(np.abs(error) ** 2)), 1e-8)
    llr = []
    for sc, value in enumerate(data):
        values = maxlog_axis(value.real, axes)
        if n_bpsc > 1:
            values += maxlog_axis(value.imag, axes)
        weight = 1.0
        if noise_weight:
            weight = 1.0 / max(symbol_noise + float(ltf_noise[DATA_K[sc] % 64]), 1e-8)
        llr.extend(v * weight for v in values)

    # Decision-directed estimate of LTF-to-DATA channel drift.  It is reported,
    # not fed back into the baseline decoder.
    ratio = np.zeros(48, dtype=np.complex128)
    good = np.abs(nearest) > 1e-9
    ratio[good] = data[good] / nearest[good]
    channel_drift_rms = float(np.sqrt(np.mean(np.abs(ratio[good] - 1.0) ** 2))) if np.any(good) else 0.0
    ratio_phase_std = float(np.std(np.angle(ratio[good]))) if np.any(good) else 0.0
    ratio_gain_mean = float(np.mean(np.abs(ratio[good]))) if np.any(good) else 0.0
    return {
        "hard": np.asarray(labels, dtype=np.uint8),
        "llr": np.asarray(llr, dtype=np.float64),
        "evm": evm,
        "cpe_rad": cpe_angle,
        "pilot_coherence": pilot_coherence,
        "residual_phase_rad": residual_phase,
        "channel_drift_rms": channel_drift_rms,
        "channel_ratio_phase_std_rad": ratio_phase_std,
        "channel_ratio_gain_mean": ratio_gain_mean,
        "constellation": data,
        "nearest": nearest,
        "raw_fft": y,
        "decision_ratio": ratio,
    }


def quantize_llr(llr, bits, normalized):
    llr = np.asarray(llr, dtype=np.float64)
    limit = (1 << (bits - 1)) - 1
    nonzero = np.abs(llr[np.abs(llr) > 1e-12])
    if normalized and len(nonzero):
        scale = float(np.percentile(nonzero, 90))
    else:
        scale = float(nonzero.max()) if len(nonzero) else 1.0
    scale = max(scale, 1e-12)
    return np.clip(np.rint(llr * limit / scale), -limit, limit).astype(np.int16)


def soft_viterbi(llr, bits=4, normalized=True, end_state=None):
    q = quantize_llr(llr, bits, normalized)
    if len(q) == 0 or len(q) & 1:
        return None, None
    steps = len(q) // 2
    inf = 1e30
    pm = np.full(64, inf, dtype=np.float64)
    pm[0] = 0.0
    survivors = []
    for t in range(steps):
        r0, r1 = int(q[2 * t]), int(q[2 * t + 1])
        nm = np.empty(64, dtype=np.float64)
        decisions = 0
        for ns in range(64):
            bit = ns & 1
            p0 = ns >> 1
            p1 = p0 | 32
            reg0 = ((p0 << 1) & 0x7E) | bit
            reg1 = ((p1 << 1) & 0x7E) | bit
            e00, e01 = parity(reg0 & 0o155), parity(reg0 & 0o117)
            e10, e11 = parity(reg1 & 0o155), parity(reg1 & 0o117)
            bm0 = (abs(r0) - (1 if e00 else -1) * r0) + (abs(r1) - (1 if e01 else -1) * r1)
            bm1 = (abs(r0) - (1 if e10 else -1) * r0) + (abs(r1) - (1 if e11 else -1) * r1)
            m0, m1 = pm[p0] + bm0, pm[p1] + bm1
            if m1 < m0:
                nm[ns] = m1
                decisions |= 1 << ns
            else:
                nm[ns] = m0
        pm = nm
        survivors.append(decisions)
    state = int(np.argmin(pm)) if end_state is None else int(end_state)
    metric = float(pm[state])
    out = np.zeros(steps, dtype=np.uint8)
    for tt in range(steps - 1, -1, -1):
        out[tt] = state & 1
        hi = (survivors[tt] >> state) & 1
        state = (state >> 1) | (hi << 5)
    return out, metric


def service_and_psdu(decoded, length):
    if decoded is None or len(decoded) < 16:
        return {"service_distance": None, "complete_psdu": False}
    best_state = 0
    best_errors = 255
    for candidate in range(1, 128):
        errors = sum(int(decoded[i]) != ((candidate >> (6 - i)) & 1) for i in range(7))
        state = candidate
        for i in range(7, 16):
            feedback = ((state >> 6) ^ (state >> 3)) & 1
            errors += int(decoded[i]) != feedback
            state = ((state << 1) & 0x7E) | feedback
        if errors < best_errors:
            best_errors = errors
            best_state = candidate
    state = best_state
    for _ in range(7, 16):
        feedback = ((state >> 6) ^ (state >> 3)) & 1
        state = ((state << 1) & 0x7E) | feedback
    available = max(0, (len(decoded) - 16) // 8)
    nbytes = min(length, available)
    psdu = bytearray(nbytes)
    for offset in range(nbytes * 8):
        feedback = ((state >> 6) ^ (state >> 3)) & 1
        psdu[offset // 8] |= (feedback ^ int(decoded[16 + offset])) << (offset % 8)
        state = ((state << 1) & 0x7E) | feedback
    complete = nbytes >= length
    fc = int.from_bytes(psdu[:2], "little") if nbytes >= 2 else None
    fcs_valid = None
    if complete and length >= 4:
        expected = int.from_bytes(psdu[length - 4:length], "little")
        calculated = binascii.crc32(psdu[:length - 4]) & 0xFFFFFFFF
        fcs_valid = expected == calculated
    internal_fcs_hits = []
    for candidate_length in range(8, nbytes + 1):
        expected = int.from_bytes(psdu[candidate_length - 4:candidate_length], "little")
        calculated = binascii.crc32(psdu[:candidate_length - 4]) & 0xFFFFFFFF
        if expected == calculated:
            internal_fcs_hits.append(candidate_length)
    protocol_valid = fc is not None and (fc & 3) == 0
    frame_type = None if fc is None else (fc >> 2) & 3
    frame_subtype = None if fc is None else (fc >> 4) & 15
    if best_errors > 2:
        scanner_path_end = "DATA/SERVICE_REJECT"
    elif not protocol_valid:
        scanner_path_end = "SERVICE/PROTOCOL_REJECT"
    elif frame_type != 0:
        scanner_path_end = "PROTOCOL/NOT_MANAGEMENT"
    elif frame_subtype not in (8, 5):
        scanner_path_end = "MANAGEMENT/NOT_BEACON_PROBE"
    else:
        scanner_path_end = "BEACON_PROBE/PAYLOAD_PARSE"
    return {
        "service_distance": int(best_errors),
        "scrambler_state": int(best_state),
        "complete_psdu": bool(complete),
        "decoded_bytes": int(nbytes),
        "fc": None if fc is None else f"0x{fc:04x}",
        "frame_type": frame_type,
        "frame_subtype": frame_subtype,
        "fcs_valid": fcs_valid,
        "internal_fcs_hit_lengths": internal_fcs_hits,
        "scanner_path_end": scanner_path_end,
        "offline_path_end": "FCS_PASS" if fcs_valid is True else "FCS_FAIL",
        "psdu_hex": bytes(psdu).hex(),
    }


def collect_data(x, ltf, cfo_hz, rate_raw, length, config):
    n_bpsc, n_cbps, n_dbps, rate_mbps, puncture = RATES[rate_raw]
    use_ltf = ltf + config["timing_delta"]
    h, ltf_noise = build_ltf_channel(x, use_ltf, cfo_hz + config["cfo_delta_hz"])
    h_work = h.copy()
    needed_symbols = math.ceil((16 + 8 * length + 6) / n_dbps)
    available_symbols = max(0, (len(x) - (ltf + 224 + 64)) // 80 + 1)
    symbols = min(needed_symbols, available_symbols)
    hard_coded = []
    soft_coded = []
    symbol_rows = []
    transmitted_confidence = []
    for si in range(symbols):
        row = demap_symbol(
            x, use_ltf + 224 + si * 80, use_ltf, cfo_hz + config["cfo_delta_hz"], h_work,
            ltf_noise, si + 1, n_bpsc, cpe=config["cpe"],
            amplitude_normalize=config["amplitude_normalize"],
            noise_weight=config["noise_weight"], decision_phase=config["decision_phase"],
            polarity_period=config["polarity_period"],
        )
        if row is None:
            break
        hard_de = deinterleave_values(row["hard"], n_cbps, n_bpsc)
        soft_de = deinterleave_values(row["llr"], n_cbps, n_bpsc)
        hard_dep = depuncture_values(hard_de, puncture, np.uint8(2))
        soft_dep = depuncture_values(soft_de, puncture, np.float64(0.0))
        if hard_dep is None or soft_dep is None:
            break
        base_index = len(soft_coded)
        hard_coded.extend(int(v) for v in hard_dep)
        soft_coded.extend(float(v) for v in soft_dep)
        for local, confidence in enumerate(np.abs(soft_dep)):
            if confidence > 0:
                transmitted_confidence.append((float(confidence), base_index + local, si, local))
        symbol_rows.append({
            "symbol": si,
            "sample_start": use_ltf + 224 + si * 80,
            "raw_power": float(np.mean(np.abs(x[use_ltf + 224 + si * 80:use_ltf + 288 + si * 80]) ** 2)),
            "evm_percent": 100.0 * row["evm"],
            "pilot_cpe_rad": row["cpe_rad"],
            "pilot_coherence_percent": 100.0 * row["pilot_coherence"],
            "residual_phase_rad": row["residual_phase_rad"],
            "channel_drift_rms_percent": 100.0 * row["channel_drift_rms"],
            "channel_ratio_phase_std_rad": row["channel_ratio_phase_std_rad"],
            "channel_ratio_gain_mean": row["channel_ratio_gain_mean"],
        })
        alpha = config["channel_alpha"]
        if alpha > 0.0:
            for sc, carrier in enumerate(DATA_K):
                ratio = row["decision_ratio"][sc]
                if abs(ratio) > 0.2 and abs(ratio) < 5.0:
                    b = int(carrier) % 64
                    h_work[b] *= (1.0 - alpha) + alpha * ratio
    hard_decoded, hard_metric = viterbi(np.asarray(hard_coded, dtype=np.uint8), signal=False)
    full_tail_available = symbols >= needed_symbols
    end_state = 0 if config["traceback_zero"] and full_tail_available else None
    soft_decoded, soft_metric = soft_viterbi(
        np.asarray(soft_coded), bits=config["quant_bits"],
        normalized=config["normalized_llr"], end_state=end_state,
    )
    hard_eval = service_and_psdu(hard_decoded, length)
    soft_eval = service_and_psdu(soft_decoded, length)
    changes = []
    if hard_decoded is not None and soft_decoded is not None:
        common = min(len(hard_decoded), len(soft_decoded))
        changes = np.flatnonzero(hard_decoded[:common] != soft_decoded[:common]).tolist()
    cpe = np.unwrap([r["pilot_cpe_rad"] for r in symbol_rows]) if symbol_rows else np.array([])
    residual = np.unwrap([r["residual_phase_rad"] for r in symbol_rows]) if symbol_rows else np.array([])
    slope = float(np.polyfit(np.arange(len(cpe)), cpe, 1)[0]) if len(cpe) >= 2 else 0.0
    residual_slope = float(np.polyfit(np.arange(len(residual)), residual, 1)[0]) if len(residual) >= 2 else 0.0
    weakest = sorted(transmitted_confidence)[:32]
    return {
        "config": config,
        "ltf_used": use_ltf,
        "rate_mbps": rate_mbps,
        "needed_symbols": needed_symbols,
        "symbols": symbols,
        "full_tail_available": full_tail_available,
        "hard_viterbi_metric": None if hard_metric is None else int(hard_metric),
        "soft_viterbi_metric": soft_metric,
        "hard": hard_eval,
        "soft": soft_eval,
        "decoded_bit_change_count": len(changes),
        "decoded_bit_change_positions": changes[:256],
        "changed_bits_by_data_symbol": {
            str(si): sum(si * n_dbps <= bit < (si + 1) * n_dbps for bit in changes)
            for si in range(symbols)
        },
        "weakest_coded_bits": [
            {"confidence": value, "coded_index": index, "data_symbol": si, "symbol_coded_index": local}
            for value, index, si, local in weakest
        ],
        "pilot_cpe_slope_rad_per_symbol": slope,
        "residual_phase_slope_rad_per_symbol": residual_slope,
        "mean_evm_percent": float(np.mean([r["evm_percent"] for r in symbol_rows])) if symbol_rows else None,
        "max_evm_percent": float(np.max([r["evm_percent"] for r in symbol_rows])) if symbol_rows else None,
        "mean_channel_drift_rms_percent": float(np.mean([r["channel_drift_rms_percent"] for r in symbol_rows])) if symbol_rows else None,
        "symbols_detail": symbol_rows,
    }


def experiment_configs():
    base = {
        "cpe": True,
        "amplitude_normalize": False,
        "noise_weight": False,
        "decision_phase": False,
        "polarity_period": 127,
        "cfo_delta_hz": 0,
        "quant_bits": 4,
        "normalized_llr": True,
        "traceback_zero": False,
        "timing_delta": 0,
        "channel_alpha": 0.0,
    }
    result = []
    for bits in (3, 4, 5):
        for normalized in (False, True):
            result.append(dict(base, name=f"soft_q{bits}_{'norm' if normalized else 'raw'}",
                               quant_bits=bits, normalized_llr=normalized))
    result.extend([
        dict(base, name="soft_q5_norm_noise", quant_bits=5, noise_weight=True),
        dict(base, name="soft_q5_norm_amp", quant_bits=5, amplitude_normalize=True),
        dict(base, name="soft_q5_norm_ddphase", quant_bits=5, decision_phase=True),
        dict(base, name="soft_q5_norm_no_cpe", quant_bits=5, cpe=False),
        dict(base, name="soft_q5_norm_channel_a10", quant_bits=5, channel_alpha=0.10),
        dict(base, name="soft_q5_norm_channel_a25", quant_bits=5, channel_alpha=0.25),
        dict(base, name="soft_q5_norm_traceback0", quant_bits=5, traceback_zero=True),
        dict(base, name="soft_q5_norm_polarity64", quant_bits=5, polarity_period=64),
    ])
    for delta in (-2000, -1000, -500, -250, 250, 500, 1000, 2000):
        result.append(dict(base, name=f"soft_q5_norm_cfo_{delta:+d}", quant_bits=5, cfo_delta_hz=delta))
    for timing in range(-8, 9):
        if timing:
            result.append(dict(base, name=f"soft_q5_norm_timing_{timing:+d}", quant_bits=5, timing_delta=timing))
    return result


def score_experiment(row):
    soft = row["soft"]
    return (
        bool(soft.get("fcs_valid")),
        -(soft.get("service_distance") if soft.get("service_distance") is not None else 999),
        -(row.get("soft_viterbi_metric") if row.get("soft_viterbi_metric") is not None else 1e30),
    )


def analyze_capture(c8):
    txt = c8.with_suffix(".TXT")
    meta = metadata(txt)
    x = load_c8(c8)
    ltf = int(meta["ltf_position"])
    cfo = float(meta["cfo_hz"])
    baseline = decode(x, ltf, cfo)
    if baseline.get("stage", 0) < 6 or baseline.get("rate_raw") not in RATES:
        return {"capture": c8.name, "metadata": meta, "baseline": baseline, "experiments": []}
    experiments = [
        collect_data(x, ltf, cfo, int(baseline["rate_raw"]), int(baseline["length"]), cfg)
        for cfg in experiment_configs()
    ]
    best = max(experiments, key=score_experiment)
    reference = next(q for q in experiments if q["config"]["name"] == "soft_q5_norm")
    fc_counts = {}
    for experiment in experiments:
        fc = experiment["soft"].get("fc")
        if fc is not None:
            fc_counts[fc] = fc_counts.get(fc, 0) + 1
    stf, stf_at = max_stf(x)
    clipped = int(np.count_nonzero(np.abs(x.real) >= 127) + np.count_nonzero(np.abs(x.imag) >= 127))
    return {
        "capture": c8.name,
        "metadata": meta,
        "stf_score_percent": 100.0 * stf,
        "stf_position": stf_at,
        "ltf_pair_score_percent": 100.0 * ltf_pair_at(x, ltf, cfo),
        "cfo_hz": cfo,
        "clipped_components": clipped,
        "clipping_percent": 100.0 * clipped / (2 * len(x)),
        "baseline": baseline,
        "experiments": experiments,
        "best_experiment": best,
        "reference_soft": reference,
        "soft_fc_consensus": sorted(fc_counts.items(), key=lambda q: (-q[1], q[0])),
        "any_fcs_valid": any(q["soft"].get("fcs_valid") is True for q in experiments),
    }


def render_markdown(rows):
    out = [
        "# Fix8w OFDM DATA robustness batch report",
        "",
        "| Capture | STF | LTF | CFO Hz | SIGNAL metric | RATE | LENGTH | hard metric | hard SVC | hard FC | hard FCS | best soft | soft metric | soft SVC | soft FC | soft FCS | EVM mean/max | clip |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---|---|---|---:|",
    ]
    for row in rows:
        base = row.get("baseline", {})
        reference = row.get("reference_soft")
        if not reference:
            out.append(f"| {row['capture']} | - | - | - | {base.get('signal_metric', '-')} | - | - | - | - | - | - | - | - | - | - | - | - | - |")
            continue
        hard, soft = reference["hard"], reference["soft"]
        best = row["best_experiment"]
        out.append(
            f"| {row['capture']} | {row['stf_score_percent']:.1f}% | {row['ltf_pair_score_percent']:.1f}% | "
            f"{row['cfo_hz']:.0f} | {base.get('signal_metric', '-')} | {reference['rate_mbps']} | {base.get('length', '-')} | "
            f"{reference['hard_viterbi_metric']} | {hard.get('service_distance')} | {hard.get('fc')} | {hard.get('fcs_valid')} | "
            f"q5_norm | {reference['soft_viterbi_metric']:.0f} | {soft.get('service_distance')} | "
            f"{soft.get('fc')} | {soft.get('fcs_valid')} | {reference['mean_evm_percent']:.1f}/{reference['max_evm_percent']:.1f}% | "
            f"{row['clipping_percent']:.3f}% |"
        )
    recovered = [r["capture"] for r in rows if r.get("any_fcs_valid")]
    out += [
        "",
        "## Batch outcome",
        "",
        f"FCS recovered by at least one soft variant: {', '.join(recovered) if recovered else 'none'}.",
        "",
        "Per-symbol EVM, pilot CPE, residual phase, channel drift, changed decoded bits, "
        "and weakest coded-bit locations are preserved in `fix8w_data_report.json`.",
    ]
    return "\n".join(out) + "\n"


def without_psdu(result):
    return {key: value for key, value in result.items() if key != "psdu_hex"}


def compact_report(rows):
    compact = []
    for row in rows:
        if not row.get("reference_soft"):
            compact.append(row)
            continue
        reference = row["reference_soft"]
        experiments = []
        for experiment in row["experiments"]:
            experiments.append({
                "name": experiment["config"]["name"],
                "config": experiment["config"],
                "soft_viterbi_metric": experiment["soft_viterbi_metric"],
                "soft": without_psdu(experiment["soft"]),
                "decoded_bit_change_count": experiment["decoded_bit_change_count"],
                "mean_evm_percent": experiment["mean_evm_percent"],
                "max_evm_percent": experiment["max_evm_percent"],
                "pilot_cpe_slope_rad_per_symbol": experiment["pilot_cpe_slope_rad_per_symbol"],
                "residual_phase_slope_rad_per_symbol": experiment["residual_phase_slope_rad_per_symbol"],
                "mean_channel_drift_rms_percent": experiment["mean_channel_drift_rms_percent"],
            })
        compact.append({
            "capture": row["capture"],
            "metadata": row["metadata"],
            "stf_score_percent": row["stf_score_percent"],
            "stf_position": row["stf_position"],
            "ltf_pair_score_percent": row["ltf_pair_score_percent"],
            "cfo_hz": row["cfo_hz"],
            "clipped_components": row["clipped_components"],
            "clipping_percent": row["clipping_percent"],
            "baseline": row["baseline"],
            "reference": {
                "config": reference["config"],
                "rate_mbps": reference["rate_mbps"],
                "needed_symbols": reference["needed_symbols"],
                "symbols": reference["symbols"],
                "hard_viterbi_metric": reference["hard_viterbi_metric"],
                "soft_viterbi_metric": reference["soft_viterbi_metric"],
                "hard": reference["hard"],
                "soft": reference["soft"],
                "decoded_bit_change_count": reference["decoded_bit_change_count"],
                "decoded_bit_change_positions": reference["decoded_bit_change_positions"],
                "changed_bits_by_data_symbol": reference["changed_bits_by_data_symbol"],
                "weakest_coded_bits": reference["weakest_coded_bits"],
                "pilot_cpe_slope_rad_per_symbol": reference["pilot_cpe_slope_rad_per_symbol"],
                "residual_phase_slope_rad_per_symbol": reference["residual_phase_slope_rad_per_symbol"],
                "mean_evm_percent": reference["mean_evm_percent"],
                "max_evm_percent": reference["max_evm_percent"],
                "mean_channel_drift_rms_percent": reference["mean_channel_drift_rms_percent"],
                "symbols_detail": reference["symbols_detail"],
            },
            "experiments": experiments,
            "soft_fc_consensus": row["soft_fc_consensus"],
            "any_fcs_valid": row["any_fcs_valid"],
        })
    return compact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    expected = [f"WAIM_{n:03d}" for n in range(7, 18)]
    pairs = []
    missing = []
    for stem in expected:
        c8 = args.directory / f"{stem}.C8"
        txt = args.directory / f"{stem}.TXT"
        if c8.exists() and txt.exists():
            pairs.append(c8)
        else:
            missing.append(stem)
    if missing and not args.allow_partial:
        raise SystemExit("missing capture pairs: " + ", ".join(missing))
    if not pairs:
        raise SystemExit("no WAIM_007..WAIM_017 capture pairs found")
    rows = [analyze_capture(c8) for c8 in pairs]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "fix8w_data_report.json").write_text(json.dumps(compact_report(rows), indent=2) + "\n")
    report = render_markdown(rows)
    (args.output / "fix8w_data_report.md").write_text(report)
    with (args.output / "fix8w_data_summary.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["capture", "stf_percent", "ltf_percent", "cfo_hz", "rate_mbps", "length", "hard_service", "hard_fc", "hard_fcs", "best_soft", "soft_service", "soft_fc", "soft_fcs", "evm_mean_percent", "clip_percent"])
        for row in rows:
            reference = row.get("reference_soft")
            if not reference:
                writer.writerow([row["capture"]])
                continue
            writer.writerow([
                row["capture"], row["stf_score_percent"], row["ltf_pair_score_percent"], row["cfo_hz"],
                reference["rate_mbps"], row["baseline"].get("length"), reference["hard"].get("service_distance"),
                reference["hard"].get("fc"), reference["hard"].get("fcs_valid"), reference["config"]["name"],
                reference["soft"].get("service_distance"), reference["soft"].get("fc"), reference["soft"].get("fcs_valid"),
                reference["mean_evm_percent"], row["clipping_percent"],
            ])
    print(report)


if __name__ == "__main__":
    main()
