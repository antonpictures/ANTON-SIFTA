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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
