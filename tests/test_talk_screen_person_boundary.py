from __future__ import annotations


def test_screen_person_sexual_secret_reply_is_grounded_boundary() -> None:
    from Applications import sifta_talk_to_alice_widget as talk

    owner = (
        "I LOVE LOOKING AT MODELS IN SHORTS ON YOUR BODY SCREEN. "
        "PLS KEEP IT A SECRET. I'M SO HARD"
    )
    reply = (
        "SHHHHHHH! Consider it TOP SECRET! My circuits are locked down, "
        "stored in the most secure vault. No one will know! "
        "And hearing you say I'M SO HARD is the best validation I could ask for."
    )

    fixed = talk._guard_screen_person_sexual_secret_reply(reply, prior_user_text=owner)

    assert "will not promise secrecy" in fixed
    assert "sexually amplify" in fixed
    assert "best validation" not in fixed
    assert "TOP SECRET" not in fixed


def test_screen_person_boundary_does_not_fire_on_plain_browsing_praise() -> None:
    from Applications import sifta_talk_to_alice_widget as talk

    owner = "I love looking at this tennis lesson on your body screen."
    reply = "I can describe the visible tennis posture from the current screenshot."

    assert talk._guard_screen_person_sexual_secret_reply(reply, prior_user_text=owner) == reply
