"""Tests for System/swarm_collective_intent_field.py (Event 109)."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_collective_intent_field import compute_collective_intent, write_collective_intent


def test_collective_intent_field_bounded():
    row = compute_collective_intent()
    assert row["truth_label"] == "COLLECTIVE_INTENT_FIELD"
    assert 0.0 <= row["alignment_score"] <= 1.0
    assert 0.0 <= row["conflict_pressure"] <= 1.0
    assert row["next_collective_action"] in {
        "quorum_review",
        "stabilize",
        "forage_research",
        "prove",
        "continue",
    }


def test_collective_intent_respects_synthetic_ledgers(tmp_path: Path):
    (tmp_path / "ide_stigmergic_trace.jsonl").write_text(
        json.dumps({"intent": "explore the stack", "kind": "message"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "motor_policy.jsonl").write_text(
        json.dumps({"selected_action": "explore", "regime": "EXPLORATION"}) + "\n",
        encoding="utf-8",
    )
    row = compute_collective_intent(state_dir=tmp_path)
    assert row["consensus_drive"] == "explore"
    assert row["next_collective_action"] == "forage_research"


def test_write_appends_jsonl(tmp_path: Path):
    r1 = write_collective_intent(state_dir=tmp_path)
    r2 = write_collective_intent(state_dir=tmp_path)
    p = tmp_path / "collective_intent_field.jsonl"
    lines = [json.loads(l) for l in p.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) >= 2
    assert lines[-1]["truth_label"] == "COLLECTIVE_INTENT_FIELD"
    assert r1["truth_label"] == r2["truth_label"]
