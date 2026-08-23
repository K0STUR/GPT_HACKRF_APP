# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-23

This folder is the canonical entry point for continuing the HackRF/PortaPack project. The canonical repository is now `K0STUR/GPT_HACKRF_APP`.

## Read first
1. `PROJECT_STATUS.md` — current frontier and history of what worked/failed.
2. `TEST_LOG.md` — hardware tests and crash evidence.
3. `NEXT_CHAT_PROMPT.md` — ready-to-use continuation prompt.
4. `HANDOVER_MASTER.md` — full historical project context.
5. `WIFI_AIM_SPEC.md` — required behaviour of the custom WiFi AIM app.
6. `FIX6_STATIC_PASS_AND_HARDWARE_TEST.md` — Fix6 ABI/static milestone and hardware-test instructions.
7. `HARDWARE_RF_NOTES.md` — hardware/RF ecosystem notes.
8. `FILE_INDEX.md` — source/build/workflow archive index.

## Current one-line status
**Fix6 is hardware-launch proven on stock Mayhem `n_260808`: the app opens without HardFault and the red RF/RSSI bar reacts to the antenna, but SCAN reports `0 AP`. The current frontier is Fix7 capture/PHY diagnostics.**

This means the stock-loader/core-ABI blocker is solved. Do not return to Fix5 rebasing unless a future zero-drift audit actually fails.

## Fix6 proven baseline
Artifact:
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

Real hardware result:
- application launch: PASS,
- no launch HardFault,
- RF/RSSI bar reacts to antenna: PASS,
- SCAN: completes but `0 AP`.

## Current frontier — Fix7
Fix7 source is readable under `source_expanded/` and addresses two concrete weaknesses found after the Fix6 hardware test:
- missing pre-trigger IQ history before the detector fires,
- unsafe M4 initialization order because `BasebandThread` auto-started before later members were initialized.

Fix7 also:
- lowers the detector threshold,
- increases scan dwell to 1000 ms/channel,
- exposes compact `M/C/D` diagnostics using the existing HunterTrigger ABI.

Interpretation during hardware testing:
- `M` follows channel, `C=0` -> control reaches M4 but detector/capture is not triggering,
- `C>0 D=0` -> captures occur but PHY decoding rejects candidates,
- `D>0` with `0 AP` -> investigate AP report / WireApReport / M0 parser,
- AP count > 0 -> continue to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

Workflow:
`.github/workflows/build_wifi_aim_full_n260808_fix7.yml`

Known Fix7 CI run at handoff:
- run `32666957127`
- job `97261737292`

Check its final status before creating another variant. Fix7 is **not hardware-proven yet** until tested on the real device.

## Firmware rule
Keep stock Mayhem `n_260808`:
- upstream tag `nightly-tag-2026-08-08`
- commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do **not** flash the matched custom `w_260822` firmware unless the user explicitly chooses that route.

## Historical artifacts — do not confuse with current frontier
- `build_results/wifi_aim_probe_n260808/` — hardware-proven simplified RF probe.
- `build_results/wifi_aim_full_n260808_fix5/` — historical FAIL; 58 rebases + 1 unresolved symbol.
- `build_results/wifi_aim_test_veneerpatch1_n260808/` — historical diagnostic candidate; static PASS only.
- `build_results/wifi_aim_bundle_w260822/` — matched custom firmware bundle; static PASS but requires flashing custom firmware and is not the current route.
- `build_results/wifi_aim_full_n260808_fix6/` — hardware-launch-proven stock baseline; SCAN `0 AP`.

## Do not restart from scratch
The project already has:
- a working 2.4 GHz RF receive path on real hardware,
- DSSS 1 Mb/s and legacy OFDM 6/12/24 Mb/s decoder paths,
- Beacon + Probe Response parsing,
- SSID/hidden SSID/BSSID/channel handling,
- exact BSSID target selection,
- LIVE / AVG / PEAK / REF / DELTA REF framework,
- a proven zero-drift stock-core ABI route on `n_260808`,
- Fix7 pre-trigger and M4 diagnostic work ready/current.

Final goal remains:
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`.

Passive receive only. Relative signal is sufficient; do not claim calibrated dBm.
