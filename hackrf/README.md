# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**. The old `K0STUR/GPT` repo is reserved for FORDstecki.

## Read first
1. `PROJECT_STATUS.md`
2. `TEST_LOG.md`
3. `NEXT_CHAT_PROMPT.md`
4. `HANDOVER_MASTER.md`
5. `WIFI_AIM_SPEC.md`
6. `source_expanded/`
7. `build_results/wifi_aim_full_n260808_fix8a/`

## Current one-line status
**Fix7c is hardware-tested on stock `n_260808` and returned `Done 0AP C10 D0`: M4 capture is working, but the current Wi-Fi PHY decoder accepts none of the captured bursts. Fix8a keeps the decoder unchanged and adds an independent raw-IQ preamble probe for OFDM 16-sample repetition, OFDM 64-sample repetition and Barker-11 DSSS. Fix8a passed the full hardened zero-drift audit and is the current hardware-test candidate.**

## Hardware result that drives the next step
Fix7c real device:

`Done 0AP C10 D0`

This rules out the earlier `C=0` detector failure. Ten capture attempts completed, zero full decodes succeeded.

## Current candidate — Fix8a
Device target remains stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Fix8a retains Fix7c's:
- 2048 IQ pretrigger;
- safer M4 initialization order;
- lower capture threshold;
- 1000 ms/channel dwell;
- separate AP/diagnostic FSK packet backing stores;
- M/C/D telemetry over existing `FSKPacket` path;
- no new M0 HunterTrigger handler.

Fix8a adds a decoder-independent raw capture probe. UI displays:
- `HIT 16/64/B a/b/c`
- `Q   16/64/B x/y/z`
- `M4 CH: n`
- final `Done xAP C# D# M#`.

Metric meaning:
- `16`: OFDM STF-like repetition, hit threshold 55;
- `64`: OFDM L-LTF-like repetition, hit threshold 60;
- `B`: Barker-11 DSSS-like correlation, hit threshold 70;
- `Q`: best score 0-100 during scan;
- `HIT`: number of captures crossing threshold.

### Static verification
- CI run `32699435547`
- job `97347800013`
- artifact ID `9510405146`
- size `24800`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7608`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `3fdfd70530a2217888c93c9c11259ecac02ca54371b4998391d31dc006224e9d`
- **RESULT `PASS`**

Downloaded artifact was independently verified: size, 32-bit word checksum and SHA match, and Fix8a UI strings are present in the PPMA.

## Next test
Do not flash firmware. Remove/move older WiFi AIM PPMA files from SD `/APPS` and copy **only** the Fix8a `.ppma` there. `WAIM.bin` is embedded.

Launch `RX -> WiFi AIM`, press SCAN and let all 13 channels complete. Photograph/report:
- `Done xAP C# D# M#`
- `HIT 16/64/B a/b/c`
- `Q   16/64/B x/y/z`.

Interpretation:
- high 16/64 scores or hits + D0 -> captured signal looks OFDM-like; debug OFDM PHY next;
- high Barker score/hits + D0 -> captured signal looks DSSS-like; debug DSSS PHY next;
- all scores low -> captures likely are non-Wi-Fi or useful preamble alignment is still wrong; improve capture selection/pretrigger before decoder internals;
- D>0 AP=0 -> report/parser path;
- AP>0 -> proceed to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

## Goal
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal strength is sufficient; do not claim calibrated dBm.
