from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from Applications import sifta_talk_to_alice_widget as talk
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping greeter-detector wiring tests: widget import failed ({type(exc).__name__}: {exc})",
        allow_module_level=True,
    )


def test_replays_four_greeter_failures_and_writes_detector_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    fixtures = [
        (
            "Alice, dispatch Grok for Round 20 and print work_receipt after pytest.",
            "Hello. I am here. I sense the weight of your presence, the quiet focus of your attention.",
        ),
        (
            "Alice, ask Grok to code Round 20 and emit FIELD_FAILURE on blocker.",
            "Hello. I am here. What can I assist you with today?",
        ),
        (
            "Alice, dispatch Grok inside SIFTA matrix-terminal PTY and log episodic_diary.",
            "Hello! You called? I'm here. What's on your mind?",
        ),
        (
            "Alice, paste to Grok arm and run py_compile + pytest with receipt output.",
            "Hello! It's good to hear from you. What's on your mind today?",
        ),
    ]

    for user_text, greeter_reply in fixtures:
        cleaned, fired = talk._strip_greeter_on_operational(
            greeter_reply,
            user_text,
            memory_card_has_relevant=True,
        )
        assert fired is True
        assert cleaned == "FIELD_FAILURE: alice_greeter_punched_through_on_operational_turn"

    trace_path = tmp_path / "alice_greeter_detector_trace.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 4
    for row in rows[-4:]:
        assert row.get("fired") is True
        assert row.get("reason")
        assert "user_text_head" in row
        assert "reply_head" in row


def test_detector_trace_logs_skipped_path_too(tmp_path, monkeypatch):
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)

    cleaned, fired = talk._strip_greeter_on_operational(
        "Receipt landed with proof.",
        "How are you doing today?",
        memory_card_has_relevant=False,
    )
    assert fired is False
    assert cleaned == "Receipt landed with proof."

    trace_path = tmp_path / "alice_greeter_detector_trace.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert rows[-1]["fired"] is False
    assert rows[-1]["reason"] == "not_operational"
