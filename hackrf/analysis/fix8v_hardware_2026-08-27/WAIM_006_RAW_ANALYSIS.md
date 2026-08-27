# Fix8u RAW IQ comparison

| Capture | CH | LTF | LTF-2048 | max STF | reported LTF pair | loose best LTF | trigger/pre dB | boundary dB | BW90 MHz | flatness | peak/median dB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| WAIM_006.C8 | 8 | 3385 | +1337 | 98.7% @3209 | 85.4% | 85.3% | +17.5 | +16.2 | 16.0 | 0.452 | 11.4 |

## Golden IQ

| Capture | CH | LTF | LTF-2048 | max STF | reported LTF pair | loose best LTF | trigger/pre dB | boundary dB | BW90 MHz | flatness | peak/median dB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| golden-6M | 6 | 1800 | -248 | 99.4% @1640 | 99.6% | 99.6% | +6.6 | +0.0 | 14.7 | 0.331 | 11.0 |
| golden-9M | 6 | 2048 | +0 | 99.4% @1905 | 99.6% | 99.6% | +10.0 | +0.0 | 14.8 | 0.328 | 12.9 |
| golden-12M | 6 | 2200 | +152 | 99.3% @2024 | 99.6% | 99.6% | +15.7 | +5.0 | 14.9 | 0.329 | 11.6 |
| golden-18M | 6 | 2500 | +452 | 99.4% @2310 | 99.6% | 99.6% | +22.5 | +0.2 | 14.8 | 0.339 | 11.9 |
| golden-24M | 6 | 3000 | +952 | 99.6% @2829 | 99.6% | 99.6% | +21.9 | -0.6 | 14.7 | 0.336 | 11.8 |
| golden-36M | 6 | 3500 | +1452 | 99.5% @3380 | 99.6% | 99.6% | +20.3 | +0.7 | 14.7 | 0.307 | 12.6 |
| golden-48M | 6 | 4096 | +2048 | 99.4% @3982 | 99.6% | 99.6% | +14.5 | -1.9 | 14.7 | 0.336 | 13.0 |
| golden-54M | 6 | 4500 | +2452 | 99.5% @4354 | 99.7% | 99.7% | -0.1 | +0.3 | 14.7 | 0.407 | 12.0 |

Thresholds: sustained STF >= 75%; weaker absolute LTF pair >= 30%.

## WAIM_006 verdict

- The old 2200-sample limit was a real search-geometry defect. Golden packets
  with LTF at 2500, 3000, 3500, 4096, and 4500 are valid but cannot be reached
  by the old search.
- WAIM_006 is different from the earlier WAIM_000..003 interference captures:
  it has a sustained 98.7% STF, an 85.4% absolute LTF pair at sample 3385, and
  a 97.5% LTF repetition coherence. It is a genuine OFDM packet found beyond
  the old search boundary.
- Fix8u's expanded search and STF/LTF admission therefore work on this capture.
  The remaining rejection happens later, after a perfect SIGNAL decode and in
  the DATA/SERVICE/MAC path. See `HARDWARE_VERDICT.md` for the decode evidence.
