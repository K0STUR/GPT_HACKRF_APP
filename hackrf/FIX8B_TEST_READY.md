# WiFi AIM Fix8b — ready for hardware test

Updated: 2026-08-24

## Previous real hardware result — Fix8a
- `Done 0AP C26 D0 M13`
- `HIT 16/64/B 21/21/0`
- `Q 16/64/B 100/100/53`

Interpretation: capture/control path works and 21/26 captures show very strong 16- and 64-sample OFDM-like repetition, but the Wi-Fi decoder still returns zero successful decodes.

## Fix8b purpose
Fix8b does not change decoder decisions. It instruments the current OFDM path to report the maximum stage reached by each capture:
- `L` — L-LTF found
- `H` — SIGNAL hard demod succeeded
- `V` — SIGNAL Viterbi produced 24 bits
- `P` — SIGNAL parity valid
- `R` — RATE recognized
- `N` — LENGTH valid
- `D` — DATA Viterbi succeeded
- `M` — Beacon/Probe parser succeeded

Additional fields:
- `LQ` — best correlation against ideal L-LTF, 0..100
- `R` — latest raw RATE parser value
- `N` — latest decoded PSDU length

## Hardened CI
- run `32704020033`
- job `97361214663`
- artifact ID `9512243932`
- result `PASS`

Verification:
- size `25864`
- memory `0x100844BC`
- entry `0x10084511`
- version `0x86B64C1D`
- tag `WAIM`
- M4 offset `8264`
- shared core symbols `7086`
- core drift `0`
- drift references `0`
- patches `0`
- same-address core refs `80`
- ambiguous `0`
- unresolved `0`
- checksum `0x00000000`
- stock/mod `_Znwj = 0x7ee24`
- SHA-256 `1ee5f5a7aa5e7eb7d4197154d70f73448331d463f43f0950ec2aa60733a44e29`
- `RESULT=PASS`

## Exact next action
Keep stock Mayhem `n_260808`. Copy only `WiFiAIM_n260808_fix8b.ppma` to SD `/APPS`, remove/move older WiFi AIM PPMA files, launch `RX -> WiFi AIM -> SCAN`, then record/photo all of:

- `Done xAP C# D# M#`
- `OF L/H/V/P x/x/x/x`
- `OF R/N/D/M x/x/x/x`
- `LQ xx R xx N xxxx`
- `HIT 16/64/B x/x/x`
- `Q 16/64/B x/x/x`

Do not change detector/capture logic until this test identifies the first failing OFDM stage.
