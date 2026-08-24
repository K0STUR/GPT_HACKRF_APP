# WiFi AIM — hardware and build test log

Updated: 2026-08-24

## Historical loader / ABI phase
### Test A — wrong nightly
External app built for a different Mayhem version was rejected as outdated. Exact firmware/app version coupling proven.

### Test B — exact n_260808 RF probe
Hardware PASS. App launched; red RF/activity bar became much weaker when antenna was unscrewed. RF receive path proven.

### Tests C–H — loader/core-address debugging
- original full app first failed M4 alignment;
- Fix1 loaded but HardFaulted because modified Mayhem core symbols shifted;
- Fix4 still had core drift;
- Fix5 rebased imports but left one unresolved `to_string_mac_address` dependency;
- matched custom `w_260822` bundle was statically valid but requires custom firmware and is not the chosen route.

### Test I — Fix6 zero-drift
Run `32631639944` PASS.
- size `22720`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

### Test J — Fix6 real hardware
Launch PASS, no HardFault, RF bar reacts to antenna, SCAN completes but 0 AP. Conclusion: loader/core ABI solved.

## Capture / PHY localization phase
### Test K — original Fix7
Added pretrigger, safer M4 init and diagnostics but hardened audit found `179` core-symbol drifts. Do not hardware-test original Fix7.

### Test L — Fix7b
Moved telemetry onto existing FSKPacket handler, restored core drift 0. Static PASS.

### Test M — Fix7c static PASS
Separate AP/diagnostic FSK backing stores, throttled telemetry, 2048 pretrigger retained.
Run `32673931447`, SHA `f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`, RESULT PASS.

### Test N — Fix7c real hardware
`Done 0AP C10 D0`

Conclusion: M4 completes captures; decoder rejects them.

### Test O — Fix8a raw-IQ preamble probe
Static PASS, run `32699435547`, SHA `3fdfd70530a2217888c93c9c11259ecac02ca54371b4998391d31dc006224e9d`.

Real hardware:
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q 16/64/B 100/100/53`

Conclusion: captured IQ strongly resembles legacy OFDM Wi-Fi.

### Test P — Fix8b OFDM stage diagnostics
Real hardware:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 2/2/2/1`
`OF R/N/D/M 0/0/0/0`
`LQ 68 R 8 N 0`
`HIT 16/64/B 22/20/0`
`Q 16/64/B 100/100/55`

Conclusion: old ideal-template LTF gate accepted only 2 captures even though ~20 had strong 64-sample repetition. SIGNAL/Viterbi can work on real RF.

### Test Q — Fix8c repetition LTF synchronization
Fix8c replaced old ideal-template gate with repetition metric `Q64 * (1 - Q16)`.

Static PASS:
- run `32708337425`
- SHA `4d573419e816af667cf17166cb0aef2dbb64b19fad4700a09d9321265c19b299`
- core drift `0`
- checksum `0`

Real hardware:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 24/24/24/15`
`OF R/N/D/M 1/0/0/0`
`SQ 98`

Conclusion: LTF synchronization problem solved. Do not revert repetition sync without new evidence.

## Functional AP discovery phase
### Test R — Fix8d full legacy OFDM
Fix8d added all legacy OFDM rates 6/9/12/18/24/36/48/54 Mb/s, 64-QAM, 2/3 and 3/4 depuncturing and erasure-aware Viterbi.

Static PASS:
- run `32712871860`
- size `26032`
- M4 offset `8264`
- core drift `0`
- checksum `0`
- SHA `359995bd49ec59eeec0fff799cd616c392fd022bdb284f558ef4f7bdeae2edeb`

Real hardware — 5 scans:
- **2/5 scans found `1AP`**;
- remaining 3 found 0 AP;
- typical full-scan capture count ~`C20–C28`.

Representative successful scan:
`Done 1AP C28 D1 M13`
`OF L/H/V/P 24/24/24/11`
`OF R/N/D/M 4/2/2/0`

Other observed Fix8d states:
- `OF R/N/D/M 10/3/3/0`
- `C26`, strong OFDM metrics.

Interpretation:
- full RATE support materially improved progression;
- real OFDM frames reach DATA Viterbi;
- OFDM MAC counter `M` stayed 0;
- global AP/D sometimes became 1, so intermittent AP success likely came through DSSS fallback.

This is the **last functional hardware baseline**.

### Test S — Fix8e post-MAC diagnostics / DSSS counters
Fix8e additions:
- AP display restored after final telemetry;
- post-DATA OFDM telemetry `P S/F/G/B/I`;
- DSSS attempt/success counters `DS A/S`;
- skip exhaustive DSSS after parity-valid OFDM SIGNAL.

Static PASS:
- branch `wifi-aim-fix8e-prep`
- PR `#11`
- run `32723430968`
- job `97419505883`
- artifact `9519205449`
- size `27048`
- M4 offset `8864`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`
- RESULT PASS.

Real hardware — 4 scans:
- **0 AP in 4/4 scans**.

Representative final screen:
`Done 0AP C1 D0 M13`
`OF L/H/V/P 0/0/0/0`
`OF R/N/D/M 0/0/0/0`
`SQ 0 R 255 N 0`
`HIT 16/64/B 1/1/0`
`Q 16/64/B 96/96/32`
`DS A/S 1/0 FC 255/255`
`P S/F/G/B/I 0/0/0/0/0`

Environment: phone sees at least 5 nearby Wi-Fi networks.

Conclusion:
- Fix8e introduces a severe **capture-throughput regression**: one full scan completed only `C1` versus Fix8d's typical `C20–C28`;
- channel acknowledgement still reached `M13`, so M0→M4 control/retune is alive;
- one DSSS attempt occurred and failed;
- leading hypothesis: the first capture that does not reach OFDM parity falls into exhaustive DSSS decoding and monopolizes M4 long enough to starve later DMA/capture work;
- this is not yet proven and is the first thing the next chat should test.

## Current repository state
- `main` = Fix8d functional source baseline + current docs.
- Fix8e source = branch `wifi-aim-fix8e-prep`, PR `#11`.
- do not merge Fix8e blindly.
- detailed current report: `FIX8E_HARDWARE_RESULT.md`.

## Exact next test/development question
Before any deeper OFDM/MAC work: **why does Fix8e collapse from ~20–28 captures per scan to ~1?**

Restore broad-scan throughput first by bounding/gating/time-slicing exhaustive DSSS work. Target: return to roughly `C20+` per full scan while preserving Fix8c repetition sync and Fix8d full legacy OFDM support. Then re-enable/use `P S/F/G/B/I` to continue post-DATA OFDM diagnosis.

## Installation fact
On exact upstream `n_260808`, external apps load from `/APPS`; M4 baseband image is embedded in `.ppma`. Copy only the matching PPMA, never a separate WAIM.bin for this stock route.
