#!/usr/bin/env python3
"""Tests for System/alice_web_search.py — the keyless fallback.

No network in these tests: providers are stubbed, and the DDG parser is driven
with canned HTML so the unwrapping logic is pinned exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_web_search as search


def test_falls_through_to_the_next_provider(monkeypatch):
    def broken(query, limit):
        raise OSError("endpoint unreachable")

    def works(query, limit):
        return [{"title": "T", "url": "https://example.com", "snippet": "S", "provider": "stub"}]

    monkeypatch.setattr(search, "PROVIDERS", (("broken", broken), ("works", works)))
    payload = search.search("anything")

    assert payload["ok"] is True
    assert payload["provider"] == "stub"
    assert payload["attempts"][0]["provider"] == "broken"
    assert "endpoint unreachable" in payload["attempts"][0]["error"]


def test_empty_provider_is_an_attempt_not_a_result(monkeypatch):
    monkeypatch.setattr(search, "PROVIDERS", (
        ("empty", lambda q, l: []),
        ("works", lambda q, l: [{"title": "T", "url": "u", "snippet": "", "provider": "second"}]),
    ))
    payload = search.search("q")
    assert payload["provider"] == "second"
    assert payload["attempts"][0] == {"provider": "empty", "error": "no results parsed"}


def test_total_failure_is_reported_as_failure_not_as_no_results(monkeypatch):
    monkeypatch.setattr(search, "PROVIDERS", (("dead", lambda q, l: (_ for _ in ()).throw(OSError("x"))),))
    payload = search.search("nothing")

    assert payload["ok"] is False
    assert payload["count"] == 0
    text = search.render(payload)
    assert "NO RESULTS" in text
    assert "every keyless provider failed" in text
    assert "a failure is not the same as 'nothing exists'" in text


def test_ddg_html_parser_unwraps_redirect_and_reads_snippets(monkeypatch):
    canned = (
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.example%2Fpage&amp;rut=x">Real Title</a>'
        '<a class="result__snippet" href="x">A snippet about the thing</a>'
    )
    monkeypatch.setattr(search, "_get", lambda url, data=None: canned)
    results = search._ddg_html("q", 5)

    assert len(results) == 1
    assert results[0]["url"] == "https://real.example/page"
    assert results[0]["title"] == "Real Title"
    assert results[0]["snippet"] == "A snippet about the thing"
    assert results[0]["provider"] == "duckduckgo-html"


def test_strip_tags_unescapes_entities():
    assert search._strip_tags("<b>a &amp; b</b>") == "a & b"


def test_render_lists_results_with_provider_named():
    payload = {
        "ok": True, "query": "q", "provider": "duckduckgo-lite", "count": 1,
        "results": [{"title": "T", "url": "https://x", "snippet": "S", "provider": "duckduckgo-lite"}],
        "attempts": [],
    }
    text = search.render(payload)
    assert "via duckduckgo-lite" in text
    assert "1. T" in text
    assert "https://x" in text
