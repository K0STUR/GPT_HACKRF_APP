#!/usr/bin/env python3
import random

RATES = {
    11: (1, 48, 24, 6, 0),
    15: (1, 48, 36, 9, 2),
    10: (2, 96, 48, 12, 0),
    14: (2, 96, 72, 18, 2),
    9:  (4, 192, 96, 24, 0),
    13: (4, 192, 144, 36, 2),
    8:  (6, 288, 192, 48, 1),
    12: (6, 288, 216, 54, 2),
}
PATS = {0: [1,1], 1: [1,1,1,0], 2: [1,1,1,0,0,1]}


def parity(x):
    return x.bit_count() & 1


def encode(bits):
    state = 0
    out = []
    for bit in bits:
        reg = ((state << 1) & 0x7e) | bit
        out.extend([parity(reg & 0o155), parity(reg & 0o117)])
        state = ((state << 1) & 0x3f) | bit
    return out


def puncture(mother, mode):
    if mode == 0:
        return mother[:]
    pat = PATS[mode]
    return [b for i,b in enumerate(mother) if pat[i % len(pat)]]


def depuncture(tx, mode):
    if mode == 0:
        return tx[:]
    pat = PATS[mode]
    out=[]; ii=0; pi=0
    while ii < len(tx) or pi != 0:
        if pat[pi]:
            assert ii < len(tx)
            out.append(tx[ii]); ii += 1
        else:
            out.append(2)
        pi = (pi + 1) % len(pat)
    return out


def viterbi(coded):
    assert len(coded) % 2 == 0
    steps = len(coded)//2
    INF=30000
    pm=[INF]*64; pm[0]=0
    surv=[]
    for t in range(steps):
        r0,r1=coded[2*t],coded[2*t+1]
        nm=[0]*64; dec=0
        for ns in range(64):
            bit=ns&1; p0=ns>>1; p1=p0|32
            reg0=((p0<<1)&0x7e)|bit
            reg1=((p1<<1)&0x7e)|bit
            bm0=((r0<2) and (parity(reg0&0o155)!=r0))+((r1<2) and (parity(reg0&0o117)!=r1))
            bm1=((r0<2) and (parity(reg1&0o155)!=r0))+((r1<2) and (parity(reg1&0o117)!=r1))
            m0=pm[p0]+bm0; m1=pm[p1]+bm1
            if m1<m0:
                nm[ns]=m1; dec |= 1<<ns
            else:
                nm[ns]=m0
        pm=nm; surv.append(dec)
    state=min(range(64), key=lambda s: pm[s])
    out=[0]*steps
    for tt in range(steps-1,-1,-1):
        out[tt]=state&1
        hi=(surv[tt]>>state)&1
        state=(state>>1)|(hi<<5)
    return out


def classify_axis(v):
    # Mirrors Fix8d's current receiver convention: negative sign -> bit 1.
    a=abs(v)
    return ((1 if v<0 else 0), 1 if a < 4/(42**0.5) else 0,
            1 if (a >= 2/(42**0.5) and a < 6/(42**0.5)) else 0)


def main():
    rng=random.Random(0x8D)
    for parser,(bpsc,cbps,dbps,mbps,mode) in RATES.items():
        bits=[rng.randrange(2) for _ in range(dbps)]
        mother=encode(bits)
        tx=puncture(mother,mode)
        assert len(tx)==cbps, (mbps,len(tx),cbps)
        dep=depuncture(tx,mode)
        assert len(dep)==2*dbps, (mbps,len(dep),2*dbps)
        got=viterbi(dep)
        assert got==bits, f'Viterbi mismatch at {mbps} Mb/s'

    # 64-QAM axis magnitude bits: levels 1,3,5,7 -> 10,11,01,00.
    s42=42**0.5
    expected={1:(1,0),3:(1,1),5:(0,1),7:(0,0)}
    for level,(b1,b2) in expected.items():
        for sign in (-1,1):
            b0,x1,x2=classify_axis(sign*level/s42)
            assert (x1,x2)==(b1,b2)
            assert b0==(1 if sign<0 else 0)

    print('FIX8D_REFERENCE_TEST=PASS all 8 legacy OFDM rates + 64-QAM thresholds')

if __name__=='__main__':
    main()
