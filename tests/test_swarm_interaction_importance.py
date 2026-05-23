import json

from System.swarm_alice_witness import witness
from System.swarm_interaction_importance import (
    classify_interaction_importance,
    journal_witness_line,
)


def test_time_query_gets_high_importance():
    row = classify_interaction_importance(
        "Alice, what is the date and time?",
        role="user",
        stt_confidence=0.96,
    )

    assert row["truth_label"] == "INTERACTION_IMPORTANCE_V1"
    assert row["importance_band"] in {"high", "critical"}
    assert row["memory_action"] in {"pin_working_memory", "promote_to_life_journal"}
    assert row["is_time_or_date_query"] is True
    assert "time_or_date_query" in row["reasons"]


def test_short_phatic_low_confidence_is_noise():
    row = classify_interaction_importance("Yeah bro.", role="user", stt_confidence=0.29)

    assert row["importance_band"] == "noise"
    assert row["memory_action"] == "ignore_noise"
    assert "phatic_or_noise" in row["reasons"]


def test_memory_and_effector_turn_is_promoted():
    row = classify_interaction_importance(
        "Alice, remember this and write it in the journal, then change the wallpaper.",
        role="user",
        stt_confidence=0.88,
    )

    assert row["importance_band"] == "critical"
    assert row["memory_action"] == "promote_to_life_journal"
    assert {"memory_or_receipt", "tool_or_effector", "identity_or_swarm"}.issubset(
        set(row["reasons"])
    )


def test_journal_witness_line_is_compact_first_person_signal():
    row = classify_interaction_importance("What time is it?", role="user", stt_confidence=1.0)
    line = journal_witness_line("What time is it?", row)

    assert line.startswith("George said:")
    assert "importance" in line
    assert "memory_action=" in line


def test_witness_accepts_importance_payload(tmp_path):
    importance = classify_interaction_importance("What is today's date?", role="user")
    out = witness(
        "George asked me the date.",
        source="test",
        state_dir=tmp_path,
        importance=importance,
    )

    assert out["importance"]["truth_label"] == "INTERACTION_IMPORTANCE_V1"
    rows = [
        json.loads(line)
        for line in (tmp_path / "alice_first_person_journal.jsonl").read_text().splitlines()
    ]
    assert rows[-1]["importance"]["is_time_or_date_query"] is True
