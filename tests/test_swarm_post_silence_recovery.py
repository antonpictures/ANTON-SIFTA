#!/usr/bin/env python3
"""Tests for swarm_post_silence_recovery — Round 50 / Tasks #55, #57, #50.

Five-failure-chain recovery layer:
  - silence self-narration block fires when last assistant turn was (silent: <reason>)
  - correction-shape detector fires on owner correction language
  - composed prompt block honors both with no leakage to other rows

All test isolation: writes go to tmp_path, real .sifta_state is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_post_silence_recovery as recovery


def _write_conversation(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# ─── recent_silence_summary ────────────────────────────────────────────


def test_recent_silence_summary_returns_none_when_no_conversation(tmp_path):
    """Empty / missing file is harmless — returns None, never raises."""
    summary = recovery.recent_silence_summary(tmp_path)
    assert summary is None


def test_recent_silence_summary_returns_none_when_last_alice_turn_is_normal(tmp_path):
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "hello"},
        {"ts": 2.0, "role": "alice", "text": "Hi George, good to see you."},
    ])
    assert recovery.recent_silence_summary(tmp_path) is None


def test_recent_silence_summary_fires_on_repetition_collapse(tmp_path):
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "remind me what we agreed yesterday"},
        {"ts": 2.0, "role": "alice", "text": "(silent: repetition collapse)"},
    ])
    s = recovery.recent_silence_summary(tmp_path)
    assert s is not None
    assert s["silenced"] is True
    # Reason is normalized to underscore form (canonical) but original space form
    # is in the narratable set; we accept either canonical.
    assert s["reason"] in ("repetition_collapse", "repetition collapse")
    assert s["alice_ts"] == 2.0
    assert "what we agreed yesterday" in s["prior_user_text"]
    assert s["prior_user_ts"] == 1.0


def test_recent_silence_summary_fires_on_self_quote_cascade(tmp_path):
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "what did you mean earlier"},
        {"ts": 2.0, "role": "alice", "text": "(silent: self_quote_cascade_intercepted)"},
    ])
    s = recovery.recent_silence_summary(tmp_path)
    assert s is not None
    assert s["reason"] == "self_quote_cascade_intercepted"


def test_recent_silence_summary_ignores_non_narratable_silence(tmp_path):
    """A bare `(silent)` row (no reason) is NOT in the narratable set."""
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "hey"},
        {"ts": 2.0, "role": "alice", "text": "(silent)"},
    ])
    assert recovery.recent_silence_summary(tmp_path) is None


def test_recent_silence_summary_only_uses_most_recent_alice_turn(tmp_path):
    """If the last alice turn is NORMAL (after an earlier silence), do not fire."""
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "what?"},
        {"ts": 2.0, "role": "alice", "text": "(silent: repetition collapse)"},
        {"ts": 3.0, "role": "user", "text": "are you there"},
        {"ts": 4.0, "role": "alice", "text": "I am here, sorry about that."},
        {"ts": 5.0, "role": "user", "text": "ok"},
    ])
    # The last alice row is normal — already recovered. Do NOT narrate again.
    assert recovery.recent_silence_summary(tmp_path) is None


def test_recent_silence_summary_finds_prior_user_text_through_intermediate_rows(tmp_path):
    """Owner row immediately before the silence is the one whose intent got swallowed."""
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "system", "text": "(some system note)"},
        {"ts": 2.0, "role": "user", "text": "summary of yesterday please"},
        {"ts": 3.0, "role": "system", "text": "(brain spawned)"},
        {"ts": 4.0, "role": "alice", "text": "(silent: repetition collapse)"},
    ])
    s = recovery.recent_silence_summary(tmp_path)
    assert s is not None
    assert "summary of yesterday" in s["prior_user_text"]


def test_recent_silence_summary_skips_malformed_rows(tmp_path):
    """Malformed JSON lines are skipped — must not break."""
    path = tmp_path / "alice_conversation.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write("{not json at all\n")
        fh.write(json.dumps({"ts": 1.0, "role": "user", "text": "hi"}) + "\n")
        fh.write("garbage line\n")
        fh.write(json.dumps({"ts": 2.0, "role": "alice", "text": "(silent: repetition collapse)"}) + "\n")
    s = recovery.recent_silence_summary(tmp_path)
    assert s is not None
    assert s["reason"] in ("repetition_collapse", "repetition collapse")


# ─── detect_correction_shape ───────────────────────────────────────────────


def test_correction_shape_returns_none_on_normal_chat():
    assert recovery.detect_correction_shape("hello alice how are you") is None
    assert recovery.detect_correction_shape("what's the weather like") is None
    assert recovery.detect_correction_shape("write me a python script") is None
    assert recovery.detect_correction_shape("") is None
    assert recovery.detect_correction_shape(None) is None  # type: ignore[arg-type]


def test_correction_shape_fires_on_phone_audio_correction():
    """The exact transcript from §19.4 Failure D."""
    text = (
        "Alice, you captured the previous conversation with tts microphone, "
        "sometimes mispells. I'm george, i was on the phone with my friend "
        "carlton, marketing department. so you heard audio to text"
    )
    det = recovery.detect_correction_shape(text)
    assert det is not None
    assert det["is_correction"] is True
    # Multiple patterns should fire on this realistic example.
    assert len(det["patterns_hit"]) >= 2
    assert any("audio" in p or "phone" in p for p in det["patterns_hit"])


def test_correction_shape_fires_on_misheard():
    det = recovery.detect_correction_shape("you misheard me, I said George not Jordan")
    assert det is not None
    assert "owner_says_alice_misheard" in det["patterns_hit"]


def test_correction_shape_fires_on_not_addressed():
    det = recovery.detect_correction_shape("that wasn't for you, sorry")
    assert det is not None
    assert "owner_says_input_was_not_addressed" in det["patterns_hit"]


def test_correction_shape_fires_on_side_conversation():
    det = recovery.detect_correction_shape("ignore that, it was a side conversation")
    assert det is not None
    assert "owner_says_audio_was_side_conversation" in det["patterns_hit"]


def test_correction_shape_fires_on_clarify_phrasing():
    det = recovery.detect_correction_shape("actually I meant the other ledger")
    assert det is not None
    assert "owner_clarifies_prior_intent" in det["patterns_hit"]


# ─── recovery_prompt_block ─────────────────────────────────────────────────


def test_recovery_prompt_block_empty_when_no_signals(tmp_path):
    assert recovery.recovery_prompt_block(tmp_path, "hello there") == ""


def test_recovery_prompt_block_contains_silence_narration_when_silenced(tmp_path):
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "explain the receipts"},
        {"ts": 2.0, "role": "alice", "text": "(silent: repetition collapse)"},
    ])
    block = recovery.recovery_prompt_block(tmp_path, "are you there?")
    assert "POST-SILENCE SELF-NARRATION REQUIRED" in block
    assert "repetition" in block.lower()
    assert "explain the receipts" in block


def test_recovery_prompt_block_contains_correction_block_when_user_corrects(tmp_path):
    block = recovery.recovery_prompt_block(
        tmp_path,
        "you misheard me — I said George not Jordan",
    )
    assert "REALITY RECOVERY" in block
    assert "owner_says_alice_misheard" in block
    assert "DO NOT greet" in block


def test_recovery_prompt_block_contains_both_when_both_fire(tmp_path):
    """Five-failure-chain: silence + correction in the same turn."""
    path = tmp_path / "alice_conversation.jsonl"
    _write_conversation(path, [
        {"ts": 1.0, "role": "user", "text": "what did you do"},
        {"ts": 2.0, "role": "alice", "text": "(silent: repetition collapse)"},
    ])
    block = recovery.recovery_prompt_block(
        tmp_path,
        "you captured tts audio from my phone call — that wasn't for you",
    )
    assert "POST-SILENCE SELF-NARRATION REQUIRED" in block
    assert "REALITY RECOVERY" in block


def test_recovery_prompt_block_never_raises_on_corrupt_state(tmp_path):
    """Corrupt state dir / unreadable file → empty block, no crash."""
    bogus = tmp_path / "doesnotexist" / "nope"
    # No file → recent_silence_summary returns None → block is ""
    assert recovery.recovery_prompt_block(bogus, "normal chat") == ""


def test_real_ledgers_untouched(tmp_path):
    """Hard invariant: the recovery layer is READ-ONLY against the conversation ledger."""
    state = Path(".sifta_state")
    watch = [
        state / "alice_conversation.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    # Run the full surface with various inputs
    _ = recovery.recent_silence_summary(tmp_path)
    _ = recovery.detect_correction_shape("you misheard")
    _ = recovery.recovery_prompt_block(tmp_path, "you misheard")

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], f"recovery layer mutated {k}: {before[k]} -> {after[k]}"
