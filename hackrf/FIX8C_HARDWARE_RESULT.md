# Fix8c real-hardware result — 2026-08-24

Device: real HackRF One + PortaPack, stock Mayhem `n_260808`.

Final screen after full 13-channel SCAN:

- `Done 0AP C26 D0 M13`
- `OF L/H/V/P 24/24/24/15`
- `OF R/N/D/M 1/0/0/0`
- `SQ 98 R 8 N 3814`
- `HIT 16/64/B 23/22/0`
- `Q 16/64/B 100/100/61`
- `M4 CH: 13`

Interpretation:
- Fix8c repetition-based LTF synchronization is a major hardware success: accepted LTF count increased from Fix8b `2` to Fix8c `24` out of 26 captures.
- SIGNAL hard demod and SIGNAL Viterbi also reached `24`; parity passed on `15` captures.
- Only `1` parity-valid frame reached the then-supported RATE set because Fix8c still supported only legacy OFDM 6/12/24 Mb/s.
- `R=8` is a valid parser representation of legacy OFDM 48 Mb/s, proving that the real RF environment contains rates outside the old 6/12/24 subset.
- `R` and `N` telemetry are independent last-nondefault fields accumulated across the scan and are not guaranteed to describe the same capture.

Phone Wi-Fi scan taken in the same area showed at least these visible SSIDs:
- `TP-LINK_K` (phone marks 2.4/5 GHz)
- `TP-LINK_05D82B`
- `Avatar`
- `ESP_D24E31`
- `fiberway.pl ZK`
- `fiberway.pl_479K`
- `wr1-2G`
- `fiberway.pl_479b`

The phone sometimes sees more networks because the location is near the edge of their coverage. This list is only a reference for later SSID validation; the current HackRF app remains passive and scans channels 1-13 only.

Next engineering step: Fix8d full legacy OFDM rates 6/9/12/18/24/36/48/54 Mb/s with 64-QAM and punctured FEC support.
