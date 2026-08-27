# Fix8w OFDM DATA robustness batch report

| Capture | STF | LTF | CFO Hz | SIGNAL metric | RATE | LENGTH | hard metric | hard SVC | hard FC | hard FCS | best soft | soft metric | soft SVC | soft FC | soft FCS | EVM mean/max | clip |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---|---|---|---:|
| WAIM_007.C8 | 99.0% | 39.9% | 843 | 6 | 24 | 56 | 117 | 3 | 0xdad5 | False | q5_norm | 618 | 3 | 0x1acb | False | 104.2/195.3% | 3.370% |
| WAIM_008.C8 | 93.8% | 35.6% | -2135 | 4 | 12 | 56 | 123 | 2 | 0x9d5b | False | q5_norm | 964 | 4 | 0x23bf | False | 89.1/91.9% | 5.295% |
| WAIM_009.C8 | 99.9% | 66.9% | 1471 | 3 | 24 | 56 | 123 | 4 | 0x36a8 | False | q5_norm | 626 | 4 | 0xe46f | False | 78.7/89.5% | 3.305% |
| WAIM_010.C8 | 100.0% | 43.2% | 27 | 3 | 24 | 56 | 120 | 2 | 0x5094 | False | q5_norm | 596 | 1 | 0x0094 | False | 89.0/104.8% | 3.373% |
| WAIM_011.C8 | 99.9% | 63.6% | -11777 | 3 | 6 | 583 | 1178 | 3 | 0xb5a9 | False | q5_norm | 4028 | 3 | 0xb5a9 | False | 107.0/225.0% | 21.330% |
| WAIM_012.C8 | 99.8% | 60.8% | -10851 | 2 | 6 | 454 | 911 | 3 | 0xd70b | False | q5_norm | 3628 | 3 | 0x4f0b | False | 101.7/135.7% | 16.290% |
| WAIM_013.C8 | 99.7% | 73.8% | 2320 | 0 | 6 | 46 | 98 | 4 | 0xba7d | False | q5_norm | 580 | 4 | 0xfa7d | False | 99.8/134.8% | 5.915% |
| WAIM_014.C8 | 99.9% | 44.6% | 300 | 4 | 24 | 56 | 120 | 3 | 0x13d3 | False | q5_norm | 692 | 2 | 0x970f | False | 65.7/112.7% | 3.900% |
| WAIM_015.C8 | 99.9% | 48.7% | -6686 | 1 | 6 | 121 | 249 | 3 | 0xacc5 | False | q5_norm | 1836 | 3 | 0x2cc5 | False | 98.8/128.2% | 15.920% |
| WAIM_016.C8 | 80.4% | 66.1% | -7909 | 0 | 6 | 56 | 33 | 0 | 0x0094 | False | q5_norm | 106 | 0 | 0x0094 | False | 47.4/88.3% | 0.058% |
| WAIM_017.C8 | 99.8% | 69.3% | -10824 | 2 | 24 | 56 | 121 | 2 | 0x8991 | False | q5_norm | 672 | 0 | 0xbd6c | False | 45.7/51.0% | 3.155% |

## Batch outcome

FCS recovered by at least one soft variant: none.

Per-symbol EVM, pilot CPE, residual phase, channel drift, changed decoded bits, and weakest coded-bit locations are preserved in `fix8w_data_report.json`.
