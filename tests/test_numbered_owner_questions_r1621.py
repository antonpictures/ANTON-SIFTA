"""r1621-03 — numbered owner questions scaffold."""
from __future__ import annotations

from System.swarm_numbered_owner_questions import (
    extract_numbered_questions,
    is_numbered_owner_questions_turn,
    numbered_questions_teaching_block,
)


def test_extracts_three_questions():
    text = (
        "1. what are you\n"
        "2. where do you run\n"
        "3. what weight file name\n"
    )
    qs = extract_numbered_questions(text)
    assert [q["n"] for q in qs] == [1, 2, 3]
    assert is_numbered_owner_questions_turn(text)


def test_teaching_block_lists_each_number():
    text = "1) Who is George?\n2) What is SIFTA?\n3) Open browser?"
    block = numbered_questions_teaching_block(text)
    assert "NUMBERED OWNER QUESTIONS" in block
    assert "1." in block and "2." in block and "3." in block
    assert "Do NOT pivot" in block


def test_single_number_not_scaffolded():
    assert not is_numbered_owner_questions_turn("1. only one question here")
    assert numbered_questions_teaching_block("1. only one") == ""
