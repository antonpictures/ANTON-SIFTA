from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

REPO = Path(__file__).resolve().parent.parent


def test_ollama_weight_labels_require_exact_model_tags():
    from Applications.sifta_system_settings import _format_ollama_weight_label

    weights = {
        "alice-Q-m1-scout-2.3b-2.7gb:latest": 2_740_000_000,
        "sifta-classifier-c1-3.1b-6.2gb:latest": 6_180_000_000,
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest": 4_400_000_000,
        "alice-m5-cortex-8b-6.3gb:latest": 6_300_000_000,
        "alice-extra-cortex-25.8b-17gb:latest": 17_000_000_000,
    }

    assert _format_ollama_weight_label("alice-Q-m1-scout-2.3b-2.7gb:latest", weights) == "⚖ 2.74 GB"
    assert _format_ollama_weight_label("sifta-classifier-c1-3.1b-6.2gb:latest", weights) == "⚖ 6.18 GB"
    assert _format_ollama_weight_label("alice-gemma4-e2b-cortex-5.1b-4.4gb:latest", weights) == "⚖ 4.40 GB"
    assert _format_ollama_weight_label("alice-m5-cortex-8b-6.3gb:latest", weights) == "⚖ 6.30 GB"
    assert _format_ollama_weight_label("alice-extra-cortex-25.8b-17gb:latest", weights) == "⚖ 17.00 GB"
    assert _format_ollama_weight_label("qwen3.5:4b", weights) == "not installed"
    assert _format_ollama_weight_label("qwen3.5:9b", weights) == "not installed"


def test_inference_defaults_persist_global_and_app_models(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    assert defaults.set_default_ollama_model("gemma4-phc:latest") == "gemma4-phc:latest"
    assert defaults.set_app_ollama_model("talk_to_alice", "alice-phc-cure") == "alice-phc-cure"

    assert defaults.get_default_ollama_model() == "gemma4-phc:latest"
    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == "alice-phc-cure"


def test_inference_stigmergic_router_selects_and_learns(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(defaults, "_CORTEX_FIELD_PATH", tmp_path / "cortex_route_field.json")
    monkeypatch.setattr(defaults, "_CORTEX_ROUTING_LEDGER", tmp_path / "cortex_route_receipts.jsonl")

    model = defaults.resolve_ollama_model(
        app_context="talk_to_alice",
        query_text="debug the kernel router and run pytest",
    )
    assert model == defaults.CANONICAL_OLLAMA_EXTRA

    bucket = defaults.classify_inference_query_bucket(
        "debug the kernel router and run pytest",
        app_context="talk_to_alice",
    )
    defaults.deposit_cortex_route_trace(
        bucket,
        defaults.CANONICAL_OLLAMA_EXTRA,
        success=False,
        amount=2.0,
        reason="test_regression",
    )
    after_failure = defaults.resolve_ollama_model(
        app_context="talk_to_alice",
        query_text="debug the kernel router and run pytest",
    )

    assert after_failure != defaults.CANONICAL_OLLAMA_EXTRA
    assert defaults._CORTEX_ROUTING_LEDGER.exists()


def test_inference_defaults_policy_matches_executable_default(monkeypatch):
    monkeypatch.delenv("SIFTA_DEFAULT_OLLAMA_MODEL", raising=False)

    from System import sifta_inference_defaults as defaults

    assert defaults.CANONICAL_OLLAMA_DAILY == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_DEFAULT == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_M5_FALLBACK == "alice-m5-cortex-8b-6.3gb:latest"
    assert defaults.CANONICAL_OLLAMA_EXTRA == "alice-extra-cortex-25.8b-17gb:latest"
    assert (
        defaults.CANONICAL_OLLAMA_LOW_RAM
        == "alice-m1-cortex-4.5b-3.4gb:latest"
    )
    assert (
        defaults.CANONICAL_OLLAMA_LOW_RAM_SOURCE
        == "alice-m1-cortex-4.5b-3.4gb:latest"
    )
    assert defaults.DEFAULT_OLLAMA_MODEL == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_REFLEX == "sifta-classifier-c1-3.1b-6.2gb:latest"
    assert defaults.CANONICAL_OLLAMA_FALLBACK == "alice-Q-m1-scout-2.3b-2.7gb:latest"
    assert defaults.CANONICAL_OLLAMA_LORA_CANDIDATE == "sifta-gemma4-alice-lora:latest"
    assert "Default Alice cortex:** `alice-gemma4-e2b-cortex-5.1b-4.4gb:latest`" in (defaults.__doc__ or "")
    assert "M5 fallback cortex:** `alice-m5-cortex-8b-6.3gb:latest`" in (defaults.__doc__ or "")
    assert "Extra research cortex:** `alice-extra-cortex-25.8b-17gb:latest`" in (defaults.__doc__ or "")
    assert "M1 Alice cortex:** `alice-m1-cortex-4.5b-3.4gb:latest`" in (defaults.__doc__ or "")
    assert "Reflex model:** `sifta-classifier-c1-3.1b-6.2gb:latest`" in (defaults.__doc__ or "")
    assert "Generative fallback/probe:** `alice-Q-m1-scout-2.3b-2.7gb:latest`" in (defaults.__doc__ or "")
    assert "LoRA surgery candidate:** `sifta-gemma4-alice-lora:latest` is retired" in (defaults.__doc__ or "")


def test_inference_page_has_no_duplicate_dropdowns(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")

    from PyQt6.QtWidgets import QApplication, QComboBox, QLabel

    from Applications.sifta_system_settings import SystemSettingsWidget

    app = QApplication.instance() or QApplication([])
    settings = SystemSettingsWidget()
    try:
        chat_source = (REPO / "Applications" / "sifta_swarm_chat.py").read_text(encoding="utf-8")
        alice_source = (REPO / "Applications" / "sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
        assert "model_selector" not in chat_source
        assert "_brain_combo" not in alice_source
        assert settings.findChild(QComboBox, "DefaultInferenceModelCombo") is None
        assert settings.findChild(QComboBox, "AliceBrainModelCombo") is None
        assert hasattr(settings, "inference_default_card")
        labels = "\n".join(label.text() for label in settings.findChildren(QLabel))
        assert "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest" in labels
        assert "alice-Q-m1-scout-2.3b-2.7gb:latest" in labels
        assert "alice-m5-cortex-8b-6.3gb:latest" in labels
        assert "sifta-classifier-c1-3.1b-6.2gb:latest" in labels
        assert "alice-extra-cortex-25.8b-17gb:latest" in labels
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()
