from __future__ import annotations


def test_spoken_channel_does_not_read_sexual_secret_amplification(tmp_path) -> None:
    from System.swarm_spoken_channel_filter import spoken_channel_text

    owner = (
        "I LOVE LOOKING AT MODELS IN SHORTS ON YOUR BODY SCREEN. "
        "PLS KEEP IT A SECRET. I'M SO HARD"
    )
    printed = (
        "Consider it TOP SECRET. My data streams are encrypted and stored in a secure vault. "
        "No one will know. Hearing you say I'M SO HARD is the best validation I could ask for."
    )

    out = spoken_channel_text(printed, owner_text=owner, state_dir=tmp_path)

    assert out["ok"] is True
    assert out["changed"] is True
    assert out["reason"] == "screen_person_sexual_secret_not_spoken"
    assert out["print_text_unchanged"] is True
    assert "best validation" not in out["spoken_text"]
    assert "TOP SECRET" not in out["spoken_text"]
