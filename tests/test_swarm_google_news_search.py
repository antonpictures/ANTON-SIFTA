#!/usr/bin/env python3
"""Tests for System/swarm_google_news_search.py (Alice's Google News organ)."""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from System.swarm_google_news_search import ( # noqa: E402
 ENGINE_KEY,
 HOME_URL,
 RSS_HOME,
 TRUTH_LABEL,
 land_intent_receipt,
 navigation_intent,
 parse_intent,
 rss_url,
 topic_url,
)


def test_topic_url_quotes_query():
 url = topic_url("ukraine ceasefire")
 assert url.startswith("https://news.google.com/search?q=")
 assert "ukraine+ceasefire" in url or "ukraine%20ceasefire" in url
 assert "hl=en-US" in url


def test_topic_url_empty_falls_back_to_home():
 assert topic_url("") == HOME_URL
 assert topic_url(" ") == HOME_URL


def test_rss_url_paths():
 assert rss_url() == RSS_HOME
 u = rss_url("epr bell")
 assert u.startswith("https://news.google.com/rss/search?q=")
 assert "epr" in u and "bell" in u


def test_parse_intent_bare_phrase():
 p = parse_intent("Google News")
 assert p["is_news"] is True
 assert p["kind"] == "home"
 assert p["url"] == HOME_URL


def test_parse_intent_search_for_phrase():
 p = parse_intent("SEARCH FOR GOOGLE NEWS")
 assert p["is_news"] is True
 assert p["kind"] == "home"


def test_parse_intent_topic_for():
 p = parse_intent("google news for fusion breakthroughs")
 assert p["is_news"] is True
 assert p["kind"] == "topic"
 assert p["topic"] == "fusion breakthroughs"
 assert "fusion" in p["url"]


def test_parse_intent_topic_about():
 p = parse_intent("Open Google News about quantum sensors please")
 assert p["is_news"] is True
 assert p["kind"] == "topic"
 assert p["topic"].lower().startswith("quantum sensors")


def test_parse_intent_reverse_search_phrasing():
 p = parse_intent("search ukraine on google news")
 assert p["is_news"] is True
 assert p["kind"] == "topic"
 assert "ukraine" in p["topic"].lower()


def test_parse_intent_non_news_returns_false():
 p = parse_intent("show me the latest from arxiv")
 assert p["is_news"] is False
 assert p["url"] == ""


def test_navigation_intent_writes_receipt(tmp_path):
 state = tmp_path / "state"
 out = navigation_intent("google news for AI safety", state_dir=state, source="owner")
 assert out is not None
 assert out["app"] == "Alice Browser"
 assert out["engine"] == ENGINE_KEY
 assert "AI" in out["topic"] or "ai" in out["topic"].lower()
 ledger = state / "google_news_intents.jsonl"
 assert ledger.exists()
 rec = json.loads(ledger.read_text().splitlines()[0])
 assert rec["truth_label"] == TRUTH_LABEL
 assert rec["kind"] == "GOOGLE_NEWS_INTENT"
 assert rec["intent_kind"] == "topic"


def test_navigation_intent_returns_none_for_unrelated_text():
 assert navigation_intent("what's the weather", write_receipt=False) is None


def test_land_intent_receipt_appends(tmp_path):
 state = tmp_path / "state"
 parsed = parse_intent("Google News")
 r1 = land_intent_receipt("Google News", parsed, state_dir=state)
 r2 = land_intent_receipt("Google News", parsed, state_dir=state)
 assert r1["ok"] and r2["ok"]
 lines = (state / "google_news_intents.jsonl").read_text().splitlines()
 assert len(lines) == 2
