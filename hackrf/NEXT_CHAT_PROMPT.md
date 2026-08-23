# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

First read, in this exact order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/HANDOVER_MASTER.md`
5. `hackrf/WIFI_AIM_SPEC.md`
6. inspect `hackrf/source_expanded/`

Do not restart the project from scratch. The old repository `K0STUR/GPT` is reserved for FORDstecki only; all HackRF work belongs in `K0STUR/GPT_HACKRF_APP`.

## Current device target
Real PortaPack firmware:
- stock Mayhem `n_260808`
- upstream tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Keep stock firmware. Do not move to matched custom `w_260822` without explicit permission.

## Hardware-proven baseline — Fix6
Fix6 passed the hardened zero-drift stock-core ABI audit and was tested on the real device.

Observed:
- application opens normally,
- no HardFault,
- red RF/RSSI bar reacts to antenna,
- SCAN completes but reports `0 AP`.

Fix6 SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Therefore the loader/core-ABI problem is solved. Remaining failure is downstream in M4 capture / Wi-Fi PHY decode / reporting.

## Fix7 lesson
Fix7 introduced the correct M4-side improvements (pre-trigger IQ, safer thread initialization, lower detector threshold, longer channel dwell and telemetry) but its extra M0 `HunterTrigger` message handler shifted 179 shared core symbols. Fix7 is archived and must not be hardware-tested.

## Current candidate — Fix7b STATIC PASS
Fix7b keeps the useful Fix7 M4 changes but removes the new M0 HunterTrigger handler. `M/C/D` diagnostics are transported through the **existing Fix6 `FSKPacket` path**. `WireApReport.flags` bit1 denotes a diagnostic-only packet.

Fix7b CI:
- PR `#4`
- run `32671853658`
- job `97273779780`
- Actions `SUCCESS`
- artifact ID `9501915159`

Hardened audit:
- size `23396`
- memory `0x10083FE4`
- entry `0x10084039`
- M4 offset `7036`
- shared core symbols `7086`
- **core_symbol_drift_count `0`**
- drift references `0`
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `730dee07e741cc5a2764dfcf9ffbae52622caf25a75ea6e94a7ffabbf9cb2b49`
- **RESULT `PASS`**

The artifact was downloaded and independently rechecked; header/version/tag/M4 offset/Thumb entry/checksum/SHA all match CI.

## Exact next action
Hardware-test `WiFiAIM_n260808_fix7b.ppma` on stock `n_260808`.

Installation:
- do NOT flash firmware;
- remove/move Fix6 from `/APPS` so there is only one WiFi AIM entry;
- copy only Fix7b `.ppma` to `/APPS`;
- do not copy `WAIM.bin` separately.

During SCAN observe:
- `M` = last channel acknowledged by M4,
- `C` = capture attempts during the scan,
- `D` = successful Wi-Fi PHY decodes during the scan.

The scan lasts about 1 second/channel (~13 seconds total). Record the exact final text, e.g. `Done 0AP C123 D0`, and whether `M` follows the channel while scanning.

Interpretation:
- HardFault -> capture full register screen; this is a runtime regression despite static ABI PASS.
- `M` follows + `C=0` -> detector/capture-start issue.
- `C>0 D=0` -> capture works; next build instruments PHY stages: OFDM LTF -> SIGNAL -> rate -> Viterbi -> MAC parser and DSSS Barker/sync -> SFD -> PLCP -> MAC parser.
- `D>0` but AP=0 -> investigate AP report/parser path.
- AP>0 -> continue to exact SSID/BSSID TARGET -> AIM -> REF/DELTA REF.

## End goal
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`

Passive receive only, channels 1-13, Beacon + Probe Response parsing, hidden SSID handling, exact BSSID targeting, decoder OFF/AUTO/ON, and LIVE/AVG/PEAK/REF/DELTA REF. Relative signal is enough; do not claim calibrated dBm.
