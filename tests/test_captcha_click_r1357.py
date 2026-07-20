"""Human-verification challenge honesty — r1360."""
from __future__ import annotations

import Applications.sifta_talk_to_alice_widget as talk


def test_captcha_request_routes_to_blocker_report_not_youtube():
    cmd = talk._extract_browser_action_command(
        "YOU HAVE TO CLICK THE 3X DUCK SQUARES ON THE SCREEN, CAN U DO IT?"
    )
    assert cmd.get("action") == "report_human_verification_challenge"


def test_youtube_steal_blocked_for_captcha_phrase():
    assert talk._extract_youtube_visible_result_query(
        "YOU HAVE TO CLICK THE 3X DUCK SQUARES ON THE SCREEN"
    ) == ""


def test_search_on_duck_ai_pls_routes_to_web_ai_not_explicit_engine():
    cmd = talk._extract_explicit_engine_search_command(
        "SEARCH ON DUCK.AI PLS what is stigmergic consciousness"
    )
    assert cmd == {}