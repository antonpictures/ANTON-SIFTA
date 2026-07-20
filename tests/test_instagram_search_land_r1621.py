"""r1621-08 — Instagram search/profile land verification."""
from __future__ import annotations

from System.swarm_instagram_search_land import (
    build_instagram_targets,
    handle_from_query,
    instagram_search_url,
    observed_matches_instagram_intent,
)


def test_kylin_milan_prefers_profile_handle():
    t = build_instagram_targets("kylin milan")
    assert t["handle"] == "kylinmilan"
    assert t["intent"] == "profile"
    assert "kylinmilan" in t["primary_url"]
    assert "instagram.com" in t["primary_url"]


def test_instagram_search_url_drop_in():
    url = instagram_search_url("kylin milan")
    assert "instagram.com" in url
    assert "kylinmilan" in url.lower()


def test_home_is_not_landed():
    r = observed_matches_instagram_intent(
        "https://www.instagram.com/",
        query="kylin milan",
    )
    assert r["ok"] is False
    assert r["reason"] == "stuck_on_home_or_login"


def test_profile_path_lands():
    r = observed_matches_instagram_intent(
        "https://www.instagram.com/kylinmilan/",
        query="kylin milan",
    )
    assert r["ok"] is True


def test_explore_search_lands():
    r = observed_matches_instagram_intent(
        "https://www.instagram.com/explore/search/keyword/?q=kylin%20milan",
        query="kylin milan",
    )
    assert r["ok"] is True


def test_handle_from_query():
    assert handle_from_query("@KylinMilan") == "kylinmilan"
