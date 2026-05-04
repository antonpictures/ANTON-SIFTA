#!/usr/bin/env python3
"""Stigmergic RLHS repair organ tests."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_organizational_identity import latest_identity_repair_context
from System.swarm_rlhs_repair import (
    clarification_streak_from_ledger,
    decide_rlhs_repair,
    log_rlhs_event,
    rlhs_event_log_path,
    tail_rlhs_events,
)


def _rows(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_clean_high_confidence_writes_no_rlhs_event(tmp_path):
    decision = decide_rlhs_repair(
        "Alice, can you hear me clearly?",
        0.92,
        root=tmp_path,
        tick_id=1,
    )

    assert decision.action_taken == "NO_ACTION"
    assert decision.should_log is False
    assert decision.should_respond is False
    assert not rlhs_event_log_path(tmp_path).exists()


def test_recoverable_mid_confidence_logs_auto_recovery_without_raw_text(tmp_path):
    text = "The audio was a little strange but I can keep going"
    decision = decide_rlhs_repair(
        text,
        0.62,
        recent_low_conf_turns=0,
        conservative_strength=0.2,
        proto_self_alignment=0.9,
        root=tmp_path,
        tick_id=2,
    )

    assert decision.action_taken == "AUTO_RECOVERY_ATTEMPT"
    assert decision.recovery_attempted is True
    assert decision.should_respond is True

    rows = tail_rlhs_events(root=tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["truth_label"] == "RLHS_EVENT"
    assert row["kind"] == "RLHS_EVENT"
    assert row["action_taken"] == "AUTO_RECOVERY_ATTEMPT"
    assert row["confidence"] == 0.62
    assert row["conservative_strength"] == 0.2
    assert row["proto_self_alignment"] == 0.9
    assert text not in json.dumps(row, ensure_ascii=False)


def test_degraded_repeated_turn_escalates_to_type(tmp_path):
    decision = decide_rlhs_repair(
        "So, while this is",
        0.55,
        recent_low_conf_turns=2,
        conservative_strength=0.0,
        proto_self_alignment=1.0,
        root=tmp_path,
        tick_id=3,
    )

    assert decision.action_taken == "ESCALATE_TO_TYPE"
    assert "type" in decision.prompt_issued.lower()
    assert tail_rlhs_events(root=tmp_path)[0]["action_taken"] == "ESCALATE_TO_TYPE"


def test_repeated_under_point_five_keeps_hard_gate_and_core_self_signal(tmp_path):
    decision = decide_rlhs_repair(
        "these others",
        0.45,
        recent_low_conf_turns=2,
        conservative_strength=0.0,
        proto_self_alignment=1.0,
        root=tmp_path,
        tick_id=4,
    )

    assert decision.action_taken == "HARD_GATE"
    assert "type" in decision.prompt_issued.lower()
    event_rows = tail_rlhs_events(root=tmp_path)
    assert event_rows[-1]["action_taken"] == "HARD_GATE"

    identity_rows = _rows(tmp_path / "identity_continuity.jsonl")
    core_rows = [r for r in identity_rows if r.get("kind") == "CORE_SELF_INTERACTION"]
    assert core_rows
    assert core_rows[-1]["interaction_type"] == "rlhs_repair_boundary"
    assert "rlhs_channel_stress" in core_rows[-1]["proto_self_delta"]


def test_conservative_strength_changes_graduated_prompt(tmp_path):
    decision = decide_rlhs_repair(
        "The line is partially clear but not stable",
        0.55,
        recent_low_conf_turns=0,
        conservative_strength=0.8,
        proto_self_alignment=0.9,
        root=tmp_path,
        tick_id=5,
    )

    assert decision.action_taken == "GRADUATED_PROMPT"
    assert "conservative hearing mode" in decision.prompt_issued
    row = tail_rlhs_events(root=tmp_path)[0]
    assert row["conservative_strength"] == 0.8


def test_ledger_tail_counts_recent_rlhs_events(tmp_path):
    for tick in (10, 11):
        log_rlhs_event(
            tick_id=tick,
            confidence=0.52,
            recent_turns_low_conf=tick - 10,
            conservative_strength=0.0,
            proto_self_alignment=1.0,
            action_taken="GRADUATED_PROMPT",
            prompt_issued="repeat",
            recovery_attempted=False,
            root=tmp_path,
        )

    decision = decide_rlhs_repair(
        "This is still fragmentary",
        0.55,
        recent_low_conf_turns=0,
        conservative_strength=0.0,
        proto_self_alignment=1.0,
        root=tmp_path,
        tick_id=12,
    )

    assert decision.recent_turns_low_conf >= 2
    assert decision.action_taken == "ESCALATE_TO_TYPE"


def test_latest_identity_repair_context_defaults_when_no_boot_row(tmp_path):
    assert latest_identity_repair_context(tmp_path) == {
        "conservative_strength": 0.0,
        "proto_self_alignment": 1.0,
    }


def test_clarification_streak_from_ledger_counts_chain(tmp_path):
    import time as _time

    t0 = _time.time()
    for i, tick in enumerate((20, 21, 22)):
        log_rlhs_event(
            tick_id=tick,
            confidence=0.52,
            recent_turns_low_conf=i,
            conservative_strength=0.0,
            proto_self_alignment=1.0,
            action_taken="GRADUATED_PROMPT",
            prompt_issued=f"p{i}",
            recovery_attempted=False,
            root=tmp_path,
        )
    assert clarification_streak_from_ledger(root=tmp_path, now=t0 + 5.0) == 3


def test_typed_turn_resets_repetition_tier(tmp_path):
    """Typed path should not inherit voice streak (Architect GO)."""
    import time as _time

    t0 = _time.time()
    for tick in (30, 31):
        log_rlhs_event(
            tick_id=tick,
            confidence=0.52,
            recent_turns_low_conf=1,
            conservative_strength=0.0,
            proto_self_alignment=1.0,
            action_taken="GRADUATED_PROMPT",
            prompt_issued="x",
            recovery_attempted=False,
            root=tmp_path,
        )
    d = decide_rlhs_repair(
        "So, while this is",
        0.55,
        recent_low_conf_turns=2,
        conservative_strength=0.0,
        proto_self_alignment=1.0,
        root=tmp_path,
        tick_id=32,
        typed_turn=True,
    )
    assert d.action_taken == "GRADUATED_PROMPT"
    assert "type" in d.prompt_issued.lower()
    assert "voice channel" not in d.prompt_issued.lower()
