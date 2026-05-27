#!/usr/bin/env python3
"""Tests for the Cowork-branch SIFTA Memory Card Composer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_memory_card_cowork import (
    ConversationTurn,
    MemoryCard,
    TRUTH_LABEL,
    compose_memory_card,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_recency_ordering_puts_newest_turns_in_card(tmp_path: Path) -> None:
    now = 10_000.0
    _write_jsonl(
        tmp_path / "alice_conversation.jsonl",
        [
            {"ts": now - 7200, "role": "owner", "text": "two hours ago"},
            {"ts": now - 60, "role": "owner", "text": "one minute ago"},
            {"ts": now - 30, "role": "alice", "text": "thirty seconds ago"},
        ],
    )
    card = compose_memory_card(
        tmp_path, token_budget=2000, now=now, persist_last_seen=False
    )
    texts = [t.text for t in card.recent_turns]
    # All three fit easily under 2000 tokens; ordering is by salience desc.
    assert "thirty seconds ago" in texts
    assert "one minute ago" in texts
    assert texts.index("thirty seconds ago") < texts.index("two hours ago")
    assert card.truth_label == TRUTH_LABEL


def test_owner_flag_boost_promotes_flagged_fact(tmp_path: Path) -> None:
    now = 10_000.0
    _write_jsonl(
        tmp_path / "alice_conversation.jsonl",
        [{"ts": now - 30, "role": "owner", "text": "x" * 500}],
    )
    _write_jsonl(
        tmp_path / "owner_facts.jsonl",
        [
            {"fact": "George prefers honest receipts", "owner_flag": True, "ts": now - 86400},
            {"fact": "unflagged trivia about something", "owner_flag": False, "ts": now - 30},
        ],
    )
    card = compose_memory_card(
        tmp_path, token_budget=2000, now=now, persist_last_seen=False
    )
    assert "George prefers honest receipts" in card.persistent_facts


def test_token_budget_is_hard_on_stuffed_fixture(tmp_path: Path) -> None:
    now = 10_000.0
    # 200 conversation rows, ~400 chars each → ~100 tokens each → ~20 000 tokens total.
    bulk = [
        {"ts": now - i, "role": "owner", "text": ("blah " * 80).strip()}
        for i in range(200)
    ]
    _write_jsonl(tmp_path / "alice_conversation.jsonl", bulk)
    budget = 300
    card = compose_memory_card(
        tmp_path, token_budget=budget, now=now, persist_last_seen=False
    )
    assert card.estimated_tokens <= budget, (
        f"estimated_tokens={card.estimated_tokens} exceeded budget={budget}"
    )
    # Should still include the newest items, just not all of them.
    assert len(card.recent_turns) >= 1


def test_malformed_jsonl_rows_are_counted_not_raised(tmp_path: Path) -> None:
    p = tmp_path / "alice_conversation.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"ts": 1, "role": "owner", "text": "valid"}\n'
        "this is not json at all\n"
        '{"ts": 2, "role": "alice", "text": "also valid"}\n'
        '{"not": "a dict but valid json"}\n'
        "{broken json",
        encoding="utf-8",
    )
    card = compose_memory_card(
        tmp_path, token_budget=2000, now=10.0, persist_last_seen=False
    )
    # Two valid rows; "{\"not\": ...}" is a dict but has no text -> filtered out
    # cleanly without counting as a parse error.
    assert any(t.text == "valid" for t in card.recent_turns)
    assert any(t.text == "also valid" for t in card.recent_turns)
    assert card.parse_errors >= 2  # two truly malformed lines


def test_deterministic_ranking_with_seeded_weights(tmp_path: Path) -> None:
    now = 10_000.0
    _write_jsonl(
        tmp_path / "alice_conversation.jsonl",
        [
            {"ts": now - 60, "role": "owner", "text": "alpha"},
            {"ts": now - 60, "role": "owner", "text": "alpha"},  # dup ts/text
            {"ts": now - 30, "role": "alice", "text": "beta"},
        ],
    )
    weights = {"recency": 1.0, "flag": 2.0, "episodic": 1.5}
    a = compose_memory_card(
        tmp_path,
        token_budget=2000,
        now=now,
        weights=weights,
        persist_last_seen=False,
    )
    b = compose_memory_card(
        tmp_path,
        token_budget=2000,
        now=now,
        weights=weights,
        persist_last_seen=False,
    )
    assert a.to_dict() == b.to_dict()


def test_last_seen_deltas_detected_between_consecutive_calls(tmp_path: Path) -> None:
    now1 = 10_000.0
    _write_jsonl(
        tmp_path / "alice_conversation.jsonl",
        [{"ts": now1 - 60, "role": "owner", "text": "first call only"}],
    )
    # First call: persist last_seen.
    card1 = compose_memory_card(
        tmp_path, token_budget=2000, now=now1, persist_last_seen=True
    )
    assert card1.last_seen_deltas, "first call should treat everything as new"

    # Append a new row strictly newer than anything from the first call.
    with (tmp_path / "alice_conversation.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now1 + 5, "role": "alice", "text": "fresh after first"}) + "\n")

    now2 = now1 + 10
    card2 = compose_memory_card(
        tmp_path, token_budget=2000, now=now2, persist_last_seen=True
    )
    joined = " | ".join(card2.last_seen_deltas)
    assert "fresh after first" in joined, (
        f"second call should pick up only the new row in deltas; got: {joined!r}"
    )
    assert "first call only" not in joined, (
        "second call should NOT replay rows that predate the persisted last_seen"
    )
