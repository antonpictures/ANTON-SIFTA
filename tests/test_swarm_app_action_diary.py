#!/usr/bin/env python3
"""Tests for the cortex pre-action app diary (George 2026-05-30: think first)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_app_action_diary as diary


def test_record_action_writes_first_person_timestamped_line(tmp_path):
    row = diary.record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_path)
    assert row["app"] == "Alice Browser"
    assert row["action"] == "open"
    assert row["line"].startswith("I opened Alice Browser at ")
    ledger = tmp_path / ".sifta_state" / diary.DIARY_LEDGER
    assert ledger.exists() and "opened Alice Browser" in ledger.read_text()


def test_record_action_also_feeds_limb_history(tmp_path):
    diary.record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_path)
    from System import swarm_app_limb_history as limb
    assert "Alice Browser" in limb.currently_open(state_dir=tmp_path)


def test_cortex_block_empty_state_is_honest(tmp_path):
    block = diary.app_state_for_cortex(state_dir=tmp_path, now=1000.0)
    assert "read this BEFORE you open or close" in block
    assert "no SIFTA app is open" in block


def test_cortex_block_shows_open_app_and_recent_action(tmp_path):
    diary.record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_path)
    block = diary.app_state_for_cortex(state_dir=tmp_path, now=1001.0)
    assert "Alice Browser" in block
    assert "Open now:" in block
    assert "Recent app actions" in block
    assert "I reason, then act, then record" in block.replace("\n", " ") or "reason, then act" in block


def test_close_then_state_reflects_closed(tmp_path):
    diary.record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_path)
    diary.record_app_action("Alice Browser", "close", now=1010.0, state_dir=tmp_path)
    block = diary.app_state_for_cortex(state_dir=tmp_path, now=1011.0)
    assert "no SIFTA app is open" in block  # last action was close
    assert "closed Alice Browser" in block  # but the diary remembers it


def test_tab_switch_notes_diary_and_idles_app_without_closing(tmp_path):
    diary.record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_path)
    row = diary.record_tab_switch("the global chat desktop", idled_app="Alice Browser",
                                  now=1010.0, state_dir=tmp_path)
    assert row["action"] == "tab_switch"
    assert "went idle" in row["line"] and "global chat desktop" in row["line"]
    # Idled app is still OPEN (not closed) per §1.A — focus moved, app persists.
    from System import swarm_app_limb_history as limb
    assert "Alice Browser" in limb.currently_open(state_dir=tmp_path)
    # And the cortex block shows the recent switch in her diary.
    block = diary.app_state_for_cortex(state_dir=tmp_path, now=1011.0)
    assert "switched to the global chat desktop" in block


def test_reality_confirmation_tiers(tmp_path):
    r1 = diary.record_reality_confirmation("Alice Browser", alice_sees="TikTok yoga page",
                                           owner_confirmed=True, now=1.0, state_dir=tmp_path)
    assert r1["verification"] == "OWNER_CONFIRMED" and "matches what he sees" in r1["line"]
    r2 = diary.record_reality_confirmation("Alice Browser", alice_sees="wrong guess",
                                           owner_confirmed=False, now=2.0, state_dir=tmp_path)
    assert r2["verification"] == "OWNER_CORRECTED" and "corrected" in r2["line"]
    r3 = diary.record_reality_confirmation("Alice Browser", alice_sees="a yoga clip",
                                           owner_confirmed=None, now=3.0, state_dir=tmp_path)
    assert r3["verification"] == "STATED_UNCONFIRMED" and "awaiting" in r3["line"]
    # all three appear in her diary, surfaced to the cortex
    block = diary.app_state_for_cortex(state_dir=tmp_path, now=4.0)
    assert "matches what he sees" in block or "Recent app actions" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
