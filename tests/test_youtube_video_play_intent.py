#!/usr/bin/env python3
"""r314: George's live failure (2026-06-01). He typed

    "open youtube.com and open THE OFFICIAL 2018 VICTORIA'S SECRET FASHION SHOW video pls Alice. thank you"

and Alice only loaded the youtube.com HOME page — no search, no result selection, no
play. Two faults stacked:

  1. The talk classifier matched "Alice Browser" and collapsed the command to the bare
     domain youtube.com BEFORE consulting the search parser (root cause, fixed by routing
     the explicit-search intent ahead of the bare-domain navigate).
  2. The auto-after-search path clicked the *first* visible result (blind, no title match,
     no forced play) instead of the title-matching + force-play helper.

This test pins the PARSER contract that both fixes depend on: the exact phrasing must be
recognised as an explicit YouTube search, carry the owner's VERBATIM title (no injected
terms — the r305 'lingerie' regression must never return), and set is_video_play so the
talk widget routes it through _schedule_youtube_result_open (title match → retry → play).

Pure module (no Qt, no network) so it runs on a headless node and on the M5.
"""
from System.swarm_youtube_search_intent import (
    parse_explicit_youtube_search,
    youtube_results_url,
)


def test_open_official_2018_video_is_a_video_play_search():
    text = ("open youtube.com and open THE OFFICIAL 2018 VICTORIA'S SECRET FASHION "
            "SHOW video pls Alice. thank you")
    out = parse_explicit_youtube_search(text)
    assert out["is_search"] is True
    assert out.get("is_video_play") is True
    q = out["query"].lower()
    # verbatim title tokens the owner actually said
    assert "official" in q
    assert "2018" in q
    assert "victoria" in q and "secret" in q and "fashion" in q and "show" in q
    # r305 anti-injection guard: never sexualise / expand the owner's words
    for injected in ("lingerie", "wings", "heels", "bikini", "underwear"):
        assert injected not in q, injected


def test_play_the_video_on_youtube_phrasing():
    out = parse_explicit_youtube_search("play the Halsey Without Me video on youtube")
    assert out["is_search"] is True
    assert out.get("is_video_play") is True
    assert "halsey" in out["query"].lower()


def test_plain_search_command_is_not_a_video_play():
    # The happy first turn from the transcript: a pure search must NOT auto-play.
    out = parse_explicit_youtube_search("search on youtube Victoria Secret fashion show")
    assert out["is_search"] is True
    assert out.get("is_video_play") in (False, None)
    assert "victoria" in out["query"].lower()


def test_non_youtube_text_is_not_a_search():
    assert parse_explicit_youtube_search("what time is it").get("is_search") is False
    assert parse_explicit_youtube_search("").get("is_search") is False


def test_results_url_encodes_verbatim_query():
    url = youtube_results_url("OFFICIAL 2018 VICTORIA'S SECRET FASHION SHOW")
    assert url.startswith("https://www.youtube.com/results?search_query=")
    assert "OFFICIAL" in url or "official" in url.lower()
    assert "2018" in url
