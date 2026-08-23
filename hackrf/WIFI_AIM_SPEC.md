# WiFi AIM — functional specification

## Purpose
Use the directional antenna connected to the HackRF `ANTENNA` SMA to find the best roof position and pointing direction for one exact Wi-Fi AP.

## Non-negotiable requirement
SSID discovery must exist. After discovery the selected AP must be locked by BSSID so two APs with the same SSID can still be distinguished.

## Main flow
`SCAN -> choose SSID/BSSID -> TARGET -> AIM -> REF -> rotate/move antenna -> maximise DELTA REF`

## SCAN mode
Initial target: 2.4 GHz only.
- channels CH1–CH13;
- centre frequencies 2412, 2417, ... 2472 MHz;
- dwell roughly 0.3–0.5 s/channel initially;
- decode Beacon and Probe Response frames;
- collect at least: SSID, BSSID, channel, last/average relative frame level;
- hidden SSID may display `<hidden>` and update later if a Probe Response reveals it.

Suggested list display:
```
AP 1/7: DOM_WIFI
BSSID: A4:5E:60:12:34:56
CH: 6    last: -63 dBr
```

## TARGET mode
After target selection:
- tune only to target channel;
- store selected BSSID;
- use frames matching the BSSID for target-specific statistics;
- continue showing target identity visibly;
- do not substitute total channel energy for target-frame level without labelling it separately.

Required target metrics:
- LIVE target level;
- AVG target level;
- PEAK target level;
- DELTA REF;
- time since last target frame / `TARGET LOST` state.

Useful optional second metric:
- total channel power, shown separately from target-frame power.

## Decoder modes
`OFF` — fastest RF/channel meter; no SSID/BSSID verification.

`AUTO` — default. Periodically turn the Wi-Fi decoder on just long enough to verify/measure the selected BSSID, then return to lighter measurement. Development design used approximately 300 ms ON / 200 ms lighter phase; adjust after real test.

`ON` — continuous decode, primarily for discovery/debugging/initial target confirmation.

## REF / directional aiming
When user presses REF, store a stable target average. Display:
`DELTA REF = current_avg - reference_avg`.

Positive delta = better than reference. Negative = worse.

Keep RF gain settings unchanged while comparing positions. If gains change, invalidate or clearly warn that REF is no longer comparable.

## Future audio mode
Hands-free roof aiming:
- absolute mode: stronger target -> higher pitch/faster beeps;
- reference mode: tone encodes delta from REF.

## PHY scope
V1:
- 802.11b DSSS DBPSK 1 Mb/s;
- legacy OFDM 6, 12, 24 Mb/s;
- enough MAC parsing for Beacon/Probe Response, SSID, BSSID, channel.

Do not implement WPA decryption, TCP/IP or payload capture. They are unnecessary for this project.

## 5 GHz
HackRF can tune to 5 GHz, but PortaPack real-time decoding and 20 MHz instantaneous bandwidth make this a second-stage feature. Do not block 2.4 GHz completion on 5 GHz.

For 40/80 MHz later, sequential 20 MHz windows may be needed; they are not simultaneous and burst timing can bias comparisons.

## Relative power caveat
HackRF is not a calibrated field-strength meter. Values should be presented as relative `dBr`/arbitrary dB-like level unless an explicit calibration process is added. The key field-use output is `DELTA REF` with fixed gain/antenna/cable configuration.
