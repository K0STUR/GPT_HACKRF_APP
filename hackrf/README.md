# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-24

This folder is the canonical entry point for continuing the HackRF/PortaPack project. The canonical repository is **`K0STUR/GPT_HACKRF_APP`**.

The old `K0STUR/GPT` repository is reserved for `FORDstecki` only.

## Read first
1. `PROJECT_STATUS.md` — current frontier and history.
2. `TEST_LOG.md` — hardware tests and build/audit evidence.
3. `NEXT_CHAT_PROMPT.md` — ready-to-use continuation prompt.
4. `HANDOVER_MASTER.md` — historical project context.
5. `WIFI_AIM_SPEC.md` — required behaviour.
6. `FIX6_STATIC_PASS_AND_HARDWARE_TEST.md` — Fix6 milestone.
7. `source_expanded/` — readable current source.
8. `build_results/wifi_aim_full_n260808_fix7/` — archived failed Fix7 output.

## Current one-line status
**Fix6 is hardware-launch proven on stock Mayhem `n_260808` but SCAN returns `0 AP`. Fix7 improved capture/telemetry but failed zero-drift ABI. Fix7b keeps the useful Fix7 M4 changes, moves telemetry onto the existing Fix6 `FSKPacket` IPC path, and has now passed the hardened zero-drift audit. Fix7b is ready for hardware test; hardware result is still pending.**

## Hardware-proven baseline — Fix6
Artifact:
`build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Real hardware:
- launch PASS
- no HardFault
- RF/RSSI bar reacts to antenna
- SCAN `0 AP`

This proves the stock loader/core-ABI route works.

## Fix7 — archived static FAIL
Fix7 added:
- 2048-sample pre-trigger history,
- safer M4 thread initialization order,
- lower detector threshold,
- 1000 ms/channel dwell,
- M/C/D runtime diagnostics.

Its additional M0 `HunterTrigger` handler shifted 179 shared core symbols. The candidate is archived for evidence and must not be put on the device.

Archived output:
`build_results/wifi_aim_full_n260808_fix7/`

## Fix7b — current static PASS candidate
Fix7b retains all useful M4/pre-trigger changes but **does not add a new M0 message-handler type**. M/C/D telemetry is multiplexed through the existing `FSKPacket` route already used by Fix6. `WireApReport.flags` bit1 marks a diagnostic-only report.

CI:
- technical PR `#4`
- run `32671853658`
- job `97273779780`
- Actions result `SUCCESS`
- artifact `wifi-aim-full-n260808-fix7b`, ID `9501915159`

Hardened verification:
- size `23396`
- header `3`
- version `0x86B64C1D` (`n_260808`)
- tag `WAIM`
- M4 offset `7036`
- shared core symbols `7086`
- **core symbol drift `0`**
- drift references `0`
- ABI rebase patches `0`
- same-address core references `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock/mod `_Znwj = 0x7ee24`
- PPMA SHA-256 `730dee07e741cc5a2764dfcf9ffbae52622caf25a75ea6e94a7ffabbf9cb2b49`
- **RESULT `PASS`**

The downloaded artifact was independently rechecked: size/header/version/tag/M4 offset/Thumb entry/checksum/SHA all match CI.

## Next hardware test
Keep stock Mayhem `n_260808`. Do not flash firmware.

Copy **only** `WiFiAIM_n260808_fix7b.ppma` into `/APPS` and remove/move Fix6 from `/APPS` first to avoid duplicate menu items. `WAIM.bin` is embedded and must not be copied separately.

During SCAN observe:
- `M` = last channel acknowledged by M4,
- `C` = capture attempts,
- `D` = successful Wi-Fi PHY decodes.

After ~13 seconds report the exact final string such as `Done 0AP C123 D0` and whether `M` followed the scanned channel.

Interpretation:
- `M` follows + `C=0` -> capture detector issue;
- `C>0 D=0` -> capture works; instrument PHY stages next;
- `D>0` but AP=0 -> report/parser path;
- AP>0 -> continue directly to SSID/BSSID TARGET and AIM/REF/DELTA.

## Firmware rule
Keep stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do **not** flash matched custom `w_260822` without explicit permission.

## Final goal
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`

Passive receive only. Relative signal is sufficient; do not claim calibrated dBm.
