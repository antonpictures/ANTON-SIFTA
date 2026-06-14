#!/usr/bin/env python3
"""Stigmergic Nanobot Tic-Tac-Toe — two nanobot swarms compete via pheromone traces.

Nanobots do not follow a central script. Each bot senses the board plus the
pheromone/refractory field, then moves toward the strongest legal gradient.
Alice plays the X swarm; the opposing nanobot swarm plays O. The environment is
the only shared memory and rejects any duplicate claim on an occupied cell.

PyQt6 embedded widget inside SIFTA OS body (§7.5). Singleton (§7.6.2).
"""

from __future__ import annotations

"""SIFTA Nanobot Tictactoe — stigmergic organ for Alice body."""

import json
import math
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Stigmergic Nanobot Tic-Tac-Toe"
APP_ID = "sifta_nanobot_tictactoe"
TRUTH_LABEL = "STIGMERGIC_NANOBOT_TICTACTOE_V1"

_BG = QColor(8, 10, 18)
_PANEL = QColor(16, 19, 32)
_PANEL_BORDER = QColor(55, 65, 100)
_TEXT = QColor(210, 220, 240)
_DIM = QColor(130, 140, 170)
_ACCENT = QColor(75, 235, 190)
_X_COLOR = QColor(255, 82, 82)
_O_COLOR = QColor(72, 160, 255)
_GRID_LINE = QColor(55, 65, 100)
_CELL_BG = QColor(18, 22, 38)
_CELL_HOVER = QColor(28, 34, 55)
_WIN_GLOW = QColor(255, 220, 80, 120)
_ENERGY_BG = QColor(30, 35, 55)
_ENERGY_FILL_X = QColor(255, 82, 82, 180)
_ENERGY_FILL_O = QColor(72, 160, 255, 180)
_DEAD_COLOR = QColor(80, 80, 80, 120)


def _publish_app_focus(detail: str) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, app_id=APP_ID)
    except Exception:
        pass


