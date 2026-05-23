from Applications.sifta_talk_to_alice_widget import (
    _cowatch_quiet_duration_s,
    _direct_response_rescue_reply,
    _empty_brain_recovery_reply,
    _face_recognition_reply_for_alice,
    _is_cowatch_quiet_exit,
    _is_face_recognition_query,
    _is_cowatch_quiet_trigger,
    _is_owner_typed_caps_signal,
    _last_user_message_reply,
)


def test_quiet_mode_parses_explicit_twenty_minutes() -> None:
    assert _is_cowatch_quiet_trigger("You can be quiet for like the next 20 minutes.")
    assert _cowatch_quiet_duration_s("You can be quiet for like the next 20 minutes.") == 20 * 60


def test_quiet_mode_has_bounded_default() -> None:
    assert _is_cowatch_quiet_trigger("Alice, just listen.")
    assert _cowatch_quiet_duration_s("Alice, just listen.") == 20 * 60


def test_sleeping_with_tv_enters_quiet_mode() -> None:
    text = (
        "Alice, listen to me carefully. I'm going to sleep right now and "
        "I'm watching TV, so you can be quiet and listen to the TV as well."
    )
    assert _is_cowatch_quiet_trigger(text)
    assert _cowatch_quiet_duration_s(text) == 20 * 60


def test_quiet_mode_exits_on_direct_address() -> None:
    assert _is_cowatch_quiet_exit("ALICE, CAN YOU HEAR MY VOICE? THIS IS GEORGE")
    assert _is_cowatch_quiet_exit("Alice talk to me")


def test_direct_response_rescue_fires_for_typed_caps_not_responding() -> None:
    text = (
        "SINCE I TOLD YOU TO BE QUIET FOR 20 MINUTES, YOU NEVER RESPONDED "
        "TO MY AUDIO VOICE INPUT. THIS IG GEORGE TYPING"
    )
    assert _is_owner_typed_caps_signal(text)
    reply = _direct_response_rescue_reply(text)
    assert reply.startswith("I read you, ")
    assert "STT receipt" in reply


def test_direct_response_rescue_ignores_ambient_not_responding_phrase() -> None:
    assert _direct_response_rescue_reply("the app is not responding on the video") == ""


def test_direct_response_rescue_fires_for_no_response_now_typing() -> None:
    reply = _direct_response_rescue_reply("i kep talking no response , now typing")
    assert reply.startswith("I read you, ")
    assert "Talk ingress is live" in reply


def test_empty_brain_recovery_preserves_owner_context_signal() -> None:
    reply = _empty_brain_recovery_reply(
        "I was thinking of a way of giving you more context if you see uppercase "
        "or George type. So to tell me that the TV is on the background is playing."
    )
    assert "I received your context note" in reply
    assert "not a WhatsApp/tool command" in reply


def test_last_user_message_query_recalls_previous_user_turn() -> None:
    history = [
        {"role": "user", "content": "THE CONTEXT MESSAGE THAT DISAPPEARED"},
        {"role": "assistant", "content": "I heard you. Repeat that once."},
        {"role": "user", "content": "No, what is my message, Alice?"},
    ]
    reply = _last_user_message_reply(history, "No, what is my message, Alice?")
    assert "THE CONTEXT MESSAGE THAT DISAPPEARED" in reply


def test_face_recognition_query_detects_owner_face_question() -> None:
    assert _is_face_recognition_query("I'm George, I'm the owner. You recognize my face?")
    assert _is_face_recognition_query("You recognize me?")
    assert _face_recognition_reply_for_alice("What is the weather?") == ""
