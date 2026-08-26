#!/usr/bin/env python3
import json
import math
from pathlib import Path

import numpy as np

FS = 20_000_000.0
LONG = np.array([
    0,1,-1,-1,1,1,-1,1,-1,1,-1,-1,-1,-1,-1,1,
    1,-1,-1,1,-1,1,-1,1,1,1,1,0,0,0,0,0,
    0,0,0,0,0,0,1,1,-1,-1,1,1,-1,1,-1,1,
    1,1,1,1,1,-1,-1,1,1,-1,1,-1,1,1,1,1,
], dtype=np.float64)
DATA_K = np.array([
    -26,-25,-24,-23,-22,-20,-19,-18,-17,-16,-15,-14,-13,-12,-11,-10,-9,-8,-6,-5,-4,-3,-2,-1,
    1,2,3,4,5,6,8,9,10,11,12,13,14,15,16,17,18,19,20,22,23,24,25,26,
], dtype=np.int32)
PILOT_K = np.array([-21,-7,7,21], dtype=np.int32)
PILOT_BASE = np.array([1,1,1,-1], dtype=np.float64)
PILOT_POL = np.array([
    1,1,1,1,-1,-1,-1,1,-1,-1,-1,-1,1,1,-1,1,
    -1,-1,1,1,-1,1,1,-1,1,1,1,1,1,1,-1,1,
    1,1,-1,1,1,-1,-1,1,1,1,-1,1,-1,-1,-1,1,
    -1,1,-1,-1,1,-1,-1,1,1,1,1,1,-1,-1,1,1,
], dtype=np.float64)
RATES = {
    11: (1,48,24,6,0), 15: (1,48,36,9,2),
    10: (2,96,48,12,0), 14: (2,96,72,18,2),
    9: (4,192,96,24,0), 13: (4,192,144,36,2),
    8: (6,288,192,48,1), 12: (6,288,216,54,2),
}


def metadata(path):
    result = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                result[k] = int(v)
            except ValueError:
                result[k] = v
    return result


def load_c8(path):
    raw = np.fromfile(path, dtype=np.int8).reshape(-1, 2).astype(np.float64)
    return raw[:, 0] + 1j * raw[:, 1]


