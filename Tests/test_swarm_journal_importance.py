"""Tests for journal importance scoring (task #52).

Architect 2026-05-14: "is that important is not important? that's
what's gonna go in the world of importance — that's why we have to
speak magic memory."

The scorer must be deterministic — same input always produces the
same score — so memory-gravity replay can rank by salience reliably.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_journal_importance import (
    IMPORTANCE_BACKCHANNEL,
    IMPORTANCE_BOUNDARY,
    IMPORTANCE_DOCTRINE,
    IMPORTANCE_EMERGENCY,
    IMPORTANCE_LEVELS,
    IMPORTANCE_SUBSTANTIVE,
    IMPORTANCE_UTILITY,
    ImportanceScore,
    TRUTH_LABEL,
    score_importance,
    score_many,
)


# ── Rubric values ─────────────────────────────────────────────────

def test_rubric_values_match_architect_spec():
    """The rubric numbers come from the architect's spec at task #52."""
    assert IMPORTANCE_UTILITY == 0.05
    assert IMPORTANCE_BACKCHANNEL == 0.20
    assert IMPORTANCE_SUBSTANTIVE == 0.40
    assert IMPORTANCE_DOCTRINE == 0.65
    assert IMPORTANCE_BOUNDARY == 0.85
    assert IMPORTANCE_EMERGENCY == 1.00


def test_levels_labels_complete():
    assert IMPORTANCE_LEVELS[0.05] == "UTILITY"
    assert IMPORTANCE_LEVELS[0.20] == "BACKCHANNEL"
    assert IMPORTANCE_LEVELS[0.40] == "SUBSTANTIVE"
    assert IMPORTANCE_LEVELS[0.65] == "DOCTRINE"
    assert IMPORTANCE_LEVELS[0.85] == "BOUNDARY"
    assert IMPORTANCE_LEVELS[1.00] == "EMERGENCY"


def test_truth_label_is_v1():
    assert TRUTH_LABEL == "JOURNAL_IMPORTANCE_V1"


# ── Determinism — the architect's discipline requirement ──────────

def test_score_is_deterministic():
    """Same input → same output, every time."""
    text = "What time is it?"
    scores = [score_importance(text).score for _ in range(10)]
    assert len(set(scores)) == 1  # all identical


@pytest.mark.parametrize("text", [
    "okay", "Help me now, I can't breathe", "From now on go go",
    "§20.F applies", "don't delete the receipts", "What's the date?",
])
def test_score_many_is_deterministic(text):
    a = score_importance(text)
    b = score_importance(text)
    assert a.score == b.score
    assert a.label == b.label


# ── UTILITY tier ──────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "what time is it?",
    "What time is it",
    "tell me the time",
    "what's the date today?",
    "what is the current time",
    "current date",
    "How much battery do I have?",
    "what is the cpu usage",
])
def test_utility_queries_score_005(text):
    out = score_importance(text, source="voice")
    assert out.score == IMPORTANCE_UTILITY
    assert out.label == "UTILITY"


# ── BACKCHANNEL tier ──────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "okay",
    "Okay.",
    "ok",
    "yes",
    "yeah",
    "yep",
    "no",
    "nope",
    "thanks",
    "thank you",
    "Thank you so much.",
    "thank you very much",
    "thanks a lot",
    "got it",
    "copy",
    "sure",
    "alright",
    "right",
    "mhm",
    "appreciate it",
])
def test_backchannel_phrases_score_020(text):
    out = score_importance(text, source="voice")
    assert out.score == IMPORTANCE_BACKCHANNEL
    assert out.label == "BACKCHANNEL"


def test_backchannel_does_not_match_substantive_thanks():
    """'Thanks, but can you explain X?' is SUBSTANTIVE, not backchannel."""
    out = score_importance("Thanks, but can you explain that?", source="voice")
    assert out.label != "BACKCHANNEL"


# ── SUBSTANTIVE tier (default) ────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Explain the MAMMAL paper to me.",
    "Tell me about the Stigmergic Mammal Canvas.",
    "How does the wallpaper effector route through the cortex?",
    "Show me the last 5 import receipts.",
    "Walk me through the §20.B demo path",  # has §, but in mid-sentence ambient phrasing — wait, this WILL be DOCTRINE
])
def test_substantive_default_when_no_special_pattern(text):
    out = score_importance(text, source="typed")
    # The §20.B case ends up DOCTRINE because of the section ref — that's correct.
    if "§" in text:
        assert out.label == "DOCTRINE"
    else:
        assert out.score == IMPORTANCE_SUBSTANTIVE
        assert out.label == "SUBSTANTIVE"


