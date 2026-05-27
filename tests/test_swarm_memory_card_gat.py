"""Tests for _attention_weighted_recent_actions (task #24 GAT prototype).

Authors:
- Prototype: grok-4.3-doctor-relay (tournament start, 2026-05-26)
- Bug fix + tests: claude-opus-4-7 (verification per §4.4)

What is tested:
1. With user_text present, lines containing user-text tokens or receipt
   markers rank above unrelated chatter.
2. Chronological order is **truly** restored after top-k selection — the
   pre-fix code did reverse-salience which mis-ordered when older but more
   relevant lines were kept alongside newer noise.
3. Edge cases: empty input, empty user_text, top_k larger than line count.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the System/ package importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_memory_card import _attention_weighted_recent_actions


def test_empty_block_returns_empty():
    assert _attention_weighted_recent_actions("", "any question") == ""


def test_empty_user_text_returns_block_unchanged():
    block = "L1\nL2\nL3"
    assert _attention_weighted_recent_actions(block, "") == block


def test_top_k_larger_than_lines_keeps_all_in_order():
    block = "\n".join(["L1 oldest", "L2 middle receipt=abc", "L3 newest"])
    out = _attention_weighted_recent_actions(block, "abc", top_k=10)
    lines = out.splitlines()
    assert lines == ["L1 oldest", "L2 middle receipt=abc", "L3 newest"], lines


def test_chronological_order_restored_when_old_line_wins_on_salience():
    """The bug-witness case.

    OLD line carries the receipt id the user is asking about; NEW line is
    irrelevant gaze tick. Both survive the top-k filter. The OLD line wins
    salience because of overlap+strength; the NEW line wins recency. We
    require the printed order to be CHRONOLOGICAL (oldest first), not
    salience-descending or salience-ascending.
    """
    block = "\n".join([
        "L1 OLD receipt=grok_paper_a4f2 at 09:00 — grok paper receipt",
        "L2 NEW trivial gaze frame at 09:15",
    ])
    out = _attention_weighted_recent_actions(block, "grok paper receipt", top_k=2)
    lines = out.splitlines()
    assert lines[0].startswith("L1"), f"expected L1 first (chronological), got: {lines}"
    assert lines[1].startswith("L2"), f"expected L2 second (chronological), got: {lines}"


def test_recent_line_with_relevance_wins_overall():
    """Confirms recency × relevance still favors recent relevant receipts."""
    block = "\n".join([
        "L1 OLD chatter unrelated",
        "L2 OLD chatter unrelated",
        "L3 NEW receipt=grok_result_b9e2 grok delegation",
    ])
    out = _attention_weighted_recent_actions(block, "grok delegation receipt", top_k=1)
    assert out.strip() == "L3 NEW receipt=grok_result_b9e2 grok delegation"


def test_receipt_strength_boost():
    """Lines with 'receipt=' / 'GROK_RESULT' / 'delegation' get the 1.2x boost."""
    block = "\n".join([
        "L1 mention grok paper but no receipt marker",
        "L2 receipt=irrelevant_id grok paper",
    ])
    # Same recency tier impossible (one is older, one is newer), but with the
    # 1.2 strength boost L2 should still be selected when top_k=1 even though
    # L1 has identical token overlap — because receipt-strength + recency wins.
    out = _attention_weighted_recent_actions(block, "grok paper", top_k=1)
    assert "receipt=irrelevant_id" in out, out


def test_top_k_then_chronological_with_three_kept():
    """Three lines kept, mixed salience and time. Output must be chronological."""
    block = "\n".join([
        "L1 oldest receipt=relevant grok paper",         # high overlap+strength, low recency
        "L2 middle bored gaze tick",                     # low everything
        "L3 NEW receipt=relevant grok paper response",   # high overlap+strength, high recency
        "L4 NEWEST chatter unrelated",                   # high recency, no overlap
    ])
    out = _attention_weighted_recent_actions(block, "grok paper receipt", top_k=3)
    lines = out.splitlines()
    # Whatever subset is kept, the output must be in original chronological order.
    indices = [int(l.split()[0][1:]) for l in lines]  # extract the digit after 'L'
    assert indices == sorted(indices), f"not chronological: {indices}"


if __name__ == "__main__":
    test_empty_block_returns_empty()
    test_empty_user_text_returns_block_unchanged()
    test_top_k_larger_than_lines_keeps_all_in_order()
    test_chronological_order_restored_when_old_line_wins_on_salience()
    test_recent_line_with_relevance_wins_overall()
    test_receipt_strength_boost()
    test_top_k_then_chronological_with_three_kept()
    print("ALL 7 PASS")
