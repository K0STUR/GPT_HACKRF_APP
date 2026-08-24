# WiFi AIM — hardware and build test log

Updated: 2026-08-24

## Test A — wrong nightly
External app built for a different Mayhem version was rejected as outdated. Conclusion: `.ppma` must exactly match device firmware.

## Test B — exact n_260808 RF probe
Hardware PASS. App launched and the red RF/activity bar became much weaker when the antenna was unscrewed. RF receive path proven.

## Test C — first full app
Loader rejected the PPMA because the embedded M4 boundary was not word-aligned.

## Test D — Fix1
Loader accepted the app but it HardFaulted immediately. Captures showed the modified build referencing shifted stock-core addresses.

## Tests E/F/G — Fix4/Fix5/veneer diagnostic
Fix4 still shifted stock core. Fix5 rebased 58 imports but had one unresolved `to_string_mac_address` dependency. Narrow veneerpatch diagnostic was static-only. These are historical and are not the current route.

## Test H — matched custom w_260822 bundle
Static PASS but requires custom matching firmware. Not the current route; do not flash without explicit user permission.

## Test I — Fix6 zero-drift audit
Run `32631639944` PASS.

- size `22720`
- version `0x86B64C1D`
- M4 offset `6624`
- shared core symbols `7118`
- core drift `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`
- RESULT `PASS`

## Test J — Fix6 real hardware
Hardware result:
- launch PASS;
- no HardFault;
- RF/RSSI reacts to antenna;
- SCAN completes with `0 AP`.

Conclusion: stock loader/core ABI and basic RF reception are solved. Failure is downstream in M4 capture / Wi-Fi PHY decode / report path.

Source review found two strong issues: no previous DMA-block pretrigger history and unsafe auto-starting BasebandThread member order.

## Test K — Fix7
Fix7 added 2048-sample pretrigger, safer M4 thread order, lower trigger threshold, 1 s/channel dwell and M/C/D diagnostics.

Run `32666957127`, job `97261737292`.

Hardened audit FAIL:
- core drift `179`;
- first shift +4 bytes around stock `0x000A3C68`;
- patches `0`;
- ambiguous `0`;
- unresolved `0`;
- checksum `0`;
- SHA-256 `cb1cab400ea934f3d0bf2d3116d624c3310375a7f7342a2c00b3ec4a4d71248f`.

Cause was tied to the extra M0 HunterTrigger handler. Do not hardware-test original Fix7.

## Test L — Fix7b
Fix7b moved telemetry to the already-existing `FSKPacket` M0 handler and restored zero drift.

Run `32671853658`, job `97273779780`: PASS.

- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `730dee07e741cc5a2764dfcf9ffbae52622caf25a75ea6e94a7ffabbf9cb2b49`

Before hardware testing, upstream inspection showed `FSKRxPacketMessage` carries a pointer to `FskPacketData`. Fix7b used the same backing store for AP and telemetry, leaving a possible overwrite window.

## Test M — Fix7c IPC hardening, STATIC PASS
Fix7c keeps Fix7b's zero-drift M0 design but hardens M4 report storage:
- separate `FskPacketData` buffers for real AP payloads and diagnostic telemetry;
- diagnostic-only marker = **flags bit7 / `0x80`**;
- failed-capture telemetry only every 16 capture attempts;
- exact C/D + channel acknowledgement on decoder/channel state changes;
- successful AP reports emitted immediately;
- 2048 pretrigger, safer M4 thread order, lower threshold and 1 s/channel retained.

Technical PR `#5`; run `32673931447`, job `97278879220`: SUCCESS.

Hardened verification:
- size `23452`
- M4 offset `7076`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA-256 `f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`
- RESULT `PASS`

## Test N — Fix7c REAL HARDWARE: capture works, decoder does not
Observed on stock `n_260808`:

`Done 0AP C10 D0`

Also:
- app launches normally;
- no HardFault;
- RF/RSSI bar remains active.

Interpretation:
- M4 executed 10 full capture attempts during the scan;
- zero captures passed the complete Wi-Fi PHY decoder;
- loader/core ABI is not the active problem;
- capture trigger is no longer the primary unknown;
- next diagnostic must determine whether captured IQ actually contains recognizable Wi-Fi preamble structure.

## Test O — Fix8a raw-IQ preamble probe, STATIC PASS
Fix8a leaves the existing Wi-Fi decoder unchanged and adds a decoder-independent probe over raw capture IQ:
- `16` = normalized 16-sample repetition score/hits (legacy OFDM STF-like structure);
- `64` = normalized 64-sample repetition score/hits (legacy OFDM L-LTF-like structure);
- `B` = Barker-11 correlation score/hits (DSSS-like structure).

Conservative hit thresholds:
- OFDM16 >= `55`;
- OFDM64 >= `60`;
- Barker >= `70`.

UI adds:
- `HIT 16/64/B a/b/c`
- `Q   16/64/B x/y/z`
- final status now includes M4 channel, e.g. `Done 0AP C10 D0 M13`.

Technical PR `#7`.
Run `32699435547`, job `97347800013`: **SUCCESS**.
Artifact ID `9510405146` (historical artifact name still says `fix7b`; compiled source is Fix8a).

Hardened verification:
- size `24800`
- memory `0x10084324`
- entry `0x10084379`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `7608`
- shared core symbols `7086`
- **core drift `0`**
- drift refs `0`
- patches `0`
- same-address core refs `79`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `3fdfd70530a2217888c93c9c11259ecac02ca54371b4998391d31dc006224e9d`
- **RESULT `PASS`**

Independent verification after downloading artifact:
- file size `24800`;
- sum of all 32-bit words = `0x00000000`;
- SHA-256 exactly matches CI;
- PPMA contains Fix8a UI strings `HIT 16/64/B` and `Q   16/64/B`.

### Exact next test — Fix8a hardware
Keep stock Mayhem `n_260808`. Replace previous WiFi AIM PPMA with Fix8a only. Run SCAN and photograph/report:
- final `Done xAP C# D# M#`;
- `HIT 16/64/B a/b/c`;
- `Q   16/64/B x/y/z`.

Interpretation:
- high OFDM16/64 scores or hits + `D0` -> captured signal looks like OFDM Wi-Fi; focus on OFDM decoder internals;
- high Barker score/hits + `D0` -> captured signal looks like DSSS Wi-Fi; focus on DSSS decoder internals;
- all probe scores low -> detector is capturing non-Wi-Fi energy or capture alignment still misses the useful preamble; improve detector/pretrigger before decoder internals.

## Installation fact
On exact upstream `n_260808`, external apps load from `/APPS` and the M4 baseband image is embedded inside the `.ppma`. Copy only the matching PPMA; never copy `WAIM.bin` separately for this stock-path test.
