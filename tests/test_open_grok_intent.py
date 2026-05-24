"""Alice must route 'open grok' (and friends) to the open_grok_cli effector.

George's rule (2026-05-23): the owner names the action in plain English; Alice
executes it in her own terminal — no button. This locks the intent → effector
routing so the command can't silently fall back to 'chat'.
"""
from __future__ import annotations

from System.swarm_edge_intent_router import classify_intent


def _decide(text: str) -> dict:
    return classify_intent(text, write_receipt=False)


def test_open_grok_routes_to_effector():
    for phrase in (
        "Alice open grok",
        "type grok in terminal",
        "start grok",
        "talk to grok",
        "open grok in the terminal",
    ):
        d = _decide(phrase)
        assert d["target"] == "open_grok_cli", f"{phrase!r} -> {d}"
        assert d["lane"] == "tool", f"{phrase!r} -> {d}"
        assert d["may_effector"] is True, f"{phrase!r} must be allowed to act: {d}"


def test_plain_chat_does_not_trigger_grok():
    """Don't fire the effector on unrelated chat that merely mentions a name."""
    d = _decide("how are you today")
    assert d["target"] != "open_grok_cli", d
