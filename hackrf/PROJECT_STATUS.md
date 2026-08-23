# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**.
The old `K0STUR/GPT` repository is reserved for `FORDstecki` only.

## Current device firmware
- Device Mayhem: stock `n_260808`
- Upstream tag: `nightly-tag-2026-08-08`
- Upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- Preserve stock firmware unless the user explicitly agrees otherwise.

## Proven hardware baseline — Fix6
Fix6 solved the stock-firmware loader/core-ABI blocker and was tested on real hardware.

Artifact:
`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Static audit:
- workflow run `32631639944` SUCCESS
- size `22720`
- core symbol drift `0`
- ABI rebase patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- RESULT `PASS`

Real hardware:
- app opens normally on stock `n_260808`
- no HardFault
- red RF/RSSI bar responds to antenna
- SCAN completes but reports `0 AP`

Therefore the remaining problem is downstream in M4 capture / Wi-Fi PHY decode / AP-report path, not external-app loading.

## Fix7 — useful diagnostics, static FAIL
Fix7 added the right M4-side ideas:
- 2048 IQ pre-trigger samples using the existing capture buffer
- safer M4 member order with auto-starting threads last
- lower detector threshold (~1.25x floor + margin)
- 1000 ms/channel scan dwell
- runtime `M/C/D` diagnostics

But Fix7 also added a new M0 `HunterTrigger` message handler. Its hardened audit showed `179` shared-core symbols shifted by +4 bytes, so the original Fix7 candidate is archived but must not be hardware-tested.

Archived Fix7 result:
`hackrf/build_results/wifi_aim_full_n260808_fix7/`

## Current candidate — Fix7b STATIC PASS
Fix7b preserves the useful Fix7 M4/pre-trigger changes but removes the new M0 `HunterTrigger` handler. Diagnostic telemetry is transported through the **existing `FSKPacket` path already used by Fix6**, using `WireApReport.flags` bit1 as a diagnostic-only report marker.

This restores the zero-drift property while keeping hardware-readable diagnostics:
- `M` = last channel acknowledged by M4
- `C` = capture attempts during current scan
- `D` = successful Wi-Fi PHY decodes during current scan

Fix7b CI:
- technical PR `#4`
- workflow run `32671853658`
- job `97273779780`
- Actions conclusion: `SUCCESS`
- artifact ID `9501915159`
- artifact digest `sha256:68093816916211b88d4fd9ec56ace728ec14c246aca2a89ba820b4f0d491a5d6`

Hardened `VERIFY.txt`:
- size `23396`
- memory `0x10083FE4`
- entry `0x10084039`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7036`
- shared core symbols `7086`
- **core symbol drift `0`**
- drift references `0`
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- no retained `to_string_mac_address` symbol
- PPMA SHA-256 `730dee07e741cc5a2764dfcf9ffbae52622caf25a75ea6e94a7ffabbf9cb2b49`
- **RESULT `PASS`**

The PPMA header/checksum/SHA were also independently rechecked after downloading the artifact and matched the CI report.

## Exact current engineering frontier
**Fix7b is approved for the next hardware test on stock `n_260808`; it is not yet hardware-proven.**

Installation/test rule:
1. keep stock Mayhem `n_260808`; do not flash firmware;
2. remove/move Fix6 from `/APPS` to avoid duplicate WiFi AIM entries;
3. copy only `WiFiAIM_n260808_fix7b.ppma` to `/APPS`;
4. do not copy `WAIM.bin` separately — it is embedded in the PPMA;
5. launch RX -> WiFi AIM;
6. press SCAN; dwell is ~1 s/channel (~13 s total);
7. record whether `M` follows the channel and the final `Done xAP C# D#` text.

Hardware interpretation:
- app HardFaults -> capture full register screen; static ABI passed, so this would be a new runtime regression
- `M` follows channel + `C=0` -> detector/capture start problem
- `C>0 D=0` -> capture works; next build instruments PHY stages (OFDM LTF/SIGNAL/rate/Viterbi/parser and DSSS sync/SFD/header/parser)
- `D>0` but AP=0 -> investigate real AP report vs diagnostic-only report parsing
- AP>0 -> proceed to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF

## Source layout
Readable current source:
`hackrf/source_expanded/`

Key files:
- `firmware/application/external/wifi_aim/ui_wifi_aim.cpp`
- `firmware/application/external/wifi_aim/ui_wifi_aim.hpp`
- `firmware/baseband/proc_wifi_aim.cpp`
- `firmware/baseband/proc_wifi_aim.hpp`
- `firmware/common/wifi_aim/wifi_aim_phy.cpp`
- `firmware/common/wifi_aim/wifi_aim_phy.hpp`
- `firmware/common/wifi_aim_wire.hpp`

## Implemented functionality
- channels 1-13 scan framework
- Beacon + Probe Response parser
- SSID / hidden SSID
- BSSID display and exact target selection
- LIVE / AVG / PEAK / REF / DELTA REF framework
- decoder OFF/AUTO/ON
- DSSS 1 Mb/s
- OFDM 6/12/24 Mb/s
- M4 `WAIM` processor + M0 UI
- synthetic/host/sanitizer/fuzz work

## Historical build chain
| Build | Result | Meaning |
|---|---|---|
| RF probe n_260808 | hardware PASS | RF path proven |
| original full app | FAIL | loader rejected image |
| Fix1 | hardware FAIL | immediate HardFault |
| Fix4 | static FAIL | stock-core parity failed |
| Fix5 | static FAIL | 58 rebases + 1 unresolved formatter import |
| Fix6 | **static PASS + hardware launch PASS** | zero drift/zero patches; SCAN `0 AP` |
| Fix7 | **static FAIL** | useful pre-trigger/telemetry, but 179 core symbols shifted |
| Fix7b | **static PASS; hardware pending** | same useful diagnostics via existing FSKPacket path, zero core drift |

## Firmware rule
Do not move to matched custom `w_260822` without explicit user permission.
