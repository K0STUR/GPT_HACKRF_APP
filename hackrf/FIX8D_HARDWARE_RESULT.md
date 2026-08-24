# WiFi AIM Fix8d — real hardware result

Date: 2026-08-24
Device: real HackRF One + PortaPack, stock Mayhem `n_260808`

## Result summary
Five full scans were performed. **2 of 5 scans reported `1AP`; 3 of 5 reported `0AP`.** This is the first repeatable end-to-end AP detection in the project.

Representative successful final scan:

```
Done 1AP C28 D1 M13
OF L/H/V/P 24/24/24/11
OF R/N/D/M 4/2/2/0
SQ 78 R 3 N 2276
HIT 16/64/B 16/15/0
Q   16/64/B 100/100/51
```

Representative zero-AP final scan:

```
Done 0AP C26 D0 M13
OF L/H/V/P 24/24/24/16
OF R/N/D/M 10/3/3/0
SQ 71 R 3 N 2396
HIT 16/64/B 25/25/0
Q   16/64/B 100/100/53
```

Progress snapshots also showed, for example:

```
S 5/13 C8 D0 M5
OF L/H/V/P 8/8/8/6
OF R/N/D/M 2/2/2/0
SQ 55 R 13 N 1300
```

and

```
S 8/13 C14 D0 M8
OF L/H/V/P 12/12/12/7
OF R/N/D/M 2/2/2/0
SQ 55 R 15 N 1300
```

## Interpretation
- Fix8c repetition-based LTF synchronization remains strongly hardware-proven: most captures now pass LTF -> SIGNAL hard demod -> SIGNAL Viterbi.
- Fix8d full legacy RATE support worked: `R` progressed substantially beyond the Fix8c baseline (`1`) and can reach `10` in a scan.
- Several captures reach DATA Viterbi (`D` in OFDM stage telemetry), but **OFDM MAC Beacon/Probe count remains `M=0`**.
- Global `Done ... D1` + `1AP` while OFDM `M=0` means the successful AP report came from the **DSSS/802.11b fallback path**, not OFDM.
- Therefore the AP parser/report path itself is capable of succeeding on real hardware.
- Current OFDM frontier is after DATA Viterbi: descrambler / SERVICE validation / frame-control classification / management Beacon/Probe recognition.

## UI issue discovered
Final diagnostic telemetry arrives after `end_scan()` and overwrites the AP/BSSID/channel text fields. Therefore a scan can say `Done 1AP` while the actual discovered SSID/BSSID is hidden by diagnostic lines. Fix8e must preserve AP details after scan.

## Phone reference at the same location
The phone Wi-Fi list showed multiple nearby/fringe networks, including examples:
- `TP-LINK_K`
- `TP-LINK_05D82B`
- `Avatar`
- `ESP_D24E31`
- `fiberway.pl ZK`
- `fiberway.pl_479K`
- `wr1-2G`
- `fiberway.pl_479b`

The phone can also see 5 GHz networks; current WiFi AIM scans only 2.4 GHz channels 1-13. The HackRF antenna may provide directional antenna gain, but the phone has a purpose-built Wi-Fi PHY and may use active scanning, so raw AP counts should not yet be compared as receiver sensitivity.

## Next action
Fix8e:
1. preserve AP/SSID/BSSID/channel display after a successful scan;
2. instrument OFDM post-DATA stages: SERVICE -> frame-control version -> management -> Beacon/Probe -> SSID;
3. expose DSSS attempt/success counters;
4. avoid running the expensive DSSS fallback on captures that already have a parity-valid legacy OFDM SIGNAL, to improve M4 throughput while preserving DSSS for non-OFDM captures.
