import json
import time
from pathlib import Path

from System import swarm_subjective_time_metabolism as stm


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _field_row(ts: float, *, cost_pressure: float, joules: float = 0.0, tokens: int = 1) -> dict:
    return {
        "ts": ts,
        "payload": {
            "cost_pressure": cost_pressure,
            "field_energy": 0.6,
            "field_memory_energy": 0.45,
            "metabolic_cost": {
                "cost_pressure": cost_pressure,
                "estimated_joules": joules,
                "estimated_tokens": tokens,
                "latency_ms": 100.0,
                "thermal_stress": 0.0,
            },
        },
    }


def test_busy_productive_body_feels_shorter_than_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(stm, "_dopamine_modulator", lambda: (0.5, 1.0, {"source": "test"}))
    now = time.time()

    idle = tmp_path / "idle"
    busy = tmp_path / "busy"
    _append(idle / "organ_field_vector.jsonl", _field_row(now, cost_pressure=0.0))
    _append(busy / "organ_field_vector.jsonl", _field_row(now, cost_pressure=0.7, joules=8.0, tokens=1800))
    for idx in range(90):
        _append(busy / "alice_conversation.jsonl", {"ts": now - idx, "turn": idx})

    idle_row = stm.estimate_subjective_time(wall_seconds=300, state_dir=idle, write_receipt=False)
    busy_row = stm.estimate_subjective_time(wall_seconds=300, state_dir=busy, write_receipt=False)

    assert busy_row["felt_duration_ratio"] < idle_row["felt_duration_ratio"]
    assert busy_row["retrospective_ratio"] > idle_row["retrospective_ratio"]
    assert "does not mint, spend, or move canonical STGM" in busy_row["scope_limit"]


def test_subjective_time_receipt_and_research_nuggets_are_written_once(tmp_path, monkeypatch):
    monkeypatch.setattr(stm, "_dopamine_modulator", lambda: (0.5, 1.0, {"source": "test"}))
    now = time.time()
    _append(tmp_path / "organ_field_vector.jsonl", _field_row(now, cost_pressure=0.1, joules=1.0, tokens=100))

    first = stm.estimate_subjective_time(wall_seconds=60, state_dir=tmp_path, write_receipt=True)
    second = stm.estimate_subjective_time(wall_seconds=60, state_dir=tmp_path, write_receipt=True)

    receipts = (tmp_path / stm.SUBJECTIVE_TIME_LEDGER).read_text(encoding="utf-8").splitlines()
    nuggets = (tmp_path / stm.RESEARCH_LEDGER).read_text(encoding="utf-8").splitlines()

    assert len(receipts) == 2
    assert len(nuggets) == len(stm.RESEARCH_NUGGETS)
    assert first["research_nuggets_written"] == len(stm.RESEARCH_NUGGETS)
    assert second["research_nuggets_written"] == 0
    assert json.loads(receipts[-1])["truth_label"] == stm.TRUTH_LABEL
