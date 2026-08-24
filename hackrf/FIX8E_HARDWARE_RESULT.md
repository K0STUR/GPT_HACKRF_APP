# WiFi AIM Fix8e — hardware result

Updated: 2026-08-24

## Device / environment
- PortaPack Mayhem stock `n_260808`
- exact target tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- passive 2.4 GHz scan, channels 1–13
- in the test location the phone sees at least 5 nearby Wi-Fi networks; earlier phone screenshots showed several 2.4/5 GHz SSIDs, so `0 AP` is not explained by an empty RF environment.

## Fix8e static build
Technical branch: `wifi-aim-fix8e-prep`
Technical PR: `#11`
Hardened run: `32723430968`
Job: `97419505883`
Artifact ID: `9519205449`

Static verification:
- size `27048`
- M4 offset `8864`
- core symbol drift `0`
- drift references `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- final checksum `0x00000000`
- SHA-256 `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`
- RESULT `PASS`

Important repository state: **Fix8e source is on branch `wifi-aim-fix8e-prep`; `main` remains the Fix8d functional baseline plus documentation. Do not merge Fix8e blindly.**

## Real hardware result
User performed 4 Fix8e scans. Result: **0 AP in all 4 scans**.

Representative final screen:

`Done 0AP C1 D0 M13`

`OF L/H/V/P 0/0/0/0`

`OF R/N/D/M 0/0/0/0`

`SQ 0 R 255 N 0`

`HIT 16/64/B 1/1/0`

`Q 16/64/B 96/96/32`

`DS A/S 1/0 FC 255/255`

`P S/F/G/B/I 0/0/0/0/0`

Interpretation:
- only **1 capture attempt** completed during the entire 13-channel scan;
- that one capture did not pass OFDM LTF/SIGNAL;
- DSSS fallback was attempted exactly once and did not decode an AP;
- M4 channel acknowledgement reached channel 13, so channel control/retune still progresses;
- raw-IQ probe on the single capture still looked strongly OFDM-like (`Q16/Q64 = 96/96`), but the sample count is too small to diagnose PHY from this run;
- the dominant new problem is **capture throughput / M4 processing starvation**, not the previously solved LTF synchronization or legacy RATE support.

## Comparison with Fix8d — critical regression
Fix8d real hardware baseline immediately before Fix8e:
- 5 scans total;
- **2/5 scans found `1AP`**;
- other scans found 0 AP;
- typical capture counts were about `C20–C28`.

Representative successful Fix8d scan:

`Done 1AP C28 D1 M13`

`OF L/H/V/P 24/24/24/11`

`OF R/N/D/M 4/2/2/0`

Other Fix8d examples included:
- `OF R/N/D/M 10/3/3/0`
- `C26` with strong OFDM repetition metrics.

Fix8d therefore proved:
- repetition-based LTF sync works on real hardware;
- full legacy OFDM RATE support materially improves progression through PHY;
- DATA Viterbi is reached on real frames;
- at least one AP can be found intermittently (most likely via DSSS fallback because global `D/AP` incremented while OFDM MAC `M` remained 0).

Fix8e changed post-DATA diagnostics, AP-display behavior, DSSS counters, and added a guard that skips exhaustive DSSS only after parity-valid OFDM SIGNAL. The observed `C1` strongly suggests the **first non-OFDM/parity-failing capture may still enter the expensive exhaustive DSSS decoder and occupy the M4 for much of the scan**, starving later DMA/capture opportunities. This is the leading hypothesis, not yet proven.

## Exact next engineering step for the new chat
Do **not** continue deeper OFDM/MAC debugging until capture throughput is restored.

Start from a diff of Fix8d vs branch `wifi-aim-fix8e-prep`, concentrating on the combined decoder fallback policy and CPU cost of the DSSS path.

Primary objective for the next code change:
1. preserve all Fix8d-proven pieces: zero-drift ABI, repetition LTF sync, full 6/9/12/18/24/36/48/54 OFDM support, pretrigger, separate IPC buffers;
2. keep Fix8e post-DATA telemetry if it does not affect throughput;
3. prevent exhaustive DSSS processing from monopolizing M4 during broad SCAN — e.g. gate/limit/time-slice DSSS or run it only on selectively DSSS-like captures;
4. hardware-test until capture count returns to roughly Fix8d territory (`C20+` across 13 channels);
5. only then use `P S/F/G/B/I` to continue OFDM post-DATA/MAC diagnosis.

Do not touch the solved loader/core ABI path or revert repetition-based LTF sync unless new evidence directly requires it.
