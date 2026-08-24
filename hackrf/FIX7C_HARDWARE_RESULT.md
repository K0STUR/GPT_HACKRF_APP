# WiFi AIM Fix7c — real hardware result

Date: 2026-08-24

Device:
- HackRF One + PortaPack
- stock Mayhem `n_260808`
- upstream tag `nightly-tag-2026-08-08`
- upstream commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`

Tested artifact SHA-256:
`f511aeae4abf4806e74d21c25fd744cfd38e3c0e4fb8c813fdc263db229c6b74`

## Observed result

Fix7c launches successfully on the real device. No HardFault was observed.

After a complete SCAN the screen showed exactly:

`Done 0AP C10 D0`

The RF/RSSI activity bar remains live.

## Interpretation

- `C10` proves the M4 detector/capture path fired and completed ten capture attempts during the scan.
- `D0` proves none of those captures completed the current Wi-Fi PHY decoder.
- `0AP` is therefore expected because no decoded Beacon/Probe Response reached the AP parser/report path.
- The current frontier is no longer loader/core ABI and no longer simply 'capture never starts'. It is capture content / Wi-Fi preamble recognition / PHY decode.

## Next diagnostic

Fix8a adds a decoder-independent raw-IQ preamble probe for each completed capture:
- `16` — normalized 16-sample repetition score/hit, useful for legacy OFDM STF-like structure;
- `64` — normalized 64-sample repetition score/hit, useful for the repeated legacy L-LTF pair;
- `B` — Barker-11 despread score/hit for DSSS.

The existing Wi-Fi decoder remains unchanged in Fix8a. This separates:
1. captures that visibly contain Wi-Fi-like preamble structure but fail the decoder, from
2. captures that are RF bursts/noise/packet fragments without usable preamble structure.

Do not return to Fix5-style ABI rebasing unless a future hardened audit actually fails.
