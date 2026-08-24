# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

Read first, in this order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/FIX8B_HARDWARE_RESULT.md`
5. `hackrf/build_results/wifi_aim_full_n260808_fix8c/VERIFY.txt`
6. `hackrf/HANDOVER_MASTER.md`
7. `hackrf/WIFI_AIM_SPEC.md`
8. inspect `hackrf/source_expanded/`

Do not restart analysis from scratch. The old `K0STUR/GPT` repo is for FORDstecki only.

## Device target
Keep the real PortaPack on stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do not flash matched custom `w_260822` without explicit user permission.

## Critical hardware sequence
Fix7c: `Done 0AP C10 D0` -> capture detector works, decoder rejects all.

Fix8a:
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q 16/64/B 100/100/53`

This proved captured IQ strongly resembles OFDM Wi-Fi.

Fix8b:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 2/2/2/1`
`OF R/N/D/M 0/0/0/0`
`LQ 68 R 8 N 0`
`HIT 16/64/B 22/20/0`
`Q 16/64/B 100/100/55`

Key interpretation:
- 20 captures look strongly 64-sample OFDM-like, but old `find_ltf()` accepts only 2;
- those two pass SIGNAL hard-demod and Viterbi; one passes parity;
- raw RATE parser value 8 is valid 48 Mb/s legacy OFDM, not a random error; current decoder only supports 6/12/24 Mb/s;
- dominant bottleneck is old ideal-template L-LTF synchronization, not loader, capture trigger, Viterbi or gross bit ordering.

## CURRENT CANDIDATE — Fix8c STATIC PASS
Fix8c replaces old ideal-template LTF gating with repetition-based synchronization:

`metric = Q64 * (1 - Q16)`

It retains Fix8b stage diagnostics and renames `LQ` to `SQ` (sync quality). Downstream CFO/equalization/SIGNAL/Viterbi/DATA/MAC logic is unchanged.

Fix8c CI:
- technical PR `#9`
- run `32708337425`
- job `97374177785`
- artifact `9513826923`

Hardened verification:
- size `25576`
- memory `0x1008439C`
- entry `0x100843F1`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `8264`
- shared core symbols `7086`
- core drift `0`
- drift refs `0`
- patches `0`
- same-address refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `4d573419e816af667cf17166cb0aef2dbb64b19fad4700a09d9321265c19b299`
- RESULT `PASS`

## Exact next action
**Hardware-test Fix8c.**

Keep stock `n_260808`; remove/move older WiFi AIM PPMA from `/APPS`; copy only `WiFiAIM_n260808_fix8c.ppma`; do not copy WAIM.bin separately.

Run `RX -> WiFi AIM -> SCAN` through all 13 channels and photograph/report:
- `Done xAP C# D# M#`
- `OF L/H/V/P a/b/c/d`
- `OF R/N/D/M e/f/g/h`
- `SQ xx R yy N zzzz`
- `HIT 16/64/B ...`
- `Q 16/64/B ...`

Primary test question: does `L` rise substantially above Fix8b's `2`, ideally toward OFDM64 hit count around `20`?

Interpretation:
- L rises strongly -> repetition sync fixed the main gate; inspect next failing stage;
- L rises but H/V/P do not -> refine FFT timing/backoff/CFO/channel estimate;
- P rises and R reaches supported 11/10/9 -> follow LENGTH/DATA;
- D>0 M=0 -> inspect descrambler/MAC parser;
- AP>0 -> proceed to SSID/BSSID selection, TARGET, AIM, REF/DELTA.

## Goal
`SCAN -> choose exact SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal is enough; do not claim calibrated dBm.
