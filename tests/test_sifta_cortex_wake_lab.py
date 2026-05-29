from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    Qt = None
    QApplication = None

from System.swarm_cortex_wake_probe import CortexModelSpec


@pytest.fixture(scope="module")
def qapp():
    if QApplication is None:
        pytest.skip("PyQt6 unavailable")
    app = QApplication.instance() or QApplication([])
    yield app


def test_manifest_registers_cortex_wake_lab() -> None:
    manifest = json.loads(Path("Applications/apps_manifest.json").read_text(encoding="utf-8"))

    entry = manifest["Cortex Wake Lab"]

    assert entry["entry_point"] == "Applications/sifta_cortex_wake_lab.py"
    assert entry["widget_class"] == "CortexWakeLabWidget"
    assert entry["category"] == "Developer"


def test_widget_lists_questions_and_models(qapp, monkeypatch) -> None:
    from Applications import sifta_cortex_wake_lab as appmod

    monkeypatch.setattr(
        appmod.wake_probe,
        "list_cortex_models",
        lambda: [
            CortexModelSpec(
                model_id="alice-test:latest",
                provider="ollama",
                available=True,
                source="test",
            )
        ],
    )
    monkeypatch.setattr(appmod.wake_probe, "latest_summary", lambda: {"models": []})

    widget = appmod.CortexWakeLabWidget()

    assert widget.models.count() == 1
    assert "experience_definition" in widget.questions.toPlainText()


def test_widget_selected_models(qapp, monkeypatch) -> None:
    from Applications import sifta_cortex_wake_lab as appmod

    monkeypatch.setattr(
        appmod.wake_probe,
        "list_cortex_models",
        lambda: [
            CortexModelSpec("alice-a:latest", "ollama", True, "test"),
            CortexModelSpec("alice-b:latest", "ollama", True, "test"),
        ],
    )
    monkeypatch.setattr(appmod.wake_probe, "latest_summary", lambda: {"models": []})

    widget = appmod.CortexWakeLabWidget()
    widget.models.item(0).setCheckState(Qt.CheckState.Checked)
    widget.models.item(1).setCheckState(Qt.CheckState.Unchecked)

    assert widget.selected_models() == ["alice-a:latest"]


def test_render_summary_populates_table(qapp, monkeypatch) -> None:
    from Applications import sifta_cortex_wake_lab as appmod

    monkeypatch.setattr(appmod.wake_probe, "list_cortex_models", lambda: [])
    monkeypatch.setattr(appmod.wake_probe, "latest_summary", lambda: {"models": []})

    widget = appmod.CortexWakeLabWidget()
    widget.render_summary(
        {
            "models": [
                {
                    "model_id": "alice-a:latest",
                    "questions": 5,
                    "ok": 5,
                    "errors": 0,
                    "avg_grounding_score": 0.91,
                    "avg_latency_s": 1.2,
                }
            ]
        }
    )

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "alice-a:latest"
