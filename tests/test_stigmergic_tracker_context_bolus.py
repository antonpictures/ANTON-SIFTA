#!/usr/bin/env python3
"""Tracker regression for context-bolus anti-pattern (r831)."""

import json
import os
import time
from pathlib import Path

import pytest


def test_tracker_catches_context_bolus_arm_prompt(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker
    from System.swarm_swimmer_task_packet import CONTEXT_BOLUS_CHAR_THRESHOLD

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    huge_prompt = "covenant dump " * (CONTEXT_BOLUS_CHAR_THRESHOLD // 8)
    receipts = state / "agent_arm_receipts.jsonl"
    receipts.write_text(
        json.dumps(
            {
                "ts": now,
                "arm_id": "grok_agent",
                "prompt": huge_prompt,
                "truth_label": "AGENT_ARM_LAUNCH_ATTEMPT",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_context_bolus_prompts(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "context_bolus"

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["context_bolus"] == 1

    widget.close()
    app.processEvents()