"""Tests for embedded native player limb (inside Alice Browser, not external handoff)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from System import swarm_embedded_native_player as player


def test_choose_embedded_stream_url_prefers_tiktok_signed_mp4():
    media = {
        "recent_errors": [
            {
                "code": 4,
                "src": "https://v16-webapp-prime.us.tiktok.com/video/tos/alisg/foo/?mime_type=video_mp4",
            }
        ]
    }
    url = player.choose_embedded_stream_url(
        {"location": "https://www.tiktok.com/"},
        fallback_url="https://www.tiktok.com/",
        media_status=media,
    )
    assert "v16-webapp-prime.us.tiktok.com" in url
    assert "mime_type=video_mp4" in url


def test_choose_embedded_stream_url_prefers_instagram_post_over_mp4():
    url = player.choose_embedded_stream_url(
        {"location": "https://www.instagram.com/p/C1mzc4CvjRh/"},
        fallback_url="https://www.instagram.com/explore/",
        media_status={"recent_errors": [{"code": 4, "src": "https://cdn.example/error.mp4"}]},
    )
    assert url == "https://www.instagram.com/p/C1mzc4CvjRh/"


def test_referer_for_url_tiktok():
    assert player.referer_for_url("https://v16-webapp-prime.us.tiktok.com/video/foo") == "https://www.tiktok.com/"


def test_fetch_stream_to_temp_uses_opener():
    payload = b"\x00\x00\x00\x18ftypmp41"

    def _fake_opener(req, timeout=30):
        assert req.get_header("Referer") == "https://www.tiktok.com/"
        return MagicMock(read=lambda max_bytes: payload)

    row = player.fetch_stream_to_temp(
        "https://v16-webapp-prime.us.tiktok.com/video/foo/?mime_type=video_mp4",
        opener=_fake_opener,
    )
    assert row["ok"] is True
    assert row["bytes"] == len(payload)
    assert row["local_path"]


def test_diagnose_media_error_labels_unchanged_from_bridge():
    from System.swarm_media_codec_bridge import diagnose_media_error_code

    d = diagnose_media_error_code(4)
    assert d["label"] == "MEDIA_ERR_SRC_NOT_SUPPORTED"


def test_build_cdn_fetch_headers_minimum_strict_set():
    headers = player.build_cdn_fetch_headers(
        "https://v16-webapp-prime.us.tiktok.com/video/foo/?mime_type=video_mp4",
        page_url="https://www.tiktok.com/",
        user_agent="Mozilla/5.0 Chrome/120",
    )
    assert headers["Referer"] == "https://www.tiktok.com/"
    assert "Mozilla" in headers["User-Agent"]
    assert "Cookie" not in headers


def test_build_cdn_fetch_headers_with_cookie():
    headers = player.build_cdn_fetch_headers(
        "https://v16-webapp-prime.us.tiktok.com/video/foo/",
        cookie_header="tt_chain_token=abc",
    )
    assert headers["Cookie"] == "tt_chain_token=abc"


def test_play_url_in_embedded_panel_tiktok_uses_fetch_first(tmp_path, monkeypatch):
    panel = MagicMock()
    panel._alice_status = MagicMock()
    fake_player = MagicMock()
    receipts: list[dict] = []

    def _capture(row, *, state_dir=None):
        receipts.append(dict(row))
        return tmp_path / "media_codec_bridge.jsonl"

    monkeypatch.setattr(player, "append_player_receipt", _capture)
    monkeypatch.setattr(
        player,
        "fetch_stream_to_temp",
        lambda *a, **k: {
            "ok": True,
            "local_path": "/tmp/alice_embed_test.mp4",
            "bytes": 128,
            "strategy": "fetch_then_play",
        },
    )

    row = player.play_url_in_embedded_panel(
        panel,
        fake_player,
        "https://v16-webapp-prime.us.tiktok.com/video/foo/?mime_type=video_mp4",
        page_url="https://www.tiktok.com/",
        state_dir=tmp_path,
    )
    assert row["ok"] is True
    assert row["strategy"] == "fetch_then_qmediaplayer"
    fake_player.play.assert_called_once()
    assert receipts[-1]["headers"]["Referer"] == "https://www.tiktok.com/"


def test_play_url_in_embedded_panel_fetch_failure_hides_overlay(tmp_path, monkeypatch):
    panel = MagicMock()
    panel._alice_status = MagicMock()
    fake_player = MagicMock()
    receipts: list[dict] = []

    def _capture(row, *, state_dir=None):
        receipts.append(dict(row))
        return tmp_path / "media_codec_bridge.jsonl"

    monkeypatch.setattr(player, "append_player_receipt", _capture)
    monkeypatch.setattr(
        player,
        "fetch_stream_to_temp",
        lambda *a, **k: {
            "ok": False,
            "reason": "fetch_failed",
            "error": "HTTPError: HTTP Error 403: Forbidden",
        },
    )

    row = player.play_url_in_embedded_panel(
        panel,
        fake_player,
        "https://v16-webapp-prime.us.tiktok.com/video/foo/?mime_type=video_mp4",
        page_url="https://www.tiktok.com/",
        state_dir=tmp_path,
    )

    assert row["ok"] is False
    assert row["reason"] == "fetch_failed"
    panel.setVisible.assert_called_with(False)
    fake_player.play.assert_not_called()
    assert receipts[-1]["ok"] is False
