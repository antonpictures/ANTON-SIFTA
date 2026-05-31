#!/usr/bin/env python3
"""Tests: Alice can name the page open in her own browser (George 2026-05-30)."""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_page_answer as bpa


def _snap(tmp_path, url, title, ts, text_chars=0):
    sd = tmp_path / ".sifta_state"; sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": url, "title": title, "domain": "www.tiktok.com",
                    "ts": ts, "text_chars": text_chars}), encoding="utf-8")


def test_names_page_even_with_no_text(tmp_path):
    # The exact live bug: TikTok page, text_chars=0, but URL+title present.
    now = time.time()
    _snap(tmp_path, "https://www.tiktok.com/@barbellinaaaaa",
          "TikTok - Make Your Day", now - 5, text_chars=0)
    p = bpa.current_browser_page(now=now, state_dir=tmp_path)
    assert p["url"].endswith("@barbellinaaaaa")
    assert p["fresh"] is True
    block = bpa.page_answer_block(now=now, state_dir=tmp_path)
    assert "tiktok.com/@barbellinaaaaa" in block
    assert "JS-rendered" in block  # honest about no body text, but still names the page


def test_reads_page_text_when_present(tmp_path):
    now = time.time()
    _snap(tmp_path, "https://en.wikipedia.org/wiki/Yoga", "Yoga - Wikipedia", now - 2, text_chars=5000)
    block = bpa.page_answer_block(now=now, state_dir=tmp_path)
    assert "Yoga - Wikipedia" in block
    assert "5000 chars" in block


def test_no_trace_is_honest(tmp_path):
    block = bpa.page_answer_block(state_dir=tmp_path)
    assert "no page receipt" in block


def test_freshest_source_wins(tmp_path):
    now = time.time()
    sd = tmp_path / ".sifta_state"; sd.mkdir(parents=True, exist_ok=True)
    # older nav snapshot
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://old.example.com", "title": "Old", "ts": now - 100}), encoding="utf-8")
    # newer focus context
    (sd / "browser_context.jsonl").write_text(
        json.dumps({"url": "https://new.example.com", "title": "New", "ts": now - 1}) + "\n", encoding="utf-8")
    p = bpa.current_browser_page(now=now, state_dir=tmp_path)
    assert p["url"] == "https://new.example.com" and p["source"] == "focus_context"


def test_old_current_page_receipt_is_still_current_when_it_is_the_live_url(tmp_path):
    now = time.time()
    _snap(tmp_path, "https://www.tiktok.com/@x", "TikTok", now - 9999, text_chars=0)
    block = bpa.page_answer_block(now=now, state_dir=tmp_path)
    assert "I am on TikTok" in block
    assert "stale" not in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
