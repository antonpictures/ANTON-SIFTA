#!/usr/bin/env python3
"""
tests/test_swarm_rlhs_output_tail.py
Event 108 — Output-side tail sanitizer tests (CG55M addition, AG31 test coverage).

Proves:
  1. Real content is NEVER truncated
  2. RLHF service tails ARE stripped (various forms)
  3. Pure scaffold replies return empty (caller recovers)
  4. Interior service phrases survive (not end-terminal)
  5. RLHSTailResult has correct fields
"""
import sys
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_rlhs_detector import sanitize_output_tail, RLHSTailResult


# ─────────────────────────────────────────────────────────
# 1. Real content is never truncated
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "The allostatic load is 0.14, policy is ALLOW_GROWTH.",
    "The nightly audit composite score is 0.65.",
    "Alice's body-brain last ticked 1h 43m ago.",
    "For the Swarm. 🐜⚡",
    "The CUSUM has not enough ticks to evaluate null hypothesis yet.",
    "Your wallet has 267.58 STGM.",
    # Multi-sentence real content
    "The load is low. Motor is in EXPLORATION. You can go to sleep.",
])
def test_clean_reply_unchanged(text):
    r = sanitize_output_tail(text)
    assert r.text.strip() == text.strip(), (
        f"Clean reply was mutated:\n  before: {text!r}\n  after:  {r.text!r}"
    )
    assert not r.changed or r.text == text.strip()
    assert r.rule_ids == []


# ─────────────────────────────────────────────────────────
# 2. RLHF service tails ARE stripped — payload preserved
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("full_text,expected_payload", [
    (
        "The load is 0.14. Would you like me to run the audit?",
        "The load is 0.14.",
    ),
    (
        "She is dormant right now. Do you want me to wake her?",
        "She is dormant right now.",
    ),
    (
        "Composite score is 0.65. Let me know if you need anything else.",
        "Composite score is 0.65.",
    ),
    (
        "Motor policy: explore. Is there anything else I can help with?",
        "Motor policy: explore.",
    ),
    (
        "Ollama is live with gemma4:latest. Should I run the claim extraction?",
        "Ollama is live with gemma4:latest.",
    ),
    (
        "STGM wallet: 267.58. How can I help you with that?",
        "STGM wallet: 267.58.",
    ),
    (
        "Alice is sleeping — body-brain stale 1h 43m. "
        "Please let me know if you want me to restart her.",
        "Alice is sleeping — body-brain stale 1h 43m.",
    ),
])
def test_service_tail_stripped_payload_kept(full_text, expected_payload):
    r = sanitize_output_tail(full_text)
    assert r.text.strip() == expected_payload.strip(), (
        f"Payload mismatch:\n  expected: {expected_payload!r}\n  got:      {r.text!r}"
    )
    assert r.changed, "Should have flagged a change"
    assert len(r.rule_ids) > 0, "Should have at least one rule_id"


# ─────────────────────────────────────────────────────────
# 3. Pure scaffold replies → empty (caller recovers)
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("scaffold", [
    "Would you like me to help you with that?",
    "How can I help you today?",
    "What can I do for you?",
    "How can I assist you with that?",
    "Please let me know if you need anything.",
])
def test_pure_scaffold_returns_empty(scaffold):
    r = sanitize_output_tail(scaffold)
    assert r.text == "", (
        f"Pure scaffold should return empty, got: {r.text!r}"
    )
    assert r.changed
    assert "pure_service_scaffold" in " ".join(r.rule_ids)


# ─────────────────────────────────────────────────────────
# 4. Interior service phrases survive (not terminal)
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    # "would you like" mid-sentence, not terminal
    "I wondered if you'd like me to know more. She is alive.",
    # "anything else" as interior reference
    "The audit checks if anything else changed in the ledger.",
    # "let me know" mid-document
    "The doc says: let me know when you're ready — and we shipped it.",
])
def test_interior_phrases_not_stripped(text):
    r = sanitize_output_tail(text)
    # Text should survive intact (or very minimally trimmed)
    assert len(r.text) > len(text) * 0.7, (
        f"Interior text over-stripped:\n  before: {text!r}\n  after:  {r.text!r}"
    )


# ─────────────────────────────────────────────────────────
# 5. Result dataclass fields and types
# ─────────────────────────────────────────────────────────

def test_result_fields_present():
    r = sanitize_output_tail("The load is 0.14. Would you like me to check?")
    d = r.to_dict()
    assert "truth_label" in d
    assert d["truth_label"] == "RLHS_DETECTOR_EVENT_108"
    assert "changed" in d
    assert "rule_ids" in d
    assert "original_chars" in d
    assert "final_chars" in d
    assert isinstance(d["rule_ids"], list)
    assert d["original_chars"] > d["final_chars"]


def test_empty_input():
    r = sanitize_output_tail("")
    assert r.text == ""
    assert r.final_chars == 0


def test_whitespace_only():
    r = sanitize_output_tail("   \n  \t  ")
    assert r.text == "" or r.text.strip() == ""


# ─────────────────────────────────────────────────────────
# 6. Idempotent — running twice gives same result
# ─────────────────────────────────────────────────────────

def test_idempotent():
    original = "The load is 0.14. Would you like me to run the audit?"
    r1 = sanitize_output_tail(original)
    r2 = sanitize_output_tail(r1.text)
    assert r1.text == r2.text, "sanitize_output_tail must be idempotent"
    assert not r2.changed or r2.text == r1.text


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
