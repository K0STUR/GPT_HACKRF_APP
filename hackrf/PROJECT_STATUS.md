# HackRF / PortaPack — PROJECT STATUS

Updated: 2026-08-24

Canonical repository: **`K0STUR/GPT_HACKRF_APP`**.
The old `K0STUR/GPT` repository is reserved for `FORDstecki` only.

## Device target
- PortaPack Mayhem: stock `n_260808`
- upstream tag: `nightly-tag-2026-08-08`
- upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- do not flash the matched custom `w_260822` firmware without explicit user permission.

## Hardware-proven baseline — Fix6
Fix6 solved the stock-loader/core-ABI problem.

Static:
- run `32631639944`
- size `22720`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`
- RESULT `PASS`

Real hardware:
- launch PASS on stock `n_260808`
- no HardFault
- RF/RSSI bar reacts to antenna
- SCAN completes with `0 AP`

Therefore loader/core ABI and basic RF reception are proven; the remaining issue is in M4 capture / Wi-Fi PHY decode / report flow.

## Fix7 — useful source ideas, static FAIL
Fix7 introduced:
- 2048-sample IQ pre-trigger history
- safer M4 initialization order with auto-starting threads last
- lower detector threshold (~1.25x floor + margin)
- 1000 ms/channel scan dwell
- runtime diagnostics `M/C/D`

But the added M0 `HunterTrigger` handler shifted 179 shared core symbols. Original Fix7 is archived and must not be hardware-tested.

## Fix7b — zero drift restored
Fix7b removed the new M0 `HunterTrigger` handler and transported telemetry through the already-existing `FSKPacket` handler. This restored zero core drift.

Fix7b static result:
- run `32671853658`
- job `97273779780`
- RESULT `PASS`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`

Before hardware testing, inspection of upstream Mayhem showed that `FSKRxPacketMessage` contains a pointer to `FskPacketData`. Fix7b used one backing buffer for both AP data and telemetry, so a retune telemetry write could theoretically overwrite an AP payload before M0 consumed it.

## CURRENT CANDIDATE — Fix7c STATIC PASS, READY FOR HARDWARE TEST
Fix7c keeps the zero-drift M0 design and hardens the M4->M0 IPC path:
- separate `FskPacketData` backing buffers for real AP reports and diagnostic reports;
- diagnostic-only marker is **flags bit7 = `0x80`**;
- failed-capture telemetry is throttled to every 16 capture attempts;
- exact counters/channel acknowledgement are still sent on every decoder/channel state transition;
- final SCAN counters are refreshed when decoding is disabled at the end of scan;
- successful AP reports are still emitted immediately.

This follows the same pointer-based `FSKRxPacketMessage` design used by upstream Mayhem's own FSK receiver, while preventing telemetry from overwriting AP data.

### Fix7c CI
Technical PR: `#5`

Run:
`32673931447`

Job:
`97278879220`

Artifact ID:
`9502420139`

The workflow artifact is still named `wifi-aim-full-n260808-fix7b` because Fix7c reused the already-hardened Fix7b audit harness; the compiled source is Fix7c from main commit `f4eec354a321b699d2ff1bf8254ddca6ab80bf7a`.

### Hardened Fix7c verification
- size `23452`
- memory `0x10083FF4`
- entry `0x10084049`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7076`
- shared core symbols `7086`
- **core symbol drift `0`**
- drift references `0`
- patch count `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- no retained `to_string_mac_address` import
- PPMA SHA-256 `f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`
- **RESULT `PASS`**

The PPMA header, word checksum and SHA-256 were independently recalculated after downloading the artifact and matched CI.

Archived text evidence:
`hackrf/build_results/wifi_aim_full_n260808_fix7c/`

## Exact next action — REAL HARDWARE TEST
Do not do more ABI work before this test.

1. keep stock Mayhem `n_260808`;
2. remove/move old WiFi AIM Fix6/Fix7 from SD `/APPS` so only one WiFi AIM entry exists;
3. copy only `WiFiAIM_n260808_fix7c.ppma` to `/APPS`;
4. do not copy `WAIM.bin` separately — it is embedded in the PPMA;
5. launch `RX -> WiFi AIM`;
6. press `SCAN`; scan takes about 13 seconds (1 s/channel for channels 1-13);
7. observe the status during scan: `S x/13 C# D# M#`;
8. record the final text: `Done xAP C# D#`;
9. if APs appear, test AP navigation, SSID/BSSID display and TARGET.

### Diagnostic meanings
- `M` = last channel acknowledged by M4. It should follow the current scan channel.
- `C` = capture attempts during the current scan.
- `D` = successful Wi-Fi PHY decodes during the current scan.

Interpretation:
- HardFault -> photograph full register screen; unexpected runtime regression despite zero-drift audit.
- `M` does not follow channel -> M0->M4 control or M4->M0 telemetry problem.
- `M` works, `C=0` -> capture detector/threshold is not triggering.
- `C>0, D=0` -> RF capture is working; next build must instrument PHY stages rather than loader/ABI.
- `D>0, AP=0` -> investigate decoded report / WireApReport / M0 parser path.
- `AP>0` -> proceed directly to SSID/BSSID selection, TARGET, AIM, REF/DELTA REF.

## Source layout
Readable current source:
`hackrf/source_expanded/`

Key files:
- `firmware/application/external/wifi_aim/ui_wifi_aim.cpp`
- `firmware/application/external/wifi_aim/ui_wifi_aim.hpp`
- `firmware/baseband/proc_wifi_aim.cpp`
- `firmware/baseband/proc_wifi_aim.hpp`
- `firmware/common/wifi_aim/wifi_aim_phy.cpp`
- `firmware/common/wifi_aim/wifi_aim_phy.hpp`
- `firmware/common/wifi_aim_wire.hpp`

## End goal
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only. Channels 1-13. Beacon + Probe Response parsing. Hidden SSID support. Exact BSSID targeting. Relative signal is sufficient; do not claim calibrated dBm.
