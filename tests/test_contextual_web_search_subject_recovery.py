from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from Applications import sifta_talk_to_alice_widget as talk


LIVE_TROJAN_WAR_TURN = (
    "In what year is the claim that trojan war happened? "
    "what is the current evidence. can you search the web and pull information?"
)


def test_generic_search_tail_uses_preceding_owner_questions() -> None:
    command = talk._extract_browser_search_command(LIVE_TROJAN_WAR_TURN)

    query = str(command.get("query") or "")
    assert "trojan war" in query.lower()
    assert "current evidence" in query.lower()
    assert query.lower() != "and pull information"
    assert parse_qs(urlparse(str(command.get("url") or "")).query)["q"] == [query]


def test_post_cortex_bridge_keeps_recovered_subject() -> None:
    command = talk._hallucination_bridge_synthesize_web_browser_action(
        LIVE_TROJAN_WAR_TURN,
        "I found current archaeological evidence on the web.",
    )

    assert command is not None
    assert "trojan war" in str(command.get("query") or "").lower()
    assert command.get("contextual_search_source") == "post_cortex_web_bridge"


def test_generic_search_tail_without_subject_does_not_move_browser() -> None:
    assert talk._extract_browser_search_command(
        "Can you search the web and pull information?"
    ) == {}


def test_named_query_after_web_command_is_unchanged() -> None:
    command = talk._extract_browser_search_command(
        "Can you search the web for current evidence about the Trojan War?"
    )

    assert command.get("query") == "current evidence about the Trojan War"
