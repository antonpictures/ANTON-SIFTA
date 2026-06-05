#!/usr/bin/env python3
"""r311: Alice's web limb is HER OWN browser arm. If the owner names a foreign browser
(Safari/Chrome/etc.), the request routes INTO Alice Browser — Alice never acts in Safari
outside her body (§7.5 Python-first surface, §1.A one Alice). Talk widget needs PyQt6, so
this skips cleanly on a headless node and runs on the M5.
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
