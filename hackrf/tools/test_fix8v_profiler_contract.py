#!/usr/bin/env python3
"""Static contract for the Fix8v measurement-only reliability profiler."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "source_expanded" / "firmware"
PHY = (ROOT / "common" / "wifi_aim" / "wifi_aim_phy.cpp").read_text()
WIRE = (ROOT / "common" / "wifi_aim_wire.hpp").read_text()
PROC = (ROOT / "baseband" / "proc_wifi_aim.cpp").read_text()
UI = (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.cpp").read_text()

for name in (
    "PROFILE_ENERGY", "PROFILE_SHADOW_256", "PROFILE_SHADOW_128",
    "PROFILE_STF", "PROFILE_LTF", "PROFILE_SIGNAL_VITERBI",
    "PROFILE_SIGNAL_PARITY", "PROFILE_RATE_LENGTH", "PROFILE_DATA_VITERBI",
    "PROFILE_SERVICE", "PROFILE_PROTOCOL", "PROFILE_MANAGEMENT",
    "PROFILE_BEACON_PROBE", "PROFILE_SSID", "PROFILE_FINAL_AP",
):
    assert name in WIRE and name in PROC, name

# The only real capture admission remains the Fix8u full-block mean. Both
# subblock variants are counters, never alternate capture conditions.
assert "const uint32_t p = powers.full" in PROC
assert "if (p >= threshold)" in PROC
assert "if (powers.max256 >= threshold) sat_inc" in PROC
assert "if (powers.max128 >= threshold) sat_inc" in PROC
capture_gate = PROC.split("if (p >= threshold)", 1)[1].split("} else {", 1)[0]
assert "copy_into_capture(buffer)" in capture_gate
assert "max256" not in capture_gate and "max128" not in capture_gate

# Ten seconds on one selected channel; no timed retune/channel increment.
assert "timer_ms_ >= 10000u" in UI
frame_body = UI.split("void WifiAimView::on_frame_sync()", 1)[1].split(
    "void WifiAimView::on_packet", 1
)[0]
assert "++scan_channel_" not in frame_body
assert '"CH -"' in (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.hpp").read_text()
assert '"CH +"' in (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.hpp").read_text()

# Fix8u sync thresholds and the Fix8t frozen-RAM capture remain intact.
for token in ("kStfThreshold = 0.75f", "kLtfTemplateThreshold = 0.30f", "kSearchSamples = 5000u"):
    assert token in PHY
for token in ("State::Frozen", "State::Dumping", "kCaptureSamples = 20'000"):
    assert token in PROC or token in (ROOT / "baseband" / "proc_wifi_aim.hpp").read_text()
assert "0xFAu" in PROC and "0xFBu" in PROC and "0xFCu" in PROC and "0xFDu" in PROC

# Profiler observes existing sequential trace boundaries; it does not add a
# second demapper/Viterbi/SERVICE/MAC implementation.
assert PROC.count("decoder_.decode(") == 1
assert "service_errors>2u" in PHY

print("FIX8V_PROFILER_CONTRACT=PASS single_channel=10s production_trigger=full shadow=256,128")
