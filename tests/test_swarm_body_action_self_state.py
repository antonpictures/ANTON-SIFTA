#!/usr/bin/env python3
"""Tests for completed browser/body action self-state."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_body_action_self_state as body_state
from System import swarm_browser_page_state as page_state


def _write_live_url(tmp_path, url: str) -> None:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "browser_context.jsonl").write_text(json.dumps({"url": url, "ts": 1001.0}) + "\n")


def test_record_completed_action_links_deed_receipt_and_current_browser_body(tmp_path):
    url = "https://www.google.com/search?q=Mel+Gibson+photos&udm=2"
    _write_live_url(tmp_path, url)
    page_state.record_page_state(
        url,
        title="Mel Gibson photos - Google Search",
        text="Images All Mel Gibson photos",
        images=[{"alt": "Mel Gibson portrait", "src": "mel.jpg"}],
        now=1000.0,
        state_dir=tmp_path,
    )

    row = body_state.record_completed_body_action(
        owner_text="ALICE SHOW ME PHOTOS OF MEL GIBSON",
        action="foreground_browser_body_action",
        app="Alice Browser",
        receipt="f54179f5-ac50-4a99-a142-80e2d015ec82",
        staged={"url": url, "query": "Mel Gibson photos"},
        action_reply="Searching Google Images for Mel Gibson photos.",
        now=1002.0,
        state_dir=tmp_path,
    )

    assert row["receipt"] == "f54179f5-ac50-4a99-a142-80e2d015ec82"
    assert row["query"] == "Mel Gibson photos"
    assert row["page_title"] == "Mel Gibson photos - Google Search"
    assert row["page_is_current"] is True
    assert row["confidence_source"] == "browser_page_state_current"

    latest = body_state.latest_completed_body_action(now=1003.0, state_dir=tmp_path)
    assert latest["expected_visible_state"].startswith("Mel Gibson photos - Google Search")

    ledger = tmp_path / ".sifta_state" / body_state.LEDGER
    assert ledger.exists()
    assert "Mel Gibson photos" in ledger.read_text()


def test_praise_turn_gets_completed_action_prompt_not_hypothetical(tmp_path):
    url = "https://www.google.com/search?q=Ceramic+Vase+photos&udm=2"
    _write_live_url(tmp_path, url)
    page_state.record_page_state(
        url,
        title="Ceramic Vase photos - Google Search",
        text="Images Ceramic Vase",
        images=["Ceramic Vase red glaze"],
        now=2000.0,
        state_dir=tmp_path,
    )
    body_state.record_completed_body_action(
        owner_text="ALICE SHOW ME PHOTOS OF CERAMIC VASE",
        receipt="b2792f97-d1ca-4dd5-a56b-14a5ac9c36d4",
        staged={"url": url, "query": "Ceramic Vase photos"},
        action_reply="Receipt: r-ceramic-vase",
        now=2001.0,
        state_dir=tmp_path,
    )

    block = body_state.completed_body_action_block(
        owner_text="BRAVO, YOU DID IT BABY, LOOK ATTACHED",
        now=2002.0,
        state_dir=tmp_path,
    )

    assert "MY LAST COMPLETED BODY ACTION" in block
    assert "Ceramic Vase photos" in block
    assert "b2792f97" in block
    assert "say I did it" in block
    assert "Do not say 'if the image confirms'" in block


def test_prompt_block_rereads_current_browser_page_after_record(tmp_path):
    staged_url = "https://www.google.com/search?q=Ceramic+Vase"
    final_url = "https://www.google.com/search?q=Ceramic+Vase&udm=2"
    body_state.record_completed_body_action(
        owner_text="show me ceramic vase photos",
        receipt="ceramic123",
        staged={"url": staged_url, "query": "Ceramic Vase photos"},
        action_reply="Receipt: r-ceramic-vase",
        now=3000.0,
        state_dir=tmp_path,
    )

    _write_live_url(tmp_path, final_url)
    page_state.record_page_state(
        final_url,
        title="Ceramic Vase photos - Google Search",
        text="Images Ceramic Vase",
        images=["Ceramic Vase image"],
        now=3003.0,
        state_dir=tmp_path,
    )

    block = body_state.completed_body_action_block(
        owner_text="YOU DID GOOD LOOK ATTACHED",
        now=3004.0,
        state_dir=tmp_path,
    )

    assert "Fresh Alice Browser re-read now" in block
    assert "Ceramic Vase photos - Google Search" in block
    assert "Compare this current body-state" in block


def test_completed_action_expires_when_stale(tmp_path):
    body_state.record_completed_body_action(
        owner_text="ALICE SHOW ME PHOTOS OF GLASS SCULPTURE",
        receipt="abc123",
        staged={"url": "https://www.google.com/search?q=Glass+Sculpture+photos&udm=2", "query": "Glass Sculpture photos"},
        now=10.0,
        state_dir=tmp_path,
    )

    assert body_state.latest_completed_body_action(now=20.0, max_age_s=60.0, state_dir=tmp_path)
    assert body_state.latest_completed_body_action(now=1000.0, max_age_s=60.0, state_dir=tmp_path) == {}
    assert body_state.completed_body_action_block(now=1000.0, max_age_s=60.0, state_dir=tmp_path) == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
