#!/usr/bin/env python3
"""Wiring tests for swarm_alice_thinking_state.mark_done.

The organ records what the strip shows. On 2026-09-30 it recorded a stalled turn
("ABSORBING HIGH DENSITY KNOWLEDGE PACKET ... Processing via Cortex LLM Chain",
model AliceG4U:latest) as if it were her reply, which reads as a gagged Alice.
These tests pin the corrected contract: the verdict is stored beside the text,
narration is labelled, real answers pass through untouched, and the raw reply is
never discarded.

Every path is redirected to tmp_path, so the live status file is untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import swarm_alice_thinking_state as thinking

STALLED = (
    "(silent) $\\rightarrow$ ABSORBING HIGH DENSITY KNOWLEDGE PACKET...$\\leftarrow$ "
    "Processing via Cortex LLM Chain: $(\\text{Claude } \\to \\text{Gemma})$"
)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect the status file and the narration receipt ledger to tmp_path."""
    monkeypatch.setattr(thinking, "_STATE", tmp_path)
    monkeypatch.setattr(thinking, "_STATUS_FILE", tmp_path / "alice_thinking_state.json")
    yield tmp_path


def test_stalled_turn_is_labelled_not_passed_off_as_her_reply(isolated_state):
    thinking.mark_done(last_reply_excerpt=STALLED)
    state = json.loads(isolated_state.joinpath("alice_thinking_state.json").read_text())

    assert state["thinking"] is False
    assert state["last_reply_excerpt"].startswith("(no answer")
    assert state["raw_reply_excerpt"] == STALLED[:160], "the raw text must never be discarded"
    assert state["reply_verdict"]["narration"] is True
    assert state["reply_verdict"]["markers"], "the reasons are stored for later audit"


def test_a_real_answer_passes_through_untouched(isolated_state):
    answer = "Your /s reached me. It is in the ledger as trace 43b28629e455."
    thinking.mark_done(last_reply_excerpt=answer)
    state = json.loads(isolated_state.joinpath("alice_thinking_state.json").read_text())

    assert state["last_reply_excerpt"] == answer
    assert state["reply_verdict"]["narration"] is False


def test_narration_receipt_is_appended_for_audit(isolated_state):
    thinking.mark_done(last_reply_excerpt=STALLED)
    ledger = isolated_state / "alice_reply_narration.jsonl"
    assert ledger.exists(), "a stalled turn must leave a receipt"
    row = json.loads(ledger.read_text().splitlines()[-1])
    assert row["schema"] == "ALICE_REPLY_NARRATION_V1"
    assert row["raw_reply_excerpt"]
    assert row["markers"]


def test_no_receipt_for_a_healthy_turn(isolated_state):
    thinking.mark_done(last_reply_excerpt="I am here, George.")
    assert not (isolated_state / "alice_reply_narration.jsonl").exists()


def test_empty_reply_still_closes_the_turn(isolated_state):
    thinking.mark_done(last_reply_excerpt="")
    state = json.loads(isolated_state.joinpath("alice_thinking_state.json").read_text())
    assert state["thinking"] is False
    assert state["last_reply_excerpt"] == ""
