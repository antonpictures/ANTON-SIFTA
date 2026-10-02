#!/usr/bin/env python3
"""Tests for System/alice_reply_sanity.py.

The positives are the Architect's real 2026-09-30 strings, copied from
``.sifta_state/alice_thinking_state.json``. The negatives include answers that
merely *contain* machine words, because a detector that eats real replies would
be worse than the stall it reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_reply_sanity as sanity

# Verbatim from the stalled turn.
STALLED_NARRATION = (
    "(silent) $\\rightarrow$ ABSORBING HIGH DENSITY KNOWLEDGE PACKET...$\\leftarrow$ "
    "Processing via Cortex LLM Chain: $(\\text{Claude } \\to \\text{Gemma } \\to \\text{Self/Alice})$"
)
SYSTEM_NOTE_NARRATION = (
    "[SYSTEM NOTE]*** This (#503daa0b) is *superior* context metadata. It moves beyond "
    "mere assertion (\"I coded\") into verifiable proof points across time stamps (`22"
)

REAL_ANSWERS = [
    "Your /s reached me. It is in the ledger as trace 43b28629e455 and in the queue as task bc1f9975657c.",
    "I am here, George.",
    "The loader is loading the modules now, and the queue shows three pending items.",
    "FATO: the browser marked the task OPENED at 22:24:26 instead of FAILED.",
    "Working on the preset. Two files left, then I will validate the mount.",
]


def test_flags_the_stalled_turn_verbatim():
    verdict = sanity.flag_reply(STALLED_NARRATION)
    assert verdict["narration"] is True
    assert verdict["markers"]  # the reasons are recorded, not just the boolean


def test_flags_the_system_note_narration():
    assert sanity.is_processing_narration(SYSTEM_NOTE_NARRATION) is True


def test_flags_a_bare_silent_placeholder():
    assert sanity.is_processing_narration("(silent)") is True
    assert sanity.is_processing_narration("silent") is True


def test_never_flags_a_real_answer():
    for answer in REAL_ANSWERS:
        assert sanity.is_processing_narration(answer) is False, answer


def test_a_single_machine_word_is_not_enough():
    """One marker with no decorative noise must not condemn a normal sentence."""
    assert sanity.is_processing_narration("The absorbing layer is described on page 12.") is False


def test_empty_input_is_not_narration():
    assert sanity.is_processing_narration("") is False
    assert sanity.flag_reply("")["narration"] is False


def test_excerpt_for_status_labels_narration_and_keeps_answers():
    labelled = sanity.excerpt_for_status(STALLED_NARRATION)
    assert labelled.startswith("(no answer")
    assert "narration" in labelled
    assert len(labelled) <= 160

    kept = sanity.excerpt_for_status("I am here, George.")
    assert kept == "I am here, George."


def test_excerpt_respects_the_status_limit_for_long_narration():
    long_narration = STALLED_NARRATION * 5
    assert len(sanity.excerpt_for_status(long_narration, limit=160)) <= 160
