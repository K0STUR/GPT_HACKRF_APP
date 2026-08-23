# HackRF / PortaPack / WiFi AIM — MASTER HANDOVER

Updated: 2026-08-22

## 1. User goal
Use a directional antenna connected directly to the HackRF/PortaPack `ANTENNA` SMA to find the best roof position/orientation for one chosen Wi-Fi AP.

SSID identification is a MUST HAVE. A generic channel-energy meter is not enough because neighbouring APs may share the same/overlapping channel.

Target workflow:
`SCAN CH1–13 -> show SSID/BSSID/channel -> choose exact BSSID -> TARGET -> AIM -> REF -> maximise DELTA REF`.

The final AIM screen should prefer signal measurements from frames belonging to the selected BSSID, not merely total channel power. Decoder modes should be `OFF / AUTO / ON` so expensive Wi-Fi PHY decoding can be intermittent.

## 2. Hardware and firmware
- HackRF One: early/classic board, around 2014 era or faithful clone.
- Classic micro-USB, expansion headers P20/P22/P28.
- Upper SMA labelled `ANTENNA` is the RF input/output.
- Lower SMA connectors are `CLK IN` / `CLK OUT`, not antenna inputs.
- PortaPack H4/H4M-class device.
- Current installed Mayhem shown by the device: `n_260808`.
- Exact upstream tag: `nightly-tag-2026-08-08`.
- Exact upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`.

HackRF facts used in the design:
- about 1 MHz–6 GHz tuning;
- up to 20 MS/s complex I/Q;
- 8-bit ADC/DAC;
- half duplex;
- not a calibrated power meter.

For antenna placement use relative dB/DELTA REF and keep AMP/LNA/VGA unchanged between reference/comparison points.

## 3. Why a custom app is needed
Stock Mayhem Looking Glass / Signal Hunter can show 2.4 GHz RF activity but do not provide the required robust AP list and target-by-BSSID workflow. The project therefore implements a Mayhem external app (`.ppma`) with:
- M0 UI/integration;
- M4 baseband/DSP image tagged `WAIM`.

## 4. WiFi AIM functionality already implemented in source
- 2.4 GHz CH1–CH13 scan framework.
- Beacon parsing.
- Probe Response parsing.
- SSID.
- hidden SSID handling.
- BSSID.
- channel.
- target selection by BSSID.
- LIVE / AVG / PEAK / REF / DELTA REF framework.
- decoder `OFF / AUTO / ON` framework.
- M4 capture/trigger/IPC pipeline.

PHY decoders implemented/tested:
- 802.11b DSSS / DBPSK 1 Mb/s;
- legacy OFDM 6 Mb/s;
- legacy OFDM 12 Mb/s;
- legacy OFDM 24 Mb/s.

The app intentionally does NOT implement WPA decryption, TCP/IP, or payload capture. Only enough 802.11 PHY/MAC is needed to identify APs and measure the selected target.

## 5. Tests already completed
Host-side / synthetic testing previously passed for:
- parser/DSSS/statistics (49 checks);
- synthetic DSSS Beacon -> SSID/BSSID/channel;
- synthetic OFDM Beacon at 6/12/24 Mb/s;
- CFO cases around +37/+47/+70 kHz during development;
- multipath echo;
- AWGN;
- int8 ADC-like quantisation;
- ASan + UBSan;
- random IQ fuzz and null input;
- actual `proc_wifi_aim` trigger -> capture -> decode -> IPC path.

A deliberately truncated long DSSS Beacon still yielded SSID/BSSID/channel within the roughly 1 ms capture window, which supports the short-capture design.

ARM work:
- Cortex-M4F / Thumb / hard-float / `-Os` probes completed;
- heavy trig/math dependencies removed from production decoder;
- production `WAIM.bin` in full builds is 16092 B;
- capture buffer was brought to about 20000 IQ samples (~1 ms @ 20 MS/s).

## 6. Real hardware proof: RF probe works
A simplified WiFiAim RF probe based on Mayhem's Signal Hunter was rebuilt exactly for `n_260808`.

First attempt built against the wrong nightly was rejected as `outdated`, confirming external-app version coupling.

The exact `n_260808` probe then launched successfully on the real PortaPack.

User observation:
- antenna attached -> much stronger red RF/activity bar excursions;
- antenna unscrewed -> much weaker excursions.

Conclusion: `ANTENNA SMA -> HackRF RF -> PortaPack -> external app` receive path is good. Do not revisit basic RF-chain feasibility unless new evidence contradicts this.

## 7. Full WiFi AIM build / failure history
### Original full build
Official Mayhem Docker/GNU ARM build completed:
- `.ppma` size 22592 B;
- `WAIM.bin` 16092 B;
- SHA-256 `e4d8a9adaf20806d6f9fac37abff22bbaa546f3ce752c2fcf90120e2a458a5dc`.

Real device result: `The .ppma file in your apps folder can't be read.`

