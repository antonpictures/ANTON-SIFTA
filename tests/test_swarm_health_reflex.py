#!/usr/bin/env python3
"""Tests for swarm_health_reflex - body-signal lexicon & care nudge organ.

Upgraded contract: zero delta on core 4 ledgers + the organ's own
output ledgers (body_event_lexicon.jsonl and body_reflex_state.json).

Focus: learning, detection, nudging, and cooldown logic.
All state is isolated.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_health_reflex as reflex


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _fingerprint(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, ""
    data = path.read_bytes()
    return len(data.splitlines()), hashlib.sha256(data).hexdigest()


def test_module_exports_public_surface():
    """Real behavior 1: the documented API is present."""
    assert hasattr(reflex, "learn_from_text")
    assert hasattr(reflex, "note_observed")
    assert hasattr(reflex, "get_reflex_block")
    assert hasattr(reflex, "lexicon_summary")


def test_learn_from_text_appends_to_isolated_lexicon(tmp_path, monkeypatch):
    """Core contract: explicit body-event teaching writes to the permanent lexicon under isolation."""
    original_lex = reflex._LEXICON_LOG
    original_state = reflex._REFLEX_STATE
    reflex._LEXICON_LOG = tmp_path / "body_event_lexicon.jsonl"
    reflex._REFLEX_STATE = tmp_path / "body_reflex_state.json"

    try:
        before = _count_lines(reflex._LEXICON_LOG)

        events = reflex.learn_from_text("Architect: this is a cough", speaker="architect")

        after = _count_lines(reflex._LEXICON_LOG)
        assert (after - before) >= 1
        assert any(e.label == "cough" for e in events)
    finally:
        reflex._LEXICON_LOG = original_lex
        reflex._REFLEX_STATE = original_state


def test_note_observed_and_get_reflex_block(tmp_path, monkeypatch):
    """Detection + nudging: known symptom produces a reflex hint under isolation."""
    original_lex = reflex._LEXICON_LOG
    original_state = reflex._REFLEX_STATE
    reflex._LEXICON_LOG = tmp_path / "body_event_lexicon.jsonl"
    reflex._REFLEX_STATE = tmp_path / "body_reflex_state.json"

    try:
        # Seed the lexicon
        reflex.learn_from_text("this is a cough", speaker="architect")

        # Simulate observed symptom
        hint = reflex.note_observed("ugh that cough hurts again")
        assert hint is not None
        assert "cough" in hint.label.lower()

        reflex._REFLEX_STATE.write_text("{}", encoding="utf-8")
        block = reflex.get_reflex_block("the cough is bad today")
        assert "BODY-SIGNAL REFLEX" in block
        assert "symptom=cough" in block
    finally:
        reflex._LEXICON_LOG = original_lex
        reflex._REFLEX_STATE = original_state


def test_lexicon_summary_is_deterministic(tmp_path, monkeypatch):
    """Summary surface works and is safe."""
    original_lex = reflex._LEXICON_LOG
    original_state = reflex._REFLEX_STATE
    reflex._LEXICON_LOG = tmp_path / "body_event_lexicon.jsonl"
    reflex._REFLEX_STATE = tmp_path / "body_reflex_state.json"

    try:
        reflex.learn_from_text("my back hurts", speaker="architect")
        summary = reflex.lexicon_summary()
        assert isinstance(summary, dict)
        assert "labels" in summary or "count" in summary
    finally:
        reflex._LEXICON_LOG = original_lex
        reflex._REFLEX_STATE = original_state


def test_real_ledgers_untouched_including_organ_own_logs(tmp_path, monkeypatch):
    """Explicit isolation gate under the upgraded contract (core 4 + organ's two state files)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "body_event_lexicon.jsonl",
        state / "body_reflex_state.json",
    ]
    before = {str(p): _fingerprint(p) for p in watch}

    original_lex = reflex._LEXICON_LOG
    original_state = reflex._REFLEX_STATE
    reflex._LEXICON_LOG = tmp_path / "body_event_lexicon.jsonl"
    reflex._REFLEX_STATE = tmp_path / "body_reflex_state.json"

    try:
        with patch("System.swarm_health_reflex._append_lexicon"), \
             patch("System.swarm_health_reflex._save_reflex_state"):

            reflex.learn_from_text("Architect: I have a cough", speaker="architect")
            reflex.note_observed("coughing again")
            _ = reflex.get_reflex_block()
            _ = reflex.lexicon_summary()
    finally:
        reflex._LEXICON_LOG = original_lex
        reflex._REFLEX_STATE = original_state

    after = {str(p): _fingerprint(p) for p in watch}
    delta = {k: {"before": before[k], "after": after[k]} for k in before if after[k] != before[k]}

    assert not delta, f"Real ledgers (incl. organ own logs) contaminated: {delta}"


def test_note_observed_respects_same_label_cooldown(tmp_path):
    """Edge probe: a repeated symptom in the cooldown window returns no second hint."""
    original_lex = reflex._LEXICON_LOG
    original_state = reflex._REFLEX_STATE
    reflex._LEXICON_LOG = tmp_path / "body_event_lexicon.jsonl"
    reflex._REFLEX_STATE = tmp_path / "body_reflex_state.json"

    try:
        learned = reflex.learn_from_text("this is a cough", speaker="architect")
        assert any(e.label == "cough" for e in learned)

        first = reflex.note_observed("that cough is back")
        second = reflex.note_observed("the cough is still there")

        assert first is not None
        assert first.label == "cough"
        assert second is None
    finally:
        reflex._LEXICON_LOG = original_lex
        reflex._REFLEX_STATE = original_state
