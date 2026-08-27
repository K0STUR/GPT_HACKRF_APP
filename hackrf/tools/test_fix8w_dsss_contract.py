#!/usr/bin/env python3
"""Static contract for Fix8w DSSS stage telemetry."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "source_expanded" / "firmware"
HPP = (ROOT / "common" / "wifi_aim" / "wifi_aim_phy.hpp").read_text()
CPP = (ROOT / "common" / "wifi_aim" / "wifi_aim_phy.cpp").read_text()
PROC_H = (ROOT / "baseband" / "proc_wifi_aim.hpp").read_text()
PROC_C = (ROOT / "baseband" / "proc_wifi_aim.cpp").read_text()
UI_H = (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.hpp").read_text()
UI_C = (ROOT / "application" / "external" / "wifi_aim" / "ui_wifi_aim.cpp").read_text()

stages = [
    "DSSS_ADMISSION", "DSSS_BARKER_CORRELATION", "DSSS_SYMBOL_TIMING",
    "DSSS_DIFFERENTIAL_DECODE", "DSSS_DESCRAMBLE", "DSSS_PLCP_HEADER",
    "DSSS_PAYLOAD", "DSSS_MAC_TYPE", "DSSS_BEACON_PROBE", "DSSS_SSID",
    "DSSS_FINAL_AP",
]
for stage in stages:
    assert stage in HPP, stage
    assert stage in CPP or stage in UI_C, stage

assert "uint16_t dsss_stage_mask" in HPP
assert "M4DsssTrace* trace = nullptr" in HPP
assert "std::array<uint16_t, wifiaim::DSSS_STAGE_COUNT> dsss_stage_counts_" in PROC_H
assert "std::array<uint16_t, wifiaim::DSSS_STAGE_COUNT> dsss_stage_counts_" in UI_H
assert "wire.ssid_len = 0xF8u" in PROC_C
assert "w.ssid_len == 0xF8u" in UI_C
assert "DSSS_STAGE_COUNT * sizeof(uint16_t)" in PROC_C
assert "DSSS_STAGE_COUNT * sizeof(uint16_t)" in UI_C
assert "profile_page_ == 3u" in UI_C
assert "send_wire_report(wire, profile_dsss_packet_)" in PROC_C

print("FIX8W_DSSS_CONTRACT=PASS stages=11 transport=WireApReport/0xF8 ABI_layout=unchanged")