def _write_receipt(event: str, payload: dict) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "app": APP_TITLE,
            "event": event,
            "truth_label": TRUTH_LABEL,
            **payload,
        }
        with (_STATE / "nanobot_tictactoe_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core stigmergic engine
# ---------------------------------------------------------------------------

@dataclass
class CellPheromone:
    """Local sematectonic trace for one board cell."""

    x: float = 0.0
    o: float = 0.0
    refractory: float = 0.0
    claim_receipt: str = ""

    def value_for(self, species: str) -> float:
        return self.x if species == "X" else self.o

    def opponent_value_for(self, species: str) -> float:
        return self.o if species == "X" else self.x

class Nanobot:
    """
    A nanobot agent that operates via stigmergy.
    It does not follow a central script, but reacts to 'pheromones'
    (traces) left in the environment (the board).
    """
    def __init__(self, species: str, color: QColor, *, agent_name: str = ""):
        self.species = species  # 'X' or 'O'
        self.color = color
        self.agent_name = agent_name or ("Alice-X" if species == "X" else "Nano-O")
        self.bot_id = f"{self.agent_name}:{uuid.uuid4().hex[:8]}"
        self.energy = 100
        self.is_alive = True
        self.last_move: Optional[int] = None

    def sense_environment(self, board: list) -> list[int]:
        """Scans the local environment for pheromone density."""
        return [i for i, cell in enumerate(board) if cell is None]

    def act(self, board: list, environment: Optional["StigmergicEnvironment"] = None) -> Optional[int]:
        """The 'work' that consumes life force."""
        if not self.is_alive:
            return None

        moves = self.sense_environment(board)
        if moves:
            if environment is None:
                target = self._fallback_stigmergic_choice(moves)
                board[target] = self.species
                self._spend_energy(15)
                self.last_move = target
                return target
            return environment.deposit_marker(self, environment.select_move_for(self, moves))

        self._spend_energy(5)
        return None

    def _fallback_stigmergic_choice(self, moves: list[int]) -> int:
        """Small board prior for legacy direct tests without an environment."""
        priority = {4: 3.0, 0: 2.0, 2: 2.0, 6: 2.0, 8: 2.0}
        return max(moves, key=lambda idx: (priority.get(idx, 1.0), -idx))

    def _spend_energy(self, amount: int) -> None:
        self.energy -= amount
        if self.energy <= 0:
            self.is_alive = False


class StigmergicEnvironment:
    """
    The 'Grid' where pheromones (moves) are deposited.
    The environment itself is the only shared memory.
    """
    WIN_CONDITIONS = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
        (0, 4, 8), (2, 4, 6),              # diags
    ]

    def __init__(self, swarm_size: int = 5, *, seed: Optional[int] = None):
        self.board: list[Optional[str]] = [None] * 9
        self.pheromones: list[CellPheromone] = [CellPheromone() for _ in range(9)]
        self.swarm: list[Nanobot] = []
        self.swarm_size = swarm_size
        self.move_log: list[dict] = []
        self.claimed_cells: dict[int, str] = {}
        self.double_spend_attempts: list[dict] = []
        self.players = {"X": "Alice", "O": "Nanobot"}
        self.turn_species = "X"
        self.winner: Optional[str] = None
        self.winning_line: Optional[tuple[int, int, int]] = None
        self.turn_index = 0
        self.game_over = False
        self.rng = random.Random(seed)

    def deploy_swarm(self) -> None:
        self.swarm.clear()
        for _ in range(self.swarm_size):
            self.swarm.append(Nanobot("X", _X_COLOR, agent_name="Alice"))
            self.swarm.append(Nanobot("O", _O_COLOR, agent_name="Nanobot"))

    def empty_cells(self) -> list[int]:
        return [i for i, cell in enumerate(self.board) if cell is None]

    def _opponent(self, species: str) -> str:
        return "O" if species == "X" else "X"

    def _lines_for_cell(self, idx: int) -> list[tuple[int, int, int]]:
        return [line for line in self.WIN_CONDITIONS if idx in line]

    def _line_pressure(self, species: str, idx: int) -> float:
        opponent = self._opponent(species)
        score = 0.0
        for line in self._lines_for_cell(idx):
            values = [self.board[i] for i in line]
            own = values.count(species)
            opp = values.count(opponent)
            empty = values.count(None)
            if opp == 0:
                score += (own + 1) ** 2
            if own == 0 and opp == 2 and empty == 1:
                score += 12.0  # block pressure emerges from opponent trace
            if own == 2 and opp == 0 and empty == 1:
                score += 16.0  # finish pressure emerges from self trace
        return score

    def _structural_prior(self, idx: int) -> float:
        if idx == 4:
            return 4.0
        if idx in (0, 2, 6, 8):
            return 2.2
        return 1.0

    def stigmergic_score(self, species: str, idx: int) -> float:
        trace = self.pheromones[idx]
        return (
            self._structural_prior(idx)
            + self._line_pressure(species, idx)
            + trace.value_for(species) * 1.6
            + trace.opponent_value_for(species) * 0.35
            - trace.refractory * 0.45
        )

    def select_move_for(self, bot: Nanobot, moves: Optional[list[int]] = None) -> int:
        legal = moves if moves is not None else self.empty_cells()
        if not legal:
            raise ValueError("no legal moves")
        scored = [(self.stigmergic_score(bot.species, idx), self.rng.random() * 0.0001, idx) for idx in legal]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2]

    def _decay_pheromones(self) -> None:
        for trace in self.pheromones:
            trace.x *= 0.90
            trace.o *= 0.90
            trace.refractory *= 0.72

    def _reinforce_world_model(self, species: str, idx: int) -> None:
        trace = self.pheromones[idx]
        if species == "X":
            trace.x += 2.5
        else:
            trace.o += 2.5
        trace.refractory = 1.0
        for line in self._lines_for_cell(idx):
            for peer in line:
                if peer == idx or self.board[peer] is not None:
                    continue
                if species == "X":
                    self.pheromones[peer].x += 0.35
                else:
                    self.pheromones[peer].o += 0.35

    def deposit_marker(self, bot: Nanobot, target: int) -> Optional[int]:
        """Claim one legal cell exactly once and leave a receipt trace."""
        if target < 0 or target >= len(self.board) or self.board[target] is not None:
            attempt = {
                "species": bot.species,
                "bot_id": bot.bot_id,
                "cell": target,
                "reason": "occupied_or_invalid",
                "existing": self.board[target] if 0 <= target < len(self.board) else None,
            }
            self.double_spend_attempts.append(attempt)
            _write_receipt("double_spend_rejected", attempt)
            bot._spend_energy(5)
            return None

        self._decay_pheromones()
        receipt_id = f"nanobot_move_{uuid.uuid4().hex[:12]}"
        self.board[target] = bot.species
        self.claimed_cells[target] = receipt_id
        self.pheromones[target].claim_receipt = receipt_id
        self._reinforce_world_model(bot.species, target)
        bot.last_move = target
        bot._spend_energy(15)
        return target

    def check_win(self) -> Optional[str]:
        for a, b, c in self.WIN_CONDITIONS:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                self.winner = self.board[a]
                self.winning_line = (a, b, c)
                return self.winner
        return None

    def is_draw(self) -> bool:
        return all(cell is not None for cell in self.board) and self.winner is None

    def all_dead(self) -> bool:
        return all(not bot.is_alive for bot in self.swarm)

    def step(self) -> Optional[dict]:
        """Run one nanobot's turn. Returns move info or None."""
        if self.game_over:
            return None

        if self.is_draw():
            self.game_over = True
            return None

        alive_bots = [b for b in self.swarm if b.is_alive and b.species == self.turn_species]
        if not alive_bots:
            self.game_over = True
            return None

        bot = alive_bots[self.turn_index % len(alive_bots)]
        self.turn_index += 1

        target = bot.act(self.board, self)

        if target is not None:
            win = self.check_win()
            entry = {
                "species": bot.species,
                "agent": self.players.get(bot.species, bot.species),
                "bot_id": bot.bot_id,
                "cell": target,
                "receipt_id": self.claimed_cells.get(target, ""),
                "energy_left": bot.energy,
                "alive": bot.is_alive,
                "pheromone": {
                    "x": round(self.pheromones[target].x, 4),
                    "o": round(self.pheromones[target].o, 4),
                    "refractory": round(self.pheromones[target].refractory, 4),
                },
            }
            self.move_log.append(entry)

            if win:
                self.game_over = True
                entry["result"] = f"{win}_wins"
            elif self.is_draw():
                self.game_over = True
                entry["result"] = "draw"
            else:
                self.turn_species = self._opponent(self.turn_species)

            return entry

        if self.all_dead():
            self.game_over = True

        return None

    def reset(self) -> None:
        self.board = [None] * 9
        self.pheromones = [CellPheromone() for _ in range(9)]
        self.move_log.clear()
        self.claimed_cells.clear()
        self.double_spend_attempts.clear()
        self.turn_species = "X"
        self.winner = None
        self.winning_line = None
        self.turn_index = 0
        self.game_over = False
        self.deploy_swarm()

    def run_alice_vs_nanobot_game(self, *, max_steps: int = 9) -> dict:
        """Run Alice-X against Nanobot-O through the same stigmergic field."""
        steps = 0
        while not self.game_over and steps < max_steps:
            self.step()
            steps += 1
        result = self.winner or ("draw" if self.is_draw() else "unfinished")
        receipt = {
            "result": result,
            "moves": len(self.move_log),
            "board": self.board[:],
            "unique_claims": len(set(self.claimed_cells)),
            "double_spend_attempts": len(self.double_spend_attempts),
            "alice_moves": [m for m in self.move_log if m.get("agent") == "Alice"],
            "nanobot_moves": [m for m in self.move_log if m.get("agent") == "Nanobot"],
        }
        _write_receipt("alice_vs_nanobot_self_play", receipt)
        return receipt


