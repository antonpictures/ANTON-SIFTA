#!/usr/bin/env python3
"""
Applications/sifta_stigmergic_go.py
══════════════════════════════════════════════════════════════════════
Stigmergic Go — SIFTA 19×19 board game with living pheromone field.

Stigmergic mechanics (per Predator v7 + 3-cortex tournament):
  • Stones are permanent deposits into a shared influence field.
  • Multiple "swimmers" (ants) explore empty intersections each step,
    biased by pheromone density + local liberties.
  • Pheromone evaporates, reinforces strong structures (eyes, walls,
    connections). The field itself computes partial territory value.
  • "Field Evolve" runs ACO-style steps; high-pheromone legal points
    are suggested for the current player.
  • Swarm-opponent modes choose and place turns from the pheromone field.
  • Live tie-in to .sifta_state/ (recent traces shown in sidebar).
  • No second Alice chat. Publishes app_focus. Single-instance.

Registration: a96120ae-7e60-4974-85c6-95095960b254 (Grok 4.3-xAI)
3-cortex tournament: grok arm → Stigmergic Go (claude=Sudoku, hermes=Calculator)
Truth label: STIGMERGIC_GO_V1

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Optional, Tuple, List, Set

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore

TRUTH_LABEL = "STIGMERGIC_GO_V1"
REGISTRATION_TRACE = "a96120ae-7e60-4974-85c6-95095960b254"

# ── Palette (Predator dark + sudoku accents + Go stone feel) ─────────
_BG = QColor(8, 10, 18)
_BG_BOARD = QColor(18, 20, 32)
_GRID = QColor(70, 75, 110)
_GRID_THICK = QColor(120, 125, 170)
_HOSHI = QColor(140, 145, 200)
_STONE_B = QColor(20, 20, 25)
_STONE_W = QColor(235, 235, 240)
_STONE_B_RIM = QColor(60, 60, 70)
_STONE_W_RIM = QColor(180, 180, 190)
_ACCENT = QColor(0, 255, 180)
_PHERO_B = QColor(40, 120, 255, 90)   # blue influence (black player)
_PHERO_W = QColor(255, 200, 80, 90)   # warm (white player)
_SWIMMER = QColor(255, 120, 80, 220)
_TEXT = QColor(200, 210, 240)
_TEXT_DIM = QColor(140, 150, 180)

BOARD_N = 19
HO_SHI = [3, 9, 15]  # 19x19 hoshi positions (0-based)


def _publish_app_focus(title: str, detail: str = "") -> None:
    if _publish_focus:
        try:
            _publish_focus(title=title, detail=detail, app_id="sifta_stigmergic_go")
        except Exception:
            pass


# ── Core Go rules (liberties, capture, ko, simple scoring) ───────────
class _GoRules:
    def __init__(self):
        self.board: List[List[Optional[str]]] = [[None for _ in range(BOARD_N)] for _ in range(BOARD_N)]
        self.captures = {"B": 0, "W": 0}
        self.last_ko: Optional[Tuple[int, int]] = None
        self.last_move: Optional[Tuple[str, int, int]] = None  # (color, r, c)
        self.passes = 0

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < BOARD_N and 0 <= c < BOARD_N

    def _neighbors(self, r: int, c: int) -> List[Tuple[int, int]]:
        return [(r+dr, c+dc) for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)] if self._in_bounds(r+dr, c+dc)]

    def _group_and_liberties(self, r: int, c: int) -> Tuple[Set[Tuple[int,int]], int]:
        return self._group_and_liberties_on(self.board, r, c)

    def _group_and_liberties_on(
        self,
        board: List[List[Optional[str]]],
        r: int,
        c: int,
    ) -> Tuple[Set[Tuple[int,int]], int]:
        color = board[r][c]
        if not color:
            return set(), 0
        group: Set[Tuple[int,int]] = set()
        libs: Set[Tuple[int,int]] = set()
        stack = [(r, c)]
        while stack:
            x, y = stack.pop()
            if (x, y) in group:
                continue
            group.add((x, y))
            for nx, ny in self._neighbors(x, y):
                v = board[nx][ny]
                if v is None:
                    libs.add((nx, ny))
                elif v == color and (nx, ny) not in group:
                    stack.append((nx, ny))
        return group, len(libs)

    def legal_moves(self, color: str) -> List[Tuple[int, int]]:
        moves: List[Tuple[int, int]] = []
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                if self.move_features(r, c, color).get("legal"):
                    moves.append((r, c))
        return moves

    def _capture_if_any(self, r: int, c: int, color: str) -> int:
        return self._capture_if_any_on(self.board, r, c, color)

    def _capture_if_any_on(
        self,
        board: List[List[Optional[str]]],
        r: int,
        c: int,
        color: str,
    ) -> int:
        """Capture opponent groups with 0 libs. Return stones captured."""
        opp = "W" if color == "B" else "B"
        total = 0
        for nr, nc in self._neighbors(r, c):
            if board[nr][nc] == opp:
                g, libs = self._group_and_liberties_on(board, nr, nc)
                if libs == 0:
                    for x, y in g:
                        board[x][y] = None
                    total += len(g)
        return total

    def move_features(self, r: int, c: int, color: str) -> dict:
        """Non-mutating legality and local feature probe for stigmergic play."""
        if not self._in_bounds(r, c):
            return {"legal": False, "reason": "out_of_bounds"}
        if self.board[r][c] is not None:
            return {"legal": False, "reason": "occupied"}
        if self.last_ko == (r, c):
            return {"legal": False, "reason": "ko"}

        trial = deepcopy(self.board)
        trial[r][c] = color
        captured = self._capture_if_any_on(trial, r, c, color)
        group, libs = self._group_and_liberties_on(trial, r, c)
        if libs == 0:
            return {"legal": False, "reason": "suicide", "captures": captured, "liberties": libs}

        friendly = 0
        opponent = 0
        for nr, nc in self._neighbors(r, c):
            if self.board[nr][nc] == color:
                friendly += 1
            elif self.board[nr][nc] is not None:
                opponent += 1
        return {
            "legal": True,
            "reason": "ok",
            "captures": captured,
            "liberties": libs,
            "group_size": len(group),
            "friendly_neighbors": friendly,
            "opponent_neighbors": opponent,
        }

    def place(self, r: int, c: int, color: str) -> Tuple[bool, str]:
        """Try place. Return (success, reason). Updates captures and ko."""
        if not self._in_bounds(r, c) or self.board[r][c] is not None:
            return False, "occupied"
        if self.last_ko == (r, c):
            return False, "ko"
        # trial
        features = self.move_features(r, c, color)
        if not features.get("legal"):
            return False, str(features.get("reason", "illegal"))
        old = deepcopy(self.board)
        self.board[r][c] = color
        captured = self._capture_if_any(r, c, color)
        # ko: single stone capture that leaves one-stone group with 1 lib? simple ko
        new_ko = None
        if captured == 1:
            # find the single captured point
            for i in range(BOARD_N):
                for j in range(BOARD_N):
                    if old[i][j] != self.board[i][j] and self.board[i][j] is None and old[i][j] is not None:
                        new_ko = (i, j)  # the point just emptied
                        break
        self.last_ko = new_ko
        self.captures[color] += captured
        self.last_move = (color, r, c)
        self.passes = 0
        return True, "ok"

    def pass_turn(self) -> None:
        self.passes += 1
        self.last_ko = None

    def is_game_over(self) -> bool:
        return self.passes >= 2

    def simple_score(self) -> dict:
        """Rough area score (no komi, no eyes perfect)."""
        b_score = self.captures["B"]
        w_score = self.captures["W"]
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                v = self.board[r][c]
                if v == "B":
                    b_score += 1
                elif v == "W":
                    w_score += 1
                else:
                    # empty: count as territory for nearest or none (naive)
                    pass  # could improve with flood but keep fast
        return {"B": b_score, "W": w_score}


# ── Stigmergic pheromone field + swimmers ────────────────────────────
class _StigmergicField:
    def __init__(self):
        self.ph: dict[str, List[List[float]]] = {
            "B": [[0.01 for _ in range(BOARD_N)] for _ in range(BOARD_N)],
            "W": [[0.01 for _ in range(BOARD_N)] for _ in range(BOARD_N)],
        }
        self.swimmers: List[Tuple[int, int, str]] = []
        self.evap = 0.06
        self.deposit = 0.8
        self.total_deposits = 0
        self.steps = 0
        self.last_selection: dict = {}

    def on_place(self, r: int, c: int, color: str) -> None:
        """Stone deposit strengthens local field."""
        val = 1.6 if color == "B" else 1.45
        self.ph[color][r][c] += val
        for nr, nc in self._nb(r, c):
            self.ph[color][nr][nc] += 0.35
        opp = "W" if color == "B" else "B"
        self.ph[opp][r][c] *= 0.35

    def _nb(self, r: int, c: int) -> List[Tuple[int, int]]:
        return [(r+dr, c+dc) for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)] if 0 <= r+dr < BOARD_N and 0 <= c+dc < BOARD_N]

    def evaporate(self) -> None:
        for color in ("B", "W"):
            for r in range(BOARD_N):
                for c in range(BOARD_N):
                    self.ph[color][r][c] *= (1.0 - self.evap)
                    self.ph[color][r][c] = max(0.005, self.ph[color][r][c])

    def _edge_penalty(self, r: int, c: int) -> float:
        edge_dist = min(r, c, BOARD_N - 1 - r, BOARD_N - 1 - c)
        return 0.65 if edge_dist == 0 else (0.82 if edge_dist == 1 else 1.0)

    def move_score(self, rules: _GoRules, color: str, r: int, c: int) -> float:
        features = rules.move_features(r, c, color)
        if not features.get("legal"):
            return 0.0
        own = self.ph[color][r][c]
        opp = "W" if color == "B" else "B"
        opp_ph = self.ph[opp][r][c]
        liberties = float(features.get("liberties", 0))
        captures = float(features.get("captures", 0))
        friendly = float(features.get("friendly_neighbors", 0))
        opponent = float(features.get("opponent_neighbors", 0))
        local_shape = 0.20 * liberties + 0.35 * friendly + 0.28 * opponent + 2.4 * captures
        influence = own * 2.1 + opp_ph * 0.45
        return max(0.001, (influence + local_shape + 0.2) * self._edge_penalty(r, c))

    def step_swimmers(self, rules: _GoRules, color: str, n: int = 12) -> List[Tuple[int, int]]:
        """ACO-style: swimmers move to high-phero + high-liberty empties, deposit."""
        self.steps += 1
        self.swimmers.clear()
        legal = rules.legal_moves(color)
        empties = legal
        if not empties:
            return []
        targets = random.sample(empties, min(n, len(empties)))
        proposals: List[Tuple[int, int]] = []
        for r, c in targets:
            self.swimmers.append((r, c, color))
            # bias walk 1-2 steps
            cr, cc = r, c
            for _ in range(2):
                cands = [(x, y) for x, y in self._nb(cr, cc) if rules.move_features(x, y, color).get("legal")]
                if not cands:
                    break
                # weight by phero + liberty estimate (simple)
                weights = []
                for x, y in cands:
                    w = (self.move_score(rules, color, x, y) ** 1.25) * (1.0 + 0.25 * random.random())
                    weights.append(w)
                s = sum(weights) or 1.0
                cr, cc = random.choices(cands, weights=[w/s for w in weights])[0]
            # deposit at final
            self.ph[color][cr][cc] += self.deposit * self.move_score(rules, color, cr, cc)
            self.total_deposits += 1
            if (cr, cc) not in proposals:
                proposals.append((cr, cc))
        self.evaporate()
        return proposals

    def suggest(self, rules: _GoRules, color: str, legal: List[Tuple[int,int]], top: int = 5) -> List[Tuple[int, int]]:
        if not legal:
            return []
        scored = sorted(legal, key=lambda p: self.move_score(rules, color, p[0], p[1]), reverse=True)
        return scored[:top]

    def choose_move(self, rules: _GoRules, color: str, evolve_steps: int = 8) -> Tuple[int, int] | None:
        """Select a legal move from the pheromone field; no search tree or oracle."""
        for _ in range(max(1, evolve_steps)):
            self.step_swimmers(rules, color, n=18)
        legal = rules.legal_moves(color)
        hot = self.suggest(rules, color, legal, top=8)
        if not hot:
            self.last_selection = {"color": color, "reason": "no_legal_move"}
            return None
        weights = [self.move_score(rules, color, r, c) ** 1.4 for r, c in hot]
        move = random.choices(hot, weights=weights, k=1)[0]
        self.last_selection = {
            "color": color,
            "move": move,
            "score": round(self.move_score(rules, color, move[0], move[1]), 4),
            "hot_points": hot,
            "selection": "pheromone_weighted_swimmer_field",
        }
        return move

    def value_at(self, r: int, c: int, color: str | None = None) -> float:
        if color:
            return self.ph[color][r][c]
        return max(self.ph["B"][r][c], self.ph["W"][r][c])

    def dominant_color(self, r: int, c: int) -> str:
        return "B" if self.ph["B"][r][c] >= self.ph["W"][r][c] else "W"

    def max_ph(self, color: str | None = None) -> float:
        if color:
            return max(max(row) for row in self.ph[color])
        return max(self.max_ph("B"), self.max_ph("W"))


# ── Widget (hardened singleton per §7.6.2) ───────────────────────────
class StigmergicGoWidget(QWidget):
    """Stigmergic Go — 19×19 with pheromone field and swimmer agents."""
    _live_instance: Optional["StigmergicGoWidget"] = None
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
                        existing.show(); existing.raise_(); existing.activateWindow()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._go_initialized = True

        self.setWindowTitle("Stigmergic Go")
        self.setMinimumSize(980, 820)
        self.setStyleSheet("background: transparent;")

        self.rules = _GoRules()
        self.field = _StigmergicField()
        self.current_color = "B"
        self.cell = 32
        self.margin = 36
        self.board_px = BOARD_N * self.cell
        self.selected: Optional[Tuple[int, int]] = None
        self.suggestions: List[Tuple[int, int]] = []
        self.last_action = "New game — black to play. Stones deposit; swimmers evolve the field."
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_evolve)
        self._auto = False
        self.swarm_colors: Set[str] = {"W"}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._color_label = QLabel("BLACK")
        self._color_label.setStyleSheet("color:#0f0; font-weight:bold; font-size:13px;")
        bar.addWidget(self._color_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            "You Black vs Swarm White",
            "You White vs Swarm Black",
            "Human vs Human",
            "Swarm vs Swarm",
        ])
        self._mode_combo.setCurrentText("You Black vs Swarm White")
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self._mode_combo)

        for txt, fn in [
            ("New", self._new_game),
            ("Pass", self._pass),
            ("Field Evolve", self._evolve),
            ("Auto Field", self._toggle_auto),
            ("Score", self._show_score),
        ]:
            b = QPushButton(txt)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)

        # main area: board + sidebar
        main = QHBoxLayout()
        main.setSpacing(10)

        self.board_widget = QWidget()
        self.board_widget.setFixedSize(self.board_px + 2*self.margin, self.board_px + 2*self.margin)
        self.board_widget.setStyleSheet("background: #0a0c16; border: 1px solid #2a2e44;")
        self.board_widget.paintEvent = self._paint_board  # type: ignore[method-assign]
        self.board_widget.mousePressEvent = self._on_click  # type: ignore[method-assign]
        main.addWidget(self.board_widget)

        # sidebar
        side = QVBoxLayout()
        side.setSpacing(4)
        self.status = QLabel(self.last_action)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#ccd; font-size:11px; min-width:260px;")
        side.addWidget(self.status)

        self.stats = QLabel("")
        self.stats.setStyleSheet("color:#0f0; font-family:Menlo; font-size:10px;")
        side.addWidget(self.stats)

        self.trace_label = QLabel("Stigmergic trace (live)")
        self.trace_label.setStyleSheet("color:#a8f; font-size:10px; margin-top:6px;")
        side.addWidget(self.trace_label)
        self.trace_box = QLabel("—")
        self.trace_box.setStyleSheet("color:#99a; font-size:9px; background:#11131f; padding:4px; border-radius:3px;")
        self.trace_box.setWordWrap(True)
        side.addWidget(self.trace_box)
        side.addStretch()
        main.addLayout(side)

        root.addLayout(main)

        self._new_game()
        _publish_app_focus("Stigmergic Go", "19×19 + pheromone swimmers (Grok 4.3)")

        self._load_recent_trace()

    def _load_recent_trace(self) -> None:
        try:
            trace = _STATE / "ide_stigmergic_trace.jsonl"
            if trace.exists():
                lines = trace.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-3:]
                if lines:
                    last = json.loads(lines[-1])
                    self.trace_box.setText(f"{last.get('ts',0):.0f} {last.get('model','')} {last.get('action','')[:40]}")
        except Exception:
            self.trace_box.setText("no readable trace")

    def _new_game(self) -> None:
        self.rules = _GoRules()
        self.field = _StigmergicField()
        self.current_color = "B"
        self._sync_swarm_colors()
        self.selected = None
        self.suggestions = []
        self.last_action = "New game. Human plays black; swarm plays white from pheromone field."
        self._color_label.setText("BLACK")
        self._color_label.setStyleSheet("color:#0f0; font-weight:bold; font-size:13px;")
        self._update_stats()
        self.board_widget.update()
        _publish_app_focus("Stigmergic Go", "new game")
        self._write_receipt("new_game", {
            "mode": self._mode_combo.currentText(),
            "swarm_colors": sorted(self.swarm_colors),
            "used_solution_oracle": False,
        })
        self._schedule_swarm_if_needed()

    def _sync_swarm_colors(self) -> None:
        mode = self._mode_combo.currentText()
        if mode == "You Black vs Swarm White":
            self.swarm_colors = {"W"}
        elif mode == "You White vs Swarm Black":
            self.swarm_colors = {"B"}
        elif mode == "Swarm vs Swarm":
            self.swarm_colors = {"B", "W"}
        else:
            self.swarm_colors = set()

    def _on_mode_changed(self, _text: str) -> None:
        self._sync_swarm_colors()
        self.last_action = f"Mode: {self._mode_combo.currentText()}"
        self._update_stats()
        self._schedule_swarm_if_needed()

    def _pass(self) -> None:
        if self.current_color in self.swarm_colors:
            self.last_action = f"{self.current_color} is controlled by the swarm field."
            self._update_stats()
            return
        self.rules.pass_turn()
        self._advance_turn()
        self.last_action = f"Pass — now {self.current_color}"
        self.suggestions = []
        if self.rules.is_game_over():
            self.last_action = "Game over (2 passes). Score to see result."
        self._update_stats()
        self.board_widget.update()
        self._schedule_swarm_if_needed()

    def _evolve(self) -> None:
        legal = self.rules.legal_moves(self.current_color)
        props = self.field.step_swimmers(self.rules, self.current_color, n=14)
        self.suggestions = self.field.suggest(self.rules, self.current_color, legal, top=6)
        self.last_action = f"{self.current_color} field evolved {self.field.steps} steps. {len(self.suggestions)} hot points."
        self._update_stats()
        self.board_widget.update()

    def _toggle_auto(self) -> None:
        self._auto = not self._auto
        if self._auto:
            self._timer.start(420)
            self.last_action = "Auto field evolution ON (swimmers running)."
        else:
            self._timer.stop()
            self.last_action = "Auto OFF."
        self._update_stats()

    def _auto_evolve(self) -> None:
        self._evolve()
        if self.current_color in self.swarm_colors:
            self._play_swarm_turn(reason="auto_field")
        self.board_widget.update()

    def _show_score(self) -> None:
        sc = self.rules.simple_score()
        ph = self.field.max_ph()
        msg = f"Score (area): B {sc['B']}  W {sc['W']}  | max pheromone {ph:.2f}"
        self.last_action = msg
        self.status.setText(msg)
        _publish_app_focus("Stigmergic Go", f"score B{sc['B']} W{sc['W']}")

    def _advance_turn(self) -> None:
        self.current_color = "W" if self.current_color == "B" else "B"
        self._color_label.setText("WHITE" if self.current_color == "W" else "BLACK")
        self._color_label.setStyleSheet("color:#ff0; font-weight:bold; font-size:13px;" if self.current_color == "W" else "color:#0f0; font-weight:bold; font-size:13px;")

    def _schedule_swarm_if_needed(self) -> None:
        if not self.rules.is_game_over() and self.current_color in self.swarm_colors:
            QTimer.singleShot(220, self._play_swarm_turn)

    def _play_swarm_turn(self, reason: str = "opponent_turn") -> None:
        if self.rules.is_game_over() or self.current_color not in self.swarm_colors:
            return
        color = self.current_color
        move = self.field.choose_move(self.rules, color, evolve_steps=10)
        if move is None:
            self.rules.pass_turn()
            self.last_action = f"Swarm {color} passed: no legal move."
            self._write_receipt("swarm_pass", {
                "color": color,
                "reason": reason,
                "used_solution_oracle": False,
                "selection": self.field.last_selection,
            })
            self._advance_turn()
            self._update_stats()
            self.board_widget.update()
            self._schedule_swarm_if_needed()
            return
        r, c = move
        ok, place_reason = self.rules.place(r, c, color)
        if not ok:
            self.last_action = f"Swarm {color} rejected {move}: {place_reason}"
            self._write_receipt("swarm_move_rejected", {
                "color": color,
                "move": move,
                "reason": place_reason,
                "selection": self.field.last_selection,
                "used_solution_oracle": False,
            })
            self._update_stats()
            return
        self.field.on_place(r, c, color)
        self.last_action = f"Swarm {color} @({r},{c}) from pheromone field"
        self._write_receipt("swarm_opponent_move", {
            "color": color,
            "move": [r, c],
            "reason": reason,
            "selection": self.field.last_selection,
            "field_steps": self.field.steps,
            "deposits": self.field.total_deposits,
            "used_solution_oracle": False,
        })
        self._advance_turn()
        self.suggestions = self.field.suggest(
            self.rules,
            self.current_color,
            self.rules.legal_moves(self.current_color),
            top=5,
        )
        self._update_stats()
        self.board_widget.update()
        self._schedule_swarm_if_needed()

    def _update_stats(self) -> None:
        sc = self.rules.simple_score()
        mode = self._mode_combo.currentText()
        self.stats.setText(
            f"Mode: {mode}\n"
            f"Turn: {self.current_color}   "
            f"Capt B:{self.rules.captures['B']} W:{self.rules.captures['W']}\n"
            f"Score B:{sc['B']} W:{sc['W']}   "
            f"Field steps:{self.field.steps} deposits:{self.field.total_deposits}\n"
            f"Swimmers:{len(self.field.swimmers)}  max_ph:{self.field.max_ph():.2f}  "
            f"swarm:{','.join(sorted(self.swarm_colors)) or 'off'}"
        )
        self.status.setText(self.last_action)

    def _on_click(self, ev) -> None:
        if self.rules.is_game_over():
            return
        if self.current_color in self.swarm_colors:
            self.last_action = f"{self.current_color} is the swarm opponent; wait for the field move."
            self._update_stats()
            self._schedule_swarm_if_needed()
            return
        x = ev.position().x() - self.margin
        y = ev.position().y() - self.margin
        c = int(round(x / self.cell))
        r = int(round(y / self.cell))
        if not (0 <= r < BOARD_N and 0 <= c < BOARD_N):
            return
        if self.rules.board[r][c] is not None:
            return
        ok, reason = self.rules.place(r, c, self.current_color)
        if ok:
            self.field.on_place(r, c, self.current_color)
            self.last_action = f"{self.current_color} @({r},{c})  field reinforced"
            self._write_receipt("human_move", {
                "color": self.current_color,
                "move": [r, c],
                "used_solution_oracle": False,
            })
            self._advance_turn()
            self.suggestions = self.field.suggest(self.rules, self.current_color, self.rules.legal_moves(self.current_color), top=5)
            self._load_recent_trace()
        else:
            self.last_action = f"Illegal: {reason}"
        self._update_stats()
        self.board_widget.update()
        _publish_app_focus("Stigmergic Go", f"move {r},{c}")
        self._schedule_swarm_if_needed()

    def _write_receipt(self, action: str, data: dict) -> None:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "app": "Stigmergic Go",
            "truth_label": TRUTH_LABEL,
            "registration_trace": REGISTRATION_TRACE,
            "action": action,
            **data,
        }
        try:
            with open(_STATE / "go_receipts.jsonl", "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def _paint_board(self, ev) -> None:
        p = QPainter(self.board_widget)
        p.fillRect(self.board_widget.rect(), _BG)
        # board bg
        p.fillRect(QRectF(self.margin-4, self.margin-4, self.board_px+8, self.board_px+8), _BG_BOARD)

        # grid
        p.setPen(QPen(_GRID, 1))
        for i in range(BOARD_N):
            p.drawLine(self.margin, self.margin + i*self.cell, self.margin + self.board_px, self.margin + i*self.cell)
            p.drawLine(self.margin + i*self.cell, self.margin, self.margin + i*self.cell, self.margin + self.board_px)

        # hoshi
        p.setBrush(_HOSHI)
        p.setPen(Qt.PenStyle.NoPen)
        for hr in HO_SHI:
            for hc in HO_SHI:
                cx = self.margin + hc * self.cell
                cy = self.margin + hr * self.cell
                p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)

        # pheromone heat (under stones)
        maxp = self.field.max_ph() or 1.0
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                val = self.field.value_at(r, c) / maxp
                if val < 0.04:
                    continue
                cx = self.margin + c * self.cell
                cy = self.margin + r * self.cell
                col = _PHERO_B if self.field.dominant_color(r, c) == "B" else _PHERO_W
                col = QColor(col.red(), col.green(), col.blue(), int(40 + 140 * min(1.0, val*1.6)))
                p.setBrush(col)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(int(cx - self.cell*0.42), int(cy - self.cell*0.42), int(self.cell*0.84), int(self.cell*0.84))

        # stones
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                v = self.rules.board[r][c]
                if not v:
                    continue
                cx = self.margin + c * self.cell
                cy = self.margin + r * self.cell
                rad = self.cell * 0.42
                if v == "B":
                    grad = QRadialGradient(cx-3, cy-3, rad*1.6)
                    grad.setColorAt(0, QColor(60,60,68))
                    grad.setColorAt(1, _STONE_B)
                    p.setBrush(grad)
                    p.setPen(QPen(_STONE_B_RIM, 1.5))
                else:
                    grad = QRadialGradient(cx-2, cy-2, rad*1.5)
                    grad.setColorAt(0, QColor(255,255,255))
                    grad.setColorAt(1, _STONE_W)
                    p.setBrush(grad)
                    p.setPen(QPen(_STONE_W_RIM, 1))
                p.drawEllipse(QPointF(cx, cy), rad, rad)

        # suggestions (hot pheromone legal)
        p.setPen(QPen(_ACCENT, 2))
        for r, c in self.suggestions:
            cx = self.margin + c * self.cell
            cy = self.margin + r * self.cell
            p.drawEllipse(QPointF(cx, cy), self.cell*0.28, self.cell*0.28)

        # last move ring
        if self.rules.last_move:
            _, lr, lc = self.rules.last_move
            p.setPen(QPen(_ACCENT, 2.5))
            cx = self.margin + lc * self.cell
            cy = self.margin + lr * self.cell
            p.drawEllipse(QPointF(cx, cy), self.cell*0.48, self.cell*0.48)

        # swimmers
        p.setPen(Qt.PenStyle.NoPen)
        for sr, sc, color in self.field.swimmers:
            p.setBrush(_SWIMMER if color == "B" else QColor(120, 220, 255, 220))
            cx = self.margin + sc * self.cell
            cy = self.margin + sr * self.cell
            p.drawEllipse(QPointF(cx, cy), 4, 4)

        p.end()

    def closeEvent(self, event) -> None:
        if type(self)._live_instance is self:
            type(self)._live_instance = None
            if id(self) in type(self)._initialized_instance_ids:
                type(self)._initialized_instance_ids.remove(id(self))
        self._timer.stop()
        super().closeEvent(event)


# ── Module entry for verifier / desktop spawner ──────────────────────
def main():
    app = QApplication(sys.argv)
    w = StigmergicGoWidget()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
