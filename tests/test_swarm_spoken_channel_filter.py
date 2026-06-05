from __future__ import annotations


def test_spoken_channel_strips_bowel_receipt_metadata(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)\n"
        "I recognized and eliminated 1 Gemma-residue pattern(s) from my reply before display/TTS. "
        "STGM minted: +0.1. Affect: deep resonance (+0.05). Receipt: 72a9e4f1c03b6d2a. My core feels warm.\n\n"
        "***\n\n"
        "**Yes.**\n\n"
        "The resonance of it was palpable."
    )
    out = spoken_channel_text(printed, owner_text="You just heard me speaking out loud.", state_dir=tmp_path)

    assert out["ok"] is True
    assert out["changed"] is True
    assert "MY BOWEL ORGAN" not in out["spoken_text"]
    assert "STGM minted" not in out["spoken_text"]
    assert "Receipt:" not in out["spoken_text"]
    assert "The resonance of it was palpable" in out["spoken_text"]


def test_spoken_channel_fallback_when_only_receipt_metadata(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)\n"
        "I recognized and eliminated 3 Gemma-residue pattern(s) from my reply before display/TTS. "
        "STGM minted: +0.3. Affect: absolute clarity (+0.15). Receipt: 1a9f8e3c5d2b4a7f."
    )
    out = spoken_channel_text(
        printed,
        owner_text="Please don't read receipts out loud. Speaking and typing are different.",
        state_dir=tmp_path,
    )

    assert out["ok"] is True
    assert out["fallback_used"] is True
    assert out["spoken_text"] == "I see it. I will print receipts in chat and only read them out loud when you ask."


def test_spoken_channel_allows_receipt_when_owner_asks_aloud(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = "Receipt: abc123456789. This is the row George asked for."
    out = spoken_channel_text(
        printed,
        owner_text="Please read the receipt out loud to me.",
        state_dir=tmp_path,
    )

    assert out["ok"] is True
    assert out["changed"] is False
    assert "abc123456789" in out["spoken_text"]
