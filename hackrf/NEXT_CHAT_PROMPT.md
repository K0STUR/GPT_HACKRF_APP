# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

Read first, in this exact order:
1. `hackrf/README.md`
2. `hackrf/PROJECT_STATUS.md`
3. `hackrf/FIX8E_HARDWARE_RESULT.md`
4. `hackrf/TEST_LOG.md`
5. `hackrf/HANDOVER_MASTER.md`
6. `hackrf/WIFI_AIM_SPEC.md`
7. inspect `hackrf/source_expanded/`
8. compare `main` against branch `wifi-aim-fix8e-prep` before editing anything.

Do not restart analysis from scratch. The old `K0STUR/GPT` repo is for FORDstecki only.

## Device target
Keep the real PortaPack on stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do not flash matched custom `w_260822` without explicit user permission.

## Critical proven sequence
Fix6 solved stock loader/core ABI on real hardware.

Fix7c:
`Done 0AP C10 D0`
-> capture pipeline works.

Fix8a:
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q 16/64/B 100/100/53`
-> captured IQ strongly resembles legacy OFDM.

Fix8b:
`OF L/H/V/P 2/2/2/1`
with ~20 strong 64-sample hits
-> old ideal-template LTF gate was the main bottleneck.

Fix8c:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 24/24/24/15`
`OF R/N/D/M 1/0/0/0`
`SQ 98`
-> repetition-based LTF synchronization fixed the bottleneck. This is hardware-proven. Do not revert it without new evidence.

Fix8d:
- adds full legacy OFDM 6/9/12/18/24/36/48/54, 64-QAM, 2/3 + 3/4 depuncturing and erasure-aware Viterbi;
- 5 real scans;
- **2/5 found `1AP`**;
- typical capture count `C20–C28`.

Representative successful Fix8d scan:
`Done 1AP C28 D1 M13`
`OF L/H/V/P 24/24/24/11`
`OF R/N/D/M 4/2/2/0`

Another Fix8d run reached `OF R/N/D/M 10/3/3/0`.

Important interpretation: OFDM MAC `M` stayed 0 while global AP/D sometimes became 1, so intermittent AP success most likely came through DSSS fallback. Fix8d is the **last functional hardware baseline**.

## CURRENT STATE — Fix8e STATIC PASS, HARDWARE REGRESSION
Fix8e source is on branch **`wifi-aim-fix8e-prep`**, PR `#11`.
Do not blindly merge it to `main`.

Fix8e adds:
- AP display restoration after final telemetry;
- post-DATA OFDM telemetry `P S/F/G/B/I`;
- DSSS attempt/success counters `DS A/S`;
- guard that skips exhaustive DSSS after parity-valid OFDM SIGNAL.

Hardened build:
- run `32723430968`
- job `97419505883`
- artifact `9519205449`
- size `27048`
- M4 offset `8864`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`
- RESULT PASS.

Real hardware Fix8e:
- **4 scans, 0 AP in all 4**;
- phone sees at least 5 nearby Wi-Fi networks.

Representative final screen:
`Done 0AP C1 D0 M13`
`OF L/H/V/P 0/0/0/0`
`OF R/N/D/M 0/0/0/0`
`SQ 0 R 255 N 0`
`HIT 16/64/B 1/1/0`
`Q 16/64/B 96/96/32`
`DS A/S 1/0 FC 255/255`
`P S/F/G/B/I 0/0/0/0/0`

## KEY INTERPRETATION
The active regression is not OFDM LTF sync or RATE support. The full 13-channel scan completed only **1 capture** versus Fix8d's typical ~20–28.

M4 channel acknowledgement still reached 13, so retuning/control proceeds. The one capture attempted DSSS and failed. Leading hypothesis: when a capture does not reach parity-valid OFDM SIGNAL, Fix8e still executes the exhaustive DSSS decoder; that CPU-heavy path may monopolize the M4 and cause later DMA/capture opportunities to be missed. This is a hypothesis, not yet proven.

## EXACT NEXT ACTION
**Do not work deeper on OFDM/MAC until capture throughput is restored.**

1. Diff `main` (Fix8d functional baseline) vs `wifi-aim-fix8e-prep`.
2. Focus first on `M4WifiDecoder::decode()` fallback policy and the CPU cost of `M4LegacyWifiDecoder::decode()`.
3. Preserve all proven parts:
   - stock `n_260808` zero-drift ABI route;
   - 2048-sample pretrigger;
   - separate AP/diagnostic IPC buffers;
   - Fix8c repetition-based LTF sync;
   - Fix8d full legacy OFDM rate support.
4. Keep Fix8e post-DATA telemetry if possible, but bound DSSS work during broad SCAN. Candidate strategies: gate DSSS by DSSS-like evidence, limit phases/offsets per capture, time-slice it, or only run full DSSS on a more selective subset.
5. Build with the same hardened zero-drift audit.
6. Hardware acceptance criterion before deeper PHY work: restore full-scan capture count to roughly **`C20+`** and keep M4 channel acknowledgement reaching 13.
7. After throughput is restored, use `P S/F/G/B/I` to locate the OFDM post-DATA/MAC failure.
8. If AP>0, ensure SSID/BSSID/channel remain visible and then continue TARGET -> AIM -> REF/DELTA.

## What NOT to do
- do not restart from RF basics;
- do not revisit loader/core ABI unless a future hardened audit fails;
- do not revert repetition LTF sync;
- do not remove full legacy OFDM support;
- do not merge Fix8e blindly before understanding `C1`;
- do not flash `w_260822` without explicit permission;
- do not claim calibrated dBm.

## Goal
`SCAN -> choose exact SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only.
