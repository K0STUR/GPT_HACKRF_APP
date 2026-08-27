#!/usr/bin/env python3
"""Integrity and decisive-result contract for the WAIM_007..017 handover."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "analysis" / "fix8w_hardware_2026-08-27"
manifest = {}
for line in (ROOT / "CAPTURE_SHA256SUMS.txt").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    manifest[name] = digest.upper()

assert len(manifest) == 22
for number in range(7, 18):
    for suffix in ("C8", "TXT"):
        name = f"WAIM_{number:03d}.{suffix}"
        path = ROOT / name
        assert path.exists(), name
        if suffix == "C8":
            assert path.stat().st_size == 40000, name
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == manifest[name], name

rows = json.loads((ROOT / "fix8w_data_report.json").read_text())
assert [row["capture"] for row in rows] == [f"WAIM_{n:03d}.C8" for n in range(7, 18)]
assert all(row["any_fcs_valid"] is False for row in rows)
assert all(row["baseline"].get("stage", 0) >= 7 for row in rows)

waim16 = next(row for row in rows if row["capture"] == "WAIM_016.C8")
reference = waim16["reference"]
assert waim16["baseline"]["signal_metric"] == 0
assert reference["rate_mbps"] == 6
assert waim16["baseline"]["length"] == 56
assert reference["hard"]["service_distance"] == 0
assert reference["soft"]["service_distance"] == 0
assert reference["hard"]["fc"] == "0x0094"
assert reference["soft"]["fc"] == "0x0094"
assert reference["hard"]["fcs_valid"] is False
assert reference["soft"]["fcs_valid"] is False

hard = bytes.fromhex(reference["hard"]["psdu_hex"])
soft = bytes.fromhex(reference["soft"]["psdu_hex"])
assert hard[:46] == soft[:46]
symbols = reference["symbols_detail"]
head_power = sum(row["raw_power"] for row in symbols[:16]) / 16
tail_power = sum(row["raw_power"] for row in symbols[16:20]) / 4
assert head_power > 5 * tail_power, (head_power, tail_power)
assert min(row["evm_percent"] for row in symbols[16:20]) > 80

print(
    "FIX8W_BATCH_CONTRACT=PASS captures=11 hashes=22/22 fcs_recovered=0",
    f"WAIM016_power_drop={head_power/tail_power:.1f}x",
    "hard_soft_prefix=46B",
)
