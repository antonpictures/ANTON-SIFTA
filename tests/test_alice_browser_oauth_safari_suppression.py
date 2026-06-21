"""r991/r1316 — Alice Browser must not steal web work into Safari."""

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


def test_suppress_unrelated_oauth_without_drop_by_alice_only_doctrine():
    assert should_suppress_oauth_safari_handoff(
        "https://accounts.google.com/o/oauth2/auth",
        owner_drop_target="",
        suppress_until=0.0,
    )
