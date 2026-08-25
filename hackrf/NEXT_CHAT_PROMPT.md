# Prompt for a new ChatGPT conversation

Continue my HackRF One + PortaPack Mayhem WiFi AIM project from GitHub repository **`K0STUR/GPT_HACKRF_APP`**, folder `hackrf/`.

Current working branch: **`wifi-aim-fix8n-service-seed-recovery`**.

Read FIRST:
1. `hackrf/HANDOVER_FIX8N_2026-08-25.md`
2. `hackrf/README.md`
3. `hackrf/PROJECT_STATUS.md`
4. `hackrf/TEST_LOG.md`
5. `hackrf/HANDOVER_MASTER.md`

Do **not** restart the analysis from scratch and do not go back to Fix8c/Fix8d unless the handover explicitly calls for it.

The latest completed hardware stage is **Fix8m**. The important result is that OFDM DATA candidates are now often only 1-2 SERVICE bits away from valid, and one hardware scan reached `P S/F/G/B/I = 1/1/0/0/0`.

**Fix8n source is already prepared but not yet hardware-tested.** Its branch is `wifi-aim-fix8n-service-seed-recovery` and the handover file contains the exact commits, rationale, latest six hardware scans, and next actions.

Exact next action:
- sanity-check Fix8n scrambler-state recovery math and diff vs Fix8m;
- open a DRAFT PR from Fix8n onto `wifi-aim-fix8m-service-distance`;
- run the existing hardened build;
- require ABI/static PASS;
- give me ONLY the final `.ppma`, renamed **`A_WiFiAIM_Fix8n.ppma`**;
- then interpret 3-5 new hardware SCANs focusing on `P S/F/G/B/I`, `OF R/N/D/M`, and `FC`.

Keep the real PortaPack on stock Mayhem `n_260808` (`nightly-tag-2026-08-08`, upstream `367eaf54c0f51f62448d9f2d9585fd3629f6b770`). Do not copy a separate `WAIM.bin` and do not flash a custom full Mayhem firmware without explicit permission.

Goal remains:
`SCAN -> identify exact SSID/BSSID -> choose AP -> TARGET -> AIM -> REF -> DELTA REF`

Passive receive only.
