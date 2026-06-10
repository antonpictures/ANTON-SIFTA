"""r899 — typed YouTube navigate must work without pre-cortex reflex env flag."""

import Applications.sifta_talk_to_alice_widget as talk


def test_typed_youtube_channel_allowed_without_reflex_env(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_PRE_CORTEX_CHAT_REFLEXES", raising=False)
    phrase = "ARE YOU ABLE AT LEAST TO LOAD UP THE GUYS YOUTUBE CHANNEL?"
    assert talk._typed_browser_navigate_effector_allowed(typed_turn=True, text=phrase)


def test_spoken_turn_not_allowed_without_reflex_env(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_PRE_CORTEX_CHAT_REFLEXES", raising=False)
    phrase = "LOAD UP THE GUYS YOUTUBE CHANNEL"
    assert not talk._typed_browser_navigate_effector_allowed(typed_turn=False, text=phrase)