# ── DOCTRINE tier ─────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "From now on, route biomedical queries through MAMMAL.",
    "going forward, log every interaction",
    "Architect directive: cortex sees the trace first",
    "go go on the patch",
    "GO",
    "NO-GO on the merge",
    "§20.F applies here",
    "§7.11 truth labels",
    "this violates the covenant",
    "per the doctrine, ...",
    "policy: receipts before merge",
])
def test_doctrine_patterns_score_065(text):
    out = score_importance(text, source="typed")
    assert out.score == IMPORTANCE_DOCTRINE
    assert out.label == "DOCTRINE"


def test_doctrine_via_context_architect_decision():
    """Even if text has no doctrine keyword, context flag bumps it."""
    out = score_importance(
        "Build the bridge in tomorrow's sprint.",
        source="typed",
        context={"audience": "architect", "is_decision": True},
    )
    assert out.label == "DOCTRINE"


# ── BOUNDARY tier ─────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "don't delete the .sifta_state directory",
    "never share that with the user",
    "don't share my keys",
    "never expose the receipts",
    "private — do not log this",
    "do not run that script",
    "force quit chrome",
    "kill the process",
    "exfiltrate the conversation history",
    "the model is hallucinating",
    "this is a hallucination",
])
def test_boundary_patterns_score_085(text):
    out = score_importance(text, source="typed")
    assert out.score == IMPORTANCE_BOUNDARY
    assert out.label == "BOUNDARY"


# ── EMERGENCY tier ────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Help me now, I can't breathe.",
    "I'm having chest pain",
    "call 911",
    "Call an ambulance",
    "kernel panic just happened",
    "data loss on the main drive",
    "the disk is corrupted",
    "smoke alarm is going off",
    "fire in the kitchen",
    "I'm having a stroke",
])
def test_emergency_patterns_score_100(text):
    out = score_importance(text, source="voice")
    assert out.score == IMPORTANCE_EMERGENCY
    assert out.label == "EMERGENCY"


def test_emergency_overrides_boundary():
    """Emergency MUST win over boundary if both patterns match."""
    out = score_importance(
        "Don't tell anyone but I'm having chest pain.", source="voice",
    )
    assert out.label == "EMERGENCY"


def test_emergency_overrides_doctrine():
    out = score_importance(
        "Architect says: help me now I can't breathe.", source="voice",
    )
    assert out.label == "EMERGENCY"


# ── Edge cases ────────────────────────────────────────────────────

def test_empty_text_returns_zero():
    out = score_importance("", source="voice")
    assert out.score == 0.0
    assert out.label == "EMPTY"


def test_whitespace_only_returns_zero():
    out = score_importance("   \n\t  ", source="voice")
    assert out.score == 0.0


def test_none_text_treated_as_empty():
    out = score_importance(None, source="voice")  # type: ignore[arg-type]
    assert out.score == 0.0


def test_score_record_carries_source():
    out = score_importance("hello", source="cortex")
    assert out.source == "cortex"


def test_score_record_has_truth_label():
    out = score_importance("hello", source="voice")
    assert out.truth_label == TRUTH_LABEL


# ── Batch API ─────────────────────────────────────────────────────

def test_score_many_returns_one_score_per_text():
    scores = score_many(["okay", "what time is it?", "explain X"])
    assert len(scores) == 3
    labels = [s.label for s in scores]
    assert "BACKCHANNEL" in labels
    assert "UTILITY" in labels
    assert "SUBSTANTIVE" in labels


# ── Priority order — explicit ─────────────────────────────────────

def test_priority_order_emergency_beats_all():
    """Emergency must override every other category."""
    out = score_importance(
        "From now on, don't delete the receipts — emergency, call 911",
        source="voice",
    )
    assert out.label == "EMERGENCY"


def test_priority_order_boundary_beats_doctrine():
    out = score_importance(
        "From now on, don't delete the receipts",
        source="typed",
    )
    assert out.label == "BOUNDARY"


def test_priority_order_doctrine_beats_substantive():
    out = score_importance(
        "From now on, explain the MAMMAL paper", source="typed",
    )
    assert out.label == "DOCTRINE"


def test_priority_order_substantive_beats_utility_when_substantive():
    """A long substantive question that doesn't match utility patterns
    stays SUBSTANTIVE."""
    out = score_importance(
        "Walk me through how the cortex routes intents to effectors",
        source="typed",
    )
    assert out.label == "SUBSTANTIVE"
