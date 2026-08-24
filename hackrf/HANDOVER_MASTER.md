# HackRF / PortaPack / WiFi AIM — MASTER HANDOVER

Updated: 2026-08-24

## 1. Goal
Build a passive PortaPack external app that can:

`SCAN CH1–13 -> identify SSID/BSSID/channel -> choose exact BSSID -> TARGET -> AIM -> REF -> DELTA REF`

SSID identification is mandatory. A generic energy meter is not sufficient because overlapping APs may share a channel. Final aiming should use frames from the selected BSSID and relative signal, not claim calibrated dBm.

Passive receive only. No deauth/jamming/interference.

## 2. Hardware / firmware target
- HackRF One + PortaPack Mayhem.
- use the upper SMA labelled `ANTENNA`; lower SMA connectors are CLK IN/OUT.
- device remains on stock Mayhem **`n_260808`**.
- upstream tag: `nightly-tag-2026-08-08`.
- upstream commit: `367eaf54c0f51f62448d9f2d9585fd3629f6b770`.
- do not flash matched custom `w_260822` without explicit user permission.

Canonical repo: **`K0STUR/GPT_HACKRF_APP`**.
Old `K0STUR/GPT` is for FORDstecki only.

## 3. Implemented app architecture
- Mayhem external `.ppma` app.
- M0 UI/integration + embedded M4 baseband image tagged `WAIM`.
- scan channels 1–13 at 20 MS/s.
- Beacon + Probe Response parsing.
- SSID + hidden SSID.
- BSSID + channel.
- TARGET selection by BSSID.
- LIVE / AVG / PEAK / REF / DELTA REF framework.
- decoder OFF/AUTO/ON framework.
- relative packet level only; not calibrated dBm.

## 4. Core ABI / loader history — solved
Early full builds shifted stock Mayhem core symbols and HardFaulted on the real device. Fix6 established the correct stock-compatible approach:
- external app/M4 isolation;
- local MAC formatter instead of missing stock symbol;
- hardened stock-vs-modified ABI audit;
- require core symbol drift 0, patch 0, ambiguous 0, unresolved 0, checksum 0.

Fix6 real hardware launches successfully on stock `n_260808`. Do not return to import rebasing unless a future hardened audit actually fails.

## 5. Critical hardware progression
### Fix7c — capture completion proven
`Done 0AP C10 D0`

Meaning: M4 completes real capture attempts; decoder was the remaining problem.

### Fix8a — captured IQ strongly OFDM-like
`Done 0AP C26 D0 M13`
`HIT 16/64/B 21/21/0`
`Q 16/64/B 100/100/53`

### Fix8b — localized old LTF synchronization failure
`OF L/H/V/P 2/2/2/1`
while roughly 20 captures had strong 64-sample repetition.

### Fix8c — repetition-based LTF sync fixed the main gate
Fix8c uses a repetition metric based on high Q64 and low Q16 rather than hard correlation to an ideal channel-free LTF.

Representative real hardware:
`Done 0AP C26 D0 M13`
`OF L/H/V/P 24/24/24/15`
`OF R/N/D/M 1/0/0/0`
`SQ 98`

This is a major hardware-proven milestone. Do not revert this synchronization without new evidence.

### Fix8d — full legacy OFDM support and first AP detections
Added:
- 6/9/12/18/24/36/48/54 Mb/s legacy OFDM;
- BPSK/QPSK/16-QAM/64-QAM;
- rate-1/2, 2/3 and 3/4 support;
- depuncturing + erasure-aware Viterbi.

Static hardened run `32712871860`: PASS, core drift 0, checksum 0, SHA `359995bd49ec59eeec0fff799cd616c392fd022bdb284f558ef4f7bdeae2edeb`.

Real hardware: 5 scans, **2/5 found `1AP`**. Typical capture count ~`C20–C28`.

Representative successful scan:
`Done 1AP C28 D1 M13`
`OF L/H/V/P 24/24/24/11`
`OF R/N/D/M 4/2/2/0`

Another scan reached:
`OF R/N/D/M 10/3/3/0`

Interpretation:
- full RATE support works;
- OFDM can reach DATA Viterbi on real RF;
- OFDM MAC counter M remained 0;
- global AP/D sometimes became 1, therefore the intermittent AP success most likely came from the DSSS fallback.

**Fix8d is the last functional hardware baseline.**

## 6. Fix8e — current regression state
Fix8e was created to add:
- post-DATA OFDM telemetry `P S/F/G/B/I`;
- DSSS attempts/success telemetry `DS A/S`;
- UI restoration so final diagnostics do not hide AP/SSID/BSSID/channel;
- a guard that skips exhaustive DSSS when OFDM SIGNAL parity already passed.

Fix8e source location:
- branch `wifi-aim-fix8e-prep`
- PR `#11`

