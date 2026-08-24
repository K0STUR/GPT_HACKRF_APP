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
Fix6 solved the loader/core ABI problem on real stock hardware. Fix7c proved M4 capture triggering and full capture completion. Fix8a proved the captured IQ strongly resembles OFDM Wi-Fi. Fix8b localized the main failure to L-LTF synchronization.

### Fix8a real hardware result
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q   16/64/B 100/100/53`

Interpretation: 26 captures; 21 looked strongly OFDM-like at both 16- and 64-sample repetition; Barker/DSSS did not dominate; decoder still accepted 0.

### Fix8b real hardware result
`Done 0AP C26 D0 M13`
`OF L/H/V/P 2/2/2/1`
`OF R/N/D/M 0/0/0/0`
`LQ 68 R 8 N 0`
`HIT 16/64/B 22/20/0`
`Q   16/64/B 100/100/55`
`M4 CH: 13`

Interpretation:
- 20 captures showed strong 64-sample OFDM-like repetition, but only 2 passed the old ideal-template `find_ltf()`;
- both accepted captures passed SIGNAL hard demod and SIGNAL Viterbi;
- one passed SIGNAL parity;
- raw RATE parser value `8` is a valid legacy OFDM code corresponding to 48 Mb/s, which the current decoder intentionally does not support (it supports 6/12/24 Mb/s rate-1/2 modes only);
- therefore Viterbi and SIGNAL bit ordering can work on real RF; the dominant bottleneck is old L-LTF timing/gating.

## CURRENT CANDIDATE — Fix8c STATIC PASS, READY FOR HARDWARE TEST
Fix8c replaces the old hard ideal-template L-LTF gate with repetition-based synchronization:

`metric = Q64 * (1 - Q16)`

Rationale:
- L-LTF contains two repeated 64-sample long training symbols;
- preceding STF is strongly 16-sample periodic;
- multipath can severely reduce correlation with an ideal time-domain LTF while preserving repetition between the two received LTF copies;
- selecting high Q64 and simultaneously low Q16 is therefore more channel-invariant than the old matched-filter threshold.

Fix8c keeps the downstream path unchanged:
- CFO estimate;
- channel estimate/equalization;
- SIGNAL demod;
- deinterleave;
- Viterbi;
- RATE/LENGTH parsing;
- DATA decode;
- MAC Beacon/Probe parser.

Fix8b stage telemetry remains. `LQ` was renamed to `SQ` and now shows Fix8c repetition-sync quality.

### Fix8c CI
Technical PR: `#9`
Run: `32708337425`
Job: `97374177785`
Artifact ID: `9513826923`

Workflow/artifact historical names still contain `fix7b`, but the compiled PPMA was independently checked to contain Fix8c `SQ` and OFDM stage strings.

### Hardened Fix8c verification
- size `25576`
- memory `0x1008439C`
- entry `0x100843F1`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `8264`
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
- SHA-256 `4d573419e816af667cf17166cb0aef2dbb64b19fad4700a09d9321265c19b299`
- **RESULT `PASS`**

Independent artifact verification reproduced size, checksum zero and SHA-256 exactly.

## Exact next action — REAL HARDWARE TEST Fix8c
1. keep stock Mayhem `n_260808`; do not flash firmware;
2. remove/move older WiFi AIM PPMA files from `/APPS`;
3. copy only `WiFiAIM_n260808_fix8c.ppma` into `/APPS`;
4. do not copy `WAIM.bin` separately;
5. launch `RX -> WiFi AIM`;
6. press `SCAN` and let all 13 channels complete;
7. photograph the full final screen.

Report especially:
- `Done xAP C# D# M#`
- `OF L/H/V/P a/b/c/d`
- `OF R/N/D/M e/f/g/h`
- `SQ xx R yy N zzzz`
- `HIT 16/64/B ...`
- `Q 16/64/B ...`

Primary success criterion for Fix8c:
- `L` should rise substantially above the Fix8b value `2`, ideally toward the observed OFDM64 hit count around `20`.

Then:
- if `L` rises but H/V/P stay low -> refine timing/backoff/CFO/channel estimate;
- if P rises and R reaches supported `11/10/9` -> proceed through LENGTH/DATA;
- if D rises but M remains 0 -> inspect descrambler/MAC prefix parsing;
- if AP>0 -> proceed immediately to SSID/BSSID selection, TARGET, AIM, REF/DELTA.

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
