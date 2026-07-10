#!/usr/bin/env python3
"""r1613 — Claude audit F1–F4: prose journal → cortex, phone hoist, end-card, no help-desk."""
from __future__ import annotations

from Applications.sifta_talk_to_alice_widget import (
    _autonomic_prebrain_must_defer_to_cortex,
    _is_terse_journal_recall_command,
    _autonomic_prebrain_reflex,
)
from System.swarm_media_ingress_gate import classify_spoken_ingress
from System.swarm_phone_call_tracker import is_phone_declaration, handle_phone_declaration


VEVSACHI = (
    "phone call on speaker and you've entered the conversation with Mr. Vevsachi. "
    "I'm going to call him again. Remember when I called him yesterday morning? "
    "You have to look in your journal. Alice, journal you have. You have memories."
)


def test_vevsachi_prose_defers_to_cortex():
    assert _is_terse_journal_recall_command(VEVSACHI) is False
    assert _autonomic_prebrain_must_defer_to_cortex(VEVSACHI) is True
    reply, tag = _autonomic_prebrain_reflex(VEVSACHI, write_receipt=False)
    assert reply == ""
    assert tag == ""
    assert "Give me a name" not in reply
    assert "Loaded from my Alice Journal" not in reply


def test_terse_journal_still_allowed():
    s = "do you remember what happened two days ago"
    assert _is_terse_journal_recall_command(s) is True
    assert _autonomic_prebrain_must_defer_to_cortex(s) is False


def test_phone_declaration_fires_on_vevsachi():
    assert is_phone_declaration(VEVSACHI) is True
    evt, reply = handle_phone_declaration(VEVSACHI, stt_conf=0.6)
    assert evt == "phone_call_active"
    # Non-log declaration: silent ledger write (cortex may still speak if allowed)


def test_thank_you_for_watching_is_observed_media():
    d = classify_spoken_ingress(
        "Thank you for watching!",
        stt_conf=0.7,
        focus_context="",
        voice_george_conf=0.0,
    )
    assert d["route"] in {"observed_media", "ambient_media"}
    assert d["reason"] == "platform_end_card_not_owner"


def test_no_helpdesk_journal_fallback():
    reply, tag = _autonomic_prebrain_reflex(
        "look in your journal for zxyzzy_nonexistent_token_12345",
        write_receipt=False,
    )
    # Either short narrative or empty cortex — never Round-46 help-desk menu
    assert "Give me a name, day part" not in (reply or "")
    assert "day part (yesterday morning)" not in (reply or "")
