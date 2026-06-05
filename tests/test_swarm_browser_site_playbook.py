#!/usr/bin/env python3
"""Tests: per-site stigmergic playbook for Alice Browser (George 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_site_playbook as pb


def test_domain_is_the_category():
    assert pb.site_category("https://www.tiktok.com/@barbellinaa") == "tiktok.com"
    assert pb.site_category("tiktok.com") == "tiktok.com"
    assert pb.site_category("https://en.wikipedia.org/wiki/Yoga") == "wikipedia.org"


def test_record_and_read_site_skill(tmp_path):
    pb.record_site_skill("tiktok.com", "search",
                         "go to tiktok.com/search?q=<query>", state_dir=tmp_path)
    book = pb.site_playbook("https://www.tiktok.com/@x", state_dir=tmp_path)
    assert "search" in book
    assert "search?q=" in book["search"]["how_to"]


def test_reinforce_use_count(tmp_path):
    pb.record_site_skill("tiktok.com", "search", "v1", state_dir=tmp_path)
    e = pb.record_site_skill("tiktok.com", "search", "v2", state_dir=tmp_path)
    assert e["use_count"] == 2


def test_seed_defaults_gives_tiktok_playbook(tmp_path):
    pb.seed_defaults(state_dir=tmp_path)
    block = pb.playbook_block("tiktok.com", state_dir=tmp_path)
    assert "HOW TO USE tiktok.com IN ALICE BROWSER" in block
    assert "search" in block and "open profile" in block
    assert "/@<handle>" in block
    google = pb.playbook_block("google.com", state_dir=tmp_path)
    assert "https://www.google.com/search?q=<query>" in google
    youtube = pb.playbook_block("youtube.com", state_dir=tmp_path)
    assert "https://www.youtube.com/results?search_query=<query>" in youtube
    assert "watch video" in youtube


def test_seed_defaults_is_idempotent(tmp_path):
    pb.seed_defaults(state_dir=tmp_path)
    pb.seed_defaults(state_dir=tmp_path)
    book = pb.site_playbook("tiktok.com", state_dir=tmp_path)
    assert book["search"]["use_count"] == 1


def test_unknown_site_falls_back_to_general_browsing(tmp_path):
    block = pb.playbook_block("example.com", state_dir=tmp_path)
    assert "no site-specific playbook yet" in block
    # she's not blind on a new site — general web-literacy kicks in
    assert "GENERAL BROWSING" in block
    assert "search box" in block and "links" in block


def test_general_browsing_block_is_durable_moves_not_queries():
    g = pb.general_browsing_block()
    assert "search box" in g
    assert "the query changes every time, the move does not" in g


def test_owner_confirmed_flag_sticks(tmp_path):
    pb.record_site_skill("tiktok.com", "search", "v1", owner_confirmed=True, state_dir=tmp_path)
    pb.record_site_skill("tiktok.com", "search", "v2", state_dir=tmp_path)  # no flag
    book = pb.site_playbook("tiktok.com", state_dir=tmp_path)
    assert book["search"]["owner_confirmed"] is True  # confirmation persists


def test_search_interest_is_recency_not_permanent_preference(tmp_path):
    pb.record_site_search("tiktok.com", "mercedes", now=100.0, state_dir=tmp_path)
    pb.record_site_search("tiktok.com", "ferrari", now=200.0, state_dir=tmp_path)

    rows = pb.recent_site_searches("tiktok.com", state_dir=tmp_path)
    assert [r["query"] for r in rows[:2]] == ["ferrari", "mercedes"]
    block = pb.search_interest_block("tiktok.com", state_dir=tmp_path)
    assert "recency only" in block
    assert "ferrari" in block and "mercedes" in block
    assert "RECENT_CONTEXT_NOT_PERMANENT_IDENTITY" in block


def test_extracts_search_query_from_common_urls():
    assert pb.extract_search_query("https://www.tiktok.com/search?q=barbellina") == "barbellina"
    assert pb.extract_search_query("https://www.google.com/search?q=mercedes+amg") == "mercedes amg"
    assert pb.extract_search_query("https://www.youtube.com/results?search_query=ai+campaigns") == "ai campaigns"


def test_record_search_from_url(tmp_path):
    row = pb.record_search_from_url(
        "https://www.google.com/search?q=ferrari",
        state_dir=tmp_path,
    )
    assert row["category"] == "google.com"
    assert row["query"] == "ferrari"


def test_resolve_site_navigation_fills_profile_slot_not_hardcoded_person(tmp_path):
    assert (
        pb.resolve_site_navigation("go on TikTok at surfcoach2026", state_dir=tmp_path)
        == "https://www.tiktok.com/@surfcoach2026"
    )
    assert (
        pb.resolve_site_navigation("open @bodymodel_xyz on TikTok", state_dir=tmp_path)
        == "https://www.tiktok.com/@bodymodel_xyz"
    )


def test_resolve_site_navigation_fills_mutable_search_query(tmp_path):
    assert (
        pb.resolve_site_navigation("search ferrari on TikTok", state_dir=tmp_path)
        == "https://www.tiktok.com/search?q=ferrari"
    )
    assert (
        pb.resolve_site_navigation("find yoga on google", state_dir=tmp_path)
        == "https://www.google.com/search?q=yoga"
    )


def test_resolve_site_navigation_does_not_turn_place_phrase_into_profile(tmp_path):
    assert pb.resolve_site_navigation("go on TikTok at the gym", state_dir=tmp_path) == ""


def test_bare_site_name_resolves_to_home_url():
    # George 2026-05-30: STT garbled "open Alice browser on Instagram"; the bare
    # site target was dropped. A reasoning body lands on the site home page.
    assert pb.home_url_from_text("And it's please open Alice browser on Instagram.") == "https://www.instagram.com"
    assert pb.home_url_from_text("open alice browser on tiktok") == "https://www.tiktok.com"
    assert pb.home_url_from_text("go to youtube in alice browser") == "https://www.youtube.com"
    assert pb.home_url_from_text("twitter please") == "https://x.com"


def test_home_url_does_not_fire_without_a_site():
    assert pb.home_url_from_text("open alice browser") == ""
    assert pb.home_url_from_text("open the camera app") == ""
    assert pb.home_url_from_text("") == ""


def test_site_kind_is_the_category_name():
    assert pb.site_kind("https://www.google.com/search?q=x") == "search engine"
    assert pb.site_kind("youtube.com") == "video platform"
    assert pb.site_kind("https://example.org/foo") == "website"  # unknown -> generic


def test_playbook_block_names_the_category(tmp_path):
    pb.seed_defaults(state_dir=tmp_path)
    block = pb.playbook_block("google.com", state_dir=tmp_path)
    assert "CATEGORY: search engine" in block
    assert "slideshow images" in block  # the new slideshow habit is seeded


# George 2026-06-02: websites change; a habit that was good before can fail. Alice
# learns once with the swarm and the fix propagates via the receipt.
def test_skill_outcome_failure_flags_relearn_when_it_worked_before(tmp_path):
    pb.record_site_skill("tiktok.com", "search", "v1 https://www.tiktok.com/search?q=<query>", state_dir=tmp_path)
    # it worked before -> a fresh failure means the site likely changed
    out = pb.record_skill_outcome("tiktok.com", "search", False, note="selector gone", state_dir=tmp_path)
    assert out["needs_relearn"] is True
    assert out["fail_count"] == 1
    stale = pb.skills_needing_relearn("tiktok.com", state_dir=tmp_path)
    assert any(s["skill"] == "search" for s in stale)
    block = pb.playbook_block("tiktok.com", state_dir=tmp_path)
    assert "needs relearn" in block


def test_skill_outcome_success_does_not_flag_relearn(tmp_path):
    pb.record_site_skill("tiktok.com", "search", "v1", state_dir=tmp_path)
    out = pb.record_skill_outcome("tiktok.com", "search", True, state_dir=tmp_path)
    assert out["needs_relearn"] is False
    assert out["success_count"] == 1
    assert pb.skills_needing_relearn("tiktok.com", state_dir=tmp_path) == []


def test_relearn_clears_flag_bumps_version_and_propagates(tmp_path):
    pb.record_site_skill("tiktok.com", "search", "old", state_dir=tmp_path)
    pb.record_skill_outcome("tiktok.com", "search", False, state_dir=tmp_path)
    assert pb.skills_needing_relearn("tiktok.com", state_dir=tmp_path)
    relearned = pb.relearn_site_skill(
        "tiktok.com", "search",
        "navigate to https://www.tiktok.com/search?q=<query> (new layout 2026)",
        source="swarm", state_dir=tmp_path,
    )
    assert relearned["needs_relearn"] is False
    assert relearned["version"] == 2
    assert pb.skills_needing_relearn("tiktok.com", state_dir=tmp_path) == []
    # the corrected recipe is now what the playbook serves to every IDE/arm
    assert "new layout 2026" in pb.site_playbook("tiktok.com", state_dir=tmp_path)["search"]["how_to"]


def test_first_time_failure_on_unknown_skill_does_not_falsely_flag(tmp_path):
    # never worked before -> a failure is not evidence the site changed
    out = pb.record_skill_outcome("newsite.com", "checkout", False, state_dir=tmp_path)
    assert out["needs_relearn"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
