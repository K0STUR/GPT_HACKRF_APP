# Fix8v-DIAG hardware handover

Date: 2026-08-27

Branch: `wifi-aim-fix8v-reliability-profiler`

Pull request: [#28](https://github.com/K0STUR/GPT_HACKRF_APP/pull/28) (draft; do not merge before further hardware validation)

This directory is the self-contained handover for the first Fix8v-DIAG hardware
profiling session. It preserves the original one-shot IQ capture, metadata, all
nine screen photographs, offline measurements, and the current engineering
verdict.

## Start here

- [Hardware verdict](HARDWARE_VERDICT.md) — consolidated interpretation and next steps.
- [WAIM_006 raw analysis](WAIM_006_RAW_ANALYSIS.md) — STF/LTF, spectrum, trigger placement, and golden comparison.
- [Energy-trigger regression](WAIM_006_ENERGY_REPORT.md) — full-block versus shadow 256/128 results.
- [Machine-readable decode summary](WAIM_006_DECODE_SUMMARY.json).
- Original capture: [WAIM_006.C8](WAIM_006.C8) and [WAIM_006.TXT](WAIM_006.TXT).

## Capture integrity

The files were copied from the SD card before analysis. The repository copies
have these SHA-256 hashes:

| File | Bytes | SHA-256 |
|---|---:|---|
| `WAIM_006.C8` | 40,000 | `2634F8D201B6CA11F81418F8DD27CFAEC8B201BBE1D80BDAF89F75AA6372666F` |
| `WAIM_006.TXT` | 251 | `F6D44C437EE7490D10FBA7615A4A7EC9F95A9813B3AFCCED47E321B25CA5B95D` |

`WAIM_006.C8` contains 20,000 complex RawS8 samples in interleaved `I,Q`
order. Its metadata reports 20 MS/s, CH8/2447 MHz, LNA 32 dB, VGA 32 dB,
RF amp off, LTF position 3385, and CFO +814 Hz.

## Screen transcription

| Channel/page | Energy | Shadow 256 | Shadow 128 | STF | LTF | Later stages | Final AP |
|---|---:|---:|---:|---:|---:|---|---:|
| CH1 COUNT | 52 | 213 | 340 | 7 | 0 | all zero | 0 |
| CH7 COUNT | 92 | 105 | 106 | 23 | 0 | all zero | 1 |
| CH8 COUNT | not supplied | not supplied | not supplied | at least 20 before freeze | at least 20 before freeze | `R/N/D/M=19/2/1/0` in TXT | 0 in photographed run |

Rejected-capture pages:

| Channel | N | STF min/avg/max | LTF min/avg/max | CFO min/avg/max Hz | Clipped components | Displayed clip % |
|---:|---:|---|---|---|---:|---:|
| 1 | 52 | 10/63/100 | 0/0/5 | 0/0/0 | 12,701 | 0.6% |
| 7 | 91 | 10/64/100 | 0/2/6 | 0/0/0 | 6,459 | 0.1% |
| 8 | 105 | 6/57/100 | 0/27/95 | -11,097/513/+12,074 | 17,504 | 0.4% |

Accepted-capture pages show CH1 `N=0`, CH7 `N=1` with STF 25 and LTF 0,
and CH8 `N=0`. The CH7 AP is the legacy DSSS fallback: its internal stages are
not represented by the OFDM counters. This is an instrumentation gap, not an
OFDM decode with a missing LTF.

Photographic evidence:

- CH1: [COUNT](photos/CH1_COUNT.jpg), [REJECTED](photos/CH1_REJECTED.jpg), [ACCEPTED](photos/CH1_ACCEPTED.jpg)
- CH7: [COUNT](photos/CH7_COUNT.jpg), [REJECTED](photos/CH7_REJECTED.jpg), [ACCEPTED A](photos/CH7_ACCEPTED_A.jpg), [ACCEPTED B](photos/CH7_ACCEPTED_B.jpg)
- CH8: [REJECTED](photos/CH8_REJECTED.jpg), [ACCEPTED](photos/CH8_ACCEPTED.jpg)

## WAIM_006 decisive results

- Offline STF is 98.7% at sample 3209 and absolute LTF-pair score is 85.4%.
- LTF is at sample 3385, or +1337 after the 2048-sample pretrigger boundary.
- LTF repetition coherence is 97.5%; BW90 is 16.0 MHz. This is a genuine
  20 MHz OFDM transmission, not a boundary false lock.
- Trigger full-block power is 966.2 versus pretrigger mean 17.2. The current
  full-block trigger did not miss or endanger this packet.
- SIGNAL decodes perfectly: metric 0, 6 Mbit/s, LENGTH 118, valid parity,
  reserved bit, and tail.
- DATA reaches Viterbi with metric 185, but minimum SERVICE distance is 3
  (admission is at most 2) and the resulting FC is `0x4cf7`, which is not a
  valid AP frame.
- A focused 153-candidate sweep over CFO +/-2 kHz and timing +/-8 samples,
  constrained to the confirmed SIGNAL, does not improve SERVICE below 3 or
  recover a valid MAC frame. Small I/Q orientation and FFT-bin sweeps also fail.

## Current verdict

Two independent loss mechanisms are present:

1. CH1/CH7 are dominated by energy captures without a valid OFDM LTF.
   Enabling max/256 or max/128 now would sharply increase capture load without
   evidence of useful OFDM admissions; no production trigger change is justified.
2. WAIM_006 proves that Fix8u's expanded search and STF/LTF synchronization
   work for a real packet beyond the old sample-2200 limit. This capture fails
   after a perfect SIGNAL, in DATA hard decisions/FEC/descrambling before a
   valid SERVICE/MAC result.

Clipping is not the primary cause at the tested gains. Do not loosen SERVICE or
MAC gates based on this capture: the rejected payload remains structurally
invalid.

## Recommended continuation

1. Keep the Fix8u PHY synchronization and the Fix8t one-shot C8 mechanism.
2. Add shadow-only STF/LTF outcome counters, so max/256 is judged by useful
   admissions rather than raw trigger count.
3. Add explicit DSSS profiler counters.
4. Capture several more CH8 packets that reach DATA/stage 7.
5. Compare hard-decision versus soft-decision DATA/Viterbi offline, while
   preserving the existing SIGNAL, SERVICE, and MAC validity gates.

## Reproduction

From the repository root, using Python with NumPy:

```text
python hackrf/tools/analyze_fix8u_c8.py hackrf/analysis/fix8v_hardware_2026-08-27 --output <output-directory>
python hackrf/tools/test_fix8v_energy_trigger.py --captures hackrf/analysis/fix8v_hardware_2026-08-27 --false-trials 2000
```

The analyzer now derives its synchronization verdict from the supplied
captures. DATA/SERVICE/MAC interpretation remains in `HARDWARE_VERDICT.md`.

## Build state

Fix8v-DIAG hardened build `n_260808` passed ABI/static checks with zero core
symbol drift, zero unresolved/ambiguous symbols, checksum zero, and all offline
regressions green. `A_WiFiAIM_Fix8v_DIAG.ppma` is 31,096 bytes; SHA-256:
`585B9EC41D25EFD51D93F23707A27A8C3F5446CD906CE32E5BDC878E5408B69C`.

PR #28 remains a draft. PR #27 remains unmerged.
