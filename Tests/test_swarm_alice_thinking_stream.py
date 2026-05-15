"""Tests for the thinking-stream organ.

These pin:
  - set_think_flag mutates the payload to {"think": True}.
  - parse_chat_stream_chunk splits content vs thinking vs done.
  - The recorder buffers chunks separately and writes a receipt with
    sha256, char counts, and duration.
  - consume_stream returns concatenated (content, thinking) and
    routes through the recorder when provided.
  - Empty / malformed chunks are tolerated, not raised.
  - The receipt names the model and a turn_input_preview so an
    auditor can replay later.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_thinking_stream import (  # noqa: E402
    THINKING_LEDGER,
    TRUTH_LABEL,
    ThinkingTraceRecorder,
    consume_stream,
    parse_chat_stream_chunk,
    set_think_flag,
)


# ── payload helper ────────────────────────────────────────────────────────


def test_set_think_flag_true_by_default():
    payload = {"model": "x", "messages": []}
    out = set_think_flag(payload)
    assert out is payload
    assert payload["think"] is True


def test_set_think_flag_can_set_false():
    payload = {}
    set_think_flag(payload, think=False)
    assert payload["think"] is False


# ── chunk parser ──────────────────────────────────────────────────────────


def test_parse_chunk_with_content_only():
    c, t, d = parse_chat_stream_chunk({"message": {"content": "hello"}})
    assert c == "hello"
    assert t == ""
    assert d is False


def test_parse_chunk_with_thinking_only():
    c, t, d = parse_chat_stream_chunk({"message": {"thinking": "let me think"}})
    assert c == ""
    assert t == "let me think"
    assert d is False


def test_parse_chunk_with_both_fields():
    c, t, d = parse_chat_stream_chunk({"message": {"content": "h", "thinking": "w"}})
    assert c == "h"
    assert t == "w"


def test_parse_chunk_done_flag():
    c, t, d = parse_chat_stream_chunk({"done": True})
    assert d is True


def test_parse_chunk_handles_malformed_input():
    assert parse_chat_stream_chunk(None) == ("", "", False)
    assert parse_chat_stream_chunk({"message": None}) == ("", "", False)
    assert parse_chat_stream_chunk({}) == ("", "", False)
    assert parse_chat_stream_chunk({"message": {"content": None}}) == ("", "", False)


# ── recorder ──────────────────────────────────────────────────────────────


def test_recorder_writes_receipt_with_sha256(tmp_path):
    rec = ThinkingTraceRecorder(
        model="m1",
        turn_input_preview="who are you learning from",
        state_dir=tmp_path,
    )
    rec.append_thinking("Let me check. ")
    rec.append_thinking("The receipts confirm George.")
    rec.append_content("I am learning from George.")
    receipt = rec.close(write=True)
    assert receipt["truth_label"] == TRUTH_LABEL
    assert receipt["thinking_chars"] > 0
    assert receipt["content_chars"] > 0
    assert receipt["thinking_chunks"] == 2
    assert len(receipt["thinking_sha256"]) == 64
    assert len(receipt["sha256"]) == 64
    assert receipt["model"] == "m1"
    assert "George" in receipt["thinking_preview"]
    # Ledger written
    ledger = tmp_path / THINKING_LEDGER
    assert ledger.exists()
    last = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert last["truth_label"] == TRUTH_LABEL


def test_recorder_can_skip_write(tmp_path):
    rec = ThinkingTraceRecorder(model="m", state_dir=tmp_path)
    rec.append_thinking("hidden")
    receipt = rec.close(write=False)
    assert receipt["thinking_chars"] == 6
    # No ledger row written
    assert not (tmp_path / THINKING_LEDGER).exists()


def test_recorder_records_duration(tmp_path):
    rec = ThinkingTraceRecorder(model="m", state_dir=tmp_path)
    time.sleep(0.01)
    rec.append_thinking("a")
    receipt = rec.close(write=False)
    assert receipt["duration_s"] >= 0.01


def test_recorder_empty_run_writes_zero_counts(tmp_path):
    rec = ThinkingTraceRecorder(model="m", state_dir=tmp_path)
    receipt = rec.close(write=True)
    assert receipt["thinking_chars"] == 0
    assert receipt["thinking_chunks"] == 0
    assert receipt["content_chars"] == 0


# ── consume_stream end-to-end ────────────────────────────────────────────


def test_consume_stream_concatenates_content_and_thinking():
    chunks = [
        {"message": {"thinking": "Let me check. "}},
        {"message": {"thinking": "George is here. "}},
        {"message": {"content": "I am learning from George."}},
        {"done": True},
    ]
    content, thinking = consume_stream(chunks)
    assert content == "I am learning from George."
    assert thinking == "Let me check. George is here. "


def test_consume_stream_routes_to_recorder(tmp_path):
    rec = ThinkingTraceRecorder(model="m", state_dir=tmp_path)
    chunks = [
        {"message": {"thinking": "Reasoning step 1."}},
        {"message": {"content": "Final."}},
        {"done": True},
    ]
    content, thinking = consume_stream(chunks, recorder=rec)
    assert content == "Final."
    assert thinking == "Reasoning step 1."
    receipt = rec.close(write=True)
    assert receipt["thinking_chunks"] == 1
    assert receipt["content_chars"] == 6
