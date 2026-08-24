# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

Read first, in this order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/TEST_LOG.md`
4. `hackrf/build_results/wifi_aim_full_n260808_fix7c/VERIFY.txt`
5. `hackrf/HANDOVER_MASTER.md`
6. `hackrf/WIFI_AIM_SPEC.md`
7. inspect `hackrf/source_expanded/`

Do not restart analysis from scratch. The old `K0STUR/GPT` repo is for FORDstecki only.

## Device target
Keep the real PortaPack on stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do not flash matched custom `w_260822` without explicit user permission.

## Proven history
Fix6 is hardware-launch proven:
- app opens on stock `n_260808`;
- no HardFault;
- RF/RSSI responds to antenna;
- SCAN returned `0 AP`.

Therefore stock-loader/core ABI and basic RF reception are proven.

Fix7 added useful pretrigger/M4 diagnostic changes but failed hardened ABI because a new M0 HunterTrigger handler shifted 179 core symbols.

Fix7b removed that M0 handler, moved diagnostics onto the existing FSKPacket path, and restored zero drift.

## CURRENT CANDIDATE — Fix7c STATIC PASS
Fix7c additionally hardens the pointer-based FSK IPC:
- separate M4 FskPacketData backing buffers for AP and telemetry;
- diagnostic-only marker = flags bit7 / `0x80`;
- failed-capture telemetry throttled to every 16 attempts;
- exact counters/channel ACK on state/channel transitions;
- 2048-sample IQ pretrigger, safer M4 thread order, lower threshold and 1 s/channel dwell retained.

Fix7c CI:
- technical PR `#5`
- run `32673931447`
- job `97278879220`
- artifact ID `9502420139`
- source commit `f4eec354a321b699d2ff1bf8254ddca6ab80bf7a`

Hardened verification:
- size `23452`
- memory `0x10083FF4`
- entry `0x10084049`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7076`
- shared core symbols `7086`
- core drift `0`
- drift refs `0`
- patches `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`
- RESULT `PASS`

The downloaded PPMA was independently checked and its header/checksum/SHA match CI.

## Exact next action
**Hardware-test Fix7c. Do not do more ABI work first.**

Install only `WiFiAIM_n260808_fix7c.ppma` in SD `/APPS`; remove/move older WiFi AIM PPMA files to avoid duplicate menu entries. Do not copy WAIM.bin separately.

Run `RX -> WiFi AIM -> SCAN`. Scan lasts about 13 s.

Observe while scanning:
- `M` = last channel acknowledged by M4; should follow channels 1-13;
- `C` = capture attempts;
- `D` = successful Wi-Fi PHY decodes.

Record exact final text: `Done xAP C# D#` and whether M tracked the channel.

Interpretation:
- HardFault -> capture full register screen.
- M fails -> M0->M4 control / telemetry problem.
- M works and C=0 -> detector/capture trigger issue.
- C>0 D=0 -> next build instruments PHY internals (OFDM LTF/SIGNAL/rate/Viterbi/parser and DSSS sync/SFD/PLCP/parser).
- D>0 AP=0 -> investigate report/parser path.
- AP>0 -> continue directly to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

## Goal
`SCAN -> choose exact SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal is enough; do not claim calibrated dBm.
