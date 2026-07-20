"""Browser time proprioception — loading vs settled land claims."""
from __future__ import annotations

from System.swarm_browser_time_sense import (
    judge_land_claim,
    note_load_finished,
    note_load_started,
    note_navigation_ordered,
    urls_roughly_match,
)


def test_ddg_query_match_allows_extra_params():
    a = "https://duckduckgo.com/?q=mercedes+sedan"
    b = "https://duckduckgo.com/?q=mercedes+sedan&ia=web"
    assert urls_roughly_match(a, b)


def test_still_loading_does_not_speak_fail(tmp_path):
    note_navigation_ordered(
        "https://duckduckgo.com/?q=mercedes+sedan",
        state_dir=tmp_path,
    )
    note_load_started(
        "https://duckduckgo.com/?q=mercedes+sedan",
        state_dir=tmp_path,
    )
    # Stale observed URL while new load in flight
    j = judge_land_claim(
        "https://duckduckgo.com/?q=mercedes+sedan",
        "https://duckduckgo.com/?q=alva+inga+in+sagram&ia=images",
        state_dir=tmp_path,
    )
    assert j["speak_fail"] is False
    assert j["action"] == "wait_still_loading"


def test_settled_match_is_landed(tmp_path):
    note_navigation_ordered(
        "https://duckduckgo.com/?q=mercedes+sedan",
        state_dir=tmp_path,
    )
    note_load_started(
        "https://duckduckgo.com/?q=mercedes+sedan",
        state_dir=tmp_path,
    )
    note_load_finished(
        "https://duckduckgo.com/?q=mercedes+sedan&ia=web",
        ok=True,
        duration_s=2.5,
        state_dir=tmp_path,
    )
    j = judge_land_claim(
        "https://duckduckgo.com/?q=mercedes+sedan",
        "https://duckduckgo.com/?q=mercedes+sedan&ia=web",
        state_dir=tmp_path,
    )
    assert j["ok"] is True
    assert j["speak_success"] is True
    assert j["speak_fail"] is False


def test_settled_mismatch_speaks_fail(tmp_path):
    note_navigation_ordered("https://example.com/a", state_dir=tmp_path)
    note_load_started("https://example.com/a", state_dir=tmp_path)
    note_load_finished(
        "https://example.com/other",
        ok=True,
        duration_s=1.0,
        state_dir=tmp_path,
    )
    j = judge_land_claim(
        "https://example.com/a",
        "https://example.com/other",
        state_dir=tmp_path,
    )
    assert j["ok"] is False
    assert j["speak_fail"] is True