### Fix1 — loader alignment/checksum
Original M4 offset was about 6493 B, not word-aligned. Fix1 moved it to 6496 and recalculated checksum.

Verified fix1 values:
- memory `0x10083EDC`;
- entry `0x10083F31`;
- header 3;
- app version `0x86B64C1D`;
- tag `WAIM`;
- M4 offset 6496;
- loader checksum `0x00000000`;
- SHA `c3e16d35398f28e2130ad992951f5368ecd6f142a473f4198514fe0adcfee49b`.

The loader accepted it, but the app immediately HardFaulted.

### HardFault evidence from real device
Capture #1:
- r0 `0x200040E0`
- r1 `0x00000040`
- r2 `0x00000200`
- r3 `0x10083F31`
- r12 `0x0007EE39`
- lr `0x10083F3B`
- pc `0x00000040`

Capture #2:
- r0 `0x200040E0`
- r1 `0x000001A4`
- r2 `0x00000200`
- r3 `0x10083F31`
- r12 `0x0007EE39`
- lr `0x10083F3B`
- pc `0x000001A4`

Entry disassembly shows first imported/core `BL` begins at about `0x10083F36`, with return LR `0x10083F3B`, exactly matching the crash.

Working probe import path references about `0x0007EE25` (`operator new` symbol ~`0x0007EE24`). Full WiFi AIM referenced about `0x0007EE39`.

Root cause: the full build shifted Mayhem core symbol addresses by including WiFi AIM content in the monolithic M0 link. The resulting `.ppma` therefore imported functions at addresses valid for the modified firmware build, while the user's device still had stock `n_260808`.

## 8. Later fixes and exact current state
### Fix2 / lowmem / fix3
- loader invariants and alignment improved;
- AP/history buffers reduced in lowmem variant;
- useful engineering work, but did not solve the core-address mismatch.

### Fix4 — isolate M0 WiFi AIM sections
Fix4 forced WiFi AIM `.text*`, `.rodata*`, `.data*`, `.gnu.linkonce*`, `.ARM.extab*`, `.ARM.exidx*` into the external region.

Build produced a valid loader image:
- size 22636 B;
- M4 offset 6540;
- loader checksum 0.

But `VERIFY.txt` reports `stock_operator_new_match=False`, so stock core addresses still did not match. RESULT=FAIL.

### Fix5 — patch imported symbols back to stock addresses
Fix5 compared modified-build imports against stock symbols and patched many external call veneers.

Exact result:
- 58 import patches found/applied;
- `operator new` corrected `0x0007EE39 -> 0x0007EE25`;
- many ReceiverModel/UI/baseband/libstdc++ functions corrected;
- ambiguous_count = 0;
- unresolved_count = 1;
- unresolved symbol: `_Z21to_string_mac_addressB5cxx11PKhhb`;
- final checksum = 0;
- RESULT=FAIL because one import remained unresolved.

Do not call fix5 fully stock-compatible until that last import is resolved and the complete import set is verified.

### Diagnostic `TEST_veneerpatch1`
A narrower test image patched 17 selected veneers.

Static verification:
- size 22436 B;
- patched_count 17;
- loader word sum 0;
- operator-new import `0x0007EE25`;
- SHA `dca529f1098d4081fb149af7cf3aeeb6a77acc658b52b8d31b09affbb2baacbb`;
- RESULT=PASS.

