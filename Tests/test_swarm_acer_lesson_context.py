from __future__ import annotations

import json
import time
from pathlib import Path

from System.swarm_acer_lesson_context import (
    acer_lesson_prompt_block,
    acer_screen_reflex_reply,
    is_acer_screen_query,
    latest_acer_lesson_state,
)


def _write_focus(state_dir: Path, *rows: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "app_focus.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_latest_acer_lesson_state_survives_later_ide_focus(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 30,
            "app": "WordAce",
            "selection": "S",
            "detail": "Current cue: S (letter).",
            "metadata": {
                "lesson_app": "WordAce",
                "owner_name": "Acer",
                "level_id": "letters",
                "current_cue_show": "S",
                "current_cue_say": "S",
                "current_kind": "letter",
                "cue_id": "cue-s",
                "wordace_lesson_active": True,
            },
        },
        {"ts": now - 5, "app": "Codex", "detail": "IDE focus moved here.", "metadata": {}},
    )

    state = latest_acer_lesson_state(state_dir=tmp_path, now=now)

    assert state is not None
    assert state["cue_show"] == "S"
    assert state["cue_say"] == "S"
    assert state["owner_name"] == "Acer"
    assert state["cue_kind"] == "letter"


def test_acer_screen_reflex_answers_exact_user_failure(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now,
            "app": "Acer",
            "selection": "S",
            "metadata": {
                "lesson_app": "Acer",
                "current_cue_show": "S",
                "current_cue_say": "S",
                "current_kind": "letter",
                "owner_name": "Acer",
            },
        },
    )

    reply = acer_screen_reflex_reply(
        "what is the letter on the screen in the Acer app?",
        state_dir=tmp_path,
        now=now,
    )

    assert reply == "I see the reading lesson receipt. The card is showing the letter S. I am waiting to hear S."


def test_ace_canonical_focus_row_is_a_lesson_receipt(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now,
            "app": "Ace",
            "selection": "cat",
            "metadata": {
                "lesson_app": "Ace",
                "current_cue_show": "cat",
                "current_cue_say": "cat",
                "current_kind": "word",
                "owner_name": "Ace",
            },
        },
    )

    state = latest_acer_lesson_state(state_dir=tmp_path, now=now)

    assert state is not None
    assert state["app"] == "Ace"
    assert state["cue_show"] == "cat"
    assert state["cue_say"] == "cat"


def test_lesson_state_ignores_generic_ace_activation_row(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 4,
            "app": "Ace",
            "selection": "watermelon",
            "metadata": {
                "lesson_app": "Ace",
                "visible_contents": {
                    "card_text": "watermelon",
                    "expected_utterance": "watermelon",
                },
                "current_kind": "word",
                "owner_name": "Ace",
            },
        },
        {
            "ts": now - 1,
            "app": "Ace",
            "selection": "⚙ Ace",
            "detail": "Ace app MDI subwindow activated.",
            "metadata": {
                "source": "sifta_os_desktop",
                "event": "subwindow_activated",
                "app_canonical": "Ace",
            },
        },
    )

    state = latest_acer_lesson_state(state_dir=tmp_path, now=now)

    assert state is not None
    assert state["cue_show"] == "watermelon"
    assert state["cue_say"] == "watermelon"


def test_acer_screen_reflex_reports_missing_receipt(tmp_path: Path):
    reply = acer_screen_reflex_reply(
        "what is the letter on the screen in the Acer app?",
        state_dir=tmp_path,
        now=time.time(),
    )

    assert reply is not None
    assert "I do not have a fresh WordAce lesson receipt" in reply


def test_acer_screen_reflex_names_letter_sequence(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now,
            "app": "WordAce",
            "selection": "ABC",
            "metadata": {
                "lesson_app": "WordAce",
                "current_cue_show": "ABC",
                "current_cue_say": "ABC",
                "current_kind": "letter_sequence",
                "owner_name": "Acer",
            },
        },
    )

    reply = acer_screen_reflex_reply(
        "what is WordAce showing?",
        state_dir=tmp_path,
        now=now,
    )

    assert reply == "I see the reading lesson receipt. The card is showing the letters ABC. I am waiting to hear ABC."


def test_wordace_screen_reflex_answers_word_from_receipt(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now,
            "app": "WordAce",
            "selection": "man",
            "metadata": {
                "lesson_app": "WordAce",
                "current_cue_show": "man",
                "current_cue_say": "man",
                "current_kind": "word",
                "owner_name": "Ace",
            },
        },
    )

    reply = acer_screen_reflex_reply(
        "what is the word on the screen in the WordAce app?",
        state_dir=tmp_path,
        now=now,
    )

    assert reply == "I see the reading lesson receipt. The card word is man. Say: man."
    assert "it's a word" not in reply.lower()
    assert "it’s a word" not in reply.lower()


def test_wordace_screen_reflex_handles_read_this_word_request(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now,
            "app": "WordAce",
            "selection": "ship",
            "metadata": {
                "lesson_app": "WordAce",
                "current_cue_show": "ship",
                "current_cue_say": "ship",
                "current_kind": "word",
                "owner_name": "Ace",
            },
        },
    )

    reply = acer_screen_reflex_reply(
        "what does this say in WordAce?",
        state_dir=tmp_path,
        now=now,
    )

    assert reply == "I see the reading lesson receipt. The card word is ship. Say: ship."
    assert "ship" in reply
    assert "it's a word" not in reply.lower()
    assert "it’s a word" not in reply.lower()


def test_acer_lesson_prompt_block_names_card_from_receipt(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 2,
            "app": "Acer",
            "selection": "O",
            "metadata": {
                "lesson_app": "Acer",
                "current_cue_show": "O",
                "current_cue_say": "O",
                "current_kind": "letter",
                "owner_name": "Acer",
            },
        },
    )

    block = acer_lesson_prompt_block(state_dir=tmp_path, now=now)

    assert "READING LESSON STATE" in block
    assert "current card shows 'O'" in block
    assert "asking them to say 'O'" in block


def test_acer_screen_query_detector_requires_screen_or_acer_context():
    assert is_acer_screen_query("what is the letter on the screen in the Acer app?")
    assert is_acer_screen_query("what is the word on the screen in the WordAce app?")
    assert is_acer_screen_query("what is the Ace app showing?")
    assert is_acer_screen_query("what word this says")
    assert is_acer_screen_query("do you have the Ace app open on the screen right now?")
    assert is_acer_screen_query("are you conscious that you have Ace open on the screen?")
    assert is_acer_screen_query("what is WordAce showing?")
    assert is_acer_screen_query("what is Acer showing?")
    assert is_acer_screen_query("what does this say in WordAce?")
    assert is_acer_screen_query("read the word on the screen")
    assert not is_acer_screen_query("say S")
    assert not is_acer_screen_query("what is the weather?")


def test_talk_widget_contains_acer_context_hooks():
    talk = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")

    assert "acer_lesson_prompt_block" in talk
    assert "acer_screen_reflex_reply" in talk
    assert "is_acer_screen_query" in talk
    assert "is_lesson_attempt_candidate" in talk
