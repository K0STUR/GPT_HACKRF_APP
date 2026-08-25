#!/usr/bin/env python3
from pathlib import Path

phy = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp')
s = phy.read_text()
old = '''    // Fix8n compact radius-1 SERVICE seed recovery.\n    uint8_t raw_state=0u;\n    for (unsigned i=0;i<7u;++i) raw_state|=static_cast<uint8_t>((decoded_[i]&1u)<<(6u-i));\n    uint8_t best_state=0u, service_errors=0xFFu;\n    for (unsigned flip=0u;flip<8u;++flip) {\n        unsigned candidate=raw_state ^ (flip<7u ? (64u>>flip) : 0u);\n        if (!candidate) continue;\n        uint8_t errors=static_cast<uint8_t>(flip<7u);\n        unsigned st=candidate;\n        for (unsigned i=7u;i<16u && errors<=1u;++i) {\n            const unsigned feedback=((st>>6)^(st>>3))&1u;\n            errors+=static_cast<uint8_t>((decoded_[i]&1u)!=feedback);\n            st=((st<<1)&0x7eu)|feedback;\n        }\n        if (errors<service_errors) { service_errors=errors; best_state=static_cast<uint8_t>(candidate); }\n    }\n    if (trace) trace->service_errors=service_errors;\n    if (!best_state || service_errors>1u) return false;\n'''
new = '''    // Fix8p: exact nearest-codeword search across all 127 legal non-zero\n    // scrambler sequences. Unlike Fix8n's radius-1 fast path, FC now reports\n    // the true Hamming distance across all 16 known-zero SERVICE bits.\n    // Distance <=2 is admitted experimentally; existing MAC structure checks\n    // remain mandatory before an AP can be reported.\n    uint8_t best_state=0u, service_errors=0xFFu;\n    for (unsigned candidate=1u;candidate<128u;++candidate) {\n        uint8_t errors=0u;\n        for (unsigned i=0u;i<7u;++i)\n            errors+=static_cast<uint8_t>((decoded_[i]&1u)!=((candidate>>(6u-i))&1u));\n        unsigned st=candidate;\n        for (unsigned i=7u;i<16u;++i) {\n            const unsigned feedback=((st>>6)^(st>>3))&1u;\n            errors+=static_cast<uint8_t>((decoded_[i]&1u)!=feedback);\n            st=((st<<1)&0x7eu)|feedback;\n        }\n        if (errors<service_errors) {\n            service_errors=errors;\n            best_state=static_cast<uint8_t>(candidate);\n        }\n    }\n    if (trace) trace->service_errors=service_errors;\n    if (!best_state || service_errors>2u) return false;\n'''
if old not in s:
    raise SystemExit('Fix8n SERVICE block not found exactly once')
if s.count(old) != 1:
    raise SystemExit(f'Fix8n SERVICE block count={s.count(old)}')
s = s.replace(old, new, 1)
phy.write_text(s)

hpp = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.hpp')
h = hpp.read_text()
h = h.replace('// Fix8m: Hamming distance of known-zero SERVICE bits 7..15.\n    uint8_t service_errors{0xFFu};',
              '// Fix8p: exact nearest legal scrambler-sequence Hamming distance across SERVICE bits 0..15.\n    uint8_t service_errors{0xFFu};')
hpp.write_text(h)
print('FIX8P_PATCH=PASS exact 127-state SERVICE search + distance<=2 diagnostic admission')
