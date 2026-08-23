# HackRF / PortaPack — hardware and RF notes

## HackRF board
The user's HackRF One is an early/classic board (around 2014 era or a faithful clone):
- classic micro-USB;
- expansion headers P20/P22/P28;
- upper SMA = `ANTENNA` RF port;
- lower SMA connectors = `CLK IN` / `CLK OUT` and must not be used as antenna ports.

PortaPack H4/H4M electrical compatibility with the old board was considered acceptable; enclosure cutout/mechanics may differ between old micro-USB HackRF and some newer USB-C clone cases.

## Mayhem / PortaPack
Current device firmware displayed: `n_260808`.

Exact project target:
- tag `nightly-tag-2026-08-08`;
- commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`.

External `.ppma` apps are version-coupled. A build for a different nightly was correctly rejected as `outdated`.

## HackRF useful RF facts
Official/used project assumptions:
- frequency range roughly 1 MHz to 6 GHz;
- 50 ohm RF port;
- 2–20 MS/s complex sample rates;
- 8-bit ADC/DAC;
- half-duplex.

Input safety: official HackRF guidance treats around -5 dBm as the safe maximum RF input specification. Do not connect strong transmitters/PA outputs directly to the RF input.

Receive gain controls:
- RF AMP: off or roughly +11 dB;
- IF/LNA: 0–40 dB in 8 dB steps;
- baseband/VGA: 0–62 dB in 2 dB steps.

Conservative starting point used in discussions:
- RF AMP OFF;
- LNA/IF ~8–16 dB near strong Wi-Fi, or 16 dB general start;
- VGA/baseband ~8–16 dB near strong Wi-Fi, or 16 dB general start.

For directional comparisons, NEVER change gains between reference and comparison unless REF is reset.

## Wi-Fi spectrum notes
2.4 GHz centre frequencies:
- CH1 2412 MHz
- CH2 2417
- CH3 2422
- CH4 2427
- CH5 2432
- CH6 2437
- CH7 2442
- CH8 2447
- CH9 2452
- CH10 2457
- CH11 2462
- CH12 2467
- CH13 2472

Wi-Fi appears as a broad, bursty approximately 20 MHz signal rather than a thin carrier line.

HackRF max 20 MS/s is only just enough for one nominal 20 MHz Wi-Fi channel. Edge roll-off/filtering means full-channel absolute power is not perfectly calibrated. For this project, target-frame relative level and DELTA REF matter more than absolute channel-integrated dBm.

## Existing stock tools
For quick RF visualisation on stock Mayhem:
- `Receive -> Looking Glass`, Wi-Fi/BT preset when available;
- Signal Hunter can be useful for ranges/thresholds.

On a PC:
- SDR++ can visualise a single 20 MHz Wi-Fi channel;
- `hackrf_sweep -f 2400:2500 -w 1000000 -l 16 -g 16` was suggested for repeatable relative spectrum sweeps.

These tools do NOT replace SSID/BSSID decoding for the final antenna-alignment objective.

## External broadband amplifier findings
One evaluated board: OpenSourceSDRLab-style `50M-6GHz 20 dB` USB-powered gain block.
Typical seller figures discussed:
- ~19.5–20 dB gain;
- 50 MHz–6 GHz;
- ~+20/+21 dBm output P1dB;
- 5 V USB supply;
- about 85 mA in official listing.

Noise figure was not numerically specified, so it should be treated as a cheap broadband gain block, not assumed to be a true low-noise first-stage LNA.

Another generic product family offered 10/20/30/40/50 dB gain from 10 MHz–6 GHz. Recommendation was 20 dB as safest universal choice; 40/50 dB is excessive for a universal HackRF accessory.

Suggested strong-signal RX chain:
`antenna -> band-pass filter -> ~20 dB amp -> 6/10 dB attenuator -> HackRF`.

In a quiet weak-signal environment, putting a real low-noise LNA before a lossy filter may improve system NF, but filtering before a broadband gain block protects its linearity in urban RF environments.

Desired dedicated LNA metrics if buying later:
- NF <1 dB at sub-GHz/2.4 GHz where practical;
- NF <1.5 dB at 5.8 GHz;
- gain 15–20 dB;
- P1dB >10 dBm;
- OIP3 >20 dBm, preferably >30 dBm in crowded RF environments.

At 5.8 GHz, PCB/SMA/coax loss is especially important; a dedicated 5–6 GHz LNA with published NF/S21/P1dB/OIP3 is preferable to a generic ultra-wideband board.

## Other PortaPack ecosystem findings
Mayhem supports external `.ppma` and standalone `.ppmp` apps on SD card under `/APPS`. App binary compatibility must match firmware build/version.

MayhemHub / HackRF.app exists for browser-based screen/control/file/update workflows, but it is not a third-party app store.

ESP32 MDK exists and can add Wi-Fi/Bluetooth/UART/SPI/I2C/GPIO to PortaPack, but it is intentionally NOT the main solution here because the user requires the directional antenna measurement to use HackRF's own RF SMA.

A community `mdk-predator` repo appeared to advertise Wi-Fi SSID/channel/security features, but its own GitHub metadata stated that it did not work on the MDK and contained hallucinated AI features. Do not treat it as a usable dependency.