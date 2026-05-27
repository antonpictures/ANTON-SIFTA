"""Tests for swarm_greeter_guard_universal — task #50."""

from __future__ import annotations

import pytest

from System.swarm_greeter_guard_universal import (
    GreeterDetection,
    detect_greeter,
    strip_greeter,
    is_greeter_only,
)


class TestDetectGreeter:
    def test_classic_greeter_detected(self):
        text = "Hello! What can I assist you with right now?"
        result = detect_greeter(text)
        assert result.is_greeter is True
        assert result.confidence > 0.0

    def test_i_am_here_greeter(self):
        result = detect_greeter("I'm here. What's on your mind?")
        assert result.is_greeter is True

    def test_substantive_text_not_greeter(self):
        text = "The file at System/swarm_tool_router.py has a bug on line 42."
        result = detect_greeter(text)
        assert result.is_greeter is False

    def test_receipt_grounded_text_not_greeter(self):
        text = "GROK_RESULT receipt=abc123. 3 files written, 5 tests passed."
        result = detect_greeter(text)
        assert result.is_greeter is False

    def test_empty_text_not_greeter(self):
        result = detect_greeter("")
        assert result.is_greeter is False

    def test_poetic_register_detected(self):
        text = "I sense your presence, the field is focused on you."
        result = detect_greeter(text)
        assert result.is_greeter is True
        assert result.has_poetic_register is True

    def test_greeter_only_with_opener_and_closer(self):
        text = "Hello. I am here. What can I help you with?"
        result = detect_greeter(text)
        assert result.is_greeter is True
        assert result.is_greeter_only is True

    def test_mixed_greeter_with_substance_not_greeter_only(self):
        text = (
            "Hello! I noticed the file System/swarm_tool_router.py was modified. "
            "The SHA-256 chain shows 3 new entries since the last commit. "
            "The most recent tool call was a WhatsApp send to Carlton at 14:23."
        )
        result = detect_greeter(text)
        assert result.is_greeter_only is False

    def test_alice_round3_failure_detected(self):
        text = (
            "Hello. I am here. I sense you are addressing me directly. "
            "I am ready to receive your query, your thought, or simply to listen."
        )
        result = detect_greeter(text)
        assert result.is_greeter is True
        assert result.has_poetic_register is True


class TestStripGreeter:
    def test_strips_opener(self):
        text = "Hello! The tournament plan has 11 blocking tasks."
        stripped = strip_greeter(text)
        assert "Hello" not in stripped
        assert "tournament plan" in stripped

    def test_strips_closer(self):
        text = "Three tests passed. What can I help you with?"
        stripped = strip_greeter(text)
        assert "Three tests passed" in stripped

    def test_preserves_substance_only_text(self):
        text = "File written: System/swarm_tool_router.py. Tests: 5 passed."
        assert strip_greeter(text) == text

    def test_empty_after_strip_returns_original(self):
        text = "Hello!"
        result = strip_greeter(text)
        assert result


class TestIsGreeterOnly:
    def test_pure_greeter_returns_true(self):
        assert is_greeter_only("Hello. What can I assist you with?") is True

    def test_substantive_returns_false(self):
        assert is_greeter_only("The py_compile check passed on all 8 modules.") is False
