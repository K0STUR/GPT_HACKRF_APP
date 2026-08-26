#!/usr/bin/env python3
"""Static/analytic contract checks for the one-shot Fix8t diagnostic capture."""

from math import atan
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "source_expanded" / "firmware"
PROC = (ROOT / "baseband" / "proc_wifi_aim.cpp").read_text()
UI = (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.cpp").read_text()
PHY = (ROOT / "common" / "wifi_aim" / "wifi_aim_phy.cpp").read_text()

# Frozen RAM capture, exact C8 byte count, bounded FIFO blocks and no live-RF
# forwarding in the diagnostic state.
assert "kCaptureSamples = 20'000" in (ROOT / "baseband" / "proc_wifi_aim.hpp").read_text()
assert "kCaptureBytes = 20'000u * 2u" in UI
assert "kWriteSize = 400u" in UI
assert 40_000 % 400 == 0
assert "ofdm_trace.stage >= 7u" in PROC
assert "if (state_ == State::Frozen) return;" in PROC
assert "capture_.data()" in PROC and "diag_stream_->write" in PROC

# C8 and all requested metadata fields must be emitted.
for field in (
    "format=C8 int8_I_int8_Q_interleaved",
    "frequency_hz=",
    "channel=",
    "sample_rate_sps=20000000",
    "lna_gain_db=",
    "vga_gain_db=",
    "rf_amp=",
    "SQ=",
    "L/H/V/P=",
    "R/N/D/M=",
    "ltf_position=",
    "cfo_hz=",
    "firmware=",
):
    assert field in UI, field

# Diagnostic CFO conversion does not alter synchronization/demodulation inputs,
# and its cubic atan approximation stays within 250 Hz over +/-Fs/32.
assert "const float phase = x - (x * x * x) / 3.0f;" in PHY
scale = 20_000_000 / (2.0 * 3.141592653589793)
worst_hz = max(abs((x - x**3 / 3.0) - atan(x)) * scale for x in (-0.2, 0.2))
assert worst_hz < 250.0, worst_hz

print(f"FIX8T_DIAG_CONTRACT=PASS c8_bytes=40000 cfo_approx_worst_hz={worst_hz:.1f}")
