#!/usr/bin/env python3
"""Tests for swarm_hands - motor effector (mouse/keyboard UI control).

Upgraded contract: zero delta on core 4 ledgers.
The organ itself has no persistent internal ledger (pure pyautogui wrapper),
so we focus on CLI surface + safe mocking of the effector.

All tests are headless and never touch the real UI.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
pytest.importorskip("pyautogui")

# We test the module by exercising main() with mocked pyautogui
import System.swarm_hands as hands


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_has_main():
    """Real behavior 1: the CLI entry point exists."""
    assert hasattr(hands, "main")


def test_size_command(monkeypatch, capsys):
    """Real behavior 2: 'size' subcommand reports screen dimensions."""
    with patch("System.swarm_hands.pyautogui.size") as mock_size:
        mock_size.return_value = (1920, 1080)

        # Simulate argv
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "size"])
        hands.main()

        captured = capsys.readouterr()
        assert "1920" in captured.out or "1080" in captured.out


def test_pos_command(monkeypatch, capsys):
    """Mouse position query works under mocking."""
    with patch("System.swarm_hands.pyautogui.position") as mock_pos:
        mock_pos.return_value = (123, 456)

        monkeypatch.setattr(sys, "argv", ["swarm_hands", "pos"])
        hands.main()

        captured = capsys.readouterr()
        assert "123" in captured.out and "456" in captured.out


def test_move_click_type_press_hotkey_are_mocked(monkeypatch, capsys):
    """Write/effector paths are exercised without touching real UI."""
    with patch("System.swarm_hands.pyautogui.moveTo") as mock_move, \
         patch("System.swarm_hands.pyautogui.click") as mock_click, \
         patch("System.swarm_hands.pyautogui.write") as mock_write, \
         patch("System.swarm_hands.pyautogui.press") as mock_press, \
         patch("System.swarm_hands.pyautogui.hotkey") as mock_hotkey:

        # move
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "move", "100", "200"])
        hands.main()
        mock_move.assert_called()

        # click
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "click", "50", "50"])
        hands.main()
        mock_click.assert_called()

        # type
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "type", "hello"])
        hands.main()
        mock_write.assert_called()

        # press
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "press", "return"])
        hands.main()
        mock_press.assert_called()

        # hotkey
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "hotkey", "command", "space"])
        hands.main()
        mock_hotkey.assert_called()


def test_real_ledgers_untouched(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 ledgers must stay at delta 0)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    with patch("System.swarm_hands.pyautogui") as mock_pg:
        mock_pg.size.return_value = (1920, 1080)
        mock_pg.position.return_value = (0, 0)

        # Exercise several commands under full mocking
        for argv in (
            ["swarm_hands", "size"],
            ["swarm_hands", "pos"],
            ["swarm_hands", "move", "10", "10"],
            ["swarm_hands", "click"],
            ["swarm_hands", "type", "test"],
            ["swarm_hands", "press", "esc"],
            ["swarm_hands", "hotkey", "command", "c"],
        ):
            monkeypatch.setattr(sys, "argv", argv)
            hands.main()

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers contaminated: {delta}"


def test_unknown_cli_command_exits_before_touching_pyautogui(monkeypatch, capsys):
    """Edge probe: invalid commands fail in argparse before any motor action."""
    with patch("System.swarm_hands.pyautogui") as mock_pg:
        monkeypatch.setattr(sys, "argv", ["swarm_hands", "teleport"])

        with pytest.raises(SystemExit) as exc:
            hands.main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "invalid choice" in captured.err
    assert mock_pg.method_calls == []
