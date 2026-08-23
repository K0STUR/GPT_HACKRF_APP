# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository `K0STUR/GPT`, folder `hackrf/`.

First read, in this exact order:
1. `hackrf/README.md`
2. `hackrf/FIX6_STATIC_PASS_AND_HARDWARE_TEST.md`
3. `hackrf/HANDOVER_MASTER.md`
4. `hackrf/PROJECT_STATUS.md`
5. `hackrf/TEST_LOG.md`
6. `hackrf/WIFI_AIM_SPEC.md`
7. inspect `hackrf/build_results/wifi_aim_full_n260808_fix6/`

Do not restart the project from scratch and do not return to Fix5 unless new hardware evidence requires it.

## Current target
My real PortaPack runs stock Mayhem `n_260808`, upstream tag `nightly-tag-2026-08-08`, commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`.

The simplified RF probe already works on real hardware and clearly reacts to attaching/removing the antenna.

## Current full-app result
The full stock-compatible candidate is:

`hackrf/build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

SHA-256:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

Fix6 build workflow run `32631639944` completed SUCCESS.

Hardened verification:
- size `22720`
- memory `0x10083EDC`
- entry `0x10083F31`
- header `3`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `6624`
- shared core symbol count `7118`
- core symbol drift count `0`
- rebase patch count `0`
- resolved same-address core references in `.ppma` `81`
- ambiguous count `0`
- unresolved count `0`
- checksum `0x00000000`
- stock `_Znwj = 0x7ee24`
- modified `_Znwj = 0x7ee24`
- no retained external `to_string_mac_address` dependency
- `RESULT=PASS`

This is the first full candidate with a clean zero-drift stock-core ABI audit. It is **not yet hardware-proven**.

## Why Fix6 solved Fix5's blocker
Fix5 had 58 rebasing patches and one unresolved symbol: `_Z21to_string_mac_addressB5cxx11PKhhb`.

Fix6 moved BSSID formatting into the external app itself. After that change the stock and modified builds retain the same relevant core addresses; the final image needs zero ABI rebasing patches and has zero unresolved/ambiguous references.

## Exact next action
Hardware-test Fix6 on stock `n_260808`:

1. Copy only `WiFiAIM_n260808_fix6.ppma` to `/APPS` on the PortaPack SD card.
2. Do NOT flash custom firmware.
3. `WAIM.bin` is already embedded inside the `.ppma`; do not copy it separately.
4. App metadata puts `WiFi AIM` in the RX menu.
5. First criterion: app launches without HardFault.
6. Then test `SCAN -> SSID/BSSID list -> choose exact BSSID -> TARGET -> rotate directional antenna -> REF/DELTA REF`.

If a HardFault occurs, capture the complete screen, especially PC/LR/R12, and record whether it happened at launch, SCAN, AP selection, TARGET, or REF.

Do not claim Fix6 is hardware-working until I report the result from the real device.

My end goal remains:
`SCAN Wi-Fi by SSID -> choose exact BSSID -> TARGET -> AIM -> REF/DELTA REF`, using a directional antenna connected to the HackRF `ANTENNA` SMA. SSID identification is mandatory and final aiming should be target-BSSID-specific whenever possible.