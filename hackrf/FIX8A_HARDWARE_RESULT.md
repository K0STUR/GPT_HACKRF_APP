# WiFi AIM Fix8a — real hardware result

Date: 2026-08-24
Device: HackRF One + PortaPack Mayhem, stock `n_260808`

Observed final screen:
- `Done 0AP C26 D0 M13`
- `HIT 16/64/B 21/21/0`
- `Q 16/64/B 100/100/53`
- `M4 CH: 13`

Interpretation:
- application launch/runtime PASS; no HardFault;
- M0->M4 channel control and M4->M0 telemetry reach channel 13;
- capture detector produced 26 completed capture attempts;
- existing Wi-Fi decoder produced 0 successful decodes;
- 21/26 captures exceeded both OFDM16 and OFDM64 repetition thresholds;
- peak normalized repetition scores were 100/100, while Barker-11 peak was 53 and produced 0 hits;
- therefore the next work is inside the OFDM synchronization/SIGNAL/data decode path, not loader ABI or basic capture triggering.

Important nuance: the raw repetition probe is deliberately decoder-independent and is not by itself proof of an IEEE 802.11 frame (e.g. narrowband periodic signals can also correlate strongly). Fix8b therefore instruments the actual OFDM decoder stages and the ideal L-LTF correlation before changing decoder behavior.

Fix8b stage meanings:
1. L = ideal L-LTF detector passed
2. H = SIGNAL hard demod passed
3. V = SIGNAL Viterbi produced 24 bits
4. P = SIGNAL parity passed
5. R = supported RATE recognized
6. N = valid LENGTH recognized
7. D = DATA Viterbi produced enough prefix bits
8. M = Beacon/Probe MAC prefix parser passed

Fix8b also reports `LQ` = best ideal-LTF correlation score (0..100), raw RATE parser value and decoded LENGTH.
