from Applications import sifta_talk_to_alice_widget as talk


def test_bare_alice_call_acknowledges_and_mentions_paused_video(monkeypatch):
    monkeypatch.setattr(talk, "_active_ai_wake_names_for_talk", lambda: {"alice"})

    reply = talk._wake_call_ack_reply("Alice", paused_video=True)

    assert reply == "Hey George, you called me. I paused the video. What should I execute?"


def test_bare_alice_execute_without_target_asks_for_target(monkeypatch):
    monkeypatch.setattr(talk, "_active_ai_wake_names_for_talk", lambda: {"alice"})

    reply = talk._wake_call_ack_reply("Hey Alice, execute", paused_video=False)

    assert reply == "Hey George, you called me. Tell me what to execute."


def test_alice_execute_with_command_does_not_get_confirmation_question(monkeypatch):
    monkeypatch.setattr(talk, "_active_ai_wake_names_for_talk", lambda: {"alice"})

    assert talk._wake_call_ack_reply("Alice execute open youtube.com", paused_video=True) == ""


def test_owner_name_is_not_alice_wake_call(monkeypatch):
    monkeypatch.setattr(talk, "_active_ai_wake_names_for_talk", lambda: {"alice"})

    assert talk._wake_call_ack_reply("George", paused_video=True) == ""
