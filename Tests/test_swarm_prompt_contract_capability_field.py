"""Prompt contract exposes Alice's unified capability field."""

from __future__ import annotations


def test_tool_affordances_include_capability_field_for_skill_questions():
    from System.swarm_prompt_contract import tool_affordances_for_turn

    text = tool_affordances_for_turn("what skills and Hermes capabilities can you use?")

    assert "YOUR CAPABILITIES — UNIFIED LIVING FIELD" in text
    assert "CAPABILITY FIELD FOR THIS TURN" in text
    assert "capability_field_status" in text
    assert "skill_pull" in text


def test_tool_affordances_include_app_habit_field_when_app_is_named():
    from System.swarm_prompt_contract import tool_affordances_for_turn

    text = tool_affordances_for_turn("WordAce should teach Ace to read sentences")

    assert "APP HABIT FIELD FOR CURRENT APP" in text
    assert "WordAce" in text
    assert "wordace_reading_coach" in text
