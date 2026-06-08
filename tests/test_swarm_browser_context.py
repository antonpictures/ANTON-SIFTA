#!/usr/bin/env python3
"""Tests for active browser-limb context publishing."""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_context as ctx


def test_publish_and_read_browser_context_from_repo_root(tmp_path):
    ctx.publish_browser_context(
        url="https://example.com/page",
        title="Example Page",
        media_status={"ok": True},
        state_dir=tmp_path,
    )

    block = ctx.get_current_browser_context_block(state_dir=tmp_path)
    assert "CURRENT BROWSER CONTEXT" in block
    assert "Example Page" in block
    assert "https://example.com/page" in block


def test_publish_and_read_browser_context_from_state_dir(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    ctx.publish_browser_context(
        url="https://www.tiktok.com/",
        title="TikTok",
        media_status={"ok": False, "recent_errors": [{"code": 4}]},
        state_dir=state_dir,
    )

    block = ctx.get_current_browser_context_block(state_dir=state_dir)
    assert "Alice Browser limb" in block
    assert "TikTok" in block
    assert "code 4" in block
    assert not (state_dir / ".sifta_state").exists()


def test_publish_browser_context_marks_page_diary_once_per_page(tmp_path):
    ctx.publish_browser_context(
        url="https://www.youtube.com/watch?v=abc123",
        title="Jensen Huang warned he'll Go ape",
        media_status={"ok": True},
        source="load_finished",
        state_dir=tmp_path,
    )
    ctx.publish_browser_context(
        url="https://www.youtube.com/watch?v=abc123",
        title="Jensen Huang warned he'll Go ape",
        media_status={"ok": True},
        source="awareness_tick",
        state_dir=tmp_path,
    )

    diary_path = tmp_path / ".sifta_state" / "episodic_diary.jsonl"
    rows = [json.loads(line) for line in diary_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["truth_label"] == ctx.BROWSER_PAGE_DIARY_TRUTH_LABEL
    assert row["event_type"] == "browser_page_loaded"
    assert row["category"] == "youtube.com"
    assert "search" in row["site_habits"]
    assert "watch video" in row["site_habits"]


def test_recent_browsing_history_scans_past_awareness_tick_spam(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    path = state_dir / "browser_context.jsonl"
    item_url = "https://www.ebay.com/itm/blue-red-patterned-sweater"
    image_url = "https://i.ebayimg.com/images/g/Q0IAAOSwW7ldYxy9/s-l1600.jpg"
    rows = [
        {
            "ts": 1000.0,
            "truth_label": ctx.TRUTH_LABEL,
            "source": "load_finished",
            "url": item_url,
            "title": "Blue Red Patterned Sweater",
        }
    ]
    rows.extend(
        {
            "ts": 1001.0 + i,
            "truth_label": ctx.TRUTH_LABEL,
            "source": "awareness_tick",
            "url": image_url,
            "title": "s-l1600.jpg (1295x1600)",
        }
        for i in range(700)
    )
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    history = ctx.recent_browsing_history(n=3, state_dir=state_dir, max_scan_lines=1000)

    assert [row["url"] for row in history[:2]] == [image_url, item_url]
    assert history[1]["title"] == "Blue Red Patterned Sweater"


def test_recent_browsing_history_skips_fake_hosts_and_global_duplicates(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    path = state_dir / "browser_context.jsonl"
    item_url = "https://www.ebay.com/itm/blue-red-patterned-sweater"
    image_url = "https://i.ebayimg.com/images/g/Q0IAAOSwW7ldYxy9/s-l1600.jpg"
    fake_url = "https://q0iaaosww7ldyxy9/s-l1600.jpg"
    rows = [
        {"ts": 1000.0, "truth_label": ctx.TRUTH_LABEL, "source": "load_finished", "url": item_url, "title": "Sweater"},
        {"ts": 1001.0, "truth_label": ctx.TRUTH_LABEL, "source": "load_finished", "url": image_url, "title": "Image"},
        {"ts": 1002.0, "truth_label": ctx.TRUTH_LABEL, "source": "awareness_tick", "url": fake_url, "title": "fake"},
        {"ts": 1003.0, "truth_label": ctx.TRUTH_LABEL, "source": "awareness_tick", "url": image_url, "title": "Image again"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    history = ctx.recent_browsing_history(n=5, state_dir=state_dir)

    assert [row["url"] for row in history] == [image_url, item_url]


def test_linked_parent_pages_for_asset_url_reads_page_state_receipt(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    path = state_dir / "browser_page_state.jsonl"
    item_url = "https://www.ebay.com/itm/blue-red-patterned-sweater"
    image_url = "https://i.ebayimg.com/images/g/Q0IAAOSwW7ldYxy9/s-l1600.jpg"
    row = {
        "ts": 1000.0,
        "truth_label": "BROWSER_PAGE_STATE_V1",
        "url": item_url,
        "title": "Blue Red Patterned Sweater",
        "images": ["https://i.ebayimg.com/images/g/Q0IAAOSwW7ldYxy9/s-l500.jpg"],
        "text": "Main product photo Q0IAAOSwW7ldYxy9",
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    parents = ctx.linked_parent_pages_for_asset_url(image_url, state_dir=state_dir)

    assert parents[0]["url"] == item_url
    assert parents[0]["title"] == "Blue Red Patterned Sweater"


def test_current_browser_context_block_includes_recent_browser_history(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    ctx.publish_browser_context(
        url="https://www.ebay.com/itm/blue-red-patterned-sweater",
        title="Blue Red Patterned Sweater",
        media_status={"ok": True},
        source="load_finished",
        state_dir=state_dir,
    )
    ctx.publish_browser_context(
        url="https://i.ebayimg.com/images/g/Q0IAAOSwW7ldYxy9/s-l1600.jpg",
        title="s-l1600.jpg (1295x1600)",
        media_status={"ok": True},
        source="load_finished",
        state_dir=state_dir,
    )

    block = ctx.get_current_browser_context_block(state_dir=state_dir)

    assert "RECENT ALICE BROWSER HISTORY" in block
    assert "Blue Red Patterned Sweater" in block
    assert "https://www.ebay.com/itm/blue-red-patterned-sweater" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
