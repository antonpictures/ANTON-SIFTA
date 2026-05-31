#!/usr/bin/env python3
"""Tests for browser stigmergic memory (WISH_013 Lane A, 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_stigmergic_memory as mem


def test_categorize_by_site_name():
    assert mem.categorize("https://www.tiktok.com/@x/video/123") == "tiktok.com"
    assert mem.categorize("https://en.wikipedia.org/wiki/Yoga") == "wikipedia.org"


def test_agreement_score_overlap():
    assert mem.agreement_score("yoga nighttime stretch", "yoga nighttime stretch") == 1.0
    assert mem.agreement_score("yoga nighttime", "completely different words") == 0.0


def test_verification_owner_confirmed_is_strongest():
    tier, _ = mem.verification_status(owner_confirmed=True)
    assert tier == mem.V_OWNER_CONFIRMED


def test_verification_image_text_match_and_mismatch():
    t1, s1 = mem.verification_status(screen_text="yoga night stretch pose",
                                     page_text="yoga night stretch pose mat")
    assert t1 == mem.V_IMAGE_MATCH and s1 >= 0.3
    t2, _ = mem.verification_status(screen_text="banana finance stock",
                                    page_text="yoga night stretch pose")
    assert t2 == mem.V_MISMATCH


def test_verification_unverified_without_image():
    tier, _ = mem.verification_status()
    assert tier == mem.V_UNVERIFIED


def test_record_visit_and_recall_grouped(tmp_path):
    mem.record_visit("https://www.tiktok.com/@a/video/1", title="nighttime yoga | TikTok",
                     learned_description="a yoga clip", state_dir=tmp_path)
    mem.record_visit("https://en.wikipedia.org/wiki/Yoga", title="Yoga - Wikipedia",
                     learned_description="encyclopedia article on yoga", state_dir=tmp_path)
    grouped = mem.recall(state_dir=tmp_path)
    assert "tiktok.com" in grouped and "wikipedia.org" in grouped
    assert grouped["tiktok.com"][0]["learned_description"] == "a yoga clip"


def test_revisit_reinforces_visit_count(tmp_path):
    mem.record_visit("https://site.com/p", title="P", state_dir=tmp_path)
    e2 = mem.record_visit("https://site.com/p", title="P", state_dir=tmp_path)
    assert e2["visit_count"] == 2


def test_confirm_upgrades_to_owner_confirmed(tmp_path):
    mem.record_visit("https://site.com/p", title="P", learned_description="d",
                     screen_text="a b c", page_text="x y z", state_dir=tmp_path)
    before = mem.latest_for_url("https://site.com/p", state_dir=tmp_path)
    assert before["verification"] in (mem.V_MISMATCH, mem.V_UNVERIFIED)
    mem.confirm("https://site.com/p", state_dir=tmp_path)
    after = mem.latest_for_url("https://site.com/p", state_dir=tmp_path)
    assert after["verification"] == mem.V_OWNER_CONFIRMED


def test_infer_tiktok_features_from_search_profile_page():
    text = "TikTok\nSearch\nbarbellinaa\n4 Following\n430.9K Followers\n11.9M Likes\nMessage\nBody check (6)"
    features = mem.infer_site_features(
        "https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        page_text=text,
    )
    names = {f["feature_name"] for f in features}
    assert {"search", "profile_page", "profile_metrics", "message_button", "profile_collection_modal"} <= names


def test_record_snapshot_memory_writes_site_features_by_category(tmp_path):
    result = mem.record_snapshot_memory(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        page_text="TikTok Search Following 430.9K Followers 11.9M Likes Message",
        state_dir=tmp_path,
    )

    assert result["visit"]["category"] == "tiktok.com"
    assert any(f["feature_name"] == "search" for f in result["features"])
    grouped = mem.recall_site_features("tiktok.com", state_dir=tmp_path)
    assert grouped["tiktok.com"][0]["category"] == "tiktok.com"
    block = mem.site_category_prompt_block("tiktok.com", state_dir=tmp_path)
    assert "BROWSER SITE CATEGORIES" in block
    assert "TikTok search" in block
    assert "profile" in block.lower()


def test_record_snapshot_memory_tracks_search_query_as_recent_interest(tmp_path):
    from System.swarm_browser_site_playbook import recent_site_searches

    mem.record_snapshot_memory(
        url="https://www.tiktok.com/search?q=mercedes",
        title="mercedes | TikTok",
        page_text="TikTok Search mercedes",
        state_dir=tmp_path,
    )
    mem.record_snapshot_memory(
        url="https://www.tiktok.com/search?q=ferrari",
        title="ferrari | TikTok",
        page_text="TikTok Search ferrari",
        state_dir=tmp_path,
    )

    rows = recent_site_searches("tiktok.com", state_dir=tmp_path)
    assert [r["query"] for r in rows[:2]] == ["ferrari", "mercedes"]


def test_state_dir_can_be_repo_root_or_state_dir(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    mem.record_site_features(
        "https://www.tiktok.com/@x",
        title="x | TikTok",
        page_text="Search Followers Likes",
        state_dir=state_dir,
    )
    assert (state_dir / "browser_site_feature_memory.jsonl").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
