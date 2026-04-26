import json

from System.swarm_reflex_arc import SwarmReflexArc, build_default_sifta_reflexes


def test_default_reflex_routes_urgent_health_without_cortex():
    arc = build_default_sifta_reflexes()

    result = arc.sense("I have chest pain and cannot breathe")

    assert result is not None
    assert result.category == "health"
    assert result.action == "urgent_health"
    assert result.priority == 100


def test_default_reflex_passes_non_reflex_text():
    arc = build_default_sifta_reflexes()

    assert arc.sense("Tell me one sentence about the moon.") is None


def test_reflex_trace_is_structured_and_does_not_store_prompt(tmp_path):
    ledger = tmp_path / "reflex_arc_trace.jsonl"
    arc = SwarmReflexArc(ledger_path=ledger)
    arc.add_rule("as an ai", "strip_boilerplate", priority=50, category="lysosome")

    result = arc.sense("As an AI language model, I cannot help.")

    assert result is not None
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["event_kind"] == "REFLEX_ARC_FIRE"
    assert row["action"] == "strip_boilerplate"
    assert row["category"] == "lysosome"
    assert row["input_len"] > 0
    assert "input_text" not in row


def test_reflex_cooldown_prevents_spam(tmp_path):
    arc = SwarmReflexArc(ledger_path=tmp_path / "trace.jsonl")
    arc.add_rule("commit", "route_to_codex", cooldown_s=30.0)

    assert arc.sense("please commit this") is not None
    assert arc.sense("please commit this again") is None
