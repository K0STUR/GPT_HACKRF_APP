#!/usr/bin/env python3
"""Static contract for calibrated Fix8u STF/LTF admission geometry."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "source_expanded" / "firmware"
PHY = (ROOT / "common" / "wifi_aim" / "wifi_aim_phy.cpp").read_text()
PROC_H = (ROOT / "baseband" / "proc_wifi_aim.hpp").read_text()
PROC = (ROOT / "baseband" / "proc_wifi_aim.cpp").read_text()

assert "kPretriggerSamples = 2'048" in PROC_H
assert "kSearchSamples = 5000u" in PHY
assert "kStfThreshold = 0.75f" in PHY
assert "kMinStfRun = 24u" in PHY
assert "kLtfTemplateThreshold = 0.30f" in PHY
assert "stf_run_end - stf_run_start + 1u" in PHY
assert "const float q=std::min(q0,q1);" in PHY
assert "ref_best<kLtfTemplateThreshold" in PHY
assert "static_cast<std::size_t>(2200u)" not in PHY

# Preserve Fix8t one-shot behavior and the Fix8s/Fix8p post-LTF pipeline.
assert "ofdm_trace.stage >= 7u" in PROC
assert "State::Frozen" in PROC and "State::Dumping" in PROC
assert "service_errors>2u" in PHY
for rate in ("case 11u", "case 15u", "case 10u", "case 14u", "case 9u", "case 13u", "case 8u", "case 12u"):
    assert rate in PHY, rate

print("FIX8U_CONTRACT=PASS pretrigger=2048 search=5000 stf=0.75x24 ltf_pair=0.30")
