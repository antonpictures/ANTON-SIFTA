from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_probe_installed_ollama_tags_uses_live_list(monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(
        defaults,
        "probe_installed_ollama_tags",
        lambda **kw: (
            "krishairnd/Gemma-4-Uncensored:latest",
            "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS",
        ),
    )

    assert defaults.resolve_live_local_ollama_default() == "krishairnd/Gemma-4-Uncensored:latest"
    assert defaults.coerce_to_installed_ollama_model(
        "alice-m5-cortex-8b-6.3gb:latest"
    ) == "krishairnd/Gemma-4-Uncensored:latest"
    assert defaults.list_live_local_ollama_fallbacks() == [
        "krishairnd/Gemma-4-Uncensored:latest",
        "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS",
    ]


def test_resolve_ollama_model_coerces_missing_local_pin(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(
        defaults,
        "probe_installed_ollama_tags",
        lambda **kw: ("krishairnd/Gemma-4-Uncensored:latest",),
    )

    defaults.set_default_ollama_model("alice-m5-cortex-8b-6.3gb:latest")
    defaults.set_app_ollama_model("talk_to_alice", "alice-m5-cortex-8b-6.3gb:latest")

    assert (
        defaults.resolve_ollama_model(app_context="talk_to_alice")
        == "krishairnd/Gemma-4-Uncensored:latest"
    )


def test_persist_ollama_boot_inventory_writes_receipt(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_OLLAMA_BOOT_INVENTORY", tmp_path / "ollama_boot_inventory.json")

    row = defaults.persist_ollama_boot_inventory(
        installed=(
            "krishairnd/Gemma-4-Uncensored:latest",
            "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS",
        )
    )

    assert row["schema"] == "SIFTA_OLLAMA_BOOT_INVENTORY_V1"
    assert row["resolved_daily_local"] == "krishairnd/Gemma-4-Uncensored:latest"
    assert "alice-m5-cortex-8b-6.3gb:latest" in row["missing_legacy_canonical"]
    saved = json.loads((tmp_path / "ollama_boot_inventory.json").read_text(encoding="utf-8"))
    assert saved["tags"] == row["tags"]


def test_talk_fallback_ladder_uses_installed_only(monkeypatch):
    import Applications.sifta_talk_to_alice_widget as talk

    monkeypatch.setattr(
        "System.sifta_inference_defaults.list_live_local_ollama_fallbacks",
        lambda **kw: [
            "krishairnd/Gemma-4-Uncensored:latest",
            "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS",
        ],
    )
    monkeypatch.setattr(
        "System.swarm_stigmergic_timeout_policy.should_fast_fallback_cloud",
        lambda *a, **k: {"fast_fallback": False, "local_fallback": ""},
    )
    monkeypatch.setattr(
        "System.swarm_stigmergic_timeout_policy.local_fallback_for_model",
        lambda *a, **k: "",
    )

    names = talk._talk_ollama_model_candidates("mimo:mimo-cli-default")
    assert "alice-m5-cortex-8b-6.3gb:latest" not in names
    assert "krishairnd/Gemma-4-Uncensored:latest" in names


def test_local_brain_default_uses_live_installed(monkeypatch):
    import swarm_local_brain

    monkeypatch.setattr(
        "System.sifta_inference_defaults.resolve_live_local_ollama_default",
        lambda **kw: "krishairnd/Gemma-4-Uncensored:latest",
    )

    assert (
        swarm_local_brain.get_default_model()
        == "ollama:krishairnd/Gemma-4-Uncensored:latest"
    )