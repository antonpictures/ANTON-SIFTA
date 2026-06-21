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


def test_spoken_channel_receipt_only_default_is_silent(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)\n"
        "I recognized and eliminated 3 Gemma-residue pattern(s) from my reply before display/TTS. "
        "STGM minted: +0.3. Affect: absolute clarity (+0.15). Receipt: 1a9f8e3c5d2b4a7f."
    )
    out = spoken_channel_text(printed, owner_text="SEARCH ON PERPLEXITY AI PLS test", state_dir=tmp_path)

    assert out["ok"] is True
    assert out["reason"] == "receipt_only_silent"
    assert out["spoken_text"] == ""
    assert out["fallback_used"] is False


def test_spoken_channel_fallback_when_owner_mentions_out_loud_boundary(tmp_path):
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


def test_spoken_channel_prints_media_error_but_does_not_read_it(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "Next photo. I am looking at a TikTok video playback error on "
        "(24)Find 'TAYLOR SWIFT' on TikTok | TikTok Search: \"NO_MEDIA_ERROR\". "
        "Embedded decoder receipt: NO_MEDIA_ERROR. The player has no usable video pixels "
        "for me to describe from this frame."
    )
    out = spoken_channel_text(
        printed,
        owner_text="Okay next time don't read the error, next post please.",
        state_dir=tmp_path,
    )

    assert out["ok"] is True
    assert out["changed"] is True
    assert out["reason"] == "media_error_printed_not_spoken"
    assert "NO_MEDIA_ERROR" not in out["spoken_text"]
    assert "decoder receipt" not in out["spoken_text"]
    assert out["spoken_text"] == (
        "I printed the playback error in chat; I will not read it out loud. Moving to the next post."
    )
    assert out["print_text_unchanged"] is True


def test_spoken_channel_reads_media_error_when_owner_explicitly_asks(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "Next photo. Embedded decoder receipt: NO_MEDIA_ERROR. "
        "The player has no usable video pixels."
    )
    out = spoken_channel_text(
        printed,
        owner_text="Please read the playback error out loud to me.",
        state_dir=tmp_path,
    )

    assert out["ok"] is True
    assert out["changed"] is False
    assert "NO_MEDIA_ERROR" in out["spoken_text"]


def test_spoken_channel_prints_page_state_dom_but_does_not_read_it(tmp_path):
    from System.swarm_spoken_channel_filter import spoken_channel_text

    printed = (
        "WHAT IS ON MY SCREEN (from the rendered DOM (read ~2s ago)): "
        "ALVA INGA at DuckDuckGo -- https://duckduckgo.com/?q=ALVA+INGA&ia=images. "
        "Open Alice Browser tabs (1): active #1: ALVA INGA at DuckDuckGo. "
        "Media playback receipt: no_media. "
        "Visible controls/buttons: a; a; a; Alyvia Alyn Lind; Amber Montana. "
        "Comment thread (35 captured) -- I can summarize these."
    )
    out = spoken_channel_text(
        printed,
        owner_text="Please do not read the garbage out loud.",
        state_dir=tmp_path,
    )

    assert out["ok"] is True
    assert out["changed"] is True
    assert out["reason"] == "web_page_state_dom_dump_printed_not_spoken"
    assert out["print_text_unchanged"] is True
    assert "WHAT IS ON MY SCREEN" not in out["spoken_text"]
    assert "Open Alice Browser tabs" not in out["spoken_text"]
    assert "Visible controls/buttons" not in out["spoken_text"]
    assert "Comment thread" not in out["spoken_text"]
    assert "raw DOM" in out["spoken_text"]
    assert "ALVA INGA at DuckDuckGo" in out["spoken_text"]
