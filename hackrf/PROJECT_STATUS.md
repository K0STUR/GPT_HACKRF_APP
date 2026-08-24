# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**.
The old `K0STUR/GPT` repository is reserved for FORDstecki only.

## Device target
- PortaPack Mayhem stock `n_260808`
- upstream tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- do not flash matched custom `w_260822` without explicit permission.

## Current frontier
The loader/core ABI problem is solved. RF receive works. M4 capture works. Repetition-based OFDM LTF synchronization works on real hardware. Full legacy OFDM RATE support materially improved progression through the PHY. The active issue is now a **Fix8e capture-throughput regression**, not a loader or synchronization problem.

## Proven sequence
### Fix7c — capture path proven
`Done 0AP C10 D0`

### Fix8a — captured IQ looks like OFDM
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q 16/64/B 100/100/53`

### Fix8b — old LTF gate localized
`OF L/H/V/P 2/2/2/1`
`HIT 16/64/B 22/20/0`

### Fix8c — repetition LTF sync fixed main gate
Representative hardware result:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 24/24/24/15`
`OF R/N/D/M 1/0/0/0`
`SQ 98`

Conclusion: new LTF sync is hardware-proven and should not be reverted without new evidence.

### Fix8d — full legacy OFDM, first intermittent AP discovery
Fix8d added all legacy OFDM rates 6/9/12/18/24/36/48/54 Mb/s, 64-QAM, depuncturing 2/3 and 3/4, and erasure-aware Viterbi.

Real hardware: 5 scans, **2/5 found `1AP`**. Typical capture counts were about `C20–C28`.

Representative successful scan:
`Done 1AP C28 D1 M13`
`OF L/H/V/P 24/24/24/11`
`OF R/N/D/M 4/2/2/0`

Another Fix8d scan reached:
`OF R/N/D/M 10/3/3/0`

Interpretation:
- full RATE support works on real RF;
- OFDM reaches DATA Viterbi;
- OFDM MAC `M` remained 0;
- global AP/D could still become 1, strongly suggesting the intermittent AP success came from DSSS fallback rather than OFDM MAC parsing.

## Fix8e — STATIC PASS, HARDWARE REGRESSION
Fix8e additions:
- preserve AP/SSID/BSSID display after final telemetry;
- post-DATA OFDM telemetry `P S/F/G/B/I`;
- DSSS attempt/success counters;
- skip expensive DSSS fallback only after parity-valid OFDM SIGNAL.

Technical branch: `wifi-aim-fix8e-prep`
Technical PR: `#11`
Hardened run: `32723430968`
Job: `97419505883`
Artifact ID: `9519205449`

Static verification:
- size `27048`
- M4 offset `8864`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- SHA-256 `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`
- RESULT `PASS`

Real hardware: **4 scans, 0 AP in all 4**.

Representative screen:
`Done 0AP C1 D0 M13`
`OF L/H/V/P 0/0/0/0`
`OF R/N/D/M 0/0/0/0`
`SQ 0 R 255 N 0`
`HIT 16/64/B 1/1/0`
`Q 16/64/B 96/96/32`
`DS A/S 1/0 FC 255/255`
`P S/F/G/B/I 0/0/0/0/0`

The phone sees at least 5 Wi-Fi networks in the same location.

### Fix8e interpretation
The striking regression is `C1` for a full 13-channel scan versus ~`C20–C28` on Fix8d. M4 channel acknowledgement still reaches 13, so control/retune progresses. The one capture triggered DSSS once and failed. The most likely current hypothesis is **M4 processing starvation caused by the exhaustive DSSS fallback on a capture that does not reach OFDM parity**. That can consume enough CPU to miss later DMA/capture opportunities. This hypothesis is plausible but not yet proven.

## Repository state — important for handover
- `main` = **Fix8d functional source baseline** plus current documentation.
- Fix8e source remains on branch `wifi-aim-fix8e-prep` / PR `#11`.
- Do not blindly merge Fix8e into `main`.
- Full Fix8e hardware report: `FIX8E_HARDWARE_RESULT.md`.

## Exact next action for new chat
**First restore capture throughput. Do not continue deeper OFDM/MAC work while Fix8e is only completing ~1 capture per scan.**

1. Compare Fix8d (`main`) vs `wifi-aim-fix8e-prep`.
2. Focus on the combined decoder fallback policy and CPU cost of the DSSS path.
3. Preserve hardware-proven pieces: stock ABI zero-drift path, 2048 pretrigger, repetition LTF sync, full legacy OFDM rates, separate IPC buffers.
4. Keep post-DATA telemetry if it is not causing the throughput regression.
5. Change broad-SCAN DSSS handling so exhaustive DSSS cannot monopolize M4: gate by DSSS-like evidence, limit/time-slice, or otherwise bound CPU work.
6. Hardware-test until capture count is back to roughly `C20+` per full scan.
7. Only then use `P S/F/G/B/I` to determine whether OFDM DATA bytes are valid management/beacon/probe frames.

## Source layout
Current readable source:
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
`SCAN -> choose exact SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Channels 1–13. Beacon + Probe Response parsing. Hidden SSID support. Exact BSSID targeting. Relative signal is sufficient; do not claim calibrated dBm.
