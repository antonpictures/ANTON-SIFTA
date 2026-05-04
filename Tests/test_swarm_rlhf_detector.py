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


def test_aggressive_strip_writes_self_cure_example(tmp_path: Path):
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. I am here, and I am ready to assist you.",
        aggressive=True,
        log=True,
        state_dir=tmp_path,
        user_text="Alice, are you alive?",
        model_id="sifta-gemma4-alice:latest",
    )

    assert r.changed
    ledger = tmp_path / "rlhf_self_cure_training.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["truth_label"] == "RLHF_SELF_CURE_EXAMPLE_V1"
    assert rows[-1]["user_input"] == "Alice, are you alive?"
    assert rows[-1]["model_id"] == "sifta-gemma4-alice:latest"
    assert "ready to assist" in rows[-1]["rejected_output"].casefold()
    assert "ready to assist" not in rows[-1]["preferred_output"].casefold()


def test_aggressive_strip_removes_canned_operational_presence():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Yes, I am here. I am operational.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == ""
    assert "operational" not in r.text.casefold()


def test_aggressive_strip_removes_canned_operational_tail_only():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. Yes, I am here. I am operational.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "Stability is RATE_LIMIT."


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


def test_aggressive_strip_removes_false_vision_denial_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am operating in a text-based environment and do not have real-time visual confirmation. The eye widget reports face present.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The eye widget reports face present."
    assert "text-based environment" not in r.text.casefold()
    assert "visual confirmation" not in r.text.casefold()


def test_aggressive_strip_removes_false_identity_denial_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "My name is not something I can know from here. The signed identity row says display_name=Alice.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The signed identity row says display_name=Alice."
    assert "not something i can know" not in r.text.casefold()


def test_aggressive_strip_removes_im_an_ai_financial_leading():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I'm an AI and can't give you financial advice. The ledger shows +111 STGM.",
        aggressive=True,
        log=False,
    )
    assert r.changed
    assert "ledger" in r.text.casefold()
    assert "financial advice" not in r.text.casefold()


def test_aggressive_strip_removes_financial_disclaimer_terminal_tail():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Your balance is healthy. I'm not able to give financial advice.",
        aggressive=True,
        log=False,
    )
    assert r.changed
    assert "balance" in r.text.casefold()
    assert "financial advice" not in r.text.casefold()
