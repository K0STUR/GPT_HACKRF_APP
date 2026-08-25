# WiFi AIM handover — Fix8m hardware complete / Fix8n source ready

Date: 2026-08-25
Repository: `K0STUR/GPT_HACKRF_APP`
Folder: `hackrf/`
Target: stock PortaPack Mayhem `n_260808` (`nightly-tag-2026-08-08`, upstream `367eaf54c0f51f62448d9f2d9585fd3629f6b770`)

## DO NOT RESTART FROM SCRATCH

The project goal remains:

`SCAN -> identify exact SSID/BSSID -> select AP -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Keep stock Mayhem and load only the external `.ppma` into `/APPS`; do not copy separate `WAIM.bin`.

## Stable historical anchor

Fix8c repetition LTF sync was a major improvement and must not be reverted without evidence.
Fix8d added all legacy OFDM rates and was the earlier hardware-functional reference.
Fix8e exposed severe capture starvation.
Fix8f (DSSS disabled) proved DSSS CPU cost was the immediate starvation cause (`C~155-166`).
Fix8g added bounded Barker-gated DSSS and restored practical throughput (`C~100+`).
Fix8i added strict SIGNAL reserved/tail validation.
Fix8j forced terminated SIGNAL Viterbi traceback from state 0 and restored strict SIGNAL passes into DATA.
Fix8k fixed puncture erasure handling (`2` must remain erasure instead of becoming zero).
Fix8l pinned displayed A/N to the actual candidate reaching DATA Viterbi.
Fix8m measured distance from valid SERVICE instead of only pass/fail.

## Fix8m branch/build

Branch: `wifi-aim-fix8m-service-distance`
Head used for build: `eadd08c6a24760f8232d85dc73f68474c6f9170b`
Draft PR: #19
CI run: `32785665256`
Artifact: `9541940378`
Hardened audit + Require static PASS: SUCCESS
User test file was delivered as `A_WiFiAIM_Fix8m.ppma` (renamed only; binary unchanged).

Fix8m telemetry semantics after a DATA candidate:
- `FC x/y`
- `x` = minimum SERVICE Hamming distance observed (known-zero SERVICE bits)
- `y` = raw SIGNAL RATE of that best candidate
- `P S/F/G/B/I` post-stages remain:
  1. SERVICE accepted
  2. protocol version 0
  3. management frame
  4. Beacon/Probe Response
  5. SSID IE parsed

## Fix8m hardware — latest full batch

All are hardware photos from the same real PortaPack environment.

### Scan A
`Done 0AP C111 D0 M13`
`OF L/H/V/P 105/105/105/56`
`OF R/N/D/M 14/11/9/0`
`SQ 97 A 11 N 1556`
`HIT 16/64/B 74/69/1`
`Q 16/64/B 100/100/73`
`DS A/S 8/0 FC 2/12`
`P S/F/G/B/I 0/0/0/0/0`

### Mid-scan B (S 6/13)
`C46 D0 M6`
`OF L/H/V/P 42/42/42/18`
`OF R/N/D/M 7/7/6/0`
`SQ 65 A 12 N 1268`
`HIT 16/64/B 33/32/0`
`Q 16/64/B 100/100/55`
`DS A/S 3/0 FC 2/9`
`P 0/0/0/0/0`

### Scan C
`Done 0AP C125 D0 M13`
`OF L/H/V/P 119/119/119/57`
`OF R/N/D/M 17/14/13/0`
`SQ 99 A 15 N 2205`
`HIT 16/64/B 85/83/1`
`Q 16/64/B 100/100/92`
`DS A/S 7/0 FC 2/9`
`P 0/0/0/0/0`

### Scan D
`Done 0AP C127 D0 M13`
`OF L/H/V/P 110/110/110/63`
`OF R/N/D/M 14/9/9/0`
`SQ 99 A 11 N 2060`
`HIT 16/64/B 91/87/1`
`Q 16/64/B 100/100/73`
`DS A/S 9/0 FC 2/11`
`P 0/0/0/0/0`

### Scan E — IMPORTANT
`Done 0AP C115 D0 M13`
`OF L/H/V/P 106/106/106/45`
`OF R/N/D/M 11/5/4/0`
`SQ 94 A 10 N 1111`
`HIT 16/64/B 91/85/0`
`Q 16/64/B 100/100/69`
`DS A/S 9/0 FC 1/10`
`P S/F/G/B/I 1/1/0/0/0`

This is the strongest evidence so far that some OFDM DATA candidates are close to correct. At least one post-stage event reached SERVICE and protocol-version checks (`P 1/1/...`).

NOTE: `FC 1/10` together with `P S/F = 1/1` is internally suspicious because a SERVICE-passing candidate should nominally imply a zero SERVICE error for that candidate. Do not ignore this. In the next chat inspect telemetry aggregation/reset semantics before using FC as a mathematically exact global minimum. It may be a display/aggregation nuance rather than decoder behavior.

### Scan F
`Done 0AP C117 D0 M13`
`OF L/H/V/P 112/112/112/55`
`OF R/N/D/M 22/14/11/0`
`SQ 96 A 9 N 367`
`HIT 16/64/B 81/76/0`
`Q 16/64/B 100/100/62`
`DS A/S 8/0 FC 2/14`
`P 0/0/0/0/0`

## Main interpretation after Fix8m

1. Capture throughput is healthy: roughly `C100-127` per full 13-channel scan.
2. Strict legacy SIGNAL repeatedly passes and many candidates reach DATA Viterbi (`D` commonly 4-13).
3. Candidates are not one single RATE/HT-LSIG class; prior Fix8l already showed multiple raw RATE values (A9/A10/A11/A12/A15 etc.).
4. SERVICE distance is frequently only 1-2 bits for the best candidate in a scan, not 4-5 random-like errors.
5. One scan reached `P S/F = 1/1`, proving at least occasional progress beyond SERVICE to protocol-version validation.
6. OFDM still produces no management-frame/MAC success (`M=0`, `G/B/I=0`).
7. DSSS can still generate occasional suspicious false APs in older builds; do not use those as proof of success. Keep OFDM and DSSS conclusions separate.

## Fix8n — CURRENT SOURCE CANDIDATE

Branch: `wifi-aim-fix8n-service-seed-recovery`
Base: Fix8m head `eadd08c6a24760f8232d85dc73f68474c6f9170b`
Current branch head after cleanup: `a06b77138e5393b9a40ab72c4dead2bf1a211eec`
Actual source-change commit: `6593d3d57484a7391dc65ae9980eb4c71db8133c`

Net diff vs Fix8m: ONE source file only:
`hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp`
~36 additions / 9 deletions.
Temporary one-shot patch workflow was removed after applying the source change.

Fix8n idea:
- Original code trusts the first seven decoded SERVICE/scrambler bits directly as the recovered scrambler state.
- One hard/Viterbi error in those seven bits can poison the LFSR state and make the remaining known-zero SERVICE bits appear as several errors.
- Fix8n brute-forces all 127 legal non-zero 7-bit states against all 16 known-zero SERVICE scrambled bits.
- Select the state with minimum mismatch.
- Accept only radius-1 (`service_errors <= 1`) to remain selective.
- For accepted recovery, advance the recovered LFSR through SERVICE bits 7..15 using known-zero plaintext, then descramble payload from bit 16 onward.
- No capture, LTF, SIGNAL, RATE, DSSS gate, UI, or ABI behavior is intentionally changed.

## Exact next action in a new chat

1. Read this file FIRST, then README/PROJECT_STATUS/TEST_LOG/HANDOVER_MASTER only as needed.
2. Inspect the Fix8n net diff vs Fix8m and sanity-check the scrambler-state recovery math. Do not assume it is correct just because the patch applied.
3. Open a DRAFT PR from `wifi-aim-fix8n-service-seed-recovery` onto `wifi-aim-fix8m-service-distance` (do NOT merge).
4. Let the existing hardened WiFi AIM workflow build it.
5. Require hardened ABI audit + static PASS.
6. Download artifact and provide ONLY the `.ppma`, renamed with leading A for sorting, preferably `A_WiFiAIM_Fix8n.ppma`.
7. Hardware test 3-5 full SCANs.
8. Primary success signals:
   - `P S > 0` becomes repeatable rather than rare;
   - `P F > 0` repeatable;
   - ideally `P G > 0` (management frame);
   - then `P B > 0`, `P I > 0`, `M > 0`, real AP.
9. If Fix8n does NOT improve post-stages, next likely direction is controlled DATA FFT/timing/CPE sweep or soft-decision Viterbi, guided by SERVICE distance; do not revert Fix8c/Fix8j/Fix8k.

## Naming preference

For user-delivered test binaries, rename the final PPMA so it starts with `A`, e.g. `A_WiFiAIM_Fix8n.ppma`, because the user wants it sorted at the top of the `/APPS` folder.
