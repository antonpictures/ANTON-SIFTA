"""X.com posting organ — r1369."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from System.swarm_xcom_posting import (
    answer_post_tweet_query,
    build_xcom_click_post_js,
    build_xcom_type_js,
    detect_post_tweet_command,
    launch_compose_tweet,
)


def test_detect_post_tweet():
    result = detect_post_tweet_command("post tweet #SIFTA is open source")
    assert result is not None
    assert result["action"] == "post_tweet"


def test_detect_no_tweet():
    result = detect_post_tweet_command("hello Alice")
    assert result is None


def test_type_js_has_text():
    js = build_xcom_type_js("Hello world #SIFTA")
    assert "Hello world #SIFTA" in js
    assert "tweetTextarea" in js


def test_click_post_js():
    js = build_xcom_click_post_js()
    assert "tweetButton" in js
    assert "click" in js


def test_launch_compose_writes_nav():
    base = Path(tempfile.mkdtemp())
    sd = base / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    result = launch_compose_tweet("Test tweet", state_dir=base)
    assert result["ok"] is True
    nav = sd / "alice_browser_open_url.txt"
    assert nav.exists()
    assert "x.com" in nav.read_text()


def test_launch_compose_writes_pending():
    base = Path(tempfile.mkdtemp())
    sd = base / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    launch_compose_tweet("Test tweet", state_dir=base)
    pending = sd / "pending_xcom_post.json"
    assert pending.exists()
    data = json.loads(pending.read_text())
    assert data["tweet_text"] == "Test tweet"
    assert data["phase"] == "navigate"


def test_launch_compose_writes_ledger():
    base = Path(tempfile.mkdtemp())
    sd = base / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    launch_compose_tweet("Test tweet", state_dir=base)
    ledger = sd / "xcom_posting.jsonl"
    assert ledger.exists()
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["action"] == "launch_compose"


def test_answer_post_tweet():
    reply = answer_post_tweet_query("post tweet #SIFTA rocks", state_dir=tempfile.mkdtemp())
    assert reply is not None
    assert "X.com" in reply
    assert "#SIFTA" in reply


def test_answer_no_post():
    reply = answer_post_tweet_query("hello Alice")
    assert reply is None
