# HackRF / PortaPack — file index

The `hackrf/` folder is the canonical self-contained handoff area.

## Human-readable handoff
- `README.md` — entry point.
- `HANDOVER_MASTER.md` — complete context and engineering frontier.
- `PROJECT_STATUS.md` — concise current state and decision point.
- `WIFI_AIM_SPEC.md` — functional specification.
- `TEST_LOG.md` — real hardware + build test history.
- `HARDWARE_RF_NOTES.md` — HackRF/PortaPack/RF notes.
- `NEXT_CHAT_PROMPT.md` — ready-to-use continuation prompt.
- `REPO_SNAPSHOT.txt` — snapshot metadata from assembly.
- `MANIFEST_SHA256.txt` — hashes for mirrored files.

## Source archive
Exact source chunks are mirrored under `source_archive/`:
- `src.part00`
- `src.part01`
- `src.part02`
- `src.part03`

Reconstruct with:
```bash
cat hackrf/source_archive/src.part* > /tmp/wifi_aim_src.b64
base64 -d /tmp/wifi_aim_src.b64 > /tmp/wifi_aim_src.tar.gz
```
Expected tar.gz SHA-256 used by CI:
`294072ffe25e369fee1276cca11ea6a374fc27b2e09a081eb444eabd8eb01cb9`

## Build results mirrored under `hackrf/build_results/`
The handoff currently includes at least:
- `wifi_aim_probe_n260808/` — working real-hardware RF probe.
- `wifi_aim_probe/` — earlier probe material.
- `wifi_aim_full_n260808/` — original full build.
- `wifi_aim_full_n260808_fix1/` — loader-aligned patch.
- `wifi_aim_full_n260808_fix2/` — aligned linker build + verification.
- `wifi_aim_full_n260808_fix3/` — low-memory/aligned attempt.
- `wifi_aim_full_n260808_fix4/` — external-section isolation; verification FAIL on stock core parity.
- `wifi_aim_full_n260808_fix5/` — symbol/import rebasing attempt; 58 patches, one unresolved import, RESULT=FAIL.
- `wifi_aim_fix5_diag/` — deeper fix5 build/symbol diagnostics.
- `wifi_aim_lowmem_n260808/` — reduced-memory variant.
- `wifi_aim_hardfault_diag/` — disassembly and HardFault diagnostics.
- `wifi_aim_test_veneerpatch1_n260808/` — 17-veneer diagnostic image, static PASS, not yet hardware-proven.
- `wifi_aim_bundle_w260822/` — matched custom firmware + APPS bundle, build/loader PASS.
- `wifi_aim_v04_diag/` — earlier v0.4 build diagnostics.

`wifi_aim_bundle_w260822/` is especially important because it contains:
- `WiFiAIM_w_260822.ppma`
- `portapack-mayhem_WIFI_AIM_w_260822.bin`
- `COPY_TO_SDCARD_WIFI_AIM_w_260822.zip`
- `WAIM.bin`
- `STATUS.txt`, `VERIFY.txt`, hashes.

Do not mix that `.ppma` with stock `n_260808`; the custom firmware and APPS are a matched set.

## Standalone diagnostics
Mirrored under `hackrf/diagnostics/`:
- `PPMA_HEADER_INSPECT.txt`
- `WIFI_AIM_FIRST_CALL.txt`
- `ppma_diag_n260808.txt`

## Workflow archive
`hackrf/workflows_archive/` mirrors all project-specific GitHub Actions workflows, including:
- original full builds;
- fix1–fix5 variants;
- fix4 PR/isolation work;
- fix5 diagnostics/signal-hunter comparison;
- low-memory builds;
- PPMA diagnostics/header inspection;
- veneer patch tests;
- matched `w_260822` firmware bundle build;
- handoff assembly workflow.

A new chat should inspect workflow history rather than inventing a fresh build pipeline.

## Exact upstream dependency for stock path
Mayhem source is not vendored. Stock-compatible work must use:
- repo `portapack-mayhem/mayhem-firmware`
- tag `nightly-tag-2026-08-08`
- commit `367eaf54c0f51f62448d9f2d9585fd3629f6b770`
- version string `n_260808`

The matched custom-firmware route uses the same source base but builds a new version string `w_260822` and requires flashing the generated firmware together with its APPS set.