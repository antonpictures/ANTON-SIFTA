"""r1397/r1401 — positive gate: web search only when owner explicitly requested it."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    _fallback_contextual_shopping_query,
    _is_search_audit_or_routing_correction,
    _owner_explicitly_requested_web_search,
)


def test_ppo_llm_turn_does_not_request_web_search():
    text = (
        "You will know LMs are neural networks and when you take doing labelite. "
        "So here you can only use the LMs. So it's messy. This is the idealized PPO use."
    )
    assert not _owner_explicitly_requested_web_search(text)


def test_search_complaint_is_audit_not_search_command():
    text = (
        "RECURRING SEARCH BUG https://www.google.com/search?q=white+brown+swimsuit REMOVE "
        "-- I DID NOT ASK FOR SEARCH"
    )
    assert _is_search_audit_or_routing_correction(text)
    assert not _owner_explicitly_requested_web_search(text)


def test_unsolicited_swimsuit_query_blocked_by_positive_owner_intent_gate():
    owner = "If you supervise my tuning, you improve them up."
    assert not _owner_explicitly_requested_web_search(owner)


def test_explicit_swimsuit_shopping_allowed_when_owner_asked():
    owner = "Where can I buy this type of swimsuit? Can you search on Google?"
    assert _owner_explicitly_requested_web_search(owner)


def test_fallback_shopping_query_requires_explicit_owner_search_intent():
    evidence = (
        "Latest browser photo vision: A woman in a brown-and-white swimsuit poses outdoors "
        "near a bright beach."
    )
    assert _fallback_contextual_shopping_query(evidence, "If you supervise my tuning") == ""
    assert _fallback_contextual_shopping_query(
        evidence,
        "search for the green puffy leg wardrobe things",
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))