#!/usr/bin/env python3
"""Smoke tests for Stigmergic Nanobot Tic-Tac-Toe."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

mod = importlib.import_module("Applications.sifta_nanobot_tictactoe")
Nanobot = mod.Nanobot
StigmergicEnvironment = mod.StigmergicEnvironment
StigmergicNanobotTicTacToeWidget = mod.StigmergicNanobotTicTacToeWidget


class TestNanobot:
    def test_sense_finds_empty_cells(self):
        board = [None, "X", None, "O", None, None, None, None, None]
        bot = Nanobot("X", None)
        moves = bot.sense_environment(board)
        assert 0 in moves
        assert 1 not in moves
        assert 3 not in moves

    def test_act_deposits_species(self):
        board = [None] * 9
        bot = Nanobot("O", None)
        target = bot.act(board)
        assert target is not None
        assert board[target] == "O"

    def test_energy_depletes(self):
        board = [None] * 9
        bot = Nanobot("X", None)
        bot.act(board)
        assert bot.energy == 85

    def test_bot_dies_at_zero_energy(self):
        bot = Nanobot("X", None)
        bot.energy = 10
        board = [None] * 9
        bot.act(board)
        assert not bot.is_alive

    def test_dead_bot_cannot_act(self):
        bot = Nanobot("X", None)
        bot.is_alive = False
        board = [None] * 9
        result = bot.act(board)
        assert result is None


class TestStigmergicEnvironment:
    def test_deploy_swarm(self):
        env = StigmergicEnvironment(swarm_size=3)
        env.deploy_swarm()
        assert len(env.swarm) == 6
        x_bots = [b for b in env.swarm if b.species == "X"]
        o_bots = [b for b in env.swarm if b.species == "O"]
        assert len(x_bots) == 3
        assert len(o_bots) == 3

    def test_check_win_row(self):
        env = StigmergicEnvironment()
        env.board = ["X", "X", "X", None, None, None, None, None, None]
        assert env.check_win() == "X"
        assert env.winning_line == (0, 1, 2)

    def test_check_win_col(self):
        env = StigmergicEnvironment()
        env.board = ["O", None, None, "O", None, None, "O", None, None]
        assert env.check_win() == "O"

    def test_check_win_diag(self):
        env = StigmergicEnvironment()
        env.board = ["X", None, None, None, "X", None, None, None, "X"]
        assert env.check_win() == "X"
        assert env.winning_line == (0, 4, 8)

    def test_no_win(self):
        env = StigmergicEnvironment()
        env.board = ["X", "O", None, None, None, None, None, None, None]
        assert env.check_win() is None

    def test_draw_detection(self):
        env = StigmergicEnvironment()
        env.board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        assert env.is_draw()

    def test_reset_clears_state(self):
        env = StigmergicEnvironment(swarm_size=2)
        env.deploy_swarm()
        env.board[0] = "X"
        env.winner = "X"
        env.game_over = True
        env.reset()
        assert all(c is None for c in env.board)
        assert env.winner is None
        assert not env.game_over
        assert len(env.swarm) == 4

    def test_step_makes_progress(self):
        env = StigmergicEnvironment(swarm_size=1)
        env.deploy_swarm()
        result = env.step()
        assert result is not None
        filled = sum(1 for c in env.board if c is not None)
        assert filled == 1

    def test_game_terminates(self):
        env = StigmergicEnvironment(swarm_size=5, seed=7)
        env.deploy_swarm()
        steps = 0
        while not env.game_over and steps < 200:
            env.step()
            steps += 1
        assert env.game_over

    def test_world_model_blocks_immediate_alice_threat(self):
        env = StigmergicEnvironment(swarm_size=1, seed=1)
        env.deploy_swarm()
        env.board = ["X", "X", None, None, "O", None, None, None, None]
        bot = next(b for b in env.swarm if b.species == "O")
        assert env.select_move_for(bot) == 2

    def test_no_double_spending_in_alice_vs_nanobot_self_play(self):
        env = StigmergicEnvironment(swarm_size=2, seed=5)
        env.deploy_swarm()
        receipt = env.run_alice_vs_nanobot_game()

        cells = [row["cell"] for row in env.move_log]
        assert len(cells) == len(set(cells))
        assert receipt["double_spend_attempts"] == 0
        assert receipt["unique_claims"] == len(env.move_log)
        assert receipt["alice_moves"]
        assert receipt["nanobot_moves"]
        assert all(env.board[cell] in {"X", "O"} for cell in cells)

    def test_illegal_duplicate_cell_claim_is_rejected(self):
        env = StigmergicEnvironment(swarm_size=1, seed=2)
        env.deploy_swarm()
        x_bot = next(b for b in env.swarm if b.species == "X")
        o_bot = next(b for b in env.swarm if b.species == "O")

        assert env.deposit_marker(x_bot, 4) == 4
        assert env.deposit_marker(o_bot, 4) is None
        assert env.board[4] == "X"
        assert len(env.double_spend_attempts) == 1
        assert env.double_spend_attempts[0]["reason"] == "occupied_or_invalid"


class TestWidget:
    def test_widget_initializes_headless_and_reuses_initialized_singleton(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        widget = StigmergicNanobotTicTacToeWidget()
        try:
            assert widget.windowTitle() == "Stigmergic Nanobot Tic-Tac-Toe"
            assert hasattr(widget, "env")
            assert id(widget) in StigmergicNanobotTicTacToeWidget._initialized_instance_ids
            widget2 = StigmergicNanobotTicTacToeWidget()
            assert widget2 is widget
        finally:
            widget.close()
            app.processEvents()


class TestManifest:
    def test_manifest_entry_exists(self):
        manifest_path = _REPO / "Applications" / "apps_manifest.json"
        with manifest_path.open() as f:
            manifest = json.load(f)
        assert "Stigmergic Nanobot Tic-Tac-Toe" in manifest
        entry = manifest["Stigmergic Nanobot Tic-Tac-Toe"]
        assert entry["widget_class"] == "StigmergicNanobotTicTacToeWidget"
        assert entry["entry_point"] == "Applications/sifta_nanobot_tictactoe.py"

    def test_entry_point_exists(self):
        path = _REPO / "Applications" / "sifta_nanobot_tictactoe.py"
        assert path.exists()
