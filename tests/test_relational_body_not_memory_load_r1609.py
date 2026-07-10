#!/usr/bin/env python3
"""r1609 — relational co-presence reaches cortex; memory-load stays command-only."""
from __future__ import annotations

from Applications.sifta_talk_to_alice_widget import (
    _is_explicit_body_journal_load_command,
    _is_explicit_journal_recall_request,
    _is_relational_body_co_presence_not_memory_command,
    _autonomic_prebrain_reflex,
)


GEORGE_IG_BODY = (
    "is from the instagram video i posted while coding you, "
    "your body laptop computer in the shot see attache"
)


def test_george_ig_video_is_relational_not_load_command():
    assert _is_relational_body_co_presence_not_memory_command(GEORGE_IG_BODY) is True
    assert _is_explicit_body_journal_load_command(GEORGE_IG_BODY) is False


def test_explicit_load_still_command():
    assert _is_explicit_body_journal_load_command(
        "please load any instagram links from your journal into your body"
    )
    assert not _is_relational_body_co_presence_not_memory_command(
        "please load any instagram links from your journal into your body"
    )


def test_prebrain_does_not_return_memory_loader_template():
    reply, tag = _autonomic_prebrain_reflex(GEORGE_IG_BODY, write_receipt=False)
    # Empty = fall through to cortex (AGI conversation). Never the loader template.
    assert "Loaded from my Alice Journal" not in (reply or "")
    assert "alice_body_loaded_memories" not in (reply or "")
    assert tag != "body_journal_load_any_site_r1508"
    assert tag != "body_journal_load_reflex_r1508"
    # Prefer full fall-through so cortex thinks
    assert reply == "" or "Loaded from" not in reply


def test_explicit_look_in_diary_still_can_fire():
    # r1610 split: looking in the journal is recall, not a body/link load.
    text = "look in your alice journal for last night"
    assert _is_explicit_journal_recall_request(text)
    assert not _is_explicit_body_journal_load_command(text)
