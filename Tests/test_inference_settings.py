from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

REPO = Path(__file__).resolve().parent.parent


def test_inference_defaults_persist_global_and_app_models(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    assert defaults.set_default_ollama_model("gemma4-phc:latest") == "gemma4-phc:latest"
    assert defaults.set_app_ollama_model("talk_to_alice", "alice-phc-cure") == "alice-phc-cure"

    assert defaults.get_default_ollama_model() == "gemma4-phc:latest"
    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == "alice-phc-cure"


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
        assert hasattr(settings, "inference_alice_card")
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()
