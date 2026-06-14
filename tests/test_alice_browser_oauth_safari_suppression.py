"""r991 — YouTube co-watch in Alice Browser must not steal into Safari via r503 OAuth handoff."""

import time

from Applications.sifta_alice_browser_widget import should_suppress_oauth_safari_handoff


def test_suppress_during_owner_drop_window():
    now = time.time()
    assert should_suppress_oauth_safari_handoff(
        "https://accounts.youtube.com/ServiceLogin?continue=...",
        suppress_until=now + 60.0,
        owner_drop_target="",
        now=now,
    )


def test_suppress_youtube_watch_oauth_redirect():
    assert should_suppress_oauth_safari_handoff(
        "https://accounts.google.com/o/oauth2/auth",
        owner_drop_target="https://www.youtube.com/watch?v=4Uk0_1yqdJo",
    )


def test_allow_unrelated_oauth_without_drop():
    assert not should_suppress_oauth_safari_handoff(
        "https://accounts.google.com/o/oauth2/auth",
        owner_drop_target="",
        suppress_until=0.0,
    )