"""Tests for the BeeSon-native Swarm Field visibility widget."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_QT_APP = None


def _app():
    global _QT_APP
    _QT_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _QT_APP


def _sample_snapshot():
    return {
        "organs": [
            {
                "organ": "terminal",
                "ledger": "terminal_organ.jsonl",
                "exists": True,
                "row_count": 2,
                "health": "green",
                "head": "abc123",
                "age_s": 0.2,
            }
        ],
        "field": [
            {
                "ledger": "ide_stigmergic_trace.jsonl",
                "type": "LLM_REGISTRATION",
                "doctor": "Codex",
                "trace_id": "t1",
                "ts": 1.0,
            }
        ],
        "stgm": {
            "current_balance": 99.97,
            "entries": [
                {"type": "STGM_DEBIT", "amount": 0.01, "balance_after": 99.97, "reason": "test"}
            ],
        },
        "swimmers": [
            {"doctor": "Codex", "model": "gpt-5", "lane": "Surgeon", "trace_id": "t1", "ts": 1.0}
        ],
        "snapshot_ts": 1.0,
    }


def test_swarm_field_widget_constructs_and_renders(monkeypatch):
    import Applications.sifta_swarm_visibility_widget as widget_mod

    _app()
    widget_mod.SwarmFieldWidget._live_instance = None
    widget_mod.SwarmFieldWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(widget_mod, "behavior_clock", None)
    focus_rows = []
    monkeypatch.setattr(widget_mod, "_publish_focus", lambda *args, **kwargs: focus_rows.append((args, kwargs)))
    monkeypatch.setattr(widget_mod, "full_snapshot", _sample_snapshot)

    w = widget_mod.SwarmFieldWidget()
    assert w.windowTitle() == "Swarm Field"
    assert "terminal" in w._organs["text"].toPlainText()
    assert "LLM_REGISTRATION" in w._field["text"].toPlainText()
    assert "99.97" in w._stgm["text"].toPlainText()
    assert "Codex" in w._swimmers["text"].toPlainText()
    assert focus_rows

    again = widget_mod.SwarmFieldWidget()
    assert again is w
    w.close()


def test_swarm_field_manifest_entry_points_to_existing_widget():
    manifest = json.loads((REPO / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["Swarm Field"]
    path = REPO / entry["entry_point"]
    assert path.exists()
    assert entry["widget_class"] == "SwarmFieldWidget"
    assert entry["category"] == "Alice"
