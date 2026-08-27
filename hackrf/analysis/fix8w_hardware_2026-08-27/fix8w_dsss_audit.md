# Fix8w DSSS fallback audit

| Case | admission | Barker | timing | differential | descramble | PLCP | payload | MAC | Beacon/Probe | SSID | final AP | failure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long_1M_beacon | True | True | True | True | True | True | True | True | True | True | True | None |
| long_1M_probe_response | True | True | True | True | True | True | True | True | True | True | True | None |
| long_2M_beacon | True | True | True | True | True | True | False | False | False | False | False | unsupported_plcp_rate |
| long_2M_probe_response | True | True | True | True | True | True | False | False | False | False | False | unsupported_plcp_rate |
| short_1M_beacon | True | True | True | True | True | False | False | False | False | False | False | sfd_or_plcp |

Long-preamble 1 Mbit/s timing sweep: 20/20 sample phases pass.

## Audit findings

- The current fallback is long-preamble, 1 Mbit/s DBPSK only.
- SIGNAL must equal `0x0A`; a valid long-preamble 2 Mbit/s (`0x14`) frame is rejected before payload.
- Short preamble/SFD and its 2 Mbit/s header modulation are unsupported.
- PLCP CRC is not checked. LENGTH is assumed to be a 1 Mbit/s microsecond count and divided by eight.
- The Fix8v baseline exposed only attempted/success. The Fix8w diagnostic patch adds all eleven stage counters over a new diagnostic subtype without changing WireApReport layout.
- The self-synchronizing descrambler and payload offset are correct for generated long-preamble 1 Mbit/s Beacon and Probe Response frames.
