# WiFi AIM Offline PHY Harness

Purpose: validate the exact production `wifi_aim_phy.cpp` against independently generated IEEE 802.11 legacy baseband IQ before any further PortaPack OTA experiments.

The CI job compiles the production decoder as a native Linux executable and checks vectors produced by `cloud9477/gr-ieee80211`'s Python PHY generator. The first suite covers all eight legacy OFDM rates plus CFO, AWGN and simple multipath sweeps.

Important methodology rule: a new OTA PHY fix should not be sent to hardware until its failure mode can be reproduced here or on a saved real HackRF IQ capture.

Outputs are `results.csv`, `results.json`, `summary.json` and the complete console log as a GitHub Actions artifact.