Hardened CI:
- run `32723430968`
- job `97419505883`
- artifact `9519205449`
- size `27048`
- M4 offset `8864`
- core drift `0`
- drift refs `0`
- patches `0`
- ambiguous `0`
- unresolved `0`
- checksum `0`
- SHA `631c9bfe66f2b4d69405c5bad5055a28e48e61069ec5cb04b6dec3a02c63f3ee`
- RESULT PASS.

Real hardware Fix8e:
- 4 scans total;
- **0 AP in 4/4**;
- same location has at least 5 Wi-Fi networks visible to phone.

Representative screen:
`Done 0AP C1 D0 M13`
`OF L/H/V/P 0/0/0/0`
`OF R/N/D/M 0/0/0/0`
`SQ 0 R 255 N 0`
`HIT 16/64/B 1/1/0`
`Q 16/64/B 96/96/32`
`DS A/S 1/0 FC 255/255`
`P S/F/G/B/I 0/0/0/0/0`

The key regression is **capture count `C1`** for a complete 13-channel scan, versus Fix8d's ~20–28.

M4 channel acknowledgement still reaches 13, so M0/M4 control and channel retune progress. The single capture attempted DSSS and failed.

Leading hypothesis: Fix8e still runs the exhaustive DSSS decoder when OFDM does not reach parity. If the first capture is non-OFDM/parity-failing, that expensive phase/offset search may monopolize M4 for much of the scan, starving later DMA/capture work. This is plausible but NOT yet proven.

## 7. Repository state at handover
Important:
- **`main` = Fix8d functional source baseline + current documentation.**
- **Fix8e source stays on `wifi-aim-fix8e-prep` / PR #11.**
- Do not merge Fix8e blindly.
- detailed current hardware report: `FIX8E_HARDWARE_RESULT.md`.

Readable source:
`hackrf/source_expanded/`

Key files:
- `firmware/application/external/wifi_aim/ui_wifi_aim.cpp`
- `firmware/application/external/wifi_aim/ui_wifi_aim.hpp`
- `firmware/baseband/proc_wifi_aim.cpp`
- `firmware/baseband/proc_wifi_aim.hpp`
- `firmware/common/wifi_aim/wifi_aim_capture_probe.hpp`
- `firmware/common/wifi_aim/wifi_aim_phy.cpp`
- `firmware/common/wifi_aim/wifi_aim_phy.hpp`
- `firmware/common/wifi_aim_wire.hpp`

## 8. Exact continuation for the next chat
The next chat should **not** continue directly into deeper OFDM parser work. First restore capture throughput.

Recommended first task:
1. read `README.md`, `PROJECT_STATUS.md`, `FIX8E_HARDWARE_RESULT.md`, `TEST_LOG.md`, `NEXT_CHAT_PROMPT.md`;
2. diff `main` against `wifi-aim-fix8e-prep`;
3. focus on `M4WifiDecoder::decode()` and the CPU cost of `M4LegacyWifiDecoder::decode()`;
4. preserve all hardware-proven components:
   - stock zero-drift ABI path;
   - 2048 IQ pretrigger;
   - separate FSK AP/diagnostic backing stores;
   - Fix8c repetition LTF synchronization;
   - Fix8d full legacy OFDM rates;
5. bound/gate/time-slice exhaustive DSSS during broad SCAN so one bad capture cannot monopolize M4;
6. re-run hardened build;
7. hardware-test with the first acceptance target: **return to `C20+` per complete 13-channel scan** while M13 still works;
8. only once throughput is restored, use Fix8e-style `P S/F/G/B/I` telemetry to classify OFDM DATA output;
9. if AP>0, verify SSID/BSSID/channel stay visible and then continue TARGET -> AIM -> REF/DELTA.

Possible implementation directions for the new chat to evaluate, not already executed:
- only run DSSS if a cheap DSSS/Barker pre-classifier suggests it;
- run a bounded subset of DSSS phases/offsets per capture;
- time-slice DSSS across captures/frame periods;
- dedicate some channels/windows to DSSS and others to OFDM;
- add a processing-time/overrun counter to prove or disprove starvation before optimizing.

## 9. What NOT to do
- do not restart RF feasibility analysis;
- do not revisit loader/core rebasing unless hardened ABI fails;
- do not revert Fix8c LTF repetition sync;
- do not remove full Fix8d legacy OFDM support;
- do not interpret Fix8e `0AP` as absence of Wi-Fi — phone sees 5+ nearby networks;
- do not merge Fix8e branch blindly;
- do not flash custom `w_260822` without explicit permission;
- do not claim calibrated absolute dBm.

## 10. End goal
`SCAN -> exact SSID/BSSID -> TARGET -> directional AIM -> REF -> DELTA REF`

Passive only.
