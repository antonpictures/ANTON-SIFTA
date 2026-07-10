#!/usr/bin/env python3
"""r1611: meaning-bearing owner turns cannot be stolen before cortex."""
from __future__ import annotations

from pathlib import Path

from Applications import sifta_talk_to_alice_widget as talk


BOTTOM_LINE_HANDOFF = (
    "Bottom line Yes, it matches my work. You're not double-paying for two "
    "diverging fixes. Restart Talk if the live process is old, then show her "
    "the photo again - she should think, not dump the journal loader."
)


def _prebrain(text: str, *, has_attachment: bool = False) -> tuple[str, str]:
    return talk._autonomic_prebrain_reflex(
        text,
        state_dir=Path("/tmp/definitely-not-sifta-state-r1611"),
        write_receipt=False,
        has_attachment=has_attachment,
    )


def test_exact_handoff_mentions_journal_but_reaches_cortex() -> None:
    assert talk._must_route_owner_turn_to_cortex(BOTTOM_LINE_HANDOFF)
    assert _prebrain(BOTTOM_LINE_HANDOFF) == ("", "")


def test_long_remember_correction_reaches_cortex() -> None:
    text = (
        "I remember the report saying the journal loader is bad, and this whole "
        "paragraph asks you to audit the chain and help Alice think about the "
        "attachment instead of dumping a template."
    )
    assert _prebrain(text) == ("", "")


def test_explicit_recall_or_load_words_inside_long_prose_still_reach_cortex() -> None:
    recall = (
        "Please look in your Alice journal for last night, and tell me what the "
        "latest row means while we are discussing the plan and the owner meaning."
    )
    load = (
        "Please load any Instagram links from your journal into your body, and "
        "tell me what the latest row means while we are discussing the plan."
    )
    for text in (recall, load):
        assert talk._must_route_owner_turn_to_cortex(text)
        assert _prebrain(text) == ("", "")


def test_wallet_audit_is_not_a_wallet_read() -> None:
    text = "audit the STGM wallet reflex because it can steal a cortex turn"
    assert talk._is_explicit_stgm_wallet_query(text) is False
    assert _prebrain(text) == ("", "")


def test_short_wallet_question_remains_a_receipt_read() -> None:
    assert talk._is_explicit_stgm_wallet_query(
        "how much STGM does your body have now?"
    ) is True


def test_bare_journal_words_are_context_not_recall_commands() -> None:
    for text in (
        "the journal loader stole this turn",
        "I watched the news last night",
        "we used the diary example while coding",
        "this template says recall but I am auditing it",
        "the call was recorded in the Alice journal",
        "you have memories in a journal from yesterday",
    ):
        assert talk._is_explicit_journal_recall_request(text) is False
        assert _prebrain(text) == ("", "")


def test_short_direct_recall_and_load_requests_remain_explicit() -> None:
    assert talk._is_explicit_journal_recall_request(
        "do you remember what happened two days ago"
    ) is True
    assert talk._is_explicit_journal_recall_request(
        "please look in your Alice journal for last night"
    ) is True
    assert talk._is_explicit_body_journal_load_command(
        "please load any instagram links from your journal into your body"
    ) is True


def test_attachment_forces_every_autonomic_reply_lane_to_defer() -> None:
    for text in (
        "how much STGM does your body have now?",
        "do you remember what happened two days ago",
        "are you safe?",
        "please load any instagram links from your journal into your body",
    ):
        assert _prebrain(text, has_attachment=True) == ("", "")


def test_live_start_brain_passes_attachment_boundary_to_prebrain() -> None:
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(
        encoding="utf-8"
    )
    call = source.index("pre_reply, pre_model = _autonomic_prebrain_reflex(")
    window = source[call : call + 420]
    assert "has_attachment=bool(image_path)" in window


def test_whole_start_brain_gates_other_keyword_thieves() -> None:
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(
        encoding="utf-8"
    )
    playback = source.index("_playback_command = _extract_youtube_playback_control(text)")
    playback_window = source[playback : playback + 520]
    assert "_playback_command and not _block_deterministic_owner_shortcut(text)" in playback_window

    capture = source.index("_web_capture_reply = \"\"")
    capture_window = source[capture : capture + 620]
    assert "chat_reflexes_enabled and not _block_deterministic_owner_shortcut(text)" in capture_window