There is NO hardware result recorded for this file in the current conversation. It is a diagnostic candidate, not proven working.

## 9. Matched custom firmware strategy — currently the cleanest alternative
To avoid external-app/core ABI mismatch by construction, a matched firmware + app bundle was built from the same modified source tree.

Folder:
`hackrf/build_results/wifi_aim_bundle_w260822/`

Artifacts:
- `WiFiAIM_w_260822.ppma` — 22636 B;
- `portapack-mayhem_WIFI_AIM_w_260822.bin` — 1048576 B;
- `COPY_TO_SDCARD_WIFI_AIM_w_260822.zip` — matched APPS/FIRMWARE SD bundle;
- `WAIM.bin`;
- hashes/status/verify.

Build version: `w_260822`.

Verification:
- memory `0x10083EDC`;
- entry `0x10083F31`;
- header 3;
- version MD5 `0x96CD1C19`;
- tag `WAIM`;
- M4 offset 6540 (aligned);
- loader checksum 0;
- `.ppma` SHA `37e7cd018c58c2264ce8b5d2929f3a137dcf1a60dd82bf64e3cb18e35c995fe0`;
- RESULT=PASS.

Important: this strategy requires flashing the included custom firmware AND using the APPS from the matched bundle. Do not mix `WiFiAIM_w_260822.ppma` with stock `n_260808`.

This route is likely the fastest way to reach the real SSID-decoder test, but changing firmware should only happen with explicit user agreement and a backup/recovery plan.

## 10. External app/linker details that matter
For this Mayhem nightly, exporter constants used in the project include:
- M4 tag header offset 76;
- M4 offset header position 80;
- external app maximum combined size 32 KiB.

Project-added virtual external slot is around `0xAE0D0000`, after upstream Signal Hunter `0xAE0B0000` and TETRA RX `0xAE0C0000`.

Do not assume a `.ppma` compiled in a modified Mayhem application link will run on stock firmware merely because the version string/checksum match. Internal absolute imported function addresses must also match.

## 11. Repository handoff structure
The `hackrf/` folder is self-contained enough for a new chat:
- human-readable docs in the folder root;
- encoded source chunks under `source_archive/`;
- every relevant WiFi AIM build/result mirrored under `build_results/`;
- standalone diagnostics under `diagnostics/`;
- all project workflows under `workflows_archive/`;
- `MANIFEST_SHA256.txt` hashes the mirrored files;
- `REPO_SNAPSHOT.txt` records the assembly snapshot.

## 12. What NOT to do in the next chat
- Do not restart from basic spectrum scanning.
- Do not replace the main HackRF RF path with ESP32/monitor-mode Wi-Fi hardware.
- Do not claim calibrated absolute dBm.
- Do not assume fix4 succeeded — it explicitly failed stock-operator-new parity.
- Do not assume fix5 succeeded — one import remains unresolved.
- Do not claim `TEST_veneerpatch1` is hardware-proven; it is only statically verified so far.
- Do not hand the matched `w_260822` `.ppma` to a device still running stock `n_260808`.

## 13. Exact continuation options
### Option A — preserve stock `n_260808`
Continue import rebasing:
1. Resolve the remaining `to_string_mac_address` symbol mapping.
2. Re-run full symbol/import comparison against stock `n_260808`.
3. Require zero ambiguous and zero unresolved imports.
4. Recompute/verify loader checksum.
5. Hardware-test the resulting stock-compatible `.ppma`.

### Option B — fastest path to real SSID test
Use the matched custom `w_260822` firmware bundle:
1. back up current SD/firmware/recovery path;
2. flash the included matched firmware;
3. copy the matched APPS bundle;
4. launch WiFi AIM;
5. test `SCAN` for real SSIDs;
6. if SSIDs appear, test BSSID TARGET and DELTA REF;
7. if no SSIDs appear, only then return to PHY capture/synchronisation diagnostics.

A new chat should inspect `PROJECT_STATUS.md` and the newest `build_results` before deciding which path to take.