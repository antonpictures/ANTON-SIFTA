#!/usr/bin/env python3
"""r311/r632/r1316: Alice's web limb is HER OWN browser arm. Foreign browser
app words (Safari/Chrome/etc.) route INTO Alice Browser. Even explicit Safari
wording is blocked/rerouted by the executor. Talk widget needs PyQt6, so this
skips cleanly on a headless node and runs on the M5.
"""
import pytest

pytest.importorskip("PyQt6")

from Applications.sifta_talk_to_alice_widget import _match_sifta_app_name  # noqa: E402


def test_foreign_browser_names_route_into_alice_browser():
    apps = ["Alice Browser"]
    for foreign in ("safari", "chrome", "googlechrome", "firefox", "edge", "arc", "brave"):
        assert _match_sifta_app_name(foreign, apps) == "Alice Browser", foreign


def test_plain_browser_words_still_route_to_alice_browser():
    apps = ["Alice Browser"]
    for word in ("browser", "webbrowser", "internetbrowser"):
        assert _match_sifta_app_name(word, apps) == "Alice Browser", word
