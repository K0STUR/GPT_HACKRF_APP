#!/usr/bin/env python3
from pathlib import Path

p = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp')
s = p.read_text()
old = '''        fft_[n].r=xr*rr-xi*ri;\n        fft_[n].i=xr*ri+xi*rr;\n'''
new = '''        // Fix8q diagnostic: conjugate the CFO-corrected OFDM sample before\n        // FFT. This reverses spectral orientation (k <-> -k) while preserving\n        // amplitude/timing. DSSS and the raw repetition detector are untouched.\n        fft_[n].r=xr*rr-xi*ri;\n        fft_[n].i=-(xr*ri+xi*rr);\n'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)
p.write_text(s)
print('FIX8Q_PATCH=PASS')