# ---------------------------------------------------------------------------
# Board canvas — paints the 3×3 grid with pheromone glow
# ---------------------------------------------------------------------------

class _BoardCanvas(QWidget):
    def __init__(self, env: StigmergicEnvironment, parent: QWidget | None = None):
        super().__init__(parent)
        self.env = env
        self.setMinimumSize(340, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h) - 24
        ox = (w - side) / 2
        oy = (h - side) / 2
        cell = side / 3

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, _BG)
        bg_grad.setColorAt(1, _PANEL)
        p.fillRect(self.rect(), bg_grad)

        for r in range(3):
            for c in range(3):
                idx = r * 3 + c
                cx = ox + c * cell
                cy = oy + r * cell
                rect = QRectF(cx + 2, cy + 2, cell - 4, cell - 4)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(_CELL_BG))
                p.drawRoundedRect(rect, 8, 8)
                trace = self.env.pheromones[idx]
                strength = min(1.0, max(trace.x, trace.o) / 4.0)
                if strength > 0.01:
                    color = QColor(_X_COLOR if trace.x >= trace.o else _O_COLOR)
                    color.setAlpha(int(35 + 105 * strength))
                    glow = QRadialGradient(
                        QPointF(cx + cell / 2, cy + cell / 2),
                        cell * 0.52,
                    )
                    glow.setColorAt(0, color)
                    glow.setColorAt(1, QColor(0, 0, 0, 0))
                    p.setBrush(QBrush(glow))
                    p.drawEllipse(QPointF(cx + cell / 2, cy + cell / 2), cell * 0.48, cell * 0.48)

        pen = QPen(_GRID_LINE, 2.5)
        p.setPen(pen)
        for i in range(1, 3):
            p.drawLine(QPointF(ox + i * cell, oy + 4), QPointF(ox + i * cell, oy + side - 4))
            p.drawLine(QPointF(ox + 4, oy + i * cell), QPointF(ox + side - 4, oy + i * cell))

        if self.env.winning_line:
            for idx in self.env.winning_line:
                r, c = divmod(idx, 3)
                cx = ox + c * cell + cell / 2
                cy = oy + r * cell + cell / 2
                glow = QRadialGradient(QPointF(cx, cy), cell * 0.55)
                glow.setColorAt(0, _WIN_GLOW)
                glow.setColorAt(1, QColor(0, 0, 0, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(QPointF(cx, cy), cell * 0.55, cell * 0.55)

        for idx in range(9):
            species = self.env.board[idx]
            if species is None:
                continue
            r, c = divmod(idx, 3)
            cx = ox + c * cell + cell / 2
            cy = oy + r * cell + cell / 2
            radius = cell * 0.30

            if species == "X":
                self._draw_x(p, cx, cy, radius, _X_COLOR)
            else:
                self._draw_o(p, cx, cy, radius, _O_COLOR)

        p.end()

    def _draw_x(self, p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
        pen = QPen(color, max(3, r * 0.22))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        d = r * 0.75
        p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
        p.drawLine(QPointF(cx + d, cy - d), QPointF(cx - d, cy + d))

    def _draw_o(self, p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
        pen = QPen(color, max(3, r * 0.22))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r * 0.78, r * 0.78)


# ---------------------------------------------------------------------------
# Swarm status panel — energy bars for each bot
# ---------------------------------------------------------------------------

class _SwarmPanel(QWidget):
    def __init__(self, env: StigmergicEnvironment, parent: QWidget | None = None):
        super().__init__(parent)
        self.env = env
        self.setFixedWidth(200)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), _PANEL)

        font = QFont("SF Mono", 9)
        p.setFont(font)
        y = 12

        p.setPen(_TEXT)
        p.drawText(10, y, "NANOBOT SWARM")
        y += 20

        bar_w = 120
        bar_h = 10

        for i, bot in enumerate(self.env.swarm):
            label = f"{bot.species}-{i // 2}"
            fill_color = _ENERGY_FILL_X if bot.species == "X" else _ENERGY_FILL_O

            if not bot.is_alive:
                p.setPen(_DEAD_COLOR)
                p.drawText(10, y + 10, f"{label}  EXPIRED")
                y += 18
                continue

            p.setPen(_DIM)
            p.drawText(10, y + 10, label)

            bx = 70
            by = y + 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_ENERGY_BG))
            p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 3, 3)

            fill_w = max(0, bar_w * bot.energy / 100)
            p.setBrush(QBrush(fill_color))
            p.drawRoundedRect(QRectF(bx, by, fill_w, bar_h), 3, 3)

            p.setPen(_DIM)
            p.drawText(bx + bar_w + 4, y + 10, f"{bot.energy}")
            y += 18

        p.setPen(_PANEL_BORDER)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class StigmergicNanobotTicTacToeWidget(QWidget):
    """Stigmergic Nanobot Tic-Tac-Toe — SIFTA app widget."""

    _live_instance: Optional["StigmergicNanobotTicTacToeWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
                    try:
                        existing.show()
                        existing.raise_()
                        existing.activateWindow()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: QWidget | None = None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(660, 460)

        self.env = StigmergicEnvironment(swarm_size=5)
        self.env.deploy_swarm()
        self._games_played = 0
        self._x_wins = 0
        self._o_wins = 0
        self._draws = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        title = QLabel(APP_TITLE)
        title.setFont(QFont("SF Mono", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT.name()}; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(8)

        self._canvas = _BoardCanvas(self.env, self)
        body.addWidget(self._canvas, stretch=1)

        self._swarm_panel = _SwarmPanel(self.env, self)
        body.addWidget(self._swarm_panel)

        root.addLayout(body, stretch=1)

        self._status_label = QLabel("Alice-X versus Nanobot-O: pheromone field ready.")
        self._status_label.setFont(QFont("SF Mono", 10))
        self._status_label.setStyleSheet(f"color: {_TEXT.name()}; background: transparent;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status_label)

        self._score_label = QLabel("X: 0  |  O: 0  |  Draw: 0")
        self._score_label.setFont(QFont("SF Mono", 9))
        self._score_label.setStyleSheet(f"color: {_DIM.name()}; background: transparent;")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._score_label)

        btn_row = QHBoxLayout()
        self._btn_step = QPushButton("Step")
        self._btn_auto = QPushButton("Auto ▶")
        self._btn_reset = QPushButton("New Game")
        for btn in (self._btn_step, self._btn_auto, self._btn_reset):
            btn.setFont(QFont("SF Mono", 10))
            btn.setStyleSheet(
                f"QPushButton {{ background: {_PANEL.name()}; color: {_TEXT.name()}; "
                f"border: 1px solid {_PANEL_BORDER.name()}; border-radius: 6px; "
                f"padding: 6px 14px; }}"
                f"QPushButton:hover {{ background: {_CELL_HOVER.name()}; }}"
            )
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        self._btn_step.clicked.connect(self._do_step)
        self._btn_auto.clicked.connect(self._toggle_auto)
        self._btn_reset.clicked.connect(self._new_game)

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(350)
        self._auto_timer.timeout.connect(self._do_step)
        self._auto_running = False

        self.setStyleSheet(f"background: {_BG.name()};")

        _publish_app_focus("boot")
        _write_receipt("boot", {"swarm_size": self.env.swarm_size})

    # -- actions --

    def _do_step(self) -> None:
        if self.env.game_over:
            if self._auto_running:
                self._auto_timer.stop()
                self._auto_running = False
                self._btn_auto.setText("Auto ▶")
            return

        result = self.env.step()
        if result:
            species = result["species"]
            cell = result["cell"]
            r, c = divmod(cell, 3)
            self._status_label.setText(
                f"{result['agent']} {species} → row {r+1} col {c+1}  "
                f"(receipt {result['receipt_id'][-6:]}, energy {result['energy_left']})"
            )
            if "result" in result:
                self._finish_game(result["result"])
        elif self.env.game_over:
            self._finish_game("all_expired")

        self._canvas.update()
        self._swarm_panel.update()

    def _finish_game(self, result: str) -> None:
        self._games_played += 1
        if result == "X_wins":
            self._x_wins += 1
            self._status_label.setText("X-SWARM WINS!")
        elif result == "O_wins":
            self._o_wins += 1
            self._status_label.setText("O-SWARM WINS!")
        elif result == "draw":
            self._draws += 1
            self._status_label.setText("DRAW — board full.")
        else:
            self._draws += 1
            self._status_label.setText("ALL NANOBOTS EXPIRED — no winner.")

        self._score_label.setText(
            f"X: {self._x_wins}  |  O: {self._o_wins}  |  Draw: {self._draws}"
        )

        _write_receipt("game_end", {
            "result": result,
            "moves": len(self.env.move_log),
            "board": self.env.board[:],
            "x_wins_total": self._x_wins,
            "o_wins_total": self._o_wins,
            "draws_total": self._draws,
        })
        _publish_app_focus(f"game_end:{result}")

    def _toggle_auto(self) -> None:
        if self._auto_running:
            self._auto_timer.stop()
            self._auto_running = False
            self._btn_auto.setText("Auto ▶")
        else:
            self._auto_timer.start()
            self._auto_running = True
            self._btn_auto.setText("Pause ⏸")

    def _new_game(self) -> None:
        if self._auto_running:
            self._auto_timer.stop()
            self._auto_running = False
            self._btn_auto.setText("Auto ▶")
        self.env.reset()
        self._status_label.setText("New swarm deployed. Step or Auto to begin.")
        self._canvas.update()
        self._swarm_panel.update()
        _write_receipt("new_game", {"swarm_size": self.env.swarm_size})

    # -- lifecycle --

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._auto_running:
            self._auto_timer.stop()
        _write_receipt("close", {"games_played": self._games_played})
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = StigmergicNanobotTicTacToeWidget()
    win.show()
    sys.exit(app.exec())
