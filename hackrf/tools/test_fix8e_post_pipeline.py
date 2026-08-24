#!/usr/bin/env python3
import random

# Reference model for the additive 802.11 scrambler used by the C++ decoder.
def scramble(bits, seed):
    state = seed & 0x7f
    out = []
    for b in bits:
        fb = ((state >> 6) & 1) ^ ((state >> 3) & 1)
        out.append((b & 1) ^ fb)
        state = ((state << 1) & 0x7e) | fb
    return out

# Mirrors the Fix8e decoder: infer the state after seven zero SERVICE bits from
# the first seven scrambled bits, then continue descrambling from bit 7.
def descramble_like_decoder(scrambled):
    state = 0
    for i in range(7):
        if scrambled[i]:
            state |= 1 << (6 - i)
    out = [0] * len(scrambled)
    for i in range(7, len(scrambled)):
        fb = ((state >> 6) & 1) ^ ((state >> 3) & 1)
        out[i] = fb ^ (scrambled[i] & 1)
        state = ((state << 1) & 0x7e) | fb
    return out

# Validate state reconstruction and SERVICE tail check for many seeds/payloads.
for seed in range(1, 128):
    random.seed(seed)
    payload = [random.getrandbits(1) for _ in range(8 * 80)]
    plain = [0] * 16 + payload
    coded = scramble(plain, seed)
    decoded = descramble_like_decoder(coded)
    assert decoded[7:] == plain[7:], f'descrambler mismatch seed={seed}'
    assert all(b == 0 for b in decoded[7:16]), f'SERVICE tail nonzero seed={seed}'

# Frame-control classification used by Fix8e post_stage.
def classify(fc):
    if fc & 0x0003:
        return 0, None, None
    typ = (fc >> 2) & 3
    subtype = (fc >> 4) & 15
    if typ != 0:
        return 2, typ, subtype
    if subtype not in (8, 5):
        return 3, typ, subtype
    return 4, typ, subtype

# Beacon, Probe Response, generic management, data, and invalid protocol version.
assert classify(0x0080) == (4, 0, 8)
assert classify(0x0050) == (4, 0, 5)
assert classify(0x0040) == (3, 0, 4)
assert classify(0x0008) == (2, 2, 0)
assert classify(0x0001)[0] == 0

print('Fix8e post-DATA reference test PASS')
