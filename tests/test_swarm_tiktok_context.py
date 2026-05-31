#!/usr/bin/env python3
"""Tests for the TikTok context organ (WISH_012 Lane A, 2026-05-30).

Built from the real snapshot George showed: @tinyhawaiianxx, video id
7645117742449823006, caption 'nighttime yoga', player failed to render,
'You may like' recommendations visible.
"""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_tiktok_context as tk


SNAP = {
    "ts": time.time(),
    "truth_label": "ALICE_BROWSER_PAGE_TEXT_V1",
    "url": "https://www.tiktok.com/@tinyhawaiianxx/video/7645117742449823006",
    "title": "nighttime yoga🧘💕 | yoga | TikTok",
    "domain": "www.tiktok.com",
    "text": ("We're having trouble playing this video. Please refresh and try again. "
             "You may like bridges with @lilliessyoga afternoon handstand @tinyhawaiianxx"),
}


def test_parses_author_id_caption():
    ctx = tk.parse_tiktok_snapshot(SNAP)
    assert ctx["is_tiktok"] is True
    assert ctx["author"] == "@tinyhawaiianxx"
    assert ctx["video_id"] == "7645117742449823006"
    assert ctx["caption"] == "nighttime yoga🧘💕"


def test_detects_player_did_not_render():
    ctx = tk.parse_tiktok_snapshot(SNAP)
    assert ctx["player_rendered"] is False


def test_pulls_recommendation_handles():
    ctx = tk.parse_tiktok_snapshot(SNAP)
    assert "@lilliessyoga" in ctx["recommendation_handles"]


def test_non_tiktok_page_is_ignored():
    ctx = tk.parse_tiktok_snapshot({"url": "https://youtube.com/watch?v=x", "domain": "youtube.com"})
    assert ctx == {"is_tiktok": False}
    assert tk.build_tiktok_context({"url": "https://example.com", "domain": "example.com"}) == ""


def test_context_string_has_honest_boundary():
    s = tk.build_tiktok_context(SNAP)
    assert "@tinyhawaiianxx" in s
    assert "nighttime yoga" in s
    assert "player_rendered=no" in s
    assert "DESCRIBE-BOUNDARY" in s  # §6: never invent the video frames


def test_get_latest_context_reads_file(tmp_path):
    p = tmp_path / "alice_browser_current_page.json"
    p.write_text(json.dumps(SNAP), encoding="utf-8")
    out = tk.get_latest_context(snapshot_path=p)
    assert out and "video_id=7645117742449823006" in out


def test_get_latest_context_stale_returns_none(tmp_path):
    p = tmp_path / "alice_browser_current_page.json"
    old = dict(SNAP, ts=time.time() - 99999)
    p.write_text(json.dumps(old), encoding="utf-8")
    assert tk.get_latest_context(snapshot_path=p, max_age_s=600.0) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
