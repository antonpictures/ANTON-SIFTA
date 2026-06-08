#!/usr/bin/env python3
"""r305: an explicit "search YouTube for X" searches YouTube for EXACTLY X.

Pins George's live-failure phrasings: the query is taken verbatim (never expanded into
words he didn't say, e.g. no 'lingerie'), trailing teaching context is dropped, and a
non-YouTube/Google command does not trigger this path at all.
"""
from System import swarm_youtube_search_intent as yt


def test_georges_exact_command_extracts_verbatim_query():
    r = yt.parse_explicit_youtube_search(
        "Pls search on youtube Victoria Secret fashion show. I want to teach you clothing on human bodies on youtube.")
    assert r["is_search"] is True
    assert r["query"] == "Victoria Secret fashion show"          # verbatim, teaching context dropped
    assert "lingerie" not in r["query"].lower()                   # NEVER inject terms he didn't say


def test_open_youtube_and_search_form():
    r = yt.parse_explicit_youtube_search("Please open Alice Browser on YouTube and search Victoria Secrets fashion.")
    assert r["is_search"] is True
    assert r["query"] == "Victoria Secrets fashion"
    assert r["is_video_play"] is False


def test_open_youtube_dot_com_and_search_form_is_search_not_autoplay():
    r = yt.parse_explicit_youtube_search("ALICE, PLS OPEN YOUTUBE.COM AND SEARCH FOR CERAMIC VASE")
    assert r["is_search"] is True
    assert r["query"] == "CERAMIC VASE"
    assert r["is_video_play"] is False


def test_open_on_youtube_dot_com_keeps_following_title_as_query():
    r = yt.parse_explicit_youtube_search("OPEN ON YOUTUBE.COM Swim Swimwear Fashion Show - Miami Swim Week")
    assert r["is_search"] is True
    assert r["query"] == "Swim Swimwear Fashion Show - Miami Swim Week"
    assert r["is_video_play"] is False


def test_stt_your_tube_alias_search_form():
    r = yt.parse_explicit_youtube_search(
        "Please open your tube and search for the Victoria Secret Fashion Show 2013."
    )
    assert r["is_search"] is True
    assert r["query"] == "Victoria Secret Fashion Show 2013"


def test_find_it_on_youtube_dot_com_correction_form():
    r = yt.parse_explicit_youtube_search(
        "The Victoria Secret Fashion Show you can find it on youtube.com which is inside Alice Browser in your body."
    )
    assert r["is_search"] is True
    assert r["query"] == "The Victoria Secret Fashion Show"


def test_open_youtube_and_open_specific_video_form():
    r = yt.parse_explicit_youtube_search(
        "open youtube.com and open THE OFFICIAL 2018 VICTORIA’S SECRET FASHION SHOW video pls Alice. thank you"
    )
    assert r["is_search"] is True
    assert r["query"] == "OFFICIAL 2018 VICTORIA’S SECRET FASHION SHOW"
    assert r["is_video_play"] is True


def test_search_X_on_youtube_form():
    r = yt.parse_explicit_youtube_search("search victoria secret models runway on youtube")
    assert r["is_search"] is True
    assert r["query"] == "victoria secret models runway"


def test_non_explicit_or_google_is_left_alone():
    assert yt.parse_explicit_youtube_search("i said victoria secret models runway")["is_search"] is False
    assert yt.parse_explicit_youtube_search("search google for white watch")["is_search"] is False
    assert yt.parse_explicit_youtube_search("what channel is this?")["is_search"] is False


def test_results_url_uses_exact_query():
    url = yt.youtube_results_url("Victoria Secret fashion show")
    assert url.startswith("https://www.youtube.com/results?search_query=")
    assert "Victoria" in url and "Secret" in url
