# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

Read first, in this order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/build_results/wifi_aim_full_n260808_fix8a/VERIFY.txt`
5. `hackrf/HANDOVER_MASTER.md`
6. `hackrf/WIFI_AIM_SPEC.md`
7. inspect `hackrf/source_expanded/`

Do not restart analysis from scratch. The old `K0STUR/GPT` repo is for FORDstecki only.

## Device target
Keep the real PortaPack on stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do not flash matched custom `w_260822` without explicit user permission.

## Critical hardware result — Fix7c
Fix7c is hardware-tested and produced exactly:

`Done 0AP C10 D0`

Meaning:
- app launched, no HardFault;
- M4 completed 10 capture attempts;
- zero captures passed the current Wi-Fi PHY decoder;
- AP list stayed empty.

Thus loader/core ABI and capture triggering are no longer the main unknown. The next question is whether raw captures actually contain recognizable Wi-Fi preamble structure.

## CURRENT CANDIDATE — Fix8a STATIC PASS
Fix8a leaves the current decoder unchanged and adds a decoder-independent raw-IQ probe:
- `16`: OFDM STF-like 16-sample repetition;
- `64`: OFDM L-LTF-like 64-sample repetition;
- `B`: Barker-11 DSSS correlation.

Scores are 0-100. Conservative hit thresholds:
- 16 >= 55;
- 64 >= 60;
- B >= 70.

UI shows:
- `HIT 16/64/B a/b/c`
- `Q   16/64/B x/y/z`
- `M4 CH: n`
- final `Done xAP C# D# M#`.

Fix8a CI:
- technical PR `#7`
- run `32699435547`
- job `97347800013`
- artifact ID `9510405146`
- artifact/workflow names may still contain `fix7b`; compiled source is Fix8a.

Hardened verification:
- size `24800`
- memory `0x10084324`
- entry `0x10084379`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7608`
- shared core symbols `7086`
- core drift `0`
- drift refs `0`
- patches `0`
- same-address core refs `79`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `3fdfd70530a2217888c93c9c11259ecac02ca54371b4998391d31dc006224e9d`
- RESULT `PASS`

Independent artifact verification reproduced the SHA and checksum and confirmed Fix8a UI strings inside the PPMA.

## Exact next action
**Hardware-test Fix8a.**

Keep stock `n_260808`. Remove/move older WiFi AIM PPMA files from `/APPS`, copy only the Fix8a `.ppma`, and do not copy `WAIM.bin` separately.

Run `RX -> WiFi AIM -> SCAN` through all 13 channels. Photograph/report exactly:
- `Done xAP C# D# M#`
- `HIT 16/64/B a/b/c`
- `Q   16/64/B x/y/z`.

Interpretation:
- high 16/64 scores or hits + D0 -> captured IQ looks like OFDM Wi-Fi; fix/instrument OFDM decoder next;
- high Barker score/hits + D0 -> captured IQ looks like DSSS Wi-Fi; fix/instrument DSSS decoder next;
- all three low -> captures are probably non-Wi-Fi or preamble alignment is still wrong; improve detector/pretrigger/capture selection before decoder internals;
- D>0 AP=0 -> report/parser path;
- AP>0 -> proceed to SSID/BSSID selection, TARGET, AIM, REF/DELTA.

## Goal
`SCAN -> choose exact SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal is enough; do not claim calibrated dBm.
