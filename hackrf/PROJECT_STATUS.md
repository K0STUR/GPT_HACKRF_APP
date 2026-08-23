# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-23

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**.
The old `K0STUR/GPT` repository is now reserved for `FORDstecki` only.

## Current device firmware
- Device Mayhem: stock `n_260808`
- Upstream tag: `nightly-tag-2026-08-08`
- Upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- Preserve stock firmware unless the user explicitly agrees otherwise.

## Proven baseline — Fix6
Fix6 solved the stock-firmware loader/core-ABI blocker and was tested on real hardware.

Artifact:
`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Static audit:
- workflow run `32631639944` SUCCESS
- size `22720`
- version `0x86B64C1D`
- M4 tag `WAIM`
- shared core symbols `7118`
- core symbol drift `0`
- ABI rebase patches `0`
- same-address core refs `81`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- RESULT `PASS`

Real hardware:
- app opens normally on stock `n_260808`
- no HardFault
- red RF/RSSI bar responds to antenna
- SCAN completes but reports `0 AP`

Therefore the current functional problem is downstream in the M4 capture / Wi-Fi PHY decode / AP-report path, not external-app loading.

## Fix7 rationale and source changes
Source inspection after Fix6's `0 AP` result identified two concrete weaknesses:

1. **Missing IQ pre-trigger history.** Fix6 started saving IQ only in the DMA block that crossed the energy threshold; a Wi-Fi preamble/L-LTF could already have started in the previous block.
2. **Unsafe M4 member initialization order.** Upstream Mayhem warns that auto-starting `BasebandThread` should be declared last. Fix7 moves `BasebandThread` and `RSSIThread` after processor state/buffers.

Fix7 source under `hackrf/source_expanded/` therefore adds:
- 2048 IQ samples of pre-trigger history using the existing capture buffer
- safer M4 thread member order
- lower detector threshold (~1.25x floor + margin)
- scan dwell 1000 ms/channel
- `M/C/D` diagnostics via the existing stock `HunterTriggerMessage` ABI

Diagnostics are intended to mean:
- `M` = last channel acknowledged by M4
- `C` = capture attempts
- `D` = successful Wi-Fi PHY decodes

## Final Fix7 CI result — STATIC FAIL, DO NOT HARDWARE TEST
Workflow:
`.github/workflows/build_wifi_aim_full_n260808_fix7.yml`

Run:
`32666957127`

Job:
`97261737292`

The GitHub Actions job completed all build/audit/publish steps, but **job success is not the same as audit PASS**. The generated `VERIFY.txt` records:
- size `23508`
- memory `0x10083FEC`
- entry `0x10084041`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7140`
- shared core symbols `7118`
- **core symbol drift `179`**
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- PPMA SHA-256 `cb1cab400ea934f3d0bf2d3116d624c3310375a7f7342a2c00b3ec4a4d71248f`
- **RESULT `FAIL`**

The first observed shared-core shift is +4 bytes around stock address `0x000A3C68`; 179 later core data/vtable/table symbols are correspondingly shifted.

Complete original CI output is archived at:
`hackrf/build_results/wifi_aim_full_n260808_fix7/`

Contents include:
- original Actions artifact ZIP
- `BUILD.log`
- `WiFiAIM_n260808_fix7.ppma`
- `.ppma.b64`
- `WAIM.bin`
- `VERIFY.txt`
- `STATUS.txt`
- hashes

**Do not copy the Fix7 `.ppma` to the device.**

## Exact current engineering frontier
Preserve the useful Fix7 M4 pre-trigger/init/diagnostic changes while restoring Fix6's exact zero-drift stock-core ABI property.

Next work:
1. identify the first Fix7-added M0 object/data/rodata/message-handler registration that changes the monolithic core layout;
2. ensure every such Fix7 M0 contribution is isolated into the external-app section rather than stock core sections;
3. rebuild against exact stock `n_260808` twice as before;
4. require:
   - `core_symbol_drift_count=0`
   - `patch_count=0`
   - `ambiguous_count=0`
   - `unresolved_count=0`
   - checksum `0`
   - `RESULT=PASS`
5. only then hardware-test and use `M/C/D` to diagnose SCAN `0 AP`.

If the future zero-drift candidate launches and shows:
- `M` follows channel + `C=0`: detector/capture start problem
- `C>0 D=0`: instrument OFDM LTF/SIGNAL/rate/Viterbi/parser and DSSS sync/SFD/header/parser
- `D>0` but AP=0: investigate WireApReport / M0 report parser
- AP>0: continue to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF

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
| Fix7 | **static FAIL** | useful capture diagnostics, but 179 shared-core symbols shifted |

## Firmware rule
Do not move to matched custom `w_260822` without explicit user permission.
