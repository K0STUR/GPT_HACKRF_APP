# Fix8v-DIAG hardware verdict

Date: 2026-08-27
Inputs: nine profiler photographs plus `WAIM_006.C8/TXT`.

## Preserved capture

The SD files were copied before analysis to `work/captures/fix8v_hardware`.

- C8 SHA-256: `2634F8D201B6CA11F81418F8DD27CFAEC8B201BBE1D80BDAF89F75AA6372666F`
- TXT SHA-256: `F6D44C437EE7490D10FBA7615A4A7EC9F95A9813B3AFCCED47E321B25CA5B95D`
- Source and copy hashes match.

## Profiler photographs

| Channel | Energy | Shadow/256 | Shadow/128 | STF admissions | LTF admissions | Final AP |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 52 | 213 | 340 | 7 | 0 | 0 |
| 7 | 92 | 105 | 106 | 23 | 0 | 1 |
| 8 | count page not supplied | count page not supplied | count page not supplied | at least 20 before C8 freeze | at least 20 before C8 freeze | 0 in photographed run |

Rejected-capture summaries:

- CH1: N=52, STF 10/63/100, LTF 0/0/5, clip 12,701 components (0.6%).
- CH7: N=91, STF 10/64/100, LTF 0/2/6, clip 6,459 components (0.1%).
- CH8: N=105, STF 6/57/100, LTF 0/27/95, CFO -11,097/513/+12,074 Hz,
  clip 17,504 components (0.4%).

CH7 has one accepted AP despite zero OFDM LTF/SIGNAL/DATA counters. This is the
legacy DSSS fallback, whose internal stages are not represented by the OFDM
pipeline counters. The accepted STF=25/LTF=0 is therefore expected and exposes
an instrumentation gap rather than an impossible OFDM decode.

## WAIM_006

- CH8, LNA=32 dB, VGA=32 dB, RF amp off.
- LTF position 3385: 1,337 samples after the 2,048-sample pretrigger boundary.
- STF 98.7% offline (metadata 99), absolute LTF pair 85.4% (metadata 85).
- CFO +814 Hz; LTF repetition coherence 97.5%.
- BW90 16.0 MHz; spectrum is consistent with a real 20 MHz OFDM transmission.
- Trigger block mean power 966.2 versus pretrigger 17.2; max/256=1607.8,
  max/128=1689.8. This packet was not endangered by the full-block trigger.
- One clipped I/Q component out of 40,000 (0.003%): clipping is irrelevant here.

The frozen cumulative pipeline was `L/H/V/P=20/20/20/20`,
`R/N/D/M=19/2/1/0`. The capture itself decodes offline as:

- SIGNAL Viterbi metric 0;
- RATE 6 Mbit/s, LENGTH 118;
- parity, reserved bit and SIGNAL tail all valid;
- DATA Viterbi reached, metric 185;
- minimum SERVICE distance 3 (firmware admission is <=2);
- decoded FC `0x4cf7`, invalid protocol version/type for an AP frame.

A focused sweep of 153 candidates over CFO +/-2 kHz and timing +/-8 samples,
while retaining the confirmed RATE=6 Mbit/s and LENGTH=118, never improves
SERVICE below 3, never reaches a post stage and never decodes an AP. I/Q
orientation and small FFT-bin sweeps also do not recover the frame. Raising the
SERVICE threshold would not solve this capture because the resulting MAC header
is still invalid.

## Verdict

There are two distinct loss mechanisms:

1. **CH1/CH7 front-end admission:** most production energy captures do not
   contain an admissible OFDM LTF. On CH1, max/256 and max/128 would multiply
   trigger load by 4.1x and 6.5x while current captures already have only 7 STF
   and zero LTF admissions. Blindly enabling either shadow trigger would likely
   increase interference/false-trigger load, especially max/128.
2. **CH8 post-SIGNAL/DATA:** Fix8u search geometry and STF/LTF synchronization
   work. WAIM_006 proves a real packet can have its LTF at 3385, far beyond the
   old 2200 limit. The remaining OFDM failure is after a perfect SIGNAL and
   during hard-decision DATA/FEC/descrambling; it is not energy trigger, limited
   search, I/Q orientation, coarse timing, CFO or clipping.

The old search-geometry defect is confirmed fixed. The test-site unreliability
is now a combination of false/interference captures on some channels and a
separate DATA-path robustness problem on genuine CH8 OFDM packets.

## Recommended next diagnostic step

- Do not change the production trigger yet.
- Add shadow-only STF/LTF outcome counters (not just raw power-hit counters) so
  max/256 can be evaluated by useful admissions rather than trigger volume.
- Add explicit DSSS pipeline/final counters so a legacy AP cannot appear as
  `FINAL AP` with all OFDM stages zero.
- For OFDM, preserve Fix8u sync and capture several more CH8 stage-7 C8 files;
  compare hard versus soft DATA decisions and Viterbi metrics. Do not loosen
  SERVICE or MAC gates based on WAIM_006.
