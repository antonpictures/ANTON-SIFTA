"""Tests for the Stigmergic Speech Game real-sentence corpus.

StigAuth: SIFTA_SPEECH_GAME_SENTENCE_CORPUS_V0
Cowork CW47 / Claude surgery cw47-0517-0312, 2026-05-17.

The Architect constraint these tests enforce, verbatim:

  "the sentence has to has to be not make up stuff we don't want any
   hallucination stuff to talk about anything that is not real or
   it's not related to us here to the computer or something"

Every accepted sentence MUST be traceable to a real local file under
.sifta_state/ or Documents/ or Applications/. No invented strings,
no LLM-generated material.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_speech_game_sentence_corpus import (  # noqa: E402
    MAX_WORDS,
    MIN_WORDS,
    RealSentence,
    TRUTH_LABEL,
    _count_words,
    _passes_filters,
    _split_into_sentences,
    harvest_all,
    next_real_sentence,
)


# ── filter primitives ────────────────────────────────────────────────────


def test_word_count_bounds_are_inclusive():
    short = " ".join(["x"] * MIN_WORDS) + "."
    long_ = " ".join(["x"] * MAX_WORDS) + "."
    too_short = " ".join(["x"] * (MIN_WORDS - 1)) + "."
    too_long = " ".join(["x"] * (MAX_WORDS + 1)) + "."
    # x alone fails the verb-ish letter requirement, but bounds-only
    # primitive is _count_words.
    assert _count_words(short) == MIN_WORDS
    assert _count_words(long_) == MAX_WORDS
    assert _count_words(too_short) == MIN_WORDS - 1
    assert _count_words(too_long) == MAX_WORDS + 1


def test_passes_filters_rejects_too_short():
    assert not _passes_filters("hi there.")


def test_passes_filters_rejects_too_long():
    s = "this is a very long sentence with way too many tokens to be a tongue twister candidate."
    assert _count_words(s) > MAX_WORDS
    assert not _passes_filters(s)


def test_passes_filters_rejects_urls():
    assert not _passes_filters("check out https://example.com today okay.")


def test_passes_filters_rejects_surgery_ids():
    assert not _passes_filters("we just shipped cw47-0517-0007 to the trace today.")


def test_passes_filters_rejects_filenames():
    assert not _passes_filters("see Applications/sifta_talk.py for the details now.")


def test_passes_filters_rejects_node_serial():
    assert not _passes_filters("the node serial is GTH4921YP3 always check.")


def test_passes_filters_accepts_real_sentence():
    s = "The reading game shows one word and waits for you."
    assert _passes_filters(s)


def test_sentence_splitter_keeps_sentences_intact():
    blob = "Alice waits. Ace reads. They play together."
    out = _split_into_sentences(blob)
    assert any("waits" in s for s in out)
    assert any("reads" in s for s in out)
    assert any("together" in s for s in out)


# ── source harvesting (real local files) ─────────────────────────────────


def test_harvest_all_returns_only_real_sentences():
    """Every harvested sentence must carry verifiable provenance."""
    pool = harvest_all()
    # The repo has at least architect_memory_digest + apps_manifest on
    # disk, so the pool should not be empty in normal operation. If the
    # workspace is empty (CI bootstrap), skip.
    if not pool:
        pytest.skip("no local sources available for sentence harvest")
    for s in pool:
        assert isinstance(s, RealSentence)
        assert s.truth_label == TRUTH_LABEL
        assert MIN_WORDS <= s.word_count <= MAX_WORDS
        assert s.source_kind in {"digest", "journal", "conversation", "manifest"}
        # The source path is repo-relative and must exist when resolved
        # against the repo root.
        resolved = _REPO / s.source_path
        assert resolved.exists(), (
            f"sentence {s.text!r} claims source {s.source_path!r} which "
            f"does not exist on disk"
        )


def test_harvest_deduplicates_by_text():
    pool = harvest_all()
    if not pool:
        pytest.skip("no local sources available")
    seen = set()
    for s in pool:
        key = s.text.casefold()
        assert key not in seen, f"duplicate sentence in pool: {s.text!r}"
        seen.add(key)


def test_harvest_respects_source_filter():
    pool_manifest_only = harvest_all(sources=["manifest"])
    if not pool_manifest_only:
        pytest.skip("manifest has no qualifying sentences right now")
    for s in pool_manifest_only:
        assert s.source_kind == "manifest"


# ── next_real_sentence semantics ─────────────────────────────────────────


def test_next_real_sentence_returns_none_on_empty_filter(tmp_path, monkeypatch):
    # Force empty pool by filtering to a non-existent source name… or by
    # passing used_keys covering everything.
    pool = harvest_all()
    if not pool:
        pytest.skip("no local sources available")
    used = [s.text for s in pool]
    out = next_real_sentence(used_keys=used)
    assert out is None


def test_next_real_sentence_is_deterministic_with_seed():
    pool = harvest_all()
    if not pool:
        pytest.skip("no local sources available")
    a = next_real_sentence(seed=12345)
    b = next_real_sentence(seed=12345)
    assert a is not None and b is not None
    assert a.text == b.text


def test_next_real_sentence_skips_used():
    pool = harvest_all()
    if len(pool) < 2:
        pytest.skip("need at least two distinct sentences in the pool")
    first = next_real_sentence(seed=7)
    assert first is not None
    second = next_real_sentence(seed=7, used_keys=[first.text])
    assert second is None or second.text.casefold() != first.text.casefold()


def test_real_sentence_carries_word_count_consistent_with_text():
    pool = harvest_all()
    if not pool:
        pytest.skip("no local sources available")
    for s in pool[:50]:
        assert _count_words(s.text) == s.word_count


def test_no_sentence_is_a_pure_token_artifact():
    """Defence-in-depth: no harvested sentence should look like a UUID,
    hash, or trace ID even partially."""
    pool = harvest_all()
    if not pool:
        pytest.skip("no local sources available")
    bad = []
    for s in pool:
        if len(s.text.replace(" ", "")) > 0 and all(c in "0123456789abcdef-" for c in s.text.replace(" ", "")):
            bad.append(s.text)
    assert not bad, f"sentences that look like hex/UUID slipped through: {bad!r}"
