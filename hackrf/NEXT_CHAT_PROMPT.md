# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository `K0STUR/GPT_HACKRF_APP`, folder `hackrf/`.

First read, in this exact order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/HANDOVER_MASTER.md`
5. `hackrf/WIFI_AIM_SPEC.md`
6. `hackrf/FIX6_STATIC_PASS_AND_HARDWARE_TEST.md`
7. inspect `hackrf/source_expanded/` and `hackrf/build_results/`

Do not restart the project from scratch and do not return to Fix5/ABI rebasing unless new audit evidence requires it.

## Current target
My real PortaPack runs stock Mayhem `n_260808`, upstream tag `nightly-tag-2026-08-08`, commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`.

Keep stock `n_260808`; do not move to the matched custom `w_260822` firmware without my explicit permission.

## Hardware-proven result — Fix6
Fix6 passed the hardened zero-drift stock-core ABI audit and has now been tested on real hardware.

Real-device result:
- app launches without HardFault,
- red RF/RSSI bar reacts to attaching/removing/aiming the antenna,
- `SCAN` runs but reports `0 AP`.

Therefore the stock-loader/core-ABI blocker is solved. The current problem is downstream in M4 packet capture / WiFi PHY decoding / reporting.

Fix6 artifact:
`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Fix6 workflow run: `32631639944` — SUCCESS.

## Current frontier — Fix7 capture/PHY diagnostics
Readable Fix7 source is under `hackrf/source_expanded/`.

Fix7 changes include:
- 2048-sample pre-trigger history using the existing capture buffer,
- safer M4 member initialization: `BasebandThread` / `RSSIThread` moved to the end of member declarations,
- lower detector threshold (~1.25x noise floor + margin),
- SCAN dwell increased to 1000 ms/channel,
- M0/M4 diagnostics using the existing HunterTrigger ABI.

During scan the UI reports:
- `M` = M4 acknowledged channel,
- `C` = capture attempts,
- `D` = successful WiFi PHY decodes.

Interpretation:
- `M` follows channel, `C=0` -> detector/start path is not triggering,
- `C>0 D=0` -> capture works but PHY decoder rejects candidates; instrument OFDM/DSSS stages next,
- `D>0` but AP count remains 0 -> investigate AP report / WireApReport / parser path,
- AP count > 0 -> continue to SSID/BSSID selection, TARGET, AIM, REF and DELTA REF.

Fix7 workflow:
`.github/workflows/build_wifi_aim_full_n260808_fix7.yml`

Known Fix7 CI run at handoff:
- run `32666957127`
- job `97261737292`

Check its current/final status in GitHub before building another variant. Do not call Fix7 hardware-proven until it is actually tested on the device.

## End goal
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`

Requirements remain:
- passive receive only,
- channels 1-13,
- Beacon + Probe Response parsing,
- hidden SSID handling,
- exact BSSID targeting,
- decoder OFF/AUTO/ON framework,
- LIVE / AVG / PEAK / REF / DELTA REF,
- relative signal is sufficient; do not claim calibrated dBm.

Directional antenna connects to the HackRF upper SMA marked `ANTENNA`; the lower SMA is CLK IN/OUT.
