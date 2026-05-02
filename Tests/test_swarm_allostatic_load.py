"""Event 102 — allostatic load from body_brain_memory tail."""

import json
from pathlib import Path

from System import swarm_allostatic_load as al


def test_allostatic_empty_memory_low_load(tmp_path: Path) -> None:
    row = al.compute_allostatic_load(state_dir=tmp_path)
    assert row["truth_label"] == al.TRUTH_LABEL
    assert row["allostatic_load"] == 0.0
    assert row["policy"] == "ALLOW_GROWTH"
    assert row["window"] == 0


def test_allostatic_high_stress_forces_repair(tmp_path: Path) -> None:
    mem = tmp_path / "body_brain_memory.jsonl"
    lines = []
    for _ in range(10):
        lines.append(
            json.dumps(
                {
                    "event": "body_brain_tick",
                    "metabolic_mode": "CRITICAL_STARVATION",
                    "td_value": -1.0,
                }
            )
        )
    mem.write_text("\n".join(lines) + "\n", encoding="utf-8")

    row = al.compute_allostatic_load(state_dir=tmp_path, window=40)
    assert row["policy"] == "FORCE_REST_REPAIR"
    assert row["allostatic_load"] > 0.75


def test_allostatic_write_appends_ledger(tmp_path: Path) -> None:
    mem = tmp_path / "body_brain_memory.jsonl"
    mem.write_text(
        json.dumps({"metabolic_mode": "GREEN_GROW", "td_value": 1.0}) + "\n",
        encoding="utf-8",
    )
    out = al.write_allostatic_load(state_dir=tmp_path)
    ledger = tmp_path / "allostatic_load.jsonl"
    assert ledger.exists()
    last = ledger.read_text(encoding="utf-8").strip().splitlines()[-1]
    parsed = json.loads(last)
    assert parsed["truth_label"] == al.TRUTH_LABEL
    assert parsed["policy"] == out["policy"]
