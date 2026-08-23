# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

First read, in this exact order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/build_results/wifi_aim_full_n260808_fix7/VERIFY.txt`
5. `hackrf/HANDOVER_MASTER.md`
6. `hackrf/WIFI_AIM_SPEC.md`
7. inspect `hackrf/source_expanded/`

Do not restart the project from scratch. The old repository `K0STUR/GPT` is now reserved for FORDstecki only; all HackRF work belongs in `K0STUR/GPT_HACKRF_APP`.

## Current device target
Real PortaPack firmware:
- stock Mayhem `n_260808`
- upstream tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Keep stock firmware. Do not move to matched custom `w_260822` without explicit permission.

## Hardware-proven baseline — Fix6
Fix6 passed the hardened zero-drift stock-core ABI audit and was tested on the real device.

Observed:
- application opens normally,
- no HardFault,
- red RF/RSSI bar reacts to antenna presence/orientation,
- `SCAN` completes but reports `0 AP`.

Fix6 artifact:
`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Fix6 audit:
- shared core symbols `7118`
- core drift `0`
- patch count `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- RESULT `PASS`

Therefore the loader/core-ABI problem is solved. Current failure is downstream in M4 capture / Wi-Fi PHY decode / reporting.

## Fix7 source changes
Readable source in `hackrf/source_expanded/` adds:
- 2048-sample pre-trigger IQ history,
- safer M4 initialization order (`BasebandThread` and `RSSIThread` last),
- lower capture threshold,
- 1000 ms/channel scan dwell,
- diagnostic `M/C/D` counters over the existing HunterTrigger ABI.

Intended hardware meanings:
- `M` follows channel -> M0-to-M4 control works,
- `C=0` -> capture detector is not firing,
- `C>0 D=0` -> captures occur but PHY rejects candidates,
- `D>0` and `0 AP` -> investigate AP report/parser path.

## Critical current result — Fix7 MUST NOT be hardware-tested
Fix7 CI run:
- run `32666957127`
- job `97261737292`

The GitHub job completed, but the actual hardened audit in `VERIFY.txt` says:
- size `23508`
- memory `0x10083FEC`
- entry `0x10084041`
- M4 offset `7140`
- shared core symbols `7118`
- **core_symbol_drift_count `179`**
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- PPMA SHA-256 `cb1cab400ea934f3d0bf2d3116d624c3310375a7f7342a2c00b3ec4a4d71248f`
- **RESULT `FAIL`**

Complete Fix7 artifact is archived in:
`hackrf/build_results/wifi_aim_full_n260808_fix7/`

Do NOT put `WiFiAIM_n260808_fix7.ppma` on the PortaPack.

## Exact next action
Preserve the useful Fix7 capture/diagnostic changes, but restore Fix6's zero-drift M0/core layout.

Investigate the first +4-byte core shift beginning around stock address `0x000A3C68`. Find which Fix7-added M0 object/data/rodata/message-handler registration escaped the external-app section, isolate it correctly, rebuild, and require all of:
- `core_symbol_drift_count=0`
- `patch_count=0`
- `ambiguous_count=0`
- `unresolved_count=0`
- final checksum `0`
- `RESULT=PASS`

Only then hardware-test the new candidate and read `M/C/D` during SCAN.

## End goal
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`

Requirements remain passive receive only, channels 1-13, Beacon + Probe Response parsing, hidden SSID handling, exact BSSID targeting, decoder OFF/AUTO/ON, and LIVE/AVG/PEAK/REF/DELTA REF. Relative signal is enough; do not claim calibrated dBm.
