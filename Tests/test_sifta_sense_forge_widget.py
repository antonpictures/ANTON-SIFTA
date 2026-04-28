from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from Applications import sifta_sense_forge_widget as appmod

_QT_APP: QApplication | None = None


def _app() -> QApplication:
    global _QT_APP
    existing = QApplication.instance()
    if existing is not None:
        return existing
    _QT_APP = QApplication([])
    return _QT_APP


def test_sense_forge_widget_imports_and_renders_without_app_chat(tmp_path, monkeypatch):
    bus_path = tmp_path / "sense_bus.jsonl"
    bus_path.write_text(
        json.dumps(
            {
                "truth": "REAL",
                "animal": "hawk/fly",
                "name": "predator_vision",
                "value": 0.72,
                "confidence": 0.9,
                "source": "fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    fake_snapshot = {
        "field_value": 0.648,
        "truth_counts": {"REAL": 1, "DEMO": 0, "BROKEN": 0, "UNKNOWN": 0},
        "readings": [
            {
                "truth": "REAL",
                "animal": "hawk/fly",
                "name": "predator_vision",
                "hardware": "camera",
                "value": 0.72,
                "confidence": 0.9,
                "contribution": 0.648,
                "source": "fixture",
            }
        ],
    }

    monkeypatch.setattr(appmod, "DEFAULT_SENSE_BUS", bus_path)
    monkeypatch.setattr(appmod, "sample_and_deposit", lambda *, writer: fake_snapshot)
    monkeypatch.setattr(appmod, "publish_focus", lambda *args, **kwargs: None)

    _app()
    widget = appmod.SenseForgeWidget()
    try:
        assert widget.APP_NAME == "SIFTA Sense Forge"
        assert widget._gci_visible is False
        assert widget._table.rowCount() == 1
        assert widget._table.item(0, 0).text() == "REAL"
        assert "field: +0.6480" == widget._field.text()
        assert "fixture" in widget._receipts.toPlainText()
    finally:
        widget.close()


def test_sense_forge_manifest_row_is_canonical_system_settings_app():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    row = manifest["Sense Forge"]

    assert row["category"] == "System Settings"
    assert row["entry_point"] == "Applications/sifta_sense_forge_widget.py"
    assert row["widget_class"] == "SenseForgeWidget"
    assert "REAL" in row["description"]
    assert "DEMO" in row["description"]
