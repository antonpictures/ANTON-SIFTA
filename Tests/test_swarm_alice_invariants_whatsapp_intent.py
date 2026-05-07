from __future__ import annotations

from System import swarm_alice_invariants as invariants


def test_extract_whatsapp_intent_accepts_owner_tell_him_phrase(monkeypatch) -> None:
    monkeypatch.setattr(invariants, "_trace", lambda _event: None)

    intent = invariants.extract_whatsapp_intent(
        "Hey Alice, can you send a message to Carlton please on WhatsApp "
        "and tell him that we have submitted the application?"
    )

    assert intent == ("Carlton", "we have submitted the application?")


def test_extract_whatsapp_intent_accepts_confirmation_that_phrase(monkeypatch) -> None:
    monkeypatch.setattr(invariants, "_trace", lambda _event: None)

    intent = invariants.extract_whatsapp_intent(
        "I confirm just send the message to Carlton that we did it."
    )

    assert intent == ("Carlton", "we did it.")


def test_extract_whatsapp_intent_keeps_message_not_repeated_command(monkeypatch) -> None:
    monkeypatch.setattr(invariants, "_trace", lambda _event: None)

    intent = invariants.extract_whatsapp_intent(
        "correct. Now I need you to send a WhatsApp message to Carlton "
        "that you and me we did it. We executed this task. The task is completed. "
        "Send a message to Carlton on WhatsApp. The task is completed. "
        "Carlton tell him exactly like that."
    )

    assert intent == (
        "Carlton",
        "you and me we did it. We executed this task. The task is completed.",
    )


def test_extract_whatsapp_intent_ignores_addressed_body_without_send_intent(monkeypatch) -> None:
    monkeypatch.setattr(invariants, "_trace", lambda _event: None)

    intent = invariants.extract_whatsapp_intent(
        "Carlton, we have submitted the A16Z speedrun application."
    )

    assert intent is None
