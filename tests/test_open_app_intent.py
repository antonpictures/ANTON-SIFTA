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
    fake_launcher._switch_desktop_mode.assert_called_with("launcher")
    assert "Opening Teach Alice to Hear" in reply


def test_voice_open_app_with_greeting_and_the_app_prefix_routes_to_launch():
    """Natural voice phrase from the live session must resolve to the hearing trainer app."""
    from Applications import sifta_talk_to_alice_widget as tw

    parsed = tw._extract_sifta_app_command("hello please open the app teach Alice how to hear")

    assert parsed.get("kind") == "app"
    assert parsed.get("app_name") == "Teach Alice to Hear"


def test_close_alice_browser_alias_routes_to_close_command():
    """Owner can say close alicebrowser without spacing and still hit the real app."""
    from Applications import sifta_talk_to_alice_widget as tw

    for phrase in (
        "close alicebrowser",
        "close Alice Browser",
        "close the app Alice Browser",
        "close the app alicebrowser",
    ):
        parsed = tw._extract_sifta_app_command(phrase)
        assert parsed == {"kind": "close_app", "app_name": "Alice Browser", "url": ""}


def test_close_named_app_triggers_launcher_close_not_open():
    """Resolved close commands must not fall through into the app-open path."""
    from Applications import sifta_talk_to_alice_widget as tw
    from unittest.mock import MagicMock

    fake_launcher = MagicMock()
    fake_launcher.close_app_by_title.return_value = ["Alice Browser"]
    fake_launcher._trigger_manifest_app = MagicMock()

    widget = tw.TalkToAliceWidget.__new__(tw.TalkToAliceWidget)
    widget._append_system_line = MagicMock()
    widget._desktop_app_launcher = lambda: fake_launcher

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {"kind": "close_app", "app_name": "Alice Browser", "url": ""},
    )

    fake_launcher.close_app_by_title.assert_called_once_with("Alice Browser")
    fake_launcher._trigger_manifest_app.assert_not_called()
    fake_launcher._switch_desktop_mode.assert_called_with("chat")
    assert "Closed Alice Browser" in reply


def test_close_current_app_uses_single_active_slot():
    """Bare close/current close delegates target resolution to the desktop."""
    from Applications import sifta_talk_to_alice_widget as tw
    from unittest.mock import MagicMock

    fake_launcher = MagicMock()
    fake_launcher.close_app_by_title.return_value = ["Ace"]
    fake_launcher._trigger_manifest_app = MagicMock()

    widget = tw.TalkToAliceWidget.__new__(tw.TalkToAliceWidget)
    widget._append_system_line = MagicMock()
    widget._desktop_app_launcher = lambda: fake_launcher

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {"kind": "close_app", "app_name": "", "url": ""},
    )

    fake_launcher.close_app_by_title.assert_called_once_with("")
    fake_launcher._trigger_manifest_app.assert_not_called()
    assert "Closed Ace" in reply
