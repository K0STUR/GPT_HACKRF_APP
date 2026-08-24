# HackRF / PortaPack / WiFi AIM — handoff

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**. The old `K0STUR/GPT` repo is reserved for FORDstecki.

## Read first
1. `PROJECT_STATUS.md`
2. `FIX8E_HARDWARE_RESULT.md`
3. `TEST_LOG.md`
4. `NEXT_CHAT_PROMPT.md`
5. `HANDOVER_MASTER.md`
6. `WIFI_AIM_SPEC.md`
7. `source_expanded/`

## Current one-line status
**Fix8d is the last functional hardware baseline: 2 of 5 scans found 1 AP and typical scans completed ~20–28 captures. Fix8e is static/ABI PASS but on real hardware regressed to 0 AP in 4/4 scans and one representative full scan completed only `C1`; the next chat must investigate M4 capture-throughput starvation before doing any deeper OFDM/MAC work.**

## Device target
Keep stock Mayhem `n_260808`:
- tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Do not flash matched custom `w_260822` without explicit permission.

## Proven milestones
- Fix6: stock loader/core ABI solved on hardware; app launches without HardFault.
- Fix7c: capture path works (`Done 0AP C10 D0`).
- Fix8a: raw capture strongly OFDM-like (`Q16/Q64 100/100`).
- Fix8b: old ideal-template LTF sync accepts only 2/26 captures.
- Fix8c: repetition LTF sync fixed that bottleneck (`L/H/V = 24/24/24`).
- Fix8d: full legacy OFDM 6/9/12/18/24/36/48/54 added; real hardware reaches DATA Viterbi and intermittently finds AP (`1AP` in 2/5 scans).
- Fix8e: added post-DATA/DSSS telemetry and throughput guard, but hardware capture count collapsed to ~`C1` in the shown run; 0 AP in 4/4 scans.

## Critical current evidence
Fix8d representative successful scan:

`Done 1AP C28 D1 M13`

`OF L/H/V/P 24/24/24/11`

`OF R/N/D/M 4/2/2/0`

Fix8e representative scan:

`Done 0AP C1 D0 M13`

`OF L/H/V/P 0/0/0/0`

`DS A/S 1/0 FC 255/255`

`HIT 16/64/B 1/1/0`

`Q 16/64/B 96/96/32`

The phone sees at least 5 nearby Wi-Fi networks in the same location, so the Fix8e `0AP` result is not due to an empty RF environment.

## Repository state
- `main`: keep as the **Fix8d functional baseline** plus handover docs.
- Fix8e source: branch **`wifi-aim-fix8e-prep`**, technical PR `#11`.
- Fix8e hardened run: `32723430968`, job `97419505883`, artifact `9519205449`.
- Fix8e static result: core drift 0, checksum 0, SHA-256 `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`, RESULT PASS.
- **Do not blindly merge Fix8e into main** until the capture-throughput regression is understood.

## Exact next step
Do not change loader/ABI, repetition LTF sync, or full OFDM RATE support.

The next chat should first diff Fix8d against `wifi-aim-fix8e-prep` and determine why the M4 now completes only ~1 capture per scan. Leading hypothesis: after the first capture fails OFDM parity, Fix8e still runs the exhaustive DSSS fallback and may occupy the M4 for a large fraction of the 13-second scan.

Primary next-code objective (for the new chat, not this one): gate/limit/time-slice DSSS during broad SCAN so capture throughput returns to Fix8d territory (`C20+`). Only after that should `P S/F/G/B/I` post-DATA telemetry be used to continue OFDM MAC diagnosis.

## Goal
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Relative signal strength is sufficient; do not claim calibrated dBm.
