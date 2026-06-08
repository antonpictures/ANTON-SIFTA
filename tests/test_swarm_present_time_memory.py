#!/usr/bin/env python3
"""Tests for Alice's present-time memory spine."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_page_state as page_state
from System import swarm_present_time_memory as ptm


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_present_time_memory_block_reads_latest_browser_action_diary_and_owner_turn(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = time.time()
    url = "https://missingmoney.com/"
    (state_dir / "browser_context.jsonl").write_text(
        json.dumps(
            {
                "url": url,
                "title": "MissingMoney.com | Search for Unclaimed Property",
                "domain": "missingmoney.com",
                "ts": now - 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    page_state.record_page_state(
        url,
        title="MissingMoney.com | Search for Unclaimed Property",
        text="Search states about unclaimed property.",
        headings=["MissingMoney.com is the official Unclaimed Property website"],
        media_playback={"status": "no_media", "playing": False},
        state_dir=state_dir,
    )
    _append(
        state_dir / "browser_action_diary.jsonl",
        {"ts": now - 2, "action": "open_url", "query": "missing money", "url": url},
    )
    _append(
        state_dir / "app_action_diary.jsonl",
        {"ts": now - 1, "action": "read_current_page", "app_name": "Alice Browser", "url": url},
    )
    _append(
        state_dir / "episodic_diary.jsonl",
        {"ts": now - 0.5, "summary": "Owner left Alice on overnight to ingest real world data."},
    )
    _append(
        state_dir / "alice_conversation.jsonl",
        {"ts": now - 0.2, "role": "user", "content": "what link is open now?"},
    )

    block = ptm.present_time_memory_block(now=now, state_dir=state_dir, max_lines=12)

    assert "PRESENT TIME MEMORY" in block
    assert ptm.TRUTH_LABEL in block
    assert "MissingMoney.com" in block
    assert "https://missingmoney.com/" in block
    assert "Latest app action" in block
    assert "Latest diary" in block
    assert "what link is open now" in block


def test_answer_present_time_query_is_grounded_in_receipts(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = time.time()
    url = "https://www.youtube.com/watch?v=6wKX_hfyMbQ"
    (state_dir / "browser_context.jsonl").write_text(
        json.dumps(
            {
                "url": url,
                "title": "Joe Rogan Experience #2508 - Joe Eszterhas - YouTube",
                "domain": "www.youtube.com",
                "ts": now - 4,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    page_state.record_page_state(
        url,
        title="Joe Rogan Experience #2508 - Joe Eszterhas - YouTube",
        text="Joe Rogan Experience #2508 - Joe Eszterhas",
        headings=["Joe Rogan Experience #2508 - Joe Eszterhas"],
        media_playback={"status": "paused", "playing": False, "current_time": 0, "duration": 1140},
        state_dir=state_dir,
    )

    reply = ptm.answer_present_time_query(
        "Alice, what are you doing right now?",
        now=now,
        state_dir=state_dir,
    )

    assert "Alice Browser" in reply
    assert "Joe Rogan Experience #2508" in reply
    assert url in reply
    assert "Media receipt" in reply


def test_answer_last_diary_journal_row_query_returns_newest_row(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = 1000.0
    _append(
        state_dir / "episodic_diary.jsonl",
        {"ts": 900.0, "summary": "Older episodic row."},
    )
    _append(
        state_dir / "alice_first_person_journal.jsonl",
        {
            "ts": 995.0,
            "date": "2026-06-05",
            "time": "05:09:30",
            "source": "app_focus",
            "line": "I noticed Ioan George Anton focused on Codex.",
        },
    )

    reply = ptm.answer_last_diary_journal_row_query(
        "what is the last row in your diary/journal?",
        now=now,
        state_dir=state_dir,
    )

    assert ".sifta_state/alice_first_person_journal.jsonl" in reply
    assert "05:09:30" in reply
    assert "focused on Codex" in reply
    assert "autonomous organism" not in reply


def test_recent_trail_keeps_the_ebay_item_from_one_click_ago(tmp_path):
    """George 2026-06-06: Alice forgot the eBay item she was browsing ONE link
    before — the present block was 1-deep. The trail must keep the item title in
    her speaking context even after newer events displace the 'latest' rows."""
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = time.time()
    # the eBay item page she was on (a few events back)
    _append(
        state_dir / "browser_context.jsonl",
        {"ts": now - 50, "url": "https://www.ebay.com/itm/335012", "title": "eBay item: Blue Red Patterned Sweater - Womens M"},
    )
    # then she clicked into the item photo and described it (newer events)
    _append(
        state_dir / "browser_action_diary.jsonl",
        {"ts": now - 30, "action": "click_image", "url": "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"},
    )
    _append(
        state_dir / "app_action_diary.jsonl",
        {"ts": now - 20, "action": "describe_browser_photo", "app_name": "Alice Browser"},
    )
    _append(
        state_dir / "episodic_diary.jsonl",
        {"ts": now - 10, "summary": "I described the browser photo with my vision arm."},
    )

    trail = ptm.recent_trail_block(n=20, now=now, state_dir=state_dir)
    assert "MY RECENT TRAIL" in trail
    assert "Blue Red Patterned Sweater" in trail   # the item from one click ago survives
    assert "describe_browser_photo" in trail
    # ordering: the eBay page line appears before the newer describe line
    assert trail.index("Blue Red Patterned Sweater") < trail.index("describe_browser_photo")

    # and the full present block carries the trail without losing its header
    block = ptm.present_time_memory_block(now=now, state_dir=state_dir, max_lines=12)
    assert "PRESENT TIME MEMORY" in block
    assert "MY RECENT TRAIL" in block
    assert "Blue Red Patterned Sweater" in block

    # bloat cap honored: trail alone stays under its budget
    assert len(trail) <= 2200
