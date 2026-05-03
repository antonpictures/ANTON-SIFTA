from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

REPO = Path(__file__).resolve().parent.parent


def test_ollama_weight_labels_require_exact_model_tags():
    from Applications.sifta_system_settings import _format_ollama_weight_label

    weights = {
        "qwen3.5:2b": 2_740_000_000,
        "sifta-classifier-c1:latest": 6_180_000_000,
        "sifta-gemma4-alice:latest": 9_610_000_000,
    }

    assert _format_ollama_weight_label("qwen3.5:2b", weights) == "⚖ 2.74 GB"
    assert _format_ollama_weight_label("sifta-classifier-c1", weights) == "⚖ 6.18 GB"
    assert _format_ollama_weight_label("sifta-gemma4-alice", weights) == "⚖ 9.61 GB"
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


def test_inference_defaults_policy_matches_executable_default(monkeypatch):
    monkeypatch.delenv("SIFTA_DEFAULT_OLLAMA_MODEL", raising=False)

    from System import sifta_inference_defaults as defaults

    assert defaults.CANONICAL_OLLAMA_DEFAULT == "sifta-gemma4-alice"
    assert defaults.DEFAULT_OLLAMA_MODEL == "sifta-gemma4-alice"
    assert defaults.CANONICAL_OLLAMA_FALLBACK == "sifta-classifier-c1:latest"
    assert "Default Alice cortex:** `sifta-gemma4-alice`" in (defaults.__doc__ or "")
    assert "Reflex fallback:** `sifta-classifier-c1:latest`" in (defaults.__doc__ or "")
    assert "gemma-4-abliterated:latest` (Ollama)" not in (defaults.__doc__ or "")


def test_inference_page_has_no_duplicate_dropdowns(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")

    from PyQt6.QtWidgets import QApplication, QComboBox

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
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()
