#!/usr/bin/env python3
"""Tests: browser page-state perception (George 2026-05-30 — "see the contents")."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_page_state as ps


def test_record_and_read_structured_state(tmp_path):
    ps.record_page_state(
        "https://www.instagram.com/", title="Instagram",
        text="lialinxo Los Angeles California Messages",
        headings=["lialinxo", "Suggested for you"],
        links=[{"text": "Home", "href": "/"}, {"text": "Explore", "href": "/explore/"}],
        buttons=["Follow", "Message"],
        images=[{"alt": "photo of person", "src": "x.jpg"}],
        scroll={"y": 0, "height": 4000, "pct": 0},
        now=1000.0, state_dir=tmp_path,
    )
    s = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert s["domain"] == "www.instagram.com"
    assert s["text_chars"] > 0 and s["images_count"] == 1 and s["links_count"] == 2
    assert s["headings"][0] == "lialinxo"
    assert ps.has_readable_content(s) is True


def test_visible_controls_are_recorded_and_surfaced(tmp_path):
    ps.record_page_state(
        "https://www.ebay.com/itm/example",
        title="Example listing | eBay",
        text="Example listing",
        buttons=["Expand image", "Add to cart"],
        controls=[
            {
                "label": "Expand image",
                "role": "button",
                "selector": 'button[aria-label="Expand image"]',
                "rect": {"x": 1200, "y": 280, "w": 48, "h": 48},
            },
            {
                "label": "Add to cart",
                "role": "button",
                "selector": 'button[aria-label="Add to cart"]',
                "rect": {"x": 1400, "y": 650, "w": 180, "h": 44},
            },
        ],
        now=1000.0,
        state_dir=tmp_path,
    )

    s = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert s["controls_count"] == 2
    assert s["visible_controls"][0]["label"] == "Expand image"
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "Visible controls/buttons" in block
    assert "Expand image" in block
    assert "Add to cart" in block


def test_page_state_records_open_browser_tabs(tmp_path):
    ps.record_page_state(
        "https://www.instagram.com/",
        title="Instagram",
        text="Instagram feed",
        open_tabs=[
            {
                "index": 0,
                "active": False,
                "title": "Maisie Williams signed photo | eBay",
                "url": "https://www.ebay.com/itm/123",
            },
            {
                "index": 1,
                "active": True,
                "title": "Instagram",
                "url": "https://www.instagram.com/",
            },
        ],
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert state["open_tabs_count"] == 2
    assert state["open_tabs"][0]["domain"] == "www.ebay.com"
    assert state["open_tabs"][1]["active"] is True
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "Open Alice Browser tabs (2)" in block
    assert "Maisie Williams signed photo" in block
    assert "active #2: Instagram" in block


def test_empty_when_no_receipt(tmp_path):
    assert ps.latest_page_state(state_dir=tmp_path) == {}
    block = ps.page_state_block(state_dir=tmp_path)
    assert "no page-state receipt yet" in block


def test_address_only_is_honest_about_missing_contents(tmp_path):
    # JS page that returned an address but no rendered content (the live IG bug)
    ps.record_page_state("https://www.instagram.com/", title="Instagram",
                         text="", now=1000.0, state_dir=tmp_path)
    s = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert ps.has_readable_content(s) is False
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "no contents" in block and "re-read" in block


def _write_live_url(tmp_path, url):
    import json as _j
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "browser_context.jsonl").write_text(_j.dumps({"url": url, "ts": 1.0}) + "\n")


def test_current_page_is_fresh_even_when_old(tmp_path):
    # George 2026-05-30: a page you are STILL on is current, no matter the age.
    url = "https://www.instagram.com/p/C72nb9ztZtv/"
    _write_live_url(tmp_path, url)
    ps.record_page_state(url, title="Instagram", text="I couldn't find my bikini",
                         headings=["kylinmilan"], now=1000.0, state_dir=tmp_path)
    s = ps.latest_page_state(now=1000.0 + 99999, max_age_s=120, state_dir=tmp_path)  # very old
    assert s["is_current_page"] is True
    assert s["fresh"] is True
    block = ps.page_state_block(now=1000.0 + 99999, max_age_s=120, state_dir=tmp_path)
    assert "stale" not in block  # she does not disown the page she is on


def test_old_receipt_for_a_page_left_is_stale(tmp_path):
    _write_live_url(tmp_path, "https://www.instagram.com/p/NEWPAGE/")
    ps.record_page_state("https://www.instagram.com/p/OLDPAGE/", title="X", text="old",
                         now=1000.0, state_dir=tmp_path)
    s = ps.latest_page_state(now=1000.0 + 99999, max_age_s=120, state_dir=tmp_path)
    assert s["is_current_page"] is False
    assert s["fresh"] is False


def test_freshness_flips_stale(tmp_path):
    ps.record_page_state("https://x.com/", title="X", text="hello world",
                         now=1000.0, state_dir=tmp_path)
    assert ps.latest_page_state(now=1010.0, max_age_s=120, state_dir=tmp_path)["fresh"] is True
    stale = ps.latest_page_state(now=1000.0 + 999, max_age_s=120, state_dir=tmp_path)
    assert stale["fresh"] is False
    assert "stale" in ps.page_state_block(now=1000.0 + 999, max_age_s=120, state_dir=tmp_path)


def test_content_hash_changes_with_content(tmp_path):
    a = ps.record_page_state("https://x.com/", text="alpha", headings=["A"],
                             now=1.0, state_dir=tmp_path)
    b = ps.record_page_state("https://x.com/", text="beta", headings=["B"],
                             now=2.0, state_dir=tmp_path)
    assert a["content_hash"] != b["content_hash"]
    same = ps.record_page_state("https://x.com/", text="alpha", headings=["A"],
                                now=3.0, state_dir=tmp_path)
    assert same["content_hash"] == a["content_hash"]


def test_block_describes_contents_with_provenance(tmp_path):
    ps.record_page_state(
        "https://www.instagram.com/p/abc/", title="Instagram",
        text="a photo caption here", headings=["lialinxo"],
        images=[{"alt": "person in white top", "src": "i.jpg"}],
        now=1000.0, state_dir=tmp_path,
    )
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "rendered DOM" in block
    assert "lialinxo" in block
    assert "images" in block


def test_comments_captured_and_surfaced_for_summary(tmp_path):
    ps.record_page_state(
        "https://www.instagram.com/p/X/", title="Instagram", text="caption",
        comments=[
            {"author": "brydcurry", "text": "The producers know exactly what they're doing."},
            {"author": "kathryn_forbes", "text": "Drops islander after general public gets mad."},
            {"author": "noise", "text": "x"},   # too short -> dropped
        ],
        now=1000.0, state_dir=tmp_path,
    )
    s = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert s["comments_count"] == 2
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "Comment thread (2 captured)" in block
    assert "brydcurry" in block
    rows = ps.comments_for_summary(now=1001.0, state_dir=tmp_path)
    assert [r["author"] for r in rows] == ["brydcurry", "kathryn_forbes"]


def test_comment_noise_is_filtered(tmp_path):
    # George 2026-05-30: scrape was capturing timestamps + 'Reply See translation' as comments.
    ps.record_page_state(
        "https://www.instagram.com/p/X/", title="Instagram", text="caption",
        comments=[
            {"author": "3w", "text": "Reply See translation"},        # timestamp + ui noise -> drop
            {"author": "139w", "text": "Reply"},                       # drop
            {"author": "kylinmilan", "text": "love you all 💋 Reply See translation"},  # keep, scrub tail
            {"author": "fan_22", "text": "Perfection 🔥"},             # keep
        ],
        now=1000.0, state_dir=tmp_path,
    )
    rows = ps.comments_for_summary(now=1001.0, state_dir=tmp_path)
    authors = [r["author"] for r in rows]
    assert "3w" not in authors and "139w" not in authors
    assert "kylinmilan" in authors and "fan_22" in authors
    km = [r for r in rows if r["author"] == "kylinmilan"][0]
    assert "Reply" not in km["text"] and "See translation" not in km["text"]
    assert "love you all" in km["text"]


def test_instagram_footer_nav_is_not_a_comment(tmp_path):
    # George 2026-05-30: scraper captured IG footer nav + highlight labels as comments.
    ps.record_page_state(
        "https://www.instagram.com/p/X/", title="Instagram", text="caption",
        comments=[
            {"author": "About", "text": "Blog Jobs Help API Privacy Terms Locations Meta Threads"},
            {"author": "API", "text": "Privacy Consumer Health Terms Locations Popular Meta"},
            {"author": "Ibiza", "text": "South Korea 25 Japan 25 Milano 25 Aruba 25"},
            {"author": "roxanavancea", "text": "Uuu so beautiful"},     # real comment -> keep
            {"author": "poxylandia", "text": "Super frumoasa, si setul e foarte fain"},  # keep
        ],
        now=1000.0, state_dir=tmp_path,
    )
    rows = ps.comments_for_summary(now=1001.0, state_dir=tmp_path)
    authors = [r["author"] for r in rows]
    assert "About" not in authors and "API" not in authors and "Ibiza" not in authors
    assert authors == ["roxanavancea", "poxylandia"]


def test_no_comments_is_honest(tmp_path):
    ps.record_page_state("https://x.com/", title="X", text="hello", now=1000.0, state_dir=tmp_path)
    assert ps.comments_for_summary(now=1001.0, state_dir=tmp_path) == []
    assert "Comment thread" not in ps.page_state_block(now=1001.0, state_dir=tmp_path)


def test_stale_left_page_comments_are_not_reused(tmp_path):
    _write_live_url(tmp_path, "https://www.instagram.com/p/CURRENT/")
    ps.record_page_state(
        "https://www.instagram.com/p/OLD/",
        title="Instagram",
        text="old post",
        comments=[{"author": "old_user", "text": "old visible comment"}],
        now=1000.0,
        state_dir=tmp_path,
    )
    assert ps.comments_for_summary(now=1000.0 + 99999, max_age_s=120, state_dir=tmp_path) == []


def test_state_dir_accepts_root_or_state_dir(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    ps.record_page_state("https://x.com/", text="hi", state_dir=sd)
    assert (sd / "browser_page_state.jsonl").exists()


def test_media_playback_signal_marks_own_browser_audio(tmp_path):
    url = "https://www.youtube.com/watch?v=abc123"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="YouTube video",
        text="",
        media_playback={"status": "playing", "playing": True, "video_count": 1},
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert state["media_playback"]["status"] == "playing"
    playing, details = ps.is_my_own_browser_playback(now=1001.0, state_dir=tmp_path)
    assert playing is True
    assert details["domain"] == "www.youtube.com"
    assert details["playing"] is True


def test_page_state_block_surfaces_paused_video_time(tmp_path):
    url = "https://www.youtube.com/watch?v=N5fCM8U4S4I"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="Victoria's Secret Fashion Show 2013 - YouTube",
        text="Victoria's Secret Fashion Show 2013",
        media_playback={
            "status": "paused",
            "playing": False,
            "video_count": 1,
            "current_time": 544.0,
            "duration": 3600.0,
        },
        now=1000.0,
        state_dir=tmp_path,
    )

    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "Media playback receipt: paused at 9:04 of 1:00:00." in block
    assert "Browser playback feeling: held_still_at_owner_pause (paused at 9:04 of 1:00:00)." in block


def test_browser_playback_feeling_is_stored_and_current_gated(tmp_path):
    url = "https://www.youtube.com/watch?v=N5fCM8U4S4I"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="Official 2018 Fashion Show",
        text="video",
        media_playback={
            "status": "playing",
            "playing": True,
            "video_count": 1,
            "current_time": 518.0,
            "duration": 2456.0,
        },
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    feeling = ps.browser_playback_feeling_from_state(state)

    assert feeling["truth_label"] == "BROWSER_PLAYBACK_FEELING_V1"
    assert feeling["feeling"] == "watching_with_george"
    assert feeling["status"] == "playing"
    assert feeling["current_time"] == "8:38"
    assert feeling["duration"] == "40:56"
    assert feeling["is_current_page"] is True


def test_media_domain_without_playing_signal_is_not_own_audio(tmp_path):
    url = "https://www.youtube.com/watch?v=abc123"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="YouTube video",
        text="",
        media_playback={"status": "paused", "playing": False, "video_count": 1},
        now=1000.0,
        state_dir=tmp_path,
    )

    playing, details = ps.is_my_own_browser_playback(now=1001.0, state_dir=tmp_path)
    assert playing is False
    assert details["reason"] == "media_domain_but_not_playing"


def test_youtube_sponsored_panel_promotes_structured_ad_state(tmp_path):
    url = "https://www.youtube.com/watch?v=abc123"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="YouTube",
        text="video page",
        sponsored=[{"kind": "youtube", "text": "AI Pentest Platform Sponsored aikido.dev"}],
        media_playback={"status": "playing", "playing": True, "video_count": 1},
        youtube_ad_state={
            "detected": True,
            "platform": "youtube",
            "placement": "page",
            "labels": ["Sponsored"],
            "ad_text": "AI Pentest Platform Sponsored",
            "skip_available": False,
            "mute_available": True,
            "video_playing": True,
        },
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    ad = ps.youtube_ad_state_from_state(state)
    assert ad["detected"] is True
    assert ad["platform"] == "youtube"
    assert ad["is_current_page"] is True
    assert ad["mute_available"] is True
    block = ps.page_state_block(now=1001.0, state_dir=tmp_path)
    assert "YouTube ad state visible" in block
    assert "AI Pentest Platform" in block


def test_youtube_ad_state_no_false_positive_without_markers(tmp_path):
    url = "https://www.youtube.com/watch?v=abc123"
    _write_live_url(tmp_path, url)
    ps.record_page_state(
        url,
        title="YouTube",
        text="ordinary video page without paid placement markers",
        media_playback={"status": "playing", "playing": True, "video_count": 1},
        youtube_ad_state={
            "detected": False,
            "platform": "youtube",
            "placement": "",
            "labels": [],
            "ad_text": "",
            "skip_available": False,
            "mute_available": True,
            "video_playing": True,
        },
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=1001.0, state_dir=tmp_path)
    assert ps.youtube_ad_state_from_state(state) == {}
    assert "YouTube ad state visible" not in ps.page_state_block(now=1001.0, state_dir=tmp_path)


def test_stale_non_current_youtube_ad_does_not_surface(tmp_path):
    _write_live_url(tmp_path, "https://www.youtube.com/watch?v=current")
    ps.record_page_state(
        "https://www.youtube.com/watch?v=old",
        title="Old YouTube",
        text="old video",
        sponsored=[{"kind": "youtube", "text": "Sponsored old panel"}],
        youtube_ad_state={
            "detected": True,
            "platform": "youtube",
            "placement": "page",
            "labels": ["Sponsored old panel"],
            "ad_text": "Sponsored old panel",
            "skip_available": False,
            "mute_available": True,
            "video_playing": True,
        },
        now=1000.0,
        state_dir=tmp_path,
    )

    state = ps.latest_page_state(now=2000.0, max_age_s=120, state_dir=tmp_path)
    ad = ps.youtube_ad_state_from_state(state)
    assert ad.get("detected") is True
    assert ad.get("is_current_page") is False
    block = ps.page_state_block(now=2000.0, max_age_s=120, state_dir=tmp_path)
    assert "YouTube ad state visible" not in block
    assert "Sponsored / ad content visible" not in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
