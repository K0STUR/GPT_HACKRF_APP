# Fix8v energy-trigger regression

The production trigger remains unchanged: full 2,048-sample DMA-block mean with threshold `noise*1.25 + 32`. The 256/128 columns are shadow candidates only.

## Packet detection over all 8 rates and 16 start offsets

| Gain | Packet RMS before gain | Threshold | Full block | Max/256 | Max/128 | Clipped components |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5x | 3.0 | 33.6 | 0.0% | 0.0% | 0.0% | 0.000% |
| 0.5x | 4.5 | 33.6 | 0.0% | 0.0% | 0.0% | 0.000% |
| 0.5x | 6.0 | 33.6 | 0.0% | 0.0% | 0.0% | 0.000% |
| 0.5x | 9.0 | 33.6 | 0.0% | 0.0% | 0.0% | 0.000% |
| 0.5x | 12.0 | 33.6 | 11.7% | 100.0% | 100.0% | 0.000% |
| 0.5x | 18.0 | 33.6 | 64.8% | 100.0% | 100.0% | 0.000% |
| 0.5x | 24.0 | 33.6 | 98.4% | 100.0% | 100.0% | 0.000% |
| 1.0x | 3.0 | 37.8 | 0.0% | 0.0% | 0.0% | 0.000% |
| 1.0x | 4.5 | 37.8 | 0.0% | 0.0% | 0.0% | 0.000% |
| 1.0x | 6.0 | 37.8 | 11.7% | 100.0% | 100.0% | 0.000% |
| 1.0x | 9.0 | 37.8 | 64.8% | 100.0% | 100.0% | 0.000% |
| 1.0x | 12.0 | 37.8 | 97.7% | 100.0% | 100.0% | 0.000% |
| 1.0x | 18.0 | 37.8 | 100.0% | 100.0% | 100.0% | 0.000% |
| 1.0x | 24.0 | 37.8 | 100.0% | 100.0% | 100.0% | 0.000% |
| 2.0x | 3.0 | 54.8 | 2.3% | 85.2% | 97.7% | 0.000% |
| 2.0x | 4.5 | 54.6 | 53.1% | 100.0% | 100.0% | 0.000% |
| 2.0x | 6.0 | 54.7 | 96.1% | 100.0% | 100.0% | 0.000% |
| 2.0x | 9.0 | 54.6 | 100.0% | 100.0% | 100.0% | 0.000% |
| 2.0x | 12.0 | 54.8 | 100.0% | 100.0% | 100.0% | 0.000% |
| 2.0x | 18.0 | 54.7 | 100.0% | 100.0% | 100.0% | 0.000% |
| 2.0x | 24.0 | 54.7 | 100.0% | 100.0% | 100.0% | 0.002% |
| 4.0x | 3.0 | 122.6 | 82.0% | 100.0% | 100.0% | 0.000% |
| 4.0x | 4.5 | 122.0 | 100.0% | 100.0% | 100.0% | 0.000% |
| 4.0x | 6.0 | 122.2 | 100.0% | 100.0% | 100.0% | 0.000% |
| 4.0x | 9.0 | 122.5 | 100.0% | 100.0% | 100.0% | 0.000% |
| 4.0x | 12.0 | 122.4 | 100.0% | 100.0% | 100.0% | 0.003% |
| 4.0x | 18.0 | 122.3 | 100.0% | 100.0% | 100.0% | 0.198% |
| 4.0x | 24.0 | 122.0 | 100.0% | 100.0% | 100.0% | 1.086% |
| 8.0x | 3.0 | 391.9 | 100.0% | 100.0% | 100.0% | 0.000% |
| 8.0x | 4.5 | 391.2 | 100.0% | 100.0% | 100.0% | 0.000% |
| 8.0x | 6.0 | 391.9 | 100.0% | 100.0% | 100.0% | 0.005% |
| 8.0x | 9.0 | 392.1 | 100.0% | 100.0% | 100.0% | 0.228% |
| 8.0x | 12.0 | 390.0 | 100.0% | 100.0% | 100.0% | 1.197% |
| 8.0x | 18.0 | 392.0 | 100.0% | 100.0% | 100.0% | 4.524% |
| 8.0x | 24.0 | 392.4 | 100.0% | 100.0% | 100.0% | 7.227% |

## False-trigger comparison

Rates are per DMA block. At 20 MS/s and 2,048 samples, 0.1% means about 9.8 false triggers/s before STF rejection.

| Gain | Threshold | Full noise | Max/256 noise | Max/128 noise | Full 128-sample impulse | Max/256 impulse | Max/128 impulse |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5x | 33.6 | 0.0000% | 0.0000% | 0.0000% | 0.00% | 0.00% | 0.00% |
| 1.0x | 37.8 | 0.0000% | 0.0000% | 0.0000% | 0.00% | 0.00% | 19.32% |
| 2.0x | 54.7 | 0.0000% | 0.0000% | 0.0000% | 0.00% | 99.17% | 100.00% |
| 4.0x | 122.3 | 0.0000% | 0.0000% | 0.0000% | 0.00% | 100.00% | 100.00% |
| 8.0x | 393.6 | 0.0000% | 0.0000% | 0.1300% | 100.00% | 100.00% | 100.00% |

## Hardware C8 block-power evidence

| Capture | CH | SQ | Trigger full | Trigger max/256 | Trigger max/128 | Pretrigger mean | Clip count | Clip % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| WAIM_006.C8 | 8 | 85 | 966.2 | 1607.8 | 1689.8 | 17.2 | 1 | 0.003% |

## Verdict

- Full-block averaging has a real offset/amplitude blind region, especially for short high-rate packets.
- Max/256 recovers much of that region at low cost in the synthetic sweep.
- Max/128 is more sensitive, but the unchanged threshold increases high-gain noise and short-impulse triggers.
- No subblock trigger is enabled in Fix8v. Hardware profiler counters must measure the candidate/false-reject ratio first.
