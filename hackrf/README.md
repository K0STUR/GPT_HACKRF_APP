# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-23

This folder is the canonical entry point for continuing the HackRF/PortaPack project in a new ChatGPT conversation.

## Read first
1. `HANDOVER_MASTER.md` — full project context and historical frontier.
2. `PROJECT_STATUS.md` — history of what worked and failed.
3. **`FIX6_STATIC_PASS_AND_HARDWARE_TEST.md` — CURRENT frontier and exact hardware-test instructions.**
4. `WIFI_AIM_SPEC.md` — required behaviour of the custom WiFi AIM app.
5. `TEST_LOG.md` — hardware tests and crash evidence.
6. `HARDWARE_RF_NOTES.md` — hardware/RF ecosystem notes.
7. `NEXT_CHAT_PROMPT.md` — ready-to-use continuation prompt.
8. `FILE_INDEX.md` — source/build/workflow archive index.

## Current one-line status
The full **WiFi AIM Fix6 for stock Mayhem `n_260808` has passed the hardened zero-drift stock-ABI audit** and is now ready for the first real-device hardware test. It is not hardware-proven yet.

## Current primary artifact
`build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Static verification highlights:
- size `22720`
- header `3`
- version `0x86B64C1D` (`n_260808`)
- tag `WAIM`
- M4 offset `6624`
- shared core symbols compared `7118`
- core symbol drift `0`
- ABI rebase patches `0`
- resolved same-address core refs `81`
- ambiguous imports `0`
- unresolved imports `0`
- final checksum `0x00000000`
- RESULT `PASS`

## Installation for current test
Keep stock Mayhem `n_260808`. Do **not** flash the custom `w_260822` firmware.

Copy only:
`WiFiAIM_n260808_fix6.ppma`

to:
`/APPS`

The `WAIM.bin` baseband image is already embedded in the `.ppma`; it is not copied separately.

The application should appear in the **RX** menu as `WiFi AIM`.

## First hardware criterion
`RX -> WiFi AIM` must open without HardFault. Then test:
`SCAN -> real SSIDs/BSSIDs -> select exact BSSID -> TARGET -> rotate directional antenna -> REF/DELTA REF`.

If it crashes, photograph the complete fault screen, especially PC/LR/R12, and record the exact action that triggered it.

## Historical artifacts — do not confuse with current candidate
- `build_results/wifi_aim_probe_n260808/` — hardware-proven simplified RF probe.
- `build_results/wifi_aim_full_n260808_fix5/` — historical FAIL; 58 rebases + 1 unresolved symbol.
- `build_results/wifi_aim_test_veneerpatch1_n260808/` — historical diagnostic candidate; static PASS only.
- `build_results/wifi_aim_bundle_w260822/` — matched custom firmware bundle; static PASS but requires flashing custom firmware and is not the current route.

## Do not restart from scratch
The project already has:
- a working 2.4 GHz RF probe on real hardware;
- Wi-Fi PHY decoding for DSSS 1 Mb/s and legacy OFDM 6/12/24 Mb/s;
- Beacon + Probe Response parsing;
- SSID/hidden SSID/BSSID/channel handling;
- target selection by exact BSSID;
- LIVE / AVG / PEAK / REF / DELTA REF framework;
- exact stock target `n_260808`, tag `nightly-tag-2026-08-08`, commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`;
- a full Fix6 candidate with zero stock-core symbol drift and zero unresolved imports.

Continue from `FIX6_STATIC_PASS_AND_HARDWARE_TEST.md`. Do not return to basic HackRF setup or Fix5 unless Fix6 hardware testing produces new evidence.