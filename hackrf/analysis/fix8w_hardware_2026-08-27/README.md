# Fix8w-DIAG: OFDM DATA robustness and DSSS audit handover

Date: 2026-08-27

Branch: `wifi-aim-fix8v-reliability-profiler`

Pull request: [#28](https://github.com/K0STUR/GPT_HACKRF_APP/pull/28), draft; do not merge before hardware validation.

This directory is the complete handover for CH8 captures `WAIM_007` through
`WAIM_017`. All captures were made at 2447 MHz, LNA 32 dB, VGA 32 dB, RF amp
off, and 20 MS/s. Source and preserved-copy SHA-256 hashes matched for all 22
files; the manifest is in [CAPTURE_SHA256SUMS.txt](CAPTURE_SHA256SUMS.txt).

## Artifacts

- [Compact machine-readable DATA report](fix8w_data_report.json): per-symbol
  EVM, pilot CPE/coherence, residual phase, channel drift, weak coded bits,
  hard/soft bit changes, decoded PSDUs, and every experiment result.
- [Batch table](fix8w_data_report.md) and
  [CSV summary](fix8w_data_summary.csv).
- [DSSS audit](fix8w_dsss_audit.md) and
  [machine-readable DSSS results](fix8w_dsss_audit.json).
- Original `WAIM_007.C8/TXT` through `WAIM_017.C8/TXT` in this directory.

## OFDM batch result

The reference soft path in the table is normalized five-bit max-log LLR. Hard
metrics cover the full signaled PSDU offline; `baseline.data_metric` in the JSON
also preserves the current firmware's bounded-prefix metric.

| Capture | STF | LTF | CFO Hz | SIGNAL metric | Rate | Length | hard metric/SVC/FC | hard end | q5 soft metric/SVC/FC | soft end | FCS any variant | EVM mean/max | clip |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---:|
| 007 | 99.0% | 39.9% | +843 | 6 | 24 | 56 | 117/3/`0xdad5` | SERVICE reject | 618/3/`0x1acb` | SERVICE reject | no | 104.2/195.3% | 3.370% |
| 008 | 93.8% | 35.6% | -2135 | 4 | 12 | 56 | 123/2/`0x9d5b` | protocol reject | 964/4/`0x23bf` | SERVICE reject | no | 89.1/91.9% | 5.295% |
| 009 | 99.9% | 66.9% | +1471 | 3 | 24 | 56 | 123/4/`0x36a8` | SERVICE reject | 626/4/`0xe46f` | SERVICE reject | no | 78.7/89.5% | 3.305% |
| 010 | 100.0% | 43.2% | +27 | 3 | 24 | 56 | 120/2/`0x5094` | control/not management | 596/1/`0x0094` | control/not management | no | 89.0/104.8% | 3.373% |
| 011 | 99.9% | 63.6% | -11777 | 3 | 6 | 583 | 1178/3/`0xb5a9` | SERVICE reject | 4028/3/`0xb5a9` | SERVICE reject | no | 107.0/225.0% | 21.330% |
| 012 | 99.8% | 60.8% | -10851 | 2 | 6 | 454 | 911/3/`0xd70b` | SERVICE reject | 3628/3/`0x4f0b` | SERVICE reject | no | 101.7/135.7% | 16.290% |
| 013 | 99.7% | 73.8% | +2320 | 0 | 6 | 46 | 98/4/`0xba7d` | SERVICE reject | 580/4/`0xfa7d` | SERVICE reject | no | 99.8/134.8% | 5.915% |
| 014 | 99.9% | 44.6% | +300 | 4 | 24 | 56 | 120/3/`0x13d3` | SERVICE reject | 692/2/`0x970f` | protocol reject | no | 65.7/112.7% | 3.900% |
| 015 | 99.9% | 48.7% | -6686 | 1 | 6 | 121 | 249/3/`0xacc5` | SERVICE reject | 1836/3/`0x2cc5` | SERVICE reject | no | 98.8/128.2% | 15.920% |
| 016 | 80.4% | 66.1% | -7909 | 0 | 6 | 56 | 33/0/`0x0094` | control/not management | 106/0/`0x0094` | control/not management | no | 47.4/88.3% | 0.058% |
| 017 | 99.8% | 69.3% | -10824 | 2 | 24 | 56 | 121/2/`0x8991` | protocol reject | 672/0/`0xbd6c` | reserved type/not management | no | 45.7/51.0% | 3.155% |

No hard path, reference soft path, or experimental soft variant recovered a
valid FCS. No decoded byte prefix contained a valid earlier embedded FCS either.

## Experiments completed

Each capture was evaluated with 54 configurations, 594 batch trials total:

- max-log soft Viterbi quantized to 3, 4, and 5 bits;
- raw versus normalized LLR;
- per-subcarrier LTF-noise weighting;
- pilot-derived CPE correction enabled and disabled;
- residual CFO offsets from -2 kHz to +2 kHz;
- FFT timing offsets -8 through +8 samples;
- amplitude normalization;
- optional decision-directed phase correction;
- decision-directed channel update at alpha 0.10 and 0.25;
- unconstrained versus state-zero traceback experiment;
- standard 127-polarity sequence versus the firmware's 64-entry prefix.

None produced a valid FCS. Improvements in SERVICE distance, FC appearance, or
EVM were not stable enough to constitute a decoder fix.

### Decoder-question verdicts

- **STF/LTF/search geometry:** working; all captures have admitted SIGNAL and
  the batch provides no reason to modify Fix8u synchronization.
- **Pilot indexing:** the standard sequence has period 127. Fix8v stores 64
  entries, but its maximum 96-byte AP prefix uses at most 33 DATA symbols at
  6 Mbit/s, so the wrap cannot affect the present firmware prefix. Full-length
  offline decoding used period 127; forcing period 64 did not recover FCS.
- **CPE:** the per-symbol pilot correction is active and useful. For WAIM_016,
  disabling it increases mean EVM from 47.4% to 93.0%. It is not the failure.
- **Residual CFO/timing:** the complete sweeps recover no FCS. Small EVM or
  SERVICE improvements do not remain consistent across captures.
- **Channel update/amplitude/decision phase:** some EVM values improve, but
  decoded payload/FCS does not. A firmware change would be speculative.
- **16-QAM scaling:** exercised by five 24 Mbit/s captures; no soft variant
  recovers FCS. The batch contains no 64-QAM packet, so 64-QAM is golden-tested
  only and cannot be judged from this hardware set.
- **Depuncturing:** all hardware rates here are rate-1/2 and do not puncture.
  Soft erasures remain covered by the 8-rate golden regression, not this batch.
- **Traceback:** forcing state zero does not recover FCS. Prefix DATA should
  remain unconstrained; encoder TAIL is followed by PAD and does not imply the
  final captured state is zero.
- **want_bits/symbol count/tail:** offline decoding uses the full signaled PSDU
  and all available symbols. The corrected standard golden generator passes
  hard plus normalized 4/5-bit FCS for 8/8 rates. Firmware's 96-byte cap is an
  intentional AP-prefix limit, not the cause for 46/56-byte captures.
- **SERVICE/MAC gates:** must remain unchanged. Relaxing them does not repair FCS.

## WAIM_016 decisive evidence

WAIM_016 is the cleanest candidate and confirms that the failure is in the RF
content near the end of the burst, not a global DATA phase/FEC convention:

- SIGNAL metric 0, 6 Mbit/s, LENGTH 56, SERVICE distance 0.
- Hard and normalized-soft output are identical for the first 46 PSDU bytes.
- Those bytes form a plausible `0x0094` control/Block Ack header and bitmap.
- DATA symbols 0..15 have power about 132..157 and EVM about 33..47%.
- At symbol 16, power collapses to 25, then 18..25 for symbols 17..19.
- EVM simultaneously rises to 84..88%; pilot coherence falls as low as 27.9%.
- Hard/soft differences are concentrated in symbols 16..19: 17, 12, 12, and
  2 decoded-bit changes respectively.
- The last ten PSDU bytes, including the signaled FCS, occupy this degraded
  tail. No candidate length inside either decoded byte stream has a valid FCS.
- CPE, timing, CFO, channel update, and traceback variants preserve the header
  but cannot reconstruct the missing/degraded tail.

This is consistent with a truncated/collided burst or a valid SIGNAL associated
with RF energy that does not remain coherent for the complete declared DATA
duration. It is not evidence for changing the Viterbi, descrambler, or gates.

## DSSS audit and diagnostic patch

The Fix8v fallback was reviewed and reproduced offline:

- long-preamble 1 Mbit/s Beacon and Probe Response: pass;
- timing sweep: 20/20 sample phases pass;
- long-preamble 2 Mbit/s: header is found, then rejected because SIGNAL must be
  `0x0A`; `0x14` payload decoding is not implemented;
- short preamble/SFD: unsupported;
- PLCP CRC: not validated;
- LENGTH is interpreted only as the 1 Mbit/s microsecond count divided by 8;
- self-synchronizing descrambler and payload offset are correct for generated
  long-preamble 1 Mbit/s frames.

Fix8w adds diagnostic counters only, not a new DSSS decoder: admission, Barker,
timing, differential decode, descramble, PLCP, payload, MAC type, Beacon/Probe,
SSID, and final AP. They use diagnostic subtype `0xF8` inside the existing
`WireApReport`; its layout and stock message ABI remain unchanged. Repeatedly
pressing ACC alternates the accepted-capture and DSSS pages.

## Firmware decision

- No OFDM DATA algorithm change is justified by this batch.
- Fix8u synchronization, Fix8s demapper/FEC fixes, and Fix8t one-shot C8 remain
  unchanged.
- SERVICE and MAC validity gates remain unchanged.
- The only firmware delta is DSSS stage instrumentation requested for the next
  hardware profiler run.
- No merge before hardware testing.

## Exact next experiment

Use a controlled transmitter plus a simultaneous monitor-mode/reference capture
so the exact transmitted PSDU and FCS are known. Send repeated 6 Mbit/s frames
of known lengths 32, 46, and 56 bytes on a quiet channel, and retain only C8s
whose per-symbol power remains present through the declared last DATA symbol.
Capture at both 32/32 and a lower-gain setting to separate clipping from burst
collision. With known bits, the existing weak-coded-bit and per-symbol reports
can produce a true BER/error map; without that ground truth, further soft/FEC
tuning would be guesswork.

Separately, run the DSSS profiler page against a known 1 Mbit/s long-preamble AP
and a 2 Mbit/s/short-preamble source to confirm the exact hardware drop stages.

## Reproduction

From the repository root, with Python and NumPy:

```text
python hackrf/tools/analyze_fix8w_data.py hackrf/analysis/fix8w_hardware_2026-08-27 --output <output-directory>
python hackrf/tools/audit_fix8w_dsss.py --output <output-directory>
python hackrf/tools/test_fix8w_data_robustness.py
python hackrf/tools/test_fix8w_dsss_contract.py
```
