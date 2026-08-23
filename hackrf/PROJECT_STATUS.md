# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-23

## Current device firmware
- Device Mayhem currently installed: `n_260808`
- Upstream tag: `nightly-tag-2026-08-08`
- Upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- Preserve stock firmware unless the user explicitly agrees otherwise.

## Current frontier — Fix7 capture/PHY diagnostics
Fix6 solved the stock-firmware loader/core-ABI blocker and has now been tested on real hardware.

### Fix6 real-hardware result
Artifact:
`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

Static verification:
- workflow run `32631639944` SUCCESS
- size `22720`
- version `0x86B64C1D`
- M4 tag `WAIM`
- shared core symbols compared `7118`
- core symbol drift `0`
- ABI rebase patches `0`
- same-address core references `81`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- RESULT `PASS`

Real PortaPack observation from the user:
- WiFi AIM opens normally on stock `n_260808`;
- no HardFault;
- red RF/RSSI bar responds to the antenna;
- `SCAN` completes but reports `0 AP`.

Therefore **do not return to Fix5/loader debugging unless a future zero-drift audit fails**. The current problem is the M4 capture / Wi-Fi PHY decode / report path.

## Why Fix7 exists
Expanded source inspection after the zero-AP hardware test found two concrete issues in Fix6:

1. **No IQ pre-trigger history.**
   The energy detector began saving IQ only from the DMA block that crossed threshold. A Wi-Fi preamble or OFDM L-LTF can already have started in the preceding block, leaving the decoder with a packet whose synchronization prefix is missing.

2. **Unsafe M4 processor initialization order.**
   `BasebandThread` auto-started before the rest of `WifiAimProcessor` state/buffers were initialized. Upstream Mayhem explicitly says auto-starting processor threads should be declared last. Fix7 moves `BasebandThread` and `RSSIThread` to the end.

Fix7 changes:
- retain ~2048 IQ samples of pre-trigger history using the existing capture buffer (no extra M4 capture RAM);
- prepend that history when an energy trigger fires;
- lower the trigger from roughly `1.5x floor + 80` to `1.25x floor + 32`;
- scan dwell increased from 450 ms/channel to 1000 ms/channel;
- runtime diagnostics sent through stock `HunterTriggerMessage` without changing Mayhem ABI;
- UI displays:
  - `C` = M4 capture attempts,
  - `D` = successful Wi-Fi PHY decodes,
  - `M` = last channel configuration acknowledged by M4.

Interpretation on hardware:
- `M` tracking scan channel => M0 -> M4 control path works;
- `C = 0` => detector/threshold still not triggering;
- `C > 0, D = 0` => IQ capture works but PHY rejects candidates;
- `D > 0` => decoder has valid Wi-Fi frames; AP reports should follow.

## Current Fix7 CI
Workflow:
`.github/workflows/build_wifi_aim_full_n260808_fix7.yml`

PR-triggered run:
`32666957127`

Job:
`97261737292`

At last checkpoint:
- source preparation PASS
- local MAC dependency removal PASS
- exact stock checkout PASS
- official toolchain build PASS
- untouched stock build / symbol-map generation IN PROGRESS
- modified Fix7 build pending
- hardened zero-drift ABI audit pending

Do not hand Fix7 to hardware until the final VERIFY shows the same stock compatibility guarantees as Fix6.

## Source layout
Readable source is now expanded under:
`hackrf/source_expanded/`

Key files:
- `firmware/application/external/wifi_aim/ui_wifi_aim.cpp`
- `firmware/application/external/wifi_aim/ui_wifi_aim.hpp`
- `firmware/baseband/proc_wifi_aim.cpp`
- `firmware/baseband/proc_wifi_aim.hpp`
- `firmware/common/wifi_aim/wifi_aim_phy.cpp`
- `firmware/common/wifi_aim/wifi_aim_phy.hpp`
- `firmware/common/wifi_aim_wire.hpp`

## Implemented WiFi AIM functionality
- channels 1–13 scan framework;
- Beacon + Probe Response parser;
- SSID / hidden SSID handling;
- BSSID display and exact-BSSID target selection;
- LIVE / AVG / PEAK / REF / DELTA REF framework;
- decoder OFF/AUTO/ON;
- DSSS 1 Mb/s path;
- legacy OFDM 6/12/24 Mb/s paths;
- M4 `WAIM` processor and M0 UI;
- previous synthetic/host/sanitizer/fuzz work.

## RF and installation facts already proven
- simplified n_260808 RF probe works on real hardware;
- upper HackRF SMA `ANTENNA` is the RF input used for this project;
- removing/changing antenna changes received RF activity;
- Mayhem loads external apps from `/APPS`;
- `WAIM.bin` is embedded inside the generated `.ppma`, so it is not copied separately to SD;
- WiFi AIM metadata places the app in RX.

## Historical build chain
| Build | Result | Meaning |
|---|---|---|
| `wifi_aim_probe_n260808` | hardware PASS | RF path proven |
| original full app | FAIL | loader rejected image |
| Fix1 | hardware FAIL | immediate HardFault |
| Fix4 | static FAIL | stock-core parity failed |
| Fix5 | static FAIL | 58 rebases + 1 unresolved MAC formatter import |
| Fix6 | **static PASS + hardware launch PASS** | zero drift/zero patches; SCAN still 0 AP |
| **Fix7** | **building** | pre-trigger + safe M4 init + CAP/DEC/M diagnostics |

## Exact next action
Finish run `32666957127` and inspect `VERIFY.txt`.

If static PASS, test `WiFiAIM_n260808_fix7.ppma` on the same stock `n_260808` device and record the final SCAN status, especially `C`, `D`, and `M`.

If `C>0 D=0`, instrument individual PHY stages next (OFDM LTF/SIGNAL/rate/Viterbi/parser and DSSS sync/SFD/header/parser) instead of changing ABI or RF UI code.
