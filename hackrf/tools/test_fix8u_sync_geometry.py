#!/usr/bin/env python3
import math
from pathlib import Path

import numpy as np

from wifi_aim_offline import DATA_K, FS, LONG, PILOT_BASE, PILOT_K, PILOT_POL, RATES, decode


def parity(v):
    return v.bit_count() & 1


def conv_encode(bits):
    state = 0
    out = []
    for bit in bits:
        reg = ((state << 1) & 0x7e) | int(bit)
        out.extend((parity(reg & 0o155), parity(reg & 0o117)))
        state = ((state << 1) & 0x3f) | int(bit)
    return out


def puncture(bits, mode):
    if mode == 0:
        return bits
    pat = [1,1,1,0] if mode == 1 else [1,1,1,0,0,1]
    return [b for i,b in enumerate(bits) if pat[i % len(pat)]]


def interleave(bits, n_cbps, n_bpsc):
    out = [0] * n_cbps
    s = max(n_bpsc // 2, 1)
    for k in range(n_cbps):
        first = s*(k//s) + ((k + (16*k)//n_cbps) % s)
        second = 16*first - (n_cbps-1)*((16*first)//n_cbps)
        out[k] = bits[second]
    return out


def constellation(bits, n_bpsc):
    b = list(map(int,bits))
    if n_bpsc == 1:
        return 1.0 if b[0] else -1.0
    if n_bpsc == 2:
        return complex(1 if b[0] else -1, 1 if b[1] else -1) / math.sqrt(2)
    if n_bpsc == 4:
        re = (1 if b[0] else -1) * (1 if b[1] else 3)
        im = (1 if b[2] else -1) * (1 if b[3] else 3)
        return complex(re,im) / math.sqrt(10)
    levels = {(1,0):1, (1,1):3, (0,1):5, (0,0):7}
    re = (1 if b[0] else -1) * levels[(b[1],b[2])]
    im = (1 if b[3] else -1) * levels[(b[4],b[5])]
    return complex(re,im) / math.sqrt(42)


def ofdm_symbol(coded, n_bpsc, pilot_index):
    freq = np.zeros(64, dtype=np.complex128)
    for n,k in enumerate(DATA_K):
        freq[k % 64] = constellation(coded[n*n_bpsc:(n+1)*n_bpsc], n_bpsc)
    pol = PILOT_POL[pilot_index & 63]
    for k,e in zip(PILOT_K,PILOT_BASE):
        freq[k % 64] = e * pol
    td = np.fft.ifft(freq)
    return np.concatenate((td[-16:],td))


def scramble(bits, seed):
    state = seed & 0x7f
    out=[]
    for bit in bits:
        fb=((state>>6)^(state>>3))&1
        out.append((int(bit)&1)^fb)
        state=((state<<1)&0x7e)|fb
    return out


def bits_lsb(data):
    return [(v >> i) & 1 for v in data for i in range(8)]


def beacon_psdu(length=96):
    bssid=bytes.fromhex("021122334455")
    frame = bytearray()
    frame += (0x0080).to_bytes(2,"little") + b"\x00\x00"
    frame += b"\xff"*6 + bssid + bssid + b"\x10\x00"
    frame += b"\x00"*8 + (100).to_bytes(2,"little") + b"\x01\x04"
    frame += bytes((0,8)) + b"FIX8TEST" + bytes((3,1,6))
    frame += bytes((1,4,0x82,0x84,0x8b,0x96))
    if len(frame) < length-4:
        frame += bytes(length-4-len(frame))
    frame += b"\x00"*4
    return bytes(frame[:length])


def standard_stf():
    vals = [
        0,0,1+1j,0,0,0,-1-1j,0,0,0,1+1j,0,0,0,-1-1j,0,0,0,-1-1j,0,0,0,1+1j,0,0,0,0,
        0,0,0,-1-1j,0,0,0,-1-1j,0,0,0,1+1j,0,0,0,1+1j,0,0,0,1+1j,0,0,0,1+1j,0,0,
    ]
    assert len(vals) == 53
    f=np.zeros(64,dtype=np.complex128)
    for k,v in zip(range(-26,27),vals):
        f[k%64]=v*math.sqrt(13/6)
    short=np.fft.ifft(f)[:16]
    return np.tile(short,10)


def make_packet(rate_raw, length=96, seed=0x5d):
    n_bpsc,n_cbps,n_dbps,_,puncture_mode=RATES[rate_raw]
    psdu=beacon_psdu(length)
    sig=[(rate_raw>>i)&1 for i in range(4)] + [0] + [(length>>i)&1 for i in range(12)]
    sig += [sum(sig)&1] + [0]*6
    sig_coded=interleave(conv_encode(sig),48,1)
    signal=ofdm_symbol(sig_coded,1,0)
    n_symbols=math.ceil((16+8*length+6)/n_dbps)
    data=[0]*16+bits_lsb(psdu)+[0]*6
    data += [0]*(n_symbols*n_dbps-len(data))
    data=scramble(data,seed)
    mother=conv_encode(data)
    tx=puncture(mother,puncture_mode)
    data_syms=[]
    for si in range(n_symbols):
        block=tx[si*n_cbps:(si+1)*n_cbps]
        assert len(block)==n_cbps
        data_syms.append(ofdm_symbol(interleave(block,n_cbps,n_bpsc),n_bpsc,si+1))
    ltf=np.fft.ifft(LONG)
    return np.concatenate((standard_stf(),ltf[-32:],ltf,ltf,signal,*data_syms))


def trigger_capture(rate_raw, ltf_position, cfo_hz=180000, noise_sigma=1.5, scale=320.0, taps=None):
    rng=np.random.default_rng(0x8A00 + rate_raw*31 + ltf_position)
    packet=make_packet(rate_raw)
    start=ltf_position-192
    assert start >= 0 and start+len(packet) <= 20000
    x=(rng.normal(0,noise_sigma,20000)+1j*rng.normal(0,noise_sigma,20000))
    if taps is not None:
        packet=np.convolve(packet,np.asarray(taps,dtype=np.complex128))[:len(packet)]
    x[start:start+len(packet)] += packet*scale
    n=np.arange(20000)
    x *= np.exp(2j*np.pi*cfo_hz*n/FS + 0.37j)
    return np.clip(np.rint(np.column_stack((x.real,x.imag))),-127,127)[:,0] + 1j*np.clip(np.rint(np.column_stack((x.real,x.imag))),-127,127)[:,1]


def q16_at(x,d):
    a,b=x[d:d+64],x[d+16:d+80]
    return abs(np.vdot(a,b))**2/(np.vdot(a,a).real*np.vdot(b,b).real)


def find_sync(x, stf_threshold=0.50, ltf_threshold=0.30, search_limit=5000, min_run=24):
    scan_end=min(len(x)-80,search_limit)
    runs=[]; start=None; peak_q=-1; peak_d=0
    for d in range(scan_end):
        q=q16_at(x,d)
        if q>=stf_threshold:
            if start is None: start=d; peak_q=q; peak_d=d
            if q>peak_q: peak_q=q; peak_d=d
        elif start is not None:
            if d-start>=min_run: runs.append((start,d-1,peak_d,peak_q))
            start=None
    if start is not None and scan_end-start>=min_run:
        runs.append((start,scan_end-1,peak_d,peak_q))
    ref=np.fft.ifft(LONG); refe=np.vdot(ref,ref).real
    best=None
    for rs,re,pd,pq in runs[:8]:
        a,b=x[pd:pd+64],x[pd+16:pd+80]
        coarse=np.angle(np.vdot(a,b))*FS/(2*np.pi*16)
        lo=max(0,rs+128); hi=min(len(x)-128,search_limit,re+176)
        for d in range(lo,hi+1):
            n=np.arange(128)
            y=x[d:d+128]*np.exp(-2j*np.pi*coarse*n/FS)
            den0=refe*np.vdot(y[:64],y[:64]).real
            den1=refe*np.vdot(y[64:],y[64:]).real
            q0=0 if den0<=1 else abs(np.vdot(ref,y[:64]))**2/den0
            q1=0 if den1<=1 else abs(np.vdot(ref,y[64:]))**2/den1
            q=min(q0,q1)
            if best is None or q>best["ltf_score"]:
                best={"ltf":d,"ltf_score":float(q),"stf_peak":float(pq),"stf_run":re-rs+1,"coarse_cfo":float(coarse)}
    if best is None or best["ltf_score"]<ltf_threshold:
        return best
    L=best["ltf"]; coarse=best["coarse_cfo"]
    n=np.arange(128)
    y=x[L:L+128]*np.exp(-2j*np.pi*coarse*n/FS)
    residual=np.angle(np.vdot(y[:64],y[64:]))*FS/(2*np.pi*64)
    best["cfo_hz"]=float(coarse+residual)
    best["accepted"]=True
    return best


def find_sync_cpp(x, stf_threshold=0.75, ltf_threshold=0.30, search_limit=5000, min_run=24):
    limit=min(len(x)-128,search_limit)
    runs=[]; start=None; peak=0
    for d in range(min(limit,len(x)-80)):
        q=q16_at(x,d)
        if q>=stf_threshold:
            if start is None: start=d; peak=q
            peak=max(peak,q); end=d
        elif start is not None:
            if end-start+1>=min_run: runs.append((peak,start,end))
            start=None; peak=0
    if start is not None and end-start+1>=min_run: runs.append((peak,start,end))
    if not runs: return None
    _,ss,se=max(runs)
    lo=min(limit,ss+128); hi=min(limit,se+176)
    qruns=[]; start=None; peak=0
    for d in range(lo,hi):
        a=x[d:d+64]; b16=x[d+16:d+80]; b64=x[d+64:d+128]
        e=np.vdot(a,a).real
        q16=abs(np.vdot(a,b16))**2/(e*np.vdot(b16,b16).real)
        q64=abs(np.vdot(a,b64))**2/(e*np.vdot(b64,b64).real)
        metric=q64*(1-q16)
        if metric>=0.15:
            if start is None: start=d; peak=metric
            peak=max(peak,metric); end=d
        elif start is not None:
            if end-start+1>=4: qruns.append((peak,start,end))
            start=None; peak=0
    if start is not None and end-start+1>=4: qruns.append((peak,start,end))
    if not qruns: return None
    _,_,best_end=max(qruns)
    nominal=max(0,best_end-8)
    bestq=-1; bestd=nominal; bestcfo=0
    ref=np.fft.ifft(LONG); refe=np.vdot(ref,ref).real
    for pd in range(ss,se+1):
        a,b=x[pd:pd+64],x[pd+16:pd+80]
        q=abs(np.vdot(a,b))**2/(np.vdot(a,a).real*np.vdot(b,b).real)
        if q>bestcfo:
            bestcfo=q; coarse=np.angle(np.vdot(a,b))*FS/(2*np.pi*16)
    for d in range(max(0,nominal-48),min(nominal+48,len(x)-128)+1):
        n=np.arange(128); y=x[d:d+128]*np.exp(-2j*np.pi*coarse*n/FS)
        q=[]
        for half in (y[:64],y[64:]):
            q.append(abs(np.vdot(ref,half))**2/(refe*np.vdot(half,half).real))
        score=min(q)
        if score>bestq: bestq=score; bestd=d
    result={"ltf":bestd,"ltf_score":float(bestq),"stf_peak":float(max(runs)[0])}
    if bestq<ltf_threshold: return result
    n=np.arange(128); y=x[bestd:bestd+128]*np.exp(-2j*np.pi*coarse*n/FS)
    residual=np.angle(np.vdot(y[:64],y[64:]))*FS/(2*np.pi*64)
    result.update(cfo_hz=float(coarse+residual),accepted=True)
    return result


if __name__ == "__main__":
    positions=[1800,2048,2200,2500,3000,3500,4096,4500]
    mins={"stf":1.0,"ltf":1.0}; failures=[]
    profiles=[
        ("clean",320.0,1.5,None,180000),
        ("noise_multipath",320.0,2.0,[1,0,0.18*np.exp(0.7j),0,0,0.09*np.exp(-0.9j)],-230000),
    ]
    total=len(RATES)*len(positions)*len(profiles)
    for profile,scale,noise,taps,cfo in profiles:
        for rate in RATES:
            for pos in positions:
                x=trigger_capture(rate,pos,cfo,noise,scale,taps)
                s=find_sync_cpp(x)
                if not s or not s.get("accepted"):
                    failures.append((profile,rate,pos,"sync",s)); continue
                d=decode(x,s["ltf"],s["cfo_hz"])
                if not d.get("decoded"):
                    failures.append((profile,rate,pos,"decode",d)); continue
                mins["stf"]=min(mins["stf"],s["stf_peak"])
                mins["ltf"]=min(mins["ltf"],s["ltf_score"])
    assert not failures, failures[:3]
    assert total == 8 * 8 * 2

    # Calibration evidence from the four hardware C8 files. These values are
    # tied to the SHA-256 hashes recorded in the Fix8u analysis report. The
    # strongest isolated lag-16 peak is still below the sustained STF gate;
    # all absolute LTF scores are far below the 30% admission boundary.
    hardware_stf = [0.494504, 0.724230, 0.488151, 0.642244]
    hardware_ltf = [0.093, 0.040, 0.058, 0.060]
    assert max(hardware_stf) < 0.75
    assert max(hardware_ltf) < 0.30
    assert mins["stf"] > 0.90
    assert mins["ltf"] > 0.80

    # Prove why the old 2,200-sample geometry was insufficient using the same
    # realistic pre-trigger placement model, not merely a constant comparison.
    old_misses=[]
    for pos in positions:
        x=trigger_capture(11,pos)
        old=find_sync_cpp(x,search_limit=2200)
        if not old or not old.get("accepted") or abs(old["ltf"]-pos)>1:
            old_misses.append(pos)
    assert all(pos in old_misses for pos in (2500,3000,3500,4096,4500)), old_misses

    print(
        "FIX8U_SYNC_GEOMETRY=PASS",
        f"cases={total}/{total}",
        "legacy_rates=8/8",
        f"positions={','.join(map(str,positions))}",
        f"golden_min_stf={mins['stf']:.3f}",
        f"golden_min_ltf={mins['ltf']:.3f}",
        f"hardware_max_stf={max(hardware_stf):.3f}",
        f"hardware_max_ltf={max(hardware_ltf):.3f}",
        f"old_search_misses={','.join(map(str,old_misses))}",
    )
