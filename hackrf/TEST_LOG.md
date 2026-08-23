# WiFi AIM — hardware and build test log

Updated: 2026-08-24

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

Working probe used the corresponding core veneer around `0x0007EE25`, strongly indicating modified-vs-stock core address drift.

## Test E — Fix4 external-section isolation
Offline loader checks passed, but stock core parity failed (`stock_operator_new_match=False`).

## Test F — Fix5 full import rebasing attempt
Results:
- 58 imports patched;
- ambiguous `0`;
- unresolved `1`: `_Z21to_string_mac_addressB5cxx11PKhhb`;
- checksum `0`;
- RESULT `FAIL`.

## Test G — narrow diagnostic `TEST_veneerpatch1`
Static verification passed after 17 selected veneer patches.
Hardware result: NOT RECORDED. Diagnostic only.

## Test H — matched custom firmware/APPS bundle `w_260822`
Static build/loader verification passed. This route requires flashing matching custom firmware and is not the current route.

## Test I — Fix6 hardened zero-drift audit
Workflow run `32631639944`: SUCCESS.

Artifact SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Verification:
- size `22720`
- memory `0x10083EDC`
- entry `0x10083F31`
- version `0x86B64C1D`
- M4 offset `6624`
- shared core symbols `7118`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- RESULT `PASS`

## Test J — Fix6 real hardware: launch PASS, SCAN 0 AP
User tested Fix6 on stock Mayhem `n_260808`.

Observed:
- app opens normally;
- no HardFault;
- red RF/RSSI bar responds to antenna;
- SCAN completes but returns `0 AP`.

Conclusion: loader/core ABI is solved on real hardware. Remaining fault is M4 capture / Wi-Fi PHY decode / report path.

Source inspection identified two concrete weaknesses:
1. capture had no previous DMA block, so packet preamble/L-LTF could be lost;
2. auto-starting `BasebandThread` was declared before processor state despite upstream requirement to keep it last.

## Test K — Fix7: improved capture telemetry, STATIC FAIL
Fix7 added:
- 2048 IQ pre-trigger samples using existing capture RAM;
- BasebandThread/RSSIThread moved last;
- lower capture threshold;
- 1000 ms/channel dwell;
- M/C/D telemetry using `HunterTrigger`.

Run `32666957127`, job `97261737292`.

Actual hardened audit:
- size `23508`
- M4 offset `7140`
- shared core symbols `7118`
- **core drift `179`**
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `cb1cab400ea934f3d0bf2d3116d624c3310375a7f7342a2c00b3ec4a4d71248f`
- RESULT `FAIL`

The shift started at +4 bytes around stock core address `0x000A3C68`. Do not hardware-test original Fix7.

## Test L — Fix7b: existing FSKPacket telemetry + zero-drift audit PASS
Fix7b preserves all useful Fix7 M4/capture changes, but removes the additional M0 `HunterTrigger` handler. Instead M4 sends diagnostic-only `WireApReport` records through the already existing `FSKPacket` message route. `flags bit1` marks diagnostics; M0 consumes those packets to update `M/C/D` and does not add them to the AP list.

Technical PR:
`#4`

Workflow run:
`32671853658`

Job:
`97273779780`

Actions result:
`SUCCESS`

Artifact:
- name `wifi-aim-full-n260808-fix7b`
- ID `9501915159`
- artifact digest `sha256:68093816916211b88d4fd9ec56ace728ec14c246aca2a89ba820b4f0d491a5d6`

Final PPMA:
`WiFiAIM_n260808_fix7b.ppma`

Hardened verification:
- size `23396`
- memory `0x10083FE4`
- entry `0x10084039`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7036`
- shared core symbol count `7086`
- **core symbol drift count `0`**
- drift reference count `0`
- patch count `0`
- same-address core refs `80`
- ambiguous count `0`
- unresolved count `0`
- final checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- no retained `to_string_mac_address`
- PPMA SHA-256 `730dee07e741cc5a2764dfcf9ffbae52622caf25a75ea6e94a7ffabbf9cb2b49`
- **RESULT `PASS`**

Independent verification after artifact download reproduced:
- file size `23396`;
- version/tag/header and M4 offset;
- Thumb entry inside the external-app M0 range;
- word-aligned M4 boundary;
- checksum exactly `0`;
- identical SHA-256.

Hardware status: **PENDING**.

## Fix7b hardware test procedure
1. Keep stock Mayhem `n_260808`; do not flash firmware.
2. Remove/move Fix6 from `/APPS` to avoid duplicate WiFi AIM entries.
3. Copy only `WiFiAIM_n260808_fix7b.ppma` to `/APPS`.
4. Do not copy `WAIM.bin` separately; it is embedded in the PPMA.
5. Launch RX -> WiFi AIM.
6. Verify no HardFault and that RF/RSSI still responds to antenna.
7. Press SCAN. It spends about 1 second on each channel 1-13.
8. Observe whether `M` follows the current channel.
9. Record final `Done xAP C# D#` exactly.

Interpretation:
- HardFault -> runtime regression despite static PASS; capture full register screen.
- `M` follows + `C=0` -> detector/capture-start issue.
- `C>0 D=0` -> detector/capture is working; next build instruments PHY stages.
- `D>0` but AP=0 -> investigate real AP report path/parser.
- AP>0 -> continue to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

## Confirmed installation behaviour
Exact upstream Mayhem `n_260808` confirms:
- external apps load from `/APPS`;
- M4 binary is appended into generated `.ppma`;
- loader loads embedded M4 from the same `.ppma` when `m4_app_offset != 0`.

Therefore stock-path tests copy only the matching `.ppma` into `/APPS`.
