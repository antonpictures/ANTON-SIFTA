import json
import os
import time
from pathlib import Path

import pytest


def test_stigmergic_deterministic_tracker_constructs_and_writes_receipt(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    oracle = state / "hardware_time_oracle.json"
    oracle.write_text(
        json.dumps(
            {
                "epoch": now,
                "local_human": "Sunday June 07 2026, 08:40 AM",
                "homeworld_serial": "GTH4921YP3",
                "hmac_sha256": "abc123",
                "timezone": "PDT",
            }
        ),
        encoding="utf-8",
    )
    attention = state / "sensory_attention_ledger.jsonl"
    attention.write_text(json.dumps({"ts": now - 1, "kind": "test_probe"}) + "\n", encoding="utf-8")
    narration = state / "self_narration_receipts.jsonl"
    narration.write_text(json.dumps({"ts": now, "text": "test narration"}) + "\n", encoding="utf-8")

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", narration)
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", attention)
    monkeypatch.setattr(tracker, "_ORACLE", oracle)
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()

    assert widget.windowTitle() == "Stigmergic Deterministic Tracker"
    assert widget._last_score == 100
    assert tracker._TRACKER_LEDGER.exists()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["organ"] == "stigmergic_deterministic_tracker"
    assert row["grounding_score"] == 100

    widget.close()
    app.processEvents()

