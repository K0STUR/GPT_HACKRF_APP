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
7. `build_results/wifi_aim_full_n260808_fix7c/`

## Current one-line status
**Fix6 is hardware-launch proven on stock Mayhem `n_260808` but SCAN returned `0 AP`. Fix7 found useful capture changes but failed ABI. Fix7b restored zero drift. Fix7c further hardened the pointer-based FSK IPC by separating AP and diagnostic backing buffers and has passed the full hardened zero-drift audit. The exact next step is a real hardware SCAN test of Fix7c.**

## Current candidate — Fix7c
Device target remains stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Fix7c keeps:
- 2048 IQ samples of pre-trigger history;
- safer M4 initialization order;
- lower capture threshold;
- 1000 ms/channel scan dwell;
- M/C/D runtime telemetry over the existing `FSKPacket` handler;
- no added M0 `HunterTrigger` handler.

Fix7c additionally uses separate M4 `FskPacketData` backing stores for real AP reports and telemetry. Diagnostic-only reports use **flags bit7 / `0x80`**. Failed-capture telemetry is throttled, while exact counters are sent on channel/decoder transitions.

### Static verification
- CI run `32673931447`
- job `97278879220`
- artifact ID `9502420139`
- source commit `f4eec354a321b699d2ff1bf8254ddca6ab80bf7a`
- size `23452`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7076`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`
- **RESULT `PASS`**

Header/checksum/SHA were independently recalculated from the downloaded artifact and matched CI.

## Next test
Do not flash firmware. Remove/move older WiFi AIM PPMA files from SD `/APPS` and copy **only** `WiFiAIM_n260808_fix7c.ppma` there. `WAIM.bin` is embedded.

Launch `RX -> WiFi AIM`, press SCAN and observe:
- `M` — last channel acknowledged by M4; should follow the current channel;
- `C` — capture attempts;
- `D` — successful Wi-Fi PHY decodes.

After the ~13 s scan report the exact `Done xAP C# D#` text and whether `M` tracked channels 1-13.

Interpretation:
- HardFault -> photograph register screen;
- M fails -> control/telemetry path;
- M works + C=0 -> detector/capture trigger;
- C>0 D=0 -> instrument PHY internals next;
- D>0 AP=0 -> report/parser path;
- AP>0 -> continue to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

## Goal
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal strength is sufficient; do not claim calibrated dBm.
