# WiFi AIM — hardware and build test log

Updated: 2026-08-23

## Test A — version mismatch
A probe/full external app built for the wrong Mayhem nightly was copied to `/APPS`.

Device response:
`The .ppma file in your apps folder is outdated. Please update your SD Card content.`

Conclusion: external app version check is active; build must match device Mayhem version exactly.

## Test B — exact n_260808 RF probe
Probe rebuilt with `VERSION_STRING=n_260808` and exact Aug-8 Mayhem snapshot.

Result: APP LAUNCHED on real hardware.

User observation:
- antenna connected -> noticeably stronger red RF/activity bar excursions;
- antenna unscrewed -> much weaker excursions.

Conclusion: RF path through HackRF `ANTENNA` SMA and external-app receive chain works.

## Test C — first full WiFi AIM `.ppma`
File size: 22592 bytes.

Device response:
`The .ppma file in your apps folder can't be read. Please update your SD Card content.`

Diagnosis: M4 boundary was not word-aligned, so loader/checksum handling rejected the file.

## Test D — Fix1, loader-aligned
Offline verification passed loader invariants and device accepted the file, but it HardFaulted immediately.

### HardFault capture #1
- r0 `200040E0`
- r1 `00000040`
- r2 `00000200`
- r3 `10083F31`
- r12 `0007EE39`
- lr `10083F3B`
- pc `00000040`

### HardFault capture #2
- r0 `200040E0`
- r1 `000001A4`
- r2 `00000200`
- r3 `10083F31`
- r12 `0007EE39`
- lr `10083F3B`
- pc `000001A4`

Working probe used the corresponding core veneer around `0x0007EE25`, which strongly indicated modified-vs-stock core address drift.

## Test E — Fix4 external-section isolation
Offline loader checks passed, but stock core parity failed (`stock_operator_new_match=False`).

Conclusion: section isolation alone did not restore exact stock internal ABI addresses.

## Test F — Fix5 full import rebasing attempt
Results:
- 58 imports patched;
- `operator new` corrected toward stock;
- ambiguous count `0`;
- unresolved count `1`;
- unresolved symbol `_Z21to_string_mac_addressB5cxx11PKhhb`;
- final checksum `0x00000000`;
- RESULT `FAIL`.

Conclusion: Fix5 supported the ABI-drift diagnosis but was not a clean stock-compatible candidate.

## Test G — narrow diagnostic `TEST_veneerpatch1`
Static verification passed after 17 selected veneer patches.

Hardware result: NOT RECORDED. Diagnostic only.

## Test H — matched custom firmware/APPS bundle `w_260822`
A complete modified Mayhem firmware and WiFi AIM app were built together.

Static build/loader verification passed. This route requires flashing the matched custom firmware and must not be mixed with stock `n_260808`.

Hardware result: NOT RECORDED.

## Test I — Fix6 local-MAC + hardened zero-drift ABI audit
Fix6 removed the external dependency on `to_string_mac_address` by formatting the BSSID locally inside the external app.

Workflow run:
`32631639944`

Overall result:
SUCCESS

Final artifact:
`build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Verification:
- size `22720`
- memory `0x10083EDC`
- entry `0x10083F31`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `6624`
- shared core symbol count `7118`
- core symbol drift count `0`
- ABI rebase patch count `0`
- resolved same-address core references `81`
- ambiguous count `0`
- unresolved count `0`
- final checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- retained `to_string_mac_address` symbol absent in stock and modified builds
- RESULT `PASS`

Interpretation: this is materially stronger than Fix5. The modified build did not shift the audited stock core symbols, and the final `.ppma` did not require any ABI rebasing patches.

## Test J — Fix6 real hardware: launch PASS, SCAN 0 AP
User tested `WiFiAIM_n260808_fix6.ppma` on the real PortaPack while keeping stock Mayhem `n_260808`.

Observed:
- application opens normally;
- no HardFault on launch;
- red RF/RSSI bar responds strongly to antenna presence/orientation, confirming live RF reception;
- pressing `SCAN` completes but returns `0 AP`.

Conclusion:
- Fix6 solved the M0 loader/core-ABI crash on real stock firmware;
- the current failure is downstream in M4 packet capture / Wi-Fi PHY decode / report path, not external-app loading;
- RSSI activity alone does not prove that the custom M4 decoder is receiving complete 802.11 preambles.

Source inspection after this test found two high-value issues to address in Fix7:
1. Fix6 starts a capture only at the DMA block whose average power crosses threshold and keeps no previous IQ block. A Wi-Fi preamble/L-LTF can therefore begin in the preceding block and be lost before the decoder sees the packet.
2. `BasebandThread` was declared before processor state/buffers even though upstream Mayhem explicitly requires auto-starting processor threads to be the last members so state is initialized before samples are processed.

Fix7 therefore adds:
- one DMA block (~2048 IQ samples) of pre-trigger history, reusing the existing capture buffer so M4 RAM does not increase;
- safer BasebandThread/RSSIThread member order;
- a less conservative energy trigger;
- 1000 ms dwell per Wi-Fi channel instead of 450 ms;
- ABI-safe runtime diagnostics over `HunterTrigger`: `C` = capture attempts, `D` = successful Wi-Fi decodes, `M` = last channel acknowledged by M4.

Fix7 CI run at time of this log update:
`32666957127`

Hardware interpretation for Fix7 diagnostics:
- `M` following the scanned channel proves M0 -> M4 configuration messages are arriving;
- `C > 0, D = 0` means RF bursts are being captured but PHY decoding is rejecting all candidates;
- `C = 0` means the capture detector/threshold still is not triggering;
- `D > 0` should correspond to actual `WAIM` AP reports and AP count growth.

## Confirmed installation behaviour
Exact upstream Mayhem `n_260808` code confirms:
- external apps are loaded from `/APPS`;
- the baseband M4 binary is appended into the generated `.ppma`;
- when `m4_app_offset != 0`, the loader reads both the application and embedded baseband image from the same `.ppma`.

Therefore stock-path tests copy only the matching `WiFiAIM_n260808_fixN.ppma` into `/APPS`.
Do not copy `WAIM.bin` separately.

## Current next criterion
Do not return to Fix5/ABI debugging unless a new zero-drift audit fails. The next frontier is Fix7 capture/decoder telemetry on real hardware.

For Fix7 require first:
1. static `RESULT=PASS` with zero core drift/unresolved/ambiguous imports;
2. app launches on stock `n_260808`;
3. during SCAN read the displayed `C`, `D`, and `M` values;
4. if APs appear, continue directly to BSSID TARGET and antenna aiming;
5. if `C>0 D=0`, instrument the PHY stages next instead of changing the loader/ABI layer.