def deinterleave(bits, n_cbps, n_bpsc):
    out = np.zeros(n_cbps, dtype=np.uint8)
    s = max(n_bpsc // 2, 1)
    for k in range(n_cbps):
        first = s * (k // s) + ((k + (16 * k) // n_cbps) % s)
        second = 16 * first - (n_cbps - 1) * ((16 * first) // n_cbps)
        out[second] = bits[k]
    return out


def depuncture(bits, mode):
    if mode == 0:
        return np.asarray(bits, dtype=np.uint8)
    pat = [1,1,1,0] if mode == 1 else [1,1,1,0,0,1]
    out = []
    ii = 0
    pi = 0
    while ii < len(bits) or pi != 0:
        if pat[pi]:
            if ii >= len(bits):
                return None
            out.append(int(bits[ii]) & 1)
            ii += 1
        else:
            out.append(2)
        pi = (pi + 1) % len(pat)
    return np.array(out, dtype=np.uint8)


def parity(v):
    return v.bit_count() & 1


def viterbi(coded, signal=False):
    if coded is None or len(coded) % 2:
        return None, None
    steps = len(coded) // 2
    inf = 30000
    pm = [inf] * 64
    pm[0] = 0
    survivors = []
    for t in range(steps):
        r0, r1 = int(coded[2*t]), int(coded[2*t+1])
        nm = [0] * 64
        dec = 0
        for ns in range(64):
            bit = ns & 1
            p0 = ns >> 1
            p1 = p0 | 32
            reg0 = ((p0 << 1) & 0x7e) | bit
            reg1 = ((p1 << 1) & 0x7e) | bit
            bm0 = ((r0 < 2) and (parity(reg0 & 0o155) != r0)) + ((r1 < 2) and (parity(reg0 & 0o117) != r1))
            bm1 = ((r0 < 2) and (parity(reg1 & 0o155) != r0)) + ((r1 < 2) and (parity(reg1 & 0o117) != r1))
            m0, m1 = pm[p0] + bm0, pm[p1] + bm1
            if m1 < m0:
                nm[ns] = m1
                dec |= 1 << ns
            else:
                nm[ns] = m0
        pm = nm
        survivors.append(dec)
    state = 0 if signal or steps == 24 else min(range(64), key=lambda q: pm[q])
    metric = pm[state]
    out = [0] * steps
    for tt in range(steps - 1, -1, -1):
        out[tt] = state & 1
        hi = (survivors[tt] >> state) & 1
        state = (state >> 1) | (hi << 5)
    return np.array(out, dtype=np.uint8), metric


def hard_symbol(x, fft_start, origin, cfo_hz, h, pilot_index, n_bpsc, bin_shift=0):
    if fft_start < 0 or fft_start + 64 > len(x):
        return None, None
    n = np.arange(fft_start, fft_start + 64)
    y = np.fft.fft(x[fft_start:fft_start+64] * np.exp(-2j*np.pi*cfo_hz*(n-origin)/FS))
    def eq(k):
        b = (k + bin_shift) % 64
        den = abs(h[b])**2
        return 0j if den < 1e-9 else y[b] / h[b]
    pol = PILOT_POL[pilot_index & 63]
    cpe = sum(eq(int(k)) * e * pol for k, e in zip(PILOT_K, PILOT_BASE))
    if abs(cpe) < 1e-8:
        return None, None
    rot = np.conj(cpe) / abs(cpe)
    zdata = np.array([eq(int(k)) * rot for k in DATA_K])
    out = []
    for z in zdata:
        re, im = z.real, z.imag
        if n_bpsc == 1:
            out.append(1 if re > 0 else 0)
        elif n_bpsc == 2:
            out.extend((1 if re > 0 else 0, 1 if im > 0 else 0))
        elif n_bpsc == 4:
            out.extend((1 if re > 0 else 0, 1 if abs(re) < 0.632455532 else 0,
                        1 if im > 0 else 0, 1 if abs(im) < 0.632455532 else 0))
        else:
            out.extend((1 if re > 0 else 0, 1 if abs(re) < 0.6172134 else 0,
                        1 if 0.3086067 <= abs(re) < 0.9258201 else 0,
                        1 if im > 0 else 0, 1 if abs(im) < 0.6172134 else 0,
                        1 if 0.3086067 <= abs(im) < 0.9258201 else 0))
    # EVM after removing common pilot phase; normalize constellation power per capture.
    return np.array(out, dtype=np.uint8), zdata


def decode(x, ltf, cfo_hz, timing_delta=0, bin_shift=0):
    L = ltf + timing_delta
    result = {"ltf": L, "cfo_hz": cfo_hz, "timing_delta": timing_delta, "bin_shift": bin_shift, "stage": 1}
    if L < 0 or L + 288 > len(x):
        result["error"] = "bounds"
        return result
    n0 = np.arange(L, L+64)
    n1 = np.arange(L+64, L+128)
    a = np.fft.fft(x[L:L+64] * np.exp(-2j*np.pi*cfo_hz*(n0-L)/FS))
    b = np.fft.fft(x[L+64:L+128] * np.exp(-2j*np.pi*cfo_hz*(n1-L)/FS))
    h = np.zeros(64, dtype=np.complex128)
    used = LONG != 0
    h[used] = 0.5 * (a[used] + b[used]) * LONG[used]
    # LTF repetition coherence and known-bin energy are useful independent diagnostics.
    result["ltf_repeat"] = float(abs(np.vdot(x[L:L+64], x[L+64:L+128]))**2 /
                                 max(1.0, np.vdot(x[L:L+64], x[L:L+64]).real * np.vdot(x[L+64:L+128], x[L+64:L+128]).real))
    sig, sig_z = hard_symbol(x, L+144, L, cfo_hz, h, 0, 1, bin_shift)
    if sig is None:
        result["error"] = "signal_hard"
        return result
    result["stage"] = 2
    dec, metric = viterbi(deinterleave(sig, 48, 1), signal=True)
    result["signal_metric"] = int(metric)
    if dec is None or len(dec) < 24:
        result["error"] = "signal_viterbi"
        return result
    result["stage"] = 3
    rate = sum(int(dec[i]) << i for i in range(4))
    length = sum(int(dec[i]) << (i-5) for i in range(5,17))
    parity_ok = (sum(int(v) for v in dec[:17]) & 1) == int(dec[17])
    reserved_ok = int(dec[4]) == 0
    tail_ok = not np.any(dec[18:24])
    result.update(rate_raw=rate, length=length, parity_ok=bool(parity_ok), reserved_ok=bool(reserved_ok), signal_tail_ok=bool(tail_ok))
    if not (parity_ok and reserved_ok and tail_ok):
        result["error"] = "signal_check"
        return result
    result["stage"] = 4
    if rate not in RATES:
        result["error"] = "rate"
        return result
    n_bpsc, n_cbps, n_dbps, mbps, puncture = RATES[rate]
    result.update(rate_mbps=mbps)
    result["stage"] = 5
    if not 36 <= length <= 2304:
        result["error"] = "length"
        return result
    result["stage"] = 6
    want_bytes = min(length, 96)
    want_bits = min(896, 16 + 8*want_bytes + 6)
    symbols = math.ceil(want_bits / n_dbps)
    available = 1 + max(0, (len(x) - (L+224+64)) // 80) if len(x) > L+288 else 0
    symbols = min(symbols, available)
    coded = []
    data_cloud = []
    for si in range(symbols):
        hard, cloud = hard_symbol(x, L+224+si*80, L, cfo_hz, h, si+1, n_bpsc, bin_shift)
        if hard is None:
            result["error"] = "data_hard"
            return result
        de = deinterleave(hard, n_cbps, n_bpsc)
        dep = depuncture(de, puncture)
        if dep is None:
            result["error"] = "depuncture"
            return result
        coded.extend(int(v) for v in dep)
        data_cloud.append(cloud)
    dec, data_metric = viterbi(np.array(coded, dtype=np.uint8), signal=False)
    result.update(symbols=symbols, data_metric=int(data_metric))
    if dec is None or len(dec) < 16 + 36*8:
        result["error"] = "data_viterbi"
        return result
    result["stage"] = 7
    best_state, service_errors = 0, 255
    for candidate in range(1,128):
        errors = sum(int(dec[i]) != ((candidate >> (6-i)) & 1) for i in range(7))
        st = candidate
        for i in range(7,16):
            fb = ((st >> 6) ^ (st >> 3)) & 1
            errors += int(dec[i]) != fb
            st = ((st << 1) & 0x7e) | fb
        if errors < service_errors:
            service_errors, best_state = errors, candidate
    result.update(service_errors=int(service_errors), scrambler_state=int(best_state))
    service_ok = service_errors <= 2
    result["service_ok"] = service_ok
    state = best_state
    for i in range(7,16):
        fb = ((state >> 6) ^ (state >> 3)) & 1
        state = ((state << 1) & 0x7e) | fb
    out = bytearray((min(len(dec), 104*8)+7)//8)
    for i in range(16, min(len(dec), len(out)*8)):
        fb = ((state >> 6) ^ (state >> 3)) & 1
        bit = fb ^ int(dec[i])
        out[i//8] |= bit << (i % 8)
        state = ((state << 1) & 0x7e) | fb
    frame = bytes(out[2:])
    if len(frame) < 36:
        result["error"] = "short_frame"
        return result
    fc = int.from_bytes(frame[:2], "little")
    typ, subtype = (fc >> 2) & 3, (fc >> 4) & 15
    result.update(fc=f"0x{fc:04x}", frame_type=typ, frame_subtype=subtype, frame_prefix=frame[:48].hex())
    if fc & 3:
        result["error"] = "protocol"
        return result
    result["post_stage"] = 2
    if typ != 0:
        result["error"] = "not_management"
        return result
    result["post_stage"] = 3
    if subtype not in (8,5):
        result["error"] = "not_beacon_probe"
        return result
    result["post_stage"] = 4
    bssid = ":".join(f"{v:02x}" for v in frame[16:22])
    p, ssid, channel = 36, None, None
    while p + 2 <= len(frame):
        eid, size = frame[p], frame[p+1]
        p += 2
        if p + size > len(frame):
            break
        if eid == 0:
            ssid = frame[p:p+size].decode("utf-8", "replace")
        elif eid == 3 and size:
            channel = frame[p]
        p += size
    result.update(bssid=bssid, ssid=ssid, advertised_channel=channel)
    if ssid is None:
        result["error"] = "no_ssid"
        return result
    result["post_stage"] = 5
    result["stage"] = 8
    if not service_ok:
        result["error"] = "service"
        return result
    result["decoded"] = True
    return result


def orientation_variants(x, cfo):
    return {
        "I+jQ": (x, cfo),
        "I-jQ": (np.conj(x), -cfo),
        "Q+jI": (1j*np.conj(x), -cfo),
        "Q-jI": (-1j*x, cfo),
    }


def main():
    root = Path(r"G:\WIFI_DIAG")
    report = []
    for c8 in sorted(root.glob("WAIM_00*.C8")):
        meta = metadata(c8.with_suffix(".TXT"))
        x = load_c8(c8)
        L, cfo = meta["ltf_position"], meta["cfo_hz"]
        variants = {}
        best = None
        # Exact metadata timing first, then a small timing/bin sweep to expose
        # convention errors without turning random noise into a large search.
        for name, (z, zcfo) in orientation_variants(x, cfo).items():
            exact = decode(z, L, zcfo)
            candidates = [exact]
            for dt in range(-8, 9):
                for shift in range(-2, 3):
                    if dt == 0 and shift == 0:
                        continue
                    candidates.append(decode(z, L, zcfo, dt, shift))
            chosen = max(candidates, key=lambda q: (q.get("stage",0), q.get("post_stage",0), -q.get("service_errors",255), -q.get("signal_metric",9999)))
            variants[name] = {"exact": exact, "best": chosen}
            tagged = dict(chosen, orientation=name)
            if best is None or (tagged.get("stage",0), tagged.get("post_stage",0), -tagged.get("service_errors",255), -tagged.get("signal_metric",9999)) > (best.get("stage",0), best.get("post_stage",0), -best.get("service_errors",255), -best.get("signal_metric",9999)):
                best = tagged
        p = np.abs(x)**2
        report.append({
            "file": c8.name,
            "metadata": meta,
            "iq": {
                "i_mean": float(x.real.mean()), "q_mean": float(x.imag.mean()),
                "i_rms": float(np.sqrt(np.mean(x.real*x.real))),
                "q_rms": float(np.sqrt(np.mean(x.imag*x.imag))),
                "clipped_i": int(np.count_nonzero(np.abs(x.real) >= 127)),
                "clipped_q": int(np.count_nonzero(np.abs(x.imag) >= 127)),
                "peak": float(np.sqrt(p.max())),
            },
            "variants": variants,
            "best": best,
        })
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

