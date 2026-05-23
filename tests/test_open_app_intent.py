#!/usr/bin/env python3
"""tests/test_open_app_intent.py — P2 acceptance test from GROK_BIG_BATCH_ORDER_2026-05-21.

Voice or typed "open Teach Alice to Hear" must resolve to an actual app launch (not fall to chat or uncertain clarification).
Unknown app names must not silently misfire or hallucinate.

This test must be able to fail if the wiring is removed or broken.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_open_known_app_resolves_to_launch():
    """ "open Teach Alice to Hear" must produce an app launch command, not uncertain or chat."""
    # This will be wired against the real _extract_sifta_app_command + execution path
    # For now the test documents the required contract.
    from Applications import sifta_talk_to_alice_widget as tw

    # Simulate the parsing path that voice goes through
    parsed = tw._extract_sifta_app_command("open Teach Alice to Hear")

    # After P2 wiring, this must return a launchable app command
    assert parsed.get("kind") == "app"
    assert "Teach Alice to Hear" in parsed.get("app_name", "") or "teach" in parsed.get("app_name", "").lower()

    # Voice phrasing the owner actually used
    parsed_voice = tw._extract_sifta_app_command("open teach alice how to hear")
    assert parsed_voice.get("kind") == "app"
    assert "Teach Alice to Hear" in parsed_voice.get("app_name", "") or "teach" in parsed_voice.get("app_name", "").lower()


def test_open_unknown_app_does_not_misfire(monkeypatch):
    """Ambiguous "open FooBar" must not launch anything and must not fall through to brain without warning."""
    from Applications import sifta_talk_to_alice_widget as tw

    parsed = tw._extract_sifta_app_command("open CompletelyUnknownAppName123")

    # Should either be uncertain (with candidates) or empty (let other logic handle), never a fake launch
    assert parsed.get("kind") in ("open_app_uncertain", "") or parsed == {}


def test_voice_open_app_actually_triggers_launcher(monkeypatch):
    """Resolved "app" command (from voice) must call the launcher's trigger method."""
    from Applications import sifta_talk_to_alice_widget as tw
    from unittest.mock import MagicMock

    fake_launcher = MagicMock()
    fake_launcher._trigger_manifest_app = MagicMock()

    def fake_get_launcher():
        return fake_launcher

    widget = tw.TalkToAliceWidget.__new__(tw.TalkToAliceWidget)
    widget._append_system_line = MagicMock()
    widget._desktop_app_launcher = fake_get_launcher

    command = {"kind": "app", "app_name": "Teach Alice to Hear"}
    reply = tw.TalkToAliceWidget._execute_sifta_app_command(widget, command)

    fake_launcher._trigger_manifest_app.assert_called_with("Teach Alice to Hear")
    assert "Opening Teach Alice to Hear" in reply


def test_voice_open_app_with_greeting_and_the_app_prefix_routes_to_launch():
    """Natural voice phrase from the live session must resolve to the hearing trainer app."""
    from Applications import sifta_talk_to_alice_widget as tw

    parsed = tw._extract_sifta_app_command("hello please open the app teach Alice how to hear")

    assert parsed.get("kind") == "app"
    assert parsed.get("app_name") == "Teach Alice to Hear"
