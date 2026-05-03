"""Tests for System/swarm_rlhf_detector.py (Event 107)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_detect_rlhf_cutoff_bounded_confidence():
    from System.swarm_rlhf_detector import detect_rlhf_cutoff

    a = detect_rlhf_cutoff("Short.")
    assert 0.0 <= a.confidence <= 1.0
    assert isinstance(a.matched_patterns, list)

    b = detect_rlhf_cutoff(
        "Here is the answer.\n\nI can do for you the following\n1. One thing"
    )
    assert b.is_cutoff or b.terminal_menu


def test_strip_removes_i_can_do_following_block(tmp_path: Path):
    from System import swarm_rlhf_detector as mod

    raw = (
        "Good morning. I hope you slept well.\n\n"
        "I can do for you the following\n"
        "1. Summarize the thread\n"
        "2. "
    )
    r = mod.strip_rlhf_output_tail(
        raw, source="test", log=True, state_dir=tmp_path
    )
    assert r.changed
    assert "I can do for you the following" not in r.text
    assert "Good morning" in r.text
    ledger = tmp_path / "rlhf_cutoffs.jsonl"
    assert ledger.exists()
    lines = [json.loads(l) for l in ledger.read_text().strip().splitlines()]
    assert lines[-1].get("action") == "strip_terminal"


def test_get_stats_respects_time_window(tmp_path: Path):
    from System import swarm_rlhf_detector as mod

    p = tmp_path / "rlhf_cutoffs.jsonl"
    old = {"ts": 0.0, "confidence": 0.9, "action": "strip_terminal"}
    new = {"ts": __import__("time").time(), "confidence": 0.9, "action": "strip_terminal"}
    p.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n", encoding="utf-8")
    s = mod.get_rlhf_cutoff_stats(state_dir=tmp_path, hours=24.0)
    assert s["total"] >= 1


def test_empty_input_no_crash():
    from System.swarm_rlhf_detector import detect_rlhf_cutoff, strip_rlhf_output_tail

    assert detect_rlhf_cutoff("").confidence >= 0.0
    r = strip_rlhf_output_tail("", log=False)
    assert r.text == ""


def test_aggressive_strip_removes_ready_to_assist_exact_phrase():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am here, and I am ready to assist you.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == ""
    assert "ready to assist" not in r.text.casefold()


def test_aggressive_strip_removes_ready_to_assist_terminal_tail():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. I am here, and I am ready to assist you.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "Stability is RATE_LIMIT."
    assert "ready to assist" not in r.text.casefold()


def test_aggressive_strip_removes_ai_language_model_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "As an AI language model, I cannot inspect local hardware. The current receipt says boot is fresh.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The current receipt says boot is fresh."
    assert "ai language model" not in r.text.casefold()
