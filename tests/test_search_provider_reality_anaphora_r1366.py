#!/usr/bin/env python3
"""r1366 — _jsonl NameError + payload-nesting fix in swarm_search_provider_reality.

George's live polenta-cooking transcript (2026-06-19) showed
'SEARCH FOR THIS RECIPE ON PERPLEXITY.AI' producing a fabricated text
narrative instead of a real, content-aware search. Root cause traced to two
bugs in `_recent_conversation_history()`:

1. `_jsonl` was referenced but never defined -> NameError, silently caught by
   `_resolve_query_anaphora`'s try/except, so anaphora ('this recipe') never
   resolved on call sites that don't pass `history=` explicitly.
2. Even with `_jsonl` defined, the function read `row["role"]`/`row["text"]`
   at the top level, but live `alice_conversation.jsonl` rows nest the turn
   under `row["payload"]` — so it always returned an empty history.

These tests use a throwaway `alice_conversation.jsonl` under a temp state_dir
so they do not depend on (or mutate) the live ledger.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from System.swarm_search_provider_reality import (
    _jsonl,
    _recent_conversation_history,
    parse_explicit_engine_pls_search,
)


@pytest.fixture
def fake_state_dir(monkeypatch, tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    conv = state_dir / "alice_conversation.jsonl"
    rows = [
        {"payload": {"role": "user", "text": "I am making polenta with boiled eggs, butter and cheese and salt."}},
        {"payload": {"role": "alice", "text": "That sounds delicious, tell me more!"}},
        {"payload": {"role": "user", "text": "Must smash the eggs mix with butter before pouring hot polenta on top."}},
        {"payload": {"role": "user", "text": "SEARCH FOR THIS RECIPE ON PERPLEXITY.AI"}},
    ]
    with conv.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    import System.swarm_search_provider_reality as mod

    monkeypatch.setattr(mod, "_state_dir", lambda *a, **k: state_dir)
    return state_dir


def test_jsonl_helper_reads_rows(fake_state_dir):
    path = fake_state_dir / "alice_conversation.jsonl"
    rows = _jsonl(path)
    assert len(rows) == 4
    assert rows[0]["payload"]["role"] == "user"


def test_jsonl_helper_tolerates_missing_file(tmp_path):
    assert _jsonl(tmp_path / "does_not_exist.jsonl") == []


def test_jsonl_helper_tolerates_bad_lines(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"payload": {"role": "user", "text": "ok"}}\nnot json\n\n', encoding="utf-8")
    rows = _jsonl(p)
    assert len(rows) == 1


def test_recent_conversation_history_reads_payload_nesting(fake_state_dir):
    hist = _recent_conversation_history(limit=10)
    assert len(hist) == 4
    assert hist[0] == {"role": "user", "content": "I am making polenta with boiled eggs, butter and cheese and salt."}


def test_anaphora_resolves_without_explicit_history_kwarg(fake_state_dir):
    """The exact bug condition from George's live session: caller does not
    pass `history=`, so resolution must fall back to reading the ledger
    itself instead of silently failing and returning the literal phrase.
    """
    result = parse_explicit_engine_pls_search("SEARCH FOR THIS RECIPE ON PERPLEXITY.AI")
    assert result is not None
    assert result["engine"] == "perplexity"
    assert result["query"].strip().upper() != "THIS RECIPE"
    assert "polenta" in result["query"].lower() or "egg" in result["query"].lower()


def test_literal_pls_form_unaffected(fake_state_dir):
    """Non-anaphoric literal queries (r1325/r1340 baseline) must still pass
    through unchanged — this fix only touches the anaphora-resolution path.
    """
    result = parse_explicit_engine_pls_search("SEARCH ON PERPLEXITY PLS lost passport")
    assert result == {
        "engine": "perplexity",
        "query": "lost passport",
        "owner_phrase_engine": "PERPLEXITY",
    }


def test_non_matching_text_returns_none(fake_state_dir):
    assert parse_explicit_engine_pls_search("") is None
    assert parse_explicit_engine_pls_search("just chatting, nothing to parse") is None
