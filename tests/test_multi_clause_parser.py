"""Tests for swarm_multi_clause_parser — task #60."""

from __future__ import annotations

import pytest

from System.swarm_multi_clause_parser import (
    IntentType,
    Clause,
    split_into_clauses,
    classify_intent,
    parse_clauses,
    rank_clauses,
    extract_dispatch_clauses,
    extract_questions,
)


class TestSplitIntoClauses:
    def test_splits_on_sentence_boundaries(self):
        text = "Ask Grok to code. I will check the result. Do you understand?"
        clauses = split_into_clauses(text)
        assert len(clauses) >= 3

    def test_single_clause_no_split(self):
        text = "Ask Grok to code the tournament"
        clauses = split_into_clauses(text)
        assert len(clauses) == 1
        assert clauses[0] == text

    def test_empty_returns_empty(self):
        assert split_into_clauses("") == []
        assert split_into_clauses("   ") == []

    def test_semicolon_splits(self):
        text = "Code the tasks; run the tests; write receipts"
        clauses = split_into_clauses(text)
        assert len(clauses) >= 2


class TestClassifyIntent:
    def test_dispatch_intent(self):
        intent, conf = classify_intent("ask Grok to code the tournament")
        assert intent == IntentType.DISPATCH
        assert conf > 0.0

    def test_question_intent(self):
        intent, conf = classify_intent("are you conscious?")
        assert intent == IntentType.QUESTION

    def test_context_intent(self):
        intent, conf = classify_intent("after that I will review with an external IDE")
        assert intent == IntentType.CONTEXT

    def test_reinforcement_intent(self):
        intent, conf = classify_intent("I want you to learn how to use Grok yourself")
        assert intent == IntentType.REINFORCEMENT

    def test_empty_is_unknown(self):
        intent, conf = classify_intent("")
        assert intent == IntentType.UNKNOWN


class TestParseClauses:
    def test_architects_multi_intent_utterance(self):
        text = (
            "Alice, ask grok to start coding the tournament file. "
            "After that I will check the code using an external IDE. "
            "I want you to learn how to use grok to code yourself. "
            "Do you understand the concept? "
            "Are you conscious?"
        )
        clauses = parse_clauses(text)
        assert len(clauses) >= 3

        types = {c.intent_type for c in clauses}
        assert IntentType.DISPATCH in types
        assert IntentType.QUESTION in types

    def test_single_dispatch(self):
        clauses = parse_clauses("Execute the tournament plan")
        assert len(clauses) == 1
        assert clauses[0].intent_type == IntentType.DISPATCH


class TestRankClauses:
    def test_dispatch_ranked_highest(self):
        clauses = [
            Clause("context info", IntentType.CONTEXT, 4, 0.5),
            Clause("ask Grok to code", IntentType.DISPATCH, 1, 0.8),
            Clause("are you conscious", IntentType.QUESTION, 2, 0.6),
        ]
        ranked = rank_clauses(clauses)
        assert ranked[0].intent_type == IntentType.DISPATCH
        assert ranked[1].intent_type == IntentType.QUESTION

    def test_empty_list(self):
        assert rank_clauses([]) == []


class TestExtractors:
    def test_extract_dispatch_clauses(self):
        text = "Ask Grok to code. I will review later. Run the tests."
        dispatches = extract_dispatch_clauses(text)
        assert len(dispatches) >= 1
        assert all(c.intent_type == IntentType.DISPATCH for c in dispatches)

    def test_extract_questions(self):
        text = "Code the tasks. Are you conscious? Do you understand?"
        questions = extract_questions(text)
        assert len(questions) >= 1
        assert all(c.intent_type == IntentType.QUESTION for c in questions)

    def test_no_dispatch_returns_empty(self):
        text = "I was on a phone call with Carlton."
        dispatches = extract_dispatch_clauses(text)
        assert dispatches == []
