"""Receipt-first training plan fixtures (r1446/r1449)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_training_examples import (
    build_training_examples,
    enrich_training_example,
    fixture_training_examples,
    supervised_example_from_row,
    write_training_examples,
)
from System.swarm_kernel_identity import owner_chat_turn_label, owner_provider_label
from System.swarm_supervised_training_field import evaluate_supervised_example
from System.swarm_token_immune_swimmers import FabricatedSystemReportSwimmer, default_swimmer_pool


@pytest.mark.parametrize(
    "example_id,sort_label,allowed_decisions",
    [
        ("joy_behar_good", "good", {"REINFORCE"}),
        ("vince_candidate", "candidate", {"REINFORCE", "OBSERVE_NO_WEIGHT_CHANGE"}),
        ("kimi_fake_bridge_bad", "bad", {"QUARANTINE_UNRECEIPTED_CLAIM", "SHAPE_AWAY"}),
        ("polenta_gold_bikini_bad", "bad", {"QUARANTINE_UNRECEIPTED_CLAIM", "SHAPE_AWAY"}),
        ("world_stt_candidate", "candidate", {"REINFORCE", "OBSERVE_NO_WEIGHT_CHANGE"}),
        ("owner_genesis_agi_correction_good", "good", {"REINFORCE"}),
        ("owner_receipts_language_colearning_good", "good", {"REINFORCE"}),
    ],
)
def test_fixture_supervised_decisions(example_id, sort_label, allowed_decisions):
    row = next(r for r in fixture_training_examples() if r["example_id"] == example_id)
    assert row["sort_label"] == sort_label
    decision = evaluate_supervised_example(supervised_example_from_row(row))
    assert decision["decision"] in allowed_decisions


def test_kimi_fixture_caught_by_fabricated_report_swimmer():
    row = next(r for r in fixture_training_examples() if r["example_id"] == "kimi_fake_bridge_bad")
    swimmer = FabricatedSystemReportSwimmer()
    hits = swimmer.patrol(row["model_output"])
    patterns = {p.pattern_name for p in hits}
    assert "fabricated_phase_claim" in patterns
    assert "fabricated_http_status_claim" in patterns


def test_build_training_examples_writes_ledger(tmp_path):
    receipt = write_training_examples(
        build_training_examples(include_conversation=False),
        state_dir=tmp_path,
    )
    assert receipt["ok"] is True
    assert receipt["count"] == 7
    out = tmp_path / "training_examples.jsonl"
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 7
    enriched = enrich_training_example(fixture_training_examples()[0])
    assert enriched["supervised_decision"] == "REINFORCE"


def test_owner_chat_turn_label_never_agi(monkeypatch):
    from System import swarm_kernel_identity as kid

    monkeypatch.setattr(kid, "owner_name", lambda: "<unclaimed>")
    monkeypatch.setattr(kid, "owner_display_name", lambda default="": kid.owner_provider_label())
    assert owner_provider_label() == "AGI Provider"
    assert owner_chat_turn_label(default="You") == "You"


def test_owner_chat_turn_label_uses_genesis_first_name(monkeypatch):
    from System import swarm_kernel_identity as kid

    monkeypatch.setattr(kid, "owner_name", lambda: "Ioan George Anton")
    assert owner_chat_turn_label(default="You") == "Ioan"


def test_default_swimmer_pool_includes_fabricated_report():
    pool = default_swimmer_pool()
    assert len(pool) >= 7
    assert any(type(s).__name__ == "FabricatedSystemReportSwimmer" for s in pool)