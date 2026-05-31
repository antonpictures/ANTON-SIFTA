#!/usr/bin/env python3
"""Tests for stigmergic taste + action consequence learning."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_taste_consequence_learning as tc


def test_predict_browser_search_is_reversible_and_records_preview(tmp_path):
    preview = tc.predict_action_consequence(
        {"kind": "browser.search", "domain": "tiktok.com", "query": "ferrari"},
        now=100.0,
        state_dir=tmp_path,
    )

    assert preview["risk"] == "LOW"
    assert preview["reversible"] is True
    assert preview["confirmation_required"] is False
    assert preview["mistake_allowed"] is True
    assert "browser_site_search_history.jsonl" in preview["expected_ledgers"]
    assert preview["taste_deltas"][0]["item"] == "ferrari"
    assert (tmp_path / ".sifta_state" / tc.PREVIEW_LEDGER).exists()


def test_high_impact_action_requires_confirmation(tmp_path):
    preview = tc.predict_action_consequence(
        {"kind": "browser.click", "label": "Pay now", "domain": "store.example"},
        state_dir=tmp_path,
    )

    assert preview["risk"] == "HIGH"
    assert preview["confirmation_required"] is True
    assert preview["mistake_allowed"] is False


def test_successful_outcome_reinforces_recent_taste(tmp_path):
    preview = tc.predict_action_consequence(
        {"kind": "browser.search", "domain": "google.com", "query": "mercedes"},
        now=100.0,
        state_dir=tmp_path,
    )
    tc.record_action_outcome(
        preview,
        {"url": "https://www.google.com/search?q=mercedes"},
        now=110.0,
        state_dir=tmp_path,
    )

    profile = tc.taste_profile("google.com", now=120.0, state_dir=tmp_path)
    assert profile[0]["item"] == "mercedes"
    assert profile[0]["recent_score"] > 0
    assert profile[0]["stable_score"] == 0


def test_owner_confirmed_taste_becomes_stable_anchor(tmp_path):
    tc.record_taste_trace(
        "music",
        "ambient",
        owner_confirmed=True,
        now=100.0,
        state_dir=tmp_path,
    )

    profile = tc.taste_profile("music", now=200.0, state_dir=tmp_path)
    assert profile[0]["item"] == "ambient"
    assert profile[0]["stable_score"] > 0


def test_mistake_outcome_is_learning_trace_not_hidden(tmp_path):
    preview = tc.predict_action_consequence(
        {"kind": "browser.search", "domain": "tiktok.com", "query": "barbellina"},
        state_dir=tmp_path,
    )
    outcome = tc.record_action_outcome(
        preview,
        {"url": "https://www.tiktok.com/search?q=wrong"},
        mistake=True,
        correction="Use the current search field; old query was stale.",
        owner_feedback="yes fix it",
        state_dir=tmp_path,
    )

    assert outcome["learning_status"] == "MISTAKE_ACCEPTED_LEARNING_TRACE"
    block = tc.mistake_learning_block(state_dir=tmp_path)
    assert "MISTAKE LEARNING" in block
    assert "old query was stale" in block


def test_taste_consequence_block_combines_taste_and_mistakes(tmp_path):
    tc.record_taste_trace("tiktok.com", "ferrari", now=100.0, state_dir=tmp_path)
    preview = tc.predict_action_consequence(
        {"kind": "browser.search", "domain": "tiktok.com", "query": "ferrari"},
        state_dir=tmp_path,
    )
    tc.record_action_outcome(preview, {}, mistake=True, correction="typed wrong site", state_dir=tmp_path)

    block = tc.taste_consequence_block(state_dir=tmp_path)
    assert "STIGMERGIC TASTE" in block
    assert "MISTAKE LEARNING" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
