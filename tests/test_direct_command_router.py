"""Tests for swarm_direct_command_router — task #58."""

from __future__ import annotations

import pytest

from System.swarm_direct_command_router import (
    DirectCommand,
    classify_as_direct_command,
    extract_keystroke,
)


class TestClassifyAsDirectCommand:
    def test_press_enter(self):
        cmd = classify_as_direct_command("press enter")
        assert cmd.is_direct is True
        assert cmd.command_type == "keystroke"
        assert cmd.key_or_text == "\n"

    def test_now_press_enter(self):
        cmd = classify_as_direct_command("Now press enter")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\n"

    def test_hit_escape(self):
        cmd = classify_as_direct_command("hit escape")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\x1b"

    def test_press_tab(self):
        cmd = classify_as_direct_command("press tab")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\t"

    def test_ctrl_c(self):
        cmd = classify_as_direct_command("press ctrl-c")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\x03"

    def test_ctrl_standalone(self):
        cmd = classify_as_direct_command("ctrl-d")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\x04"

    def test_type_quoted_text(self):
        cmd = classify_as_direct_command('type "hello world"')
        assert cmd.is_direct is True
        assert cmd.command_type == "type_text"
        assert cmd.key_or_text == "hello world"

    def test_type_backtick_command(self):
        cmd = classify_as_direct_command("type `ls -la`")
        assert cmd.is_direct is True
        assert cmd.command_type == "type_command"
        assert "ls -la" in cmd.key_or_text

    def test_normal_text_not_direct(self):
        cmd = classify_as_direct_command(
            "Alice, ask Grok to code the tournament"
        )
        assert cmd.is_direct is False

    def test_empty_text_not_direct(self):
        cmd = classify_as_direct_command("")
        assert cmd.is_direct is False

    def test_press_up_arrow(self):
        cmd = classify_as_direct_command("press up")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\x1b[A"

    def test_press_down_arrow(self):
        cmd = classify_as_direct_command("press down")
        assert cmd.is_direct is True
        assert cmd.key_or_text == "\x1b[B"


class TestExtractKeystroke:
    def test_returns_keystroke_for_command(self):
        assert extract_keystroke("press enter") == "\n"
        assert extract_keystroke("hit tab") == "\t"

    def test_returns_none_for_normal_text(self):
        assert extract_keystroke("how are you") is None

    def test_returns_none_for_empty(self):
        assert extract_keystroke("") is None
