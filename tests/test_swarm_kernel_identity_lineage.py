from __future__ import annotations

import json
from pathlib import Path

from System import swarm_kernel_identity as kid


def _conversation_row(model: str) -> str:
    return json.dumps(
        {
            "payload": {
                "role": "alice",
                "text": "Online.",
                "model": model,
            }
        }
    )


def test_ai_lineage_title_separates_live_provider_from_system(tmp_path: Path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(kid, "_STATE", state)
    monkeypatch.setattr(kid, "_GENESIS_FILE", state / "owner_genesis.json")
    monkeypatch.setattr(kid, "_ALIAS_FILE", state / "ai_name_alias.json")
    (state / "owner_genesis.json").write_text(
        json.dumps({"owner_name": "George", "ai_display_name": "Alice"}),
        encoding="utf-8",
    )
    (state / "alice_conversation.jsonl").write_text(
        _conversation_row("alice-gemini-pro-cortex:latest") + "\n",
        encoding="utf-8",
    )

    assert kid.ai_provider_name() == "Gemini"
    assert kid.ai_lineage_title() == "Alice of SIFTA #node-unbound"
    assert kid.ai_identity_sentence().startswith("I am Alice of SIFTA #node-unbound.")
    assert "model provider/family is Gemini" in kid.ai_identity_sentence()


def test_ai_lineage_title_honors_explicit_provider_overlay(tmp_path: Path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(kid, "_STATE", state)
    monkeypatch.setattr(kid, "_GENESIS_FILE", state / "owner_genesis.json")
    monkeypatch.setattr(kid, "_ALIAS_FILE", state / "ai_name_alias.json")
    (state / "owner_genesis.json").write_text(
        json.dumps({"owner_name": "George", "ai_display_name": "Alice"}),
        encoding="utf-8",
    )
    (state / "ai_name_alias.json").write_text(
        json.dumps({"alias": "Alice", "provider_name": "Grok", "weight_name": "Grok3"}),
        encoding="utf-8",
    )

    assert kid.ai_provider_name() == "Grok"
    assert kid.ai_lineage_title() == "Alice of SIFTA #node-unbound"
    assert "The active weights are Grok3." in kid.ai_identity_sentence()


def test_ai_lineage_ignores_fast_path_protocol_model_names(tmp_path: Path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(kid, "_STATE", state)
    monkeypatch.setattr(kid, "_GENESIS_FILE", state / "owner_genesis.json")
    monkeypatch.setattr(kid, "_ALIAS_FILE", state / "ai_name_alias.json")
    (state / "owner_genesis.json").write_text(
        json.dumps({"owner_name": "George", "ai_display_name": "Alice"}),
        encoding="utf-8",
    )
    (state / "alice_conversation.jsonl").write_text(
        _conversation_row("day_segment_recall_protocol") + "\n",
        encoding="utf-8",
    )

    assert kid.ai_provider_name() == ""
    assert kid.ai_weight_name() == ""
    assert kid.ai_lineage_title() == "Alice of SIFTA #node-unbound"
    assert "Alice of Day" not in kid.ai_identity_sentence()


def test_hardware_suffix_is_stable_private_and_model_independent(monkeypatch):
    monkeypatch.setattr(kid, "ai_name", lambda: "Lola")
    genesis = {"silicon": "TEST-HARDWARE-ONE"}
    monkeypatch.setattr(kid, "_read_genesis", lambda: genesis)
    first = kid.ai_lineage_title()
    assert first.startswith("Lola of SIFTA #node-")
    assert "TEST-HARDWARE-ONE" not in first
    monkeypatch.setattr(kid, "ai_provider_name", lambda: "AnotherModel")
    assert kid.ai_lineage_title() == first
    genesis["silicon"] = "TEST-HARDWARE-TWO"
    assert kid.ai_lineage_title() != first
