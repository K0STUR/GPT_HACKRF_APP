# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-23

This folder is the canonical entry point for continuing the HackRF/PortaPack project. The canonical repository is now **`K0STUR/GPT_HACKRF_APP`**.

The old `K0STUR/GPT` repository has been cleaned and is now reserved for `FORDstecki` only.

## Read first
1. `PROJECT_STATUS.md` — current frontier and history of what worked/failed.
2. `TEST_LOG.md` — hardware tests and build/audit evidence.
3. `NEXT_CHAT_PROMPT.md` — ready-to-use continuation prompt.
4. `HANDOVER_MASTER.md` — historical project context.
5. `WIFI_AIM_SPEC.md` — required behaviour of the custom WiFi AIM app.
6. `FIX6_STATIC_PASS_AND_HARDWARE_TEST.md` — Fix6 milestone.
7. `source_expanded/` — readable current source.
8. `build_results/wifi_aim_full_n260808_fix7/` — complete archived Fix7 CI output.

## Current one-line status
**Fix6 is hardware-launch proven on stock Mayhem `n_260808`: app launch PASS, RF/RSSI reacts to the antenna, but SCAN returns `0 AP`. Fix7 added the right capture/diagnostic changes, but its hardened stock-core ABI audit FAILED because it shifted 179 shared core symbols. Therefore Fix7 must NOT be hardware-tested yet.**

## Proven baseline — Fix6
Artifact:
`build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Static verification:
- size `22720`
- header `3`
- version `0x86B64C1D` (`n_260808`)
- tag `WAIM`
- M4 offset `6624`
- shared core symbols compared `7118`
- core symbol drift `0`
- ABI rebase patches `0`
- same-address core references `81`
- ambiguous imports `0`
- unresolved imports `0`
- checksum `0x00000000`
- RESULT `PASS`

Real hardware:
- launch: PASS
- HardFault: none
- RF/RSSI bar reacts to antenna: PASS
- SCAN: `0 AP`

This proves the stock loader/core-ABI route works. Do not return to Fix5-style rebasing unless new evidence actually requires it.

## Fix7 — source improvement, static ABI FAIL
Fix7 source under `source_expanded/` adds:
- 2048 IQ samples of pre-trigger history using the existing capture buffer,
- safer M4 initialization order (`BasebandThread` / `RSSIThread` moved last),
- lower detector threshold,
- 1000 ms/channel scan dwell,
- `M/C/D` diagnostics over the existing stock `HunterTriggerMessage` ABI.

Intended diagnostics:
- `M` = last channel acknowledged by M4,
- `C` = capture attempts,
- `D` = successful Wi-Fi PHY decodes.

Fix7 CI:
- run `32666957127`
- job `97261737292`
- GitHub job itself completed successfully, including build and publication steps.

However the **actual hardened VERIFY result is FAIL**:
- size `23508`
- memory `0x10083FEC`
- entry `0x10084041`
- M4 offset `7140`
- shared core symbols `7118`
- **core symbol drift `179`**
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- PPMA SHA-256 `cb1cab400ea934f3d0bf2d3116d624c3310375a7f7342a2c00b3ec4a4d71248f`
- **RESULT `FAIL`**

Complete archived output:
`build_results/wifi_aim_full_n260808_fix7/`

It contains the original Actions artifact ZIP, `BUILD.log`, `.ppma`, `.b64`, `WAIM.bin`, `VERIFY.txt`, `STATUS.txt`, and hashes.

**Do not copy `WiFiAIM_n260808_fix7.ppma` to the PortaPack.**

## Exact next engineering action
Keep the useful Fix7 pre-trigger / M4 init / diagnostics changes, but restore the same zero-drift property achieved by Fix6.

Investigate the first new 4-byte shift in the modified M0/core layout (the drift starts around stock `0x000A3C68`) and determine which Fix7-added M0 object/data/rodata/registration escaped the external-app section. Then rebuild and require:
- `core_symbol_drift_count=0`
- `patch_count=0`
- `ambiguous_count=0`
- `unresolved_count=0`
- final checksum `0`
- `RESULT=PASS`

Only after that should a new Fix7-compatible candidate be hardware-tested and its `M/C/D` values used to localize SCAN `0 AP`.

## Firmware rule
Keep stock Mayhem `n_260808`:
- upstream tag `nightly-tag-2026-08-08`
- commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do **not** flash the matched custom `w_260822` firmware without explicit user permission.

## Final goal
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`

Passive receive only. Relative signal is sufficient; do not claim calibrated dBm.
