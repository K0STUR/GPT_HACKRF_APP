# WiFi AIM n_260808 Fix6 — static PASS and hardware test

Updated: 2026-08-23

## Status

`WiFiAIM_n260808_fix6.ppma` is the first full WiFi AIM candidate that passes the hardened stock-ABI zero-drift audit against the exact stock Mayhem target:

- firmware version: `n_260808`
- upstream tag: `nightly-tag-2026-08-08`
- upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- build workflow run: `32631639944`
- workflow conclusion: SUCCESS
- hardware status: **NOT YET TESTED / NOT YET HARDWARE-PROVEN**

## Exact verification

From `build_results/wifi_aim_full_n260808_fix6/VERIFY.txt`:

- size = `22720`
- memory = `0x10083EDC`
- entry = `0x10083F31`
- header = `3`
- version = `0x86B64C1D`
- tag = `WAIM`
- M4 offset = `6624`
- shared core symbols compared = `7118`
- core symbol drift count = `0`
- ABI rebase patch count = `0`
- resolved same-address core references in `.ppma` = `81`
- ambiguous imports = `0`
- unresolved imports = `0`
- final loader checksum = `0x00000000`
- stock `_Znwj` = `0x7ee24`
- modified `_Znwj` = `0x7ee24`
- stock `to_string_mac_address` retained symbol = absent
- modified `to_string_mac_address` retained symbol = absent
- RESULT = `PASS`

SHA-256 of final PPMA:
`4084904bb1d12229895066f0d1b3424c1dfb5a54fcf40705b6c4cae4f05fe225`

## Why Fix6 is materially different from Fix5

Fix5 needed 58 address patches and still had one unresolved import, `to_string_mac_address`, so it was not safe to hand off as stock-compatible.

Fix6 removes that non-stock retained-symbol dependency by formatting the BSSID locally inside the external app. The hardened Fix6 audit then compares the stock and modified symbol maps and requires zero core-symbol drift. The result is stronger than a successful rebase: the full candidate requires **zero rebasing patches** because the relevant core ABI addresses did not move.

## SD-card installation

The final `.ppma` already contains the baseband `WAIM` M4 image. `WAIM.bin` is a build/debug artifact and is **not** copied separately to the SD card.

Copy only:

`build_results/wifi_aim_full_n260808_fix6/WiFiAIM_n260808_fix6.ppma`

to:

`/APPS/WiFiAIM_n260808_fix6.ppma`

on the PortaPack SD card.

Do not flash custom firmware for this test. This candidate is specifically for the existing stock `n_260808` route.

The app metadata places `WiFi AIM` in the RX menu.

## First hardware test sequence

1. Boot stock Mayhem `n_260808` with the Fix6 `.ppma` in `/APPS`.
2. Open RX -> `WiFi AIM`.
3. First pass criterion: **no HardFault on launch**.
4. Start `SCAN` and verify channels 1-13 are scanned.
5. Verify real SSIDs are listed; hidden networks should remain representable.
6. Verify BSSID is shown and selectable.
7. Select an exact AP/BSSID and enter `TARGET`.
8. Rotate the directional antenna and verify `LIVE`, `AVG`, and `PEAK` react to direction.
9. Set `REF` and verify `DELTA REF` changes consistently while aiming.

## Failure capture

If a HardFault/Guru screen occurs, record a photo of the complete screen and especially:

- `PC`
- `LR`
- `R12`
- all other visible registers
- exact action immediately before the failure: app launch, SCAN, AP selection, TARGET, REF, etc.

Do not call Fix6 hardware-proven until the user explicitly reports the real-device result.

## RF connector reminder

Use the HackRF `ANTENNA` SMA for the directional antenna. The other SMA is CLK IN/OUT, not an RF antenna input.
