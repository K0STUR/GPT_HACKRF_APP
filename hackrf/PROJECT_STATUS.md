# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**.
The old `K0STUR/GPT` repository is reserved for `FORDstecki` only.

## Device target
- PortaPack Mayhem: stock `n_260808`
- upstream tag: `nightly-tag-2026-08-08`
- upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- do not flash matched custom `w_260822` without explicit permission.

## Proven baseline
Fix6 solved loader/core ABI on real hardware. Fix7c then proved the M4 capture detector is firing and full captures are completed.

### Fix7c real hardware result
Exact final screen:

`Done 0AP C10 D0`

Meaning:
- application launches normally;
- no HardFault;
- M4 completed `10` capture attempts;
- existing Wi-Fi PHY decoder accepted `0` captures;
- AP list remains empty.

Therefore loader/ABI is solved and `C=0` detector failure is ruled out for this test. The active question is now whether those captures contain recognizable Wi-Fi preamble structure or merely unrelated/poorly aligned RF energy.

## CURRENT CANDIDATE — Fix8a STATIC PASS, READY FOR HARDWARE TEST
Fix8a deliberately does **not** alter the existing Wi-Fi decoder. It adds an independent raw-IQ capture probe so the next hardware run tells us what kind of signal was actually captured.

Probe metrics:
- `16`: normalized complex repetition at lag 16, looking for legacy OFDM STF-like periodicity;
- `64`: normalized complex repetition at lag 64, looking for repeated legacy OFDM L-LTF-like structure;
- `B`: Barker-11 despread correlation, looking for DSSS-like structure.

Scores are shown 0–100. Conservative hit thresholds are:
- OFDM16 >= `55`;
- OFDM64 >= `60`;
- Barker >= `70`.

UI after/during SCAN shows:
- `HIT 16/64/B a/b/c` — number of captures crossing each threshold;
- `Q   16/64/B x/y/z` — best score seen during the scan;
- `M4 CH: n` — last M4 channel acknowledgement;
- final status `Done xAP C# D# M#`.

Fix8a telemetry reuses otherwise-unused BSSID bytes only on diagnostic-only packets (`flags bit7 = 0x80`, marker `ssid_len=0xF8`) and does not add any new M0 message-handler type or alter stock-core message ABI.

### Fix8a CI
Technical PR: `#7`

Run:
`32699435547`

Job:
`97347800013`

Artifact ID:
`9510405146`

The audit harness and artifact filename still contain `fix7b` in their historical names, but the compiled source is current Fix8a from `main`; the downloaded PPMA contains `HIT 16/64/B` and `Q   16/64/B` strings.

### Hardened Fix8a verification
- size `24800`
- memory `0x10084324`
- entry `0x10084379`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7608`
- shared core symbols `7086`
- **core symbol drift `0`**
- drift references `0`
- patch count `0`
- same-address core refs `79`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- PPMA SHA-256 `3fdfd70530a2217888c93c9c11259ecac02ca54371b4998391d31dc006224e9d`
- **RESULT `PASS`**

Independent local verification reproduced size, checksum zero and SHA-256 exactly.

## Exact next action — REAL HARDWARE TEST Fix8a
1. keep stock Mayhem `n_260808`; do not flash firmware;
2. remove/move previous WiFi AIM PPMA from `/APPS` so only one entry exists;
3. copy only the Fix8a `.ppma` into `/APPS`;
4. do not copy `WAIM.bin` separately;
5. launch `RX -> WiFi AIM`;
6. press `SCAN` and let all 13 channels finish;
7. photograph the final screen or report exactly:
   - `Done xAP C# D# M#`
   - `HIT 16/64/B a/b/c`
   - `Q   16/64/B x/y/z`.

Interpretation:
- OFDM16/64 high or hit counts >0 while `D=0` -> captures look like OFDM Wi-Fi; instrument/fix OFDM decoder next;
- Barker high or hit count >0 while `D=0` -> captures look like DSSS Wi-Fi; instrument/fix DSSS decoder next;
- all three scores low -> captures likely are non-Wi-Fi energy or useful preamble still lies outside/alignment of capture; improve detector/pretrigger/capture selection before decoder internals;
- `D>0` but AP=0 -> report/parser path;
- AP>0 -> continue directly to SSID/BSSID TARGET/AIM/REF/DELTA.

## Source layout
Readable current source:
`hackrf/source_expanded/`

Key files:
- `firmware/application/external/wifi_aim/ui_wifi_aim.cpp`
- `firmware/application/external/wifi_aim/ui_wifi_aim.hpp`
- `firmware/baseband/proc_wifi_aim.cpp`
- `firmware/baseband/proc_wifi_aim.hpp`
- `firmware/common/wifi_aim/wifi_aim_capture_probe.hpp`
- `firmware/common/wifi_aim/wifi_aim_phy.cpp`
- `firmware/common/wifi_aim/wifi_aim_phy.hpp`
- `firmware/common/wifi_aim_wire.hpp`

## End goal
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Channels 1-13. Beacon + Probe Response parsing. Hidden SSID support. Exact BSSID targeting. Relative signal is sufficient; do not claim calibrated dBm.
