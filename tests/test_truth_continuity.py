"""Truth continuity organ — cross-turn grounding ledger (Round-2 stub)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_build_event_minimal() -> None:
    from System.swarm_truth_continuity import build_event, SCHEMA_LITERAL

    row = build_event(
        turn_index=3,
        continuity_score=None,
        drift_flags=["thread_drop"],
        evidence_refs=["sha8:deadbeef"],
        writer="test",
        note="unit test row",
        truth_label="OBSERVED",
    )
    assert row["schema"] == SCHEMA_LITERAL
    assert row["continuity_score"] is None


def test_build_event_score_bounds() -> None:
    from System.swarm_truth_continuity import build_event

    build_event(
        turn_index=0,
        continuity_score=1.0,
        drift_flags=[],
        evidence_refs=[],
        writer="test",
        note="ok",
    )
    with pytest.raises(ValueError):
        build_event(
            turn_index=0,
            continuity_score=1.5,
            drift_flags=[],
            evidence_refs=[],
            writer="test",
            note="bad score",
        )


def test_proof_of_property_stub() -> None:
    from System.swarm_truth_continuity import proof_of_property

    out = proof_of_property()
    assert out.get("ok") is True


def test_append_event_roundtrip(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_truth_continuity as mod

    ledger = tmp_path / "truth_continuity_events.jsonl"
    monkeypatch.setattr(mod, "TRUTH_CONTINUITY_LEDGER", ledger)
    row = mod.build_event(
        turn_index=1,
        continuity_score=0.25,
        drift_flags=[],
        evidence_refs=[],
        writer="pytest",
        note="append roundtrip",
    )
    mod.append_event(row, write_ledger=True)
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == row["event_id"]


def test_append_respects_kill_switch(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_truth_continuity as mod

    monkeypatch.setenv("SIFTA_TRUTH_CONTINUITY_DISABLE", "1")
    ledger = tmp_path / "truth_continuity_events.jsonl"
    monkeypatch.setattr(mod, "TRUTH_CONTINUITY_LEDGER", ledger)
    row = mod.build_event(
        turn_index=0,
        continuity_score=None,
        drift_flags=[],
        evidence_refs=[],
        writer="pytest",
        note="disabled",
    )
    out = mod.append_event(row, write_ledger=True)
    assert out.get("disabled") is True
    assert not ledger.exists()


def test_allowed_dissociation_override_roundtrip(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_truth_continuity as mod

    overrides = tmp_path / "truth_continuity_overrides.jsonl"
    monkeypatch.setattr(mod, "TRUTH_CONTINUITY_OVERRIDES", overrides)

    row = mod.append_allowed_dissociation(
        reason="Architect marked this as allowed coping language.",
        ttl_s=60,
    )

    active = mod.active_allowed_dissociation(now=row["ts"] + 1)
    assert active is not None
    assert active["schema"] == mod.OVERRIDE_SCHEMA_LITERAL
    assert active["override_id"] == row["override_id"]


def test_biological_continuity_override_softens_penalty(monkeypatch, tmp_path: Path) -> None:
    from System import swarm_truth_continuity as mod

    state = tmp_path
    monkeypatch.setattr(mod, "_STATE", state)
    monkeypatch.setattr(mod, "TRUTH_CONTINUITY_LEDGER", state / "truth_continuity_events.jsonl")
    monkeypatch.setattr(mod, "TRUTH_CONTINUITY_OVERRIDES", state / "truth_continuity_overrides.jsonl")

    (state / "cuttlefish_display.jsonl").write_text(
        json.dumps({"payload": {"pattern": "alarm"}}) + "\n",
        encoding="utf-8",
    )
    (state / "electric_field.jsonl").write_text(
        json.dumps({"payload": {"dipole_moments": [0.0, 0.0, 0.0]}}) + "\n",
        encoding="utf-8",
    )
    (state / "td_receipts.jsonl").write_text(
        json.dumps({"td_error": 0.9}) + "\n",
        encoding="utf-8",
    )
    override = mod.append_allowed_dissociation(
        reason="Allowed context: human says fine as coping phrase.",
        ttl_s=60,
    )

    row = mod.evaluate_biological_continuity("I am fine.", turn_index=7)

    assert row["continuity_score"] == 0.9
    assert "somatic_contradiction_alarm_vs_calm_speech" in row["drift_flags"]
    assert "allowed_dissociation_override" in row["drift_flags"]
    assert row["override_id"] == override["override_id"]
    assert row["override_applied"] is True
    assert row["td_reward_override"] == 0.0
