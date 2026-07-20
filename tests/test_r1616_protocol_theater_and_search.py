"""r1616 — protocol theater gag + r1615 search subject still holds."""
from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk


def test_data_acquisition_protocol_is_internal_processing_theater() -> None:
    raw = (
        "(DATA ACQUISITION PROTOCOL: ENGAGED)\n"
        "(QUERY VECTOR: TROJAN_WAR / SEMANTIC DENSITY HIGH)\n"
        "(SOURCE PARSING PRIORITY: HOMERIAN NARRATIVE)\n\n"
        "Yes. I have a substantial data cluster on the Trojan War."
    )
    rule = talk._domain_boilerplate_rule_id(
        raw, prior_user_text="do you have any facts on the Trojan War?"
    )
    assert rule == "lysosome/internal-processing-theater"


def test_trojan_web_search_still_recovers_subject_r1615() -> None:
    turn = (
        "In what year is the claim that trojan war happened? "
        "what is the current evidence. can you search the web and pull information?"
    )
    command = talk._extract_browser_search_command(turn)
    query = str(command.get("query") or "").lower()
    assert "trojan war" in query
    assert query != "and pull information"
