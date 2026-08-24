# Fix8b real-hardware result

Date: 2026-08-24
Device: PortaPack / HackRF, stock Mayhem `n_260808`

Observed after one full SCAN:

- `Done 0AP C26 D0 M13`
- `OF L/H/V/P 2/2/2/1`
- `OF R/N/D/M 0/0/0/0`
- `LQ 68 R 8 N 0`
- `HIT 16/64/B 22/20/0`
- `Q 16/64/B 100/100/55`
- `M4 CH: 13`

Interpretation:
- M0<->M4 channel control is healthy through channel 13.
- 26 captures occurred.
- 22 captures showed strong 16-sample OFDM-like repetition and 20 showed strong 64-sample repetition; peak quality reached 100/100.
- Only 2 captures passed the current ideal-template `find_ltf()` gate.
- Both LTF-passing captures reached SIGNAL hard demod and SIGNAL Viterbi; one passed SIGNAL parity.
- The last parity-valid SIGNAL reported raw RATE parser value `8`, which is a valid legacy OFDM RATE code corresponding to 48 Mb/s, currently unsupported by the 6/12/24-only decoder. This is evidence that real SIGNAL/Viterbi decoding is functioning, not a random near-miss.
- No capture reached a currently supported RATE/LENGTH/DATA/MAC result, hence D=0/AP=0.

Main conclusion:
The dominant bottleneck is now the L-LTF synchronizer. Strong channel-invariant 64-sample repetition is present in many captures, while the current matched filter against an ideal undistorted L-LTF accepts only 2/26. Next candidate Fix8c should replace the hard ideal-template gate with repetition-based LTF timing while preserving CFO/channel estimate and downstream decoder logic.
