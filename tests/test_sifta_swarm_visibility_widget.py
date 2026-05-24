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


def test_swarm_field_widget_constructs_and_renders(monkeypatch, tmp_path):
    import Applications.sifta_swarm_visibility_widget as widget_mod

    _app()
    widget_mod.SwarmFieldWidget._live_instance = None
    widget_mod.SwarmFieldWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(widget_mod, "behavior_clock", None)
    focus_rows = []
    monkeypatch.setattr(widget_mod, "_publish_focus", lambda *args, **kwargs: focus_rows.append((args, kwargs)))
    monkeypatch.setattr(widget_mod, "full_snapshot", _sample_snapshot)
    monkeypatch.setattr(widget_mod, "_STATE", tmp_path)
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({
            "payload": {
                "ts": 1.0,
                "role": "user",
                "text": "[Matrix Terminal]: Alice open Grok",
                "routing_metadata": {"surface": "matrix_terminal"},
            }
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "sifta_desktop_app_state.json").write_text(
        json.dumps({"desktop_mode": "chat", "active_app": "Terminal", "open_apps": ["Terminal"]}),
        encoding="utf-8",
    )
    (tmp_path / "app_focus.jsonl").write_text(
        json.dumps({"ts": 1.0, "app": "Terminal", "detail": "Matrix Terminal focused"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "matrix_terminal_process_trace.jsonl").write_text(
        json.dumps({"ts": 1.0, "action": "write_command", "text": "send command -> grok: grok"}) + "\n",
        encoding="utf-8",
    )

    w = widget_mod.SwarmFieldWidget()
    assert w.windowTitle() == "Swarm Field"
    assert "terminal" in w._organs["text"].toPlainText()
    assert "LLM_REGISTRATION" in w._field["text"].toPlainText()
    assert "99.97" in w._stgm["text"].toPlainText()
    assert "Codex" in w._swimmers["text"].toPlainText()
    assert "Matrix Terminal" in w._global_chat["text"].toPlainText()
    assert "Terminal" in w._territory["text"].toPlainText()
    assert "write_command" in w._process["text"].toPlainText()
    assert focus_rows

    again = widget_mod.SwarmFieldWidget()
    assert again is w
    w.close()


def test_widget_tail_jsonl_uses_bounded_file_tail(monkeypatch, tmp_path):
    import Applications.sifta_swarm_visibility_widget as widget_mod

    path = tmp_path / "alice_conversation.jsonl"
    path.write_text(
        "".join(
            json.dumps({"payload": {"role": "user", "text": f"old-{i}", "ts": i}}) + "\n"
            for i in range(80)
        )
        + json.dumps({"payload": {"role": "assistant", "text": "latest", "ts": 100}}) + "\n",
        encoding="utf-8",
    )

    def fail_read_text(self, *args, **kwargs):
        raise AssertionError(f"full text read in widget tailer: {self}")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    rows = widget_mod._tail_jsonl(path, 3)

    assert [row["payload"]["text"] for row in rows] == ["old-78", "old-79", "latest"]


def test_swarm_field_manifest_entry_points_to_existing_widget():
    manifest = json.loads((REPO / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["Swarm Field"]
    path = REPO / entry["entry_point"]
    assert path.exists()
    assert entry["widget_class"] == "SwarmFieldWidget"
    assert entry["category"] == "Alice"
