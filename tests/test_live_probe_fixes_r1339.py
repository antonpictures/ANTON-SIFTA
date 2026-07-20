from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_search_provider_reality import answer_provider_reality_audit


def test_provider_audit_question_does_not_parse_as_search():
    text = (
        "SO IF THE PREVIOUS PROMPT WAS TO USE GOOGLE, YOU JUST PICKED DUCKDUCK GOO "
        "UNCONSCIOUSLY JUST THINKING SEARCH THE WEB, CORRECT?"
    )
    assert talk._is_search_audit_or_routing_correction(text)
    assert talk._extract_explicit_internet_search_command(text) == {}


def test_official_website_command_parses_taylor_swift():
    cmd = talk._extract_official_website_load_command(
        "FIND TYLOR SWIFT OFFICIAL WEBSISITE:) AND LOAD IT, HOW CLEAR CAN I BE:)"
    )
    assert cmd.get("kind") == "browser_url"
    assert "official website" in str(cmd.get("query") or "").lower()
    assert "tylor swift" in str(cmd.get("query") or "").lower()


def test_sc_then_describe_clothing_detected():
    text = "/SC then /SC DESCRIBE CLOTHING"
    assert talk._is_sc_describe_clothing_command(text)


def test_provider_reality_audit_reply_without_ledger():
    reply = answer_provider_reality_audit(
        "SO IF THE PREVIOUS PROMPT WAS TO USE GOOGLE, YOU JUST PICKED DUCKDUCK GO, CORRECT?"
    )
    assert "routing-audit" in reply.lower() or "provider" in reply.lower()