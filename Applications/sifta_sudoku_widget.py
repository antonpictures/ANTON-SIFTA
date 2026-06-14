#!/usr/bin/env python3
"""
Applications/sifta_sudoku_widget.py
StigAuth: COWORK_STIGMERGIC_SUDOKU_V0

Stigmergic Sudoku — ACO (Ant Colony Optimization) meets the 9×9 grid.

Swimmers explore empty cells, depositing pheromones on candidate digits
proportional to constraint satisfaction. Over iterations the pheromone
field converges and the swarm fills the board. The user can also play
manually cell-by-cell.

No second Alice chat (§7.6). Publishes app_focus so Alice knows
what the Architect is doing.
"""
from __future__ import annotations

"""SIFTA Sudoku Widget — stigmergic organ for Alice body."""

import json
import math
import random
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
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
    _publish_focus = None  # type: ignore

TRUTH_LABEL = "STIGMERGIC_SUDOKU_V1"
SELF_PLAY_TRUTH_LABEL = "STIGMERGIC_SUDOKU_SELF_PLAY_V1"

# ── palette ──────────────────────────────────────────────────────────
_BG_DARK = QColor(18, 18, 28)
_BG_CELL = QColor(28, 30, 46)
_BG_CELL_GIVEN = QColor(38, 40, 58)
_GRID_LINE = QColor(70, 75, 110)
_GRID_THICK = QColor(140, 145, 200)
_TEXT_GIVEN = QColor(220, 225, 255)
_TEXT_USER = QColor(120, 220, 160)
_TEXT_ERROR = QColor(255, 90, 90)
_ACCENT = QColor(160, 120, 255)
_PHERO_LOW = QColor(60, 40, 120, 40)
_PHERO_HIGH = QColor(180, 120, 255, 160)
_SELECT_RING = QColor(200, 160, 255, 200)
_SWIMMER_DOT = QColor(255, 200, 80, 200)


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


# ── Sudoku generator ────────────────────────────────────────────────

def _full_board() -> list[list[int]]:
    """Generate a completed valid 9×9 Sudoku board."""
    board = [[0] * 9 for _ in range(9)]

    def _possible(r: int, c: int) -> list[int]:
        used = set()
        for k in range(9):
            used.add(board[r][k])
            used.add(board[k][c])
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for dr in range(3):
            for dc in range(3):
                used.add(board[br + dr][bc + dc])
        return [d for d in range(1, 10) if d not in used]

    def _fill(pos: int) -> bool:
        if pos == 81:
            return True
        r, c = divmod(pos, 9)
        cands = _possible(r, c)
        random.shuffle(cands)
        for d in cands:
            board[r][c] = d
            if _fill(pos + 1):
                return True
            board[r][c] = 0
        return False

    _fill(0)
    return board


_ROWS = [[(r, c) for c in range(9)] for r in range(9)]
_COLS = [[(r, c) for r in range(9)] for c in range(9)]
_BOXES = [
    [(r, c) for r in range(br, br + 3) for c in range(bc, bc + 3)]
    for br in range(0, 9, 3)
    for bc in range(0, 9, 3)
]
_UNITS = _ROWS + _COLS + _BOXES


def _candidate_digits(board: list[list[int]], r: int, c: int) -> list[int]:
    """Digits allowed by Sudoku constraints only. No solution oracle."""
    if board[r][c]:
        return [board[r][c]]
    used = set()
    for k in range(9):
        if board[r][k]:
            used.add(board[r][k])
        if board[k][c]:
            used.add(board[k][c])
    br, bc = 3 * (r // 3), 3 * (c // 3)
    for dr in range(3):
        for dc in range(3):
            v = board[br + dr][bc + dc]
            if v:
                used.add(v)
    return [d for d in range(1, 10) if d not in used]


def _is_valid_complete(board: list[list[int]]) -> bool:
    target = set(range(1, 10))
    for unit in _UNITS:
        vals = [board[r][c] for r, c in unit]
        if set(vals) != target:
            return False
    return True


def _hidden_single_moves(
    board: list[list[int]],
    candidates: dict[tuple[int, int], list[int]] | None = None,
) -> list[tuple[int, int, int, str]]:
    if candidates is None:
        candidates = {
            (r, c): _candidate_digits(board, r, c)
            for r in range(9)
            for c in range(9)
            if board[r][c] == 0
        }
    moves: dict[tuple[int, int], tuple[int, int, int, str]] = {}
    for unit in _UNITS:
        for d in range(1, 10):
            locs = [
                (r, c)
                for r, c in unit
                if board[r][c] == 0 and d in candidates.get((r, c), [])
            ]
            if len(locs) == 1:
                r, c = locs[0]
                moves[(r, c)] = (r, c, d, "hidden_single")
    return list(moves.values())


def _constraint_solve_without_oracle(
    puzzle: list[list[int]],
) -> tuple[bool, list[list[int]], int]:
    """Solve with naked/hidden singles only; used to grade generated boards.

    This is not a backtracker and never sees the completed solution. It mirrors
    the Sudoku constraints available to the swarm field.
    """
    board = deepcopy(puzzle)
    placements = 0
    while True:
        progress = False
        candidates = {
            (r, c): _candidate_digits(board, r, c)
            for r in range(9)
            for c in range(9)
            if board[r][c] == 0
        }
        if any(not cands for cands in candidates.values()):
            return False, board, placements

        for (r, c), cands in list(candidates.items()):
            if board[r][c] == 0 and len(cands) == 1:
                board[r][c] = cands[0]
                placements += 1
                progress = True

        if progress:
            continue

        for r, c, d, _reason in _hidden_single_moves(board, candidates):
            if board[r][c] == 0:
                board[r][c] = d
                placements += 1
                progress = True

        if not progress:
            break

    return _is_valid_complete(board), board, placements


_logical_solve_without_oracle = _constraint_solve_without_oracle


def _make_puzzle(clues: int = 32) -> tuple[list[list[int]], list[list[int]], set[tuple[int, int]]]:
    """Return (puzzle, solution, given_cells).

    The hidden solution is kept for the human Check button only. Removal keeps
    boards that are solvable by the same constraint field the swarm sees, so
    the app does not need to smuggle the answer key into the solver.
    """
    solution = _full_board()
    puzzle = deepcopy(solution)
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    target_clues = max(17, min(clues, 65))
    current_clues = 81
    for r, c in cells:
        if current_clues <= target_clues:
            break
        old = puzzle[r][c]
        puzzle[r][c] = 0
        ok, _solved, _placements = _constraint_solve_without_oracle(puzzle)
        if ok:
            current_clues -= 1
        else:
            puzzle[r][c] = old
    given = {(r, c) for r in range(9) for c in range(9) if puzzle[r][c] != 0}
    return puzzle, solution, given


# ── Stigmergic ACO solver ───────────────────────────────────────────

class _StigmergicSolver:
    """Constraint-only stigmergic solver for Sudoku.

    Swimmers do not know the completed board. They deposit pheromones from
    local row/column/box pressure, hidden-single scarcity, and evaporation.
    The only commitments are Sudoku-valid forced placements.
    """

    truth_label = "STIGMERGIC_SUDOKU_CONSTRAINT_FIELD_V1"

    def __init__(self, puzzle: list[list[int]]):
        self.puzzle = deepcopy(puzzle)
        self.board = deepcopy(puzzle)
        # pheromone[r][c][d] = pheromone level for digit d+1 at cell (r,c)
        self.pheromone: list[list[list[float]]] = [
            [[0.08] * 9 for _ in range(9)] for _ in range(9)
        ]
        self.empty_cells = [
            (r, c) for r in range(9) for c in range(9) if puzzle[r][c] == 0
        ]
        self.evaporation = 0.12
        self.deposit_strength = 1.7
        self.swimmers: list[tuple[int, int]] = []
        self.total_deposits = 0
        self.iterations = 0
        self.solved_cells = 0
        self.last_event = "initialized"
        self.energy = 0.0
        self.stalled = False
        self.used_solution_oracle = False

    def _candidates(self, r: int, c: int) -> list[int]:
        return _candidate_digits(self.board, r, c)

    def _candidate_map(self) -> dict[tuple[int, int], list[int]]:
        return {
            (r, c): self._candidates(r, c)
            for r, c in self.empty_cells
            if self.board[r][c] == 0
        }

    def _hidden_pressure(
        self,
        candidates: dict[tuple[int, int], list[int]],
        r: int,
        c: int,
        d: int,
    ) -> float:
        pressure = 0.0
        units = [
            _ROWS[r],
            _COLS[c],
            _BOXES[(r // 3) * 3 + (c // 3)],
        ]
        for unit in units:
            locs = [
                (rr, cc)
                for rr, cc in unit
                if self.board[rr][cc] == 0 and d in candidates.get((rr, cc), [])
            ]
            if len(locs) == 1:
                pressure += 1.25
            elif locs:
                pressure += 0.2 / len(locs)
        return pressure

    def _field_energy(self, candidates: dict[tuple[int, int], list[int]]) -> float:
        # Lower is better: unsolved cells and wide candidate sets are high energy.
        return sum((len(cands) - 1) ** 2 + 1 for cands in candidates.values())

    def step(self) -> bool:
        """Run one iteration: swimmers explore, deposit, evaporate. Returns True when done."""
        if not self.empty_cells:
            return _is_valid_complete(self.board)

        self.iterations += 1
        self.swimmers.clear()
        candidates = self._candidate_map()
        self.energy = self._field_energy(candidates)

        if any(not cands for cands in candidates.values()):
            self.stalled = True
            self.last_event = "stalled_no_candidates"
            return False

        n_ants = min(len(self.empty_cells), 28)
        targets = random.sample(self.empty_cells, n_ants)

        # Evaporate first so stale trails decay unless refreshed by constraints.
        for r in range(9):
            for c in range(9):
                for d in range(9):
                    self.pheromone[r][c][d] *= (1.0 - self.evaporation)
                    self.pheromone[r][c][d] = max(0.01, self.pheromone[r][c][d])

        for r, c in targets:
            self.swimmers.append((r, c))
            cands = candidates.get((r, c), [])
            if not cands:
                continue

            scarcity = 1.0 / len(cands)
            for d in cands:
                pressure = scarcity + self._hidden_pressure(candidates, r, c, d)
                deposit = self.deposit_strength * pressure
                self.pheromone[r][c][d - 1] += deposit
                self.total_deposits += 1

        newly_solved: list[tuple[int, int, int, str]] = []
        claimed: set[tuple[int, int]] = set()
        for (r, c), cands in candidates.items():
            if len(cands) == 1:
                newly_solved.append((r, c, cands[0], "naked_single"))
                claimed.add((r, c))

        for r, c, d, reason in _hidden_single_moves(self.board, candidates):
            if (r, c) not in claimed:
                newly_solved.append((r, c, d, reason))
                claimed.add((r, c))

        for r, c, d, reason in newly_solved:
            if self.board[r][c] != 0:
                continue
            if d not in self._candidates(r, c):
                continue
            self.board[r][c] = d
            if (r, c) in self.empty_cells:
                self.empty_cells.remove((r, c))
            self.solved_cells += 1
            self.last_event = reason

        if not newly_solved:
            self.last_event = "foraging"
        return len(self.empty_cells) == 0 and _is_valid_complete(self.board)

    def max_pheromone_at(self, r: int, c: int) -> float:
        return max(self.pheromone[r][c])


def _board_hash(board: list[list[int]]) -> str:
    payload = json.dumps(board, sort_keys=True, separators=(",", ":"))
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _pheromone_mass(solver: _StigmergicSolver) -> float:
    return round(
        sum(sum(sum(cell) for cell in row) for row in solver.pheromone),
        3,
    )


def run_stigmergic_self_play(
    *,
    rounds: int = 3,
    clues: int = 32,
    max_steps: int = 220,
    seed: int | None = None,
) -> list[dict]:
    """Run two independent Sudoku swarms against each other as a race.

    Sudoku is not adversarial like Go, so "self-play" means two separate
    stigmergic fields receive the same puzzle and race to solve it. Both sides
    use only row/column/box constraints and their own pheromone deposits.
    Neither side receives the generated solution board.
    """

    rounds = max(1, int(rounds))
    clues = max(17, min(int(clues), 65))
    max_steps = max(1, int(max_steps))
    old_random_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    results: list[dict] = []
    try:
        for round_idx in range(1, rounds + 1):
            puzzle, _solution, given = _make_puzzle(clues)
            solvers = [
                ("alpha_swarm", _StigmergicSolver(puzzle)),
                ("beta_swarm", _StigmergicSolver(puzzle)),
            ]
            finished: dict[str, bool] = {}

            for _step_idx in range(1, max_steps + 1):
                for name, solver in solvers:
                    if name in finished:
                        continue
                    done = solver.step()
                    if done or solver.stalled:
                        finished[name] = bool(done)
                if len(finished) == len(solvers):
                    break

            sides: list[dict] = []
            for name, solver in solvers:
                valid = _is_valid_complete(solver.board)
                sides.append(
                    {
                        "name": name,
                        "solved": bool(valid),
                        "iterations": solver.iterations,
                        "deposits": solver.total_deposits,
                        "pheromone_mass": _pheromone_mass(solver),
                        "energy": round(solver.energy, 3),
                        "last_event": solver.last_event,
                        "stalled": solver.stalled,
                        "used_solution_oracle": solver.used_solution_oracle,
                        "solver_truth_label": solver.truth_label,
                    }
                )

            solved_sides = [s for s in sides if s["solved"]]
            if solved_sides:
                solved_sides.sort(key=lambda s: (int(s["iterations"]), int(s["deposits"]), str(s["name"])))
                winner = solved_sides[0]["name"]
            else:
                sides.sort(key=lambda s: (float(s["energy"]), -int(s["deposits"]), str(s["name"])))
                winner = sides[0]["name"]

            results.append(
                {
                    "truth_label": SELF_PLAY_TRUTH_LABEL,
                    "round": round_idx,
                    "puzzle_hash": _board_hash(puzzle),
                    "given_cells": len(given),
                    "max_steps": max_steps,
                    "mode": "two_independent_pheromone_fields_race_same_puzzle",
                    "winner": winner,
                    "sides": sides,
                    "used_solution_oracle": any(s["used_solution_oracle"] for s in sides),
                }
            )
    finally:
        random.setstate(old_random_state)
    return results


# ── Widget ───────────────────────────────────────────────────────────

_DIFFICULTY = {"Easy": 42, "Medium": 32, "Hard": 25, "Expert": 20}


class StigmergicSudokuWidget(QWidget):
    """Stigmergic Sudoku widget — ACO swarm + manual play.

    Single-instance per §7.6.2 (IDE_BOOT_COVENANT.md) with the hardened
    poisoned-singleton guard (id in _initialized_instance_ids) to guarantee
    that QWidget.__init__ / super().__init__ runs exactly once on every
    fresh instance, even when the App Store / desktop launcher or tests
    cause re-entrant __init__ or stale C++ objects.
    """
    _live_instance: Optional["StigmergicSudokuWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        # §7.6.2 + poisoned-singleton guard (exact pattern from TeachAceToReadWidget)
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()  # raises RuntimeError on deleted C++ side
                if id(existing) not in cls._initialized_instance_ids:
                    # Poisoned (previous __init__ never completed) — discard
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

    def __init__(self, parent=None):
        # Probe uses only the class set + id(self) — safe before super().__init__.
        # This is the only guard that prevents the "super-class __init__() of type
        # StigmergicSudokuWidget was never called" RuntimeError on fresh wrappers.
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._sudoku_initialized = True

        self.setWindowTitle("Stigmergic Sudoku")
        self.setMinimumSize(620, 720)
        self.setStyleSheet("background: transparent;")

        # game state
        self._puzzle: list[list[int]] = []
        self._solution: list[list[int]] = []
        self._board: list[list[int]] = []
        self._given: set[tuple[int, int]] = set()
        self._selected: tuple[int, int] | None = None
        self._errors: set[tuple[int, int]] = set()
        self._solver: _StigmergicSolver | None = None
        self._solving = False
        self._game_won = False
        self._start_time = 0.0
        self._elapsed = 0.0

        # ── layout ───────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self._diff_combo = QComboBox()
        self._diff_combo.addItems(list(_DIFFICULTY.keys()))
        self._diff_combo.setCurrentText("Medium")
        self._diff_combo.setFixedWidth(110)
        self._diff_combo.setStyleSheet(
            "QComboBox { background: #23253a; color: #ccd; border: 1px solid #555; "
            "border-radius: 6px; padding: 4px 8px; font-size: 13px; }"
        )
        bar.addWidget(self._diff_combo)

        for label, slot in [
            ("New Game", self._new_game),
            ("Swarm Solve", self._toggle_solve),
            ("Self-Play x3", self._run_self_play_demo),
            ("Check", self._check_board),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: #2e3050; color: #ccd; border: 1px solid #555; "
                "border-radius: 6px; padding: 4px 14px; font-size: 13px; }"
                "QPushButton:hover { background: #3e4070; }"
            )
            btn.clicked.connect(slot)
            bar.addWidget(btn)
            if label == "Swarm Solve":
                self._solve_btn = btn

        bar.addStretch()

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #9a8ccc; font-size: 12px;")
        bar.addWidget(self._status_lbl)

        self._timer_lbl = QLabel("00:00")
        self._timer_lbl.setStyleSheet("color: #7a7aaa; font-size: 12px; font-family: monospace;")
        bar.addWidget(self._timer_lbl)

        root.addLayout(bar)
        root.addStretch()

        # solve timer
        self._solve_timer = QTimer(self)
        self._solve_timer.setInterval(60)
        self._solve_timer.timeout.connect(self._solve_step)

        # clock timer
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)

        self._new_game()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── game logic ───────────────────────────────────────────────

    def _new_game(self):
        diff = self._diff_combo.currentText()
        clues = _DIFFICULTY.get(diff, 32)
        self._puzzle, self._solution, self._given = _make_puzzle(clues)
        actual_clues = len(self._given)
        self._board = deepcopy(self._puzzle)
        self._selected = None
        self._errors.clear()
        self._solver = None
        self._solving = False
        self._game_won = False
        self._solve_btn.setText("Swarm Solve")
        self._solve_timer.stop()
        self._start_time = time.time()
        self._elapsed = 0.0
        self._clock_timer.start()
        self._status_lbl.setText(f"{diff} — {sum(1 for r in self._board for v in r if v == 0)} empty")
        self._publish("new_game", {
            "difficulty": diff,
            "requested_clues": clues,
            "actual_clues": actual_clues,
            "oracle_available_to_solver": False,
        })
        self.update()

    def _toggle_solve(self):
        if self._game_won:
            return
        if self._solving:
            self._solving = False
            self._solve_timer.stop()
            self._solve_btn.setText("Swarm Solve")
            self._status_lbl.setText("Paused")
        else:
            if self._solver is None:
                self._solver = _StigmergicSolver(self._puzzle)
                self._solver.board = deepcopy(self._board)
                empty = [(r, c) for r in range(9) for c in range(9)
                         if self._board[r][c] == 0]
                self._solver.empty_cells = empty
            self._solving = True
            self._solve_timer.start()
            self._solve_btn.setText("Pause")
            self._status_lbl.setText("Swarm active…")
            self._publish("swarm_solve_started", {})

    def _solve_step(self):
        if not self._solver:
            return
        done = self._solver.step()
        for r in range(9):
            for c in range(9):
                if self._solver.board[r][c] and not self._board[r][c]:
                    self._board[r][c] = self._solver.board[r][c]

        empty = sum(1 for r in self._board for v in r if v == 0)
        self._status_lbl.setText(
            f"Iter {self._solver.iterations} · {self._solver.solved_cells} placed · "
            f"{empty} left · {self._solver.total_deposits} deposits · E={self._solver.energy:.0f}"
        )
        if self._solver.stalled:
            self._solving = False
            self._solve_timer.stop()
            self._solve_btn.setText("Swarm Solve")
            self._status_lbl.setText(
                f"Swarm stalled · {empty} left · last={self._solver.last_event}"
            )
            self._write_receipt("swarm_stalled", {
                "iterations": self._solver.iterations,
                "deposits": self._solver.total_deposits,
                "empty_cells": empty,
                "energy": round(self._solver.energy, 3),
                "last_event": self._solver.last_event,
                "used_solution_oracle": self._solver.used_solution_oracle,
                "solver_truth_label": self._solver.truth_label,
            })
        if done:
            self._solving = False
            self._solve_timer.stop()
            self._solve_btn.setText("Swarm Solve")
            self._game_won = True
            self._clock_timer.stop()
            self._status_lbl.setText(
                f"Solved in {self._solver.iterations} iterations "
                f"· {self._solver.total_deposits} pheromone deposits"
            )
            self._publish("swarm_solved", {
                "iterations": self._solver.iterations,
                "deposits": self._solver.total_deposits,
                "used_solution_oracle": self._solver.used_solution_oracle,
                "solver_truth_label": self._solver.truth_label,
            })
            self._write_receipt("swarm_solve", {
                "iterations": self._solver.iterations,
                "deposits": self._solver.total_deposits,
                "elapsed_s": round(self._elapsed, 1),
                "energy": round(self._solver.energy, 3),
                "last_event": self._solver.last_event,
                "used_solution_oracle": self._solver.used_solution_oracle,
                "solver_truth_label": self._solver.truth_label,
            })
        self.update()

    def _check_board(self):
        self._errors.clear()
        for r in range(9):
            for c in range(9):
                v = self._board[r][c]
                if v and v != self._solution[r][c]:
                    self._errors.add((r, c))
        if self._errors:
            self._status_lbl.setText(f"{len(self._errors)} error(s)")
        elif all(self._board[r][c] != 0 for r in range(9) for c in range(9)):
            self._game_won = True
            self._clock_timer.stop()
            self._status_lbl.setText("Solved!")
            self._publish("manual_solved", {"elapsed_s": round(self._elapsed, 1)})
            self._write_receipt("manual_solve", {"elapsed_s": round(self._elapsed, 1)})
        else:
            self._status_lbl.setText("No errors so far")
        self.update()

    def _run_self_play_demo(self):
        diff = self._diff_combo.currentText()
        clues = _DIFFICULTY.get(diff, 32)
        seed = int(time.time() * 1000) & 0xFFFFFFFF
        results = run_stigmergic_self_play(rounds=3, clues=clues, max_steps=220, seed=seed)
        solved_sides = sum(1 for row in results for side in row["sides"] if side["solved"])
        winners = ", ".join(str(row.get("winner")) for row in results)
        self._status_lbl.setText(f"Self-play x3 · {solved_sides}/6 swarms solved · winners: {winners}")
        self._publish("self_play_x3", {
            "difficulty": diff,
            "rounds": len(results),
            "solved_sides": solved_sides,
            "used_solution_oracle": any(row["used_solution_oracle"] for row in results),
            "truth_label": SELF_PLAY_TRUTH_LABEL,
        })
        self._write_receipt("self_play_x3", {
            "difficulty": diff,
            "rounds": len(results),
            "seed": seed,
            "solved_sides": solved_sides,
            "used_solution_oracle": any(row["used_solution_oracle"] for row in results),
            "self_play_truth_label": SELF_PLAY_TRUTH_LABEL,
            "results": results,
        })
        self.update()

    def _tick_clock(self):
        self._elapsed = time.time() - self._start_time
        m, s = divmod(int(self._elapsed), 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    # ── input ────────────────────────────────────────────────────

    def _grid_rect(self) -> QRectF:
        w = self.width() - 32
        h = self.height() - 80
        side = min(w, h)
        x = (self.width() - side) / 2
        y = 56
        return QRectF(x, y, side, side)

    def _cell_at(self, px: float, py: float) -> tuple[int, int] | None:
        gr = self._grid_rect()
        if not gr.contains(QPointF(px, py)):
            return None
        cell = gr.width() / 9
        c = int((px - gr.x()) / cell)
        r = int((py - gr.y()) / cell)
        if 0 <= r < 9 and 0 <= c < 9:
            return r, c
        return None

    def mousePressEvent(self, ev):
        pos = self._cell_at(ev.position().x(), ev.position().y())
        if pos and pos not in self._given and not self._game_won:
            self._selected = pos
            self.update()
        super().mousePressEvent(ev)

    def keyPressEvent(self, ev):
        if self._selected is None or self._game_won:
            super().keyPressEvent(ev)
            return
        r, c = self._selected
        if (r, c) in self._given:
            super().keyPressEvent(ev)
            return

        key = ev.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            digit = key - Qt.Key.Key_1 + 1
            self._board[r][c] = digit
            self._errors.discard((r, c))
            empty = sum(1 for rr in range(9) for cc in range(9) if self._board[rr][cc] == 0)
            self._status_lbl.setText(f"{empty} empty")
            self.update()
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_0):
            self._board[r][c] = 0
            self._errors.discard((r, c))
            self.update()
        elif key == Qt.Key.Key_Up and r > 0:
            self._selected = (r - 1, c)
            self.update()
        elif key == Qt.Key.Key_Down and r < 8:
            self._selected = (r + 1, c)
            self.update()
        elif key == Qt.Key.Key_Left and c > 0:
            self._selected = (r, c - 1)
            self.update()
        elif key == Qt.Key.Key_Right and c < 8:
            self._selected = (r, c + 1)
            self.update()
        else:
            super().keyPressEvent(ev)

    # ── painting ─────────────────────────────────────────────────

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # background
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, _BG_DARK)
        bg.setColorAt(1, QColor(12, 12, 22))
        p.fillRect(self.rect(), bg)

        gr = self._grid_rect()
        cell_w = gr.width() / 9
        cell_h = gr.height() / 9

        # pheromone heat layer
        if self._solver and self._solving:
            max_ph = 1.0
            for r, c in self._solver.empty_cells:
                v = self._solver.max_pheromone_at(r, c)
                if v > max_ph:
                    max_ph = v
            for r in range(9):
                for c in range(9):
                    if (r, c) in self._given or self._board[r][c] != 0:
                        continue
                    v = self._solver.max_pheromone_at(r, c)
                    t = min(v / max(max_ph, 1.0), 1.0)
                    if t > 0.05:
                        cx = gr.x() + c * cell_w + cell_w / 2
                        cy = gr.y() + r * cell_h + cell_h / 2
                        rad = QRadialGradient(QPointF(cx, cy), cell_w * 0.6)
                        col = _lerp_color(_PHERO_LOW, _PHERO_HIGH, t)
                        rad.setColorAt(0, col)
                        rad.setColorAt(1, QColor(0, 0, 0, 0))
                        p.setBrush(QBrush(rad))
                        p.setPen(Qt.PenStyle.NoPen)
                        p.drawRect(QRectF(
                            gr.x() + c * cell_w, gr.y() + r * cell_h,
                            cell_w, cell_h,
                        ))

        # cell backgrounds
        for r in range(9):
            for c in range(9):
                rect = QRectF(gr.x() + c * cell_w, gr.y() + r * cell_h, cell_w, cell_h)
                if (r, c) in self._given:
                    p.fillRect(rect, _BG_CELL_GIVEN)
                else:
                    p.fillRect(rect, _BG_CELL)

        # selected cell highlight
        if self._selected:
            sr, sc = self._selected
            rect = QRectF(gr.x() + sc * cell_w, gr.y() + sr * cell_h, cell_w, cell_h)
            p.setPen(QPen(_SELECT_RING, 2.5))
            p.setBrush(QColor(160, 120, 255, 30))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        # error cells
        for r, c in self._errors:
            rect = QRectF(gr.x() + c * cell_w, gr.y() + r * cell_h, cell_w, cell_h)
            p.fillRect(rect, QColor(255, 50, 50, 35))

        # grid lines
        thin_pen = QPen(_GRID_LINE, 1)
        thick_pen = QPen(_GRID_THICK, 2.5)
        for i in range(10):
            pen = thick_pen if i % 3 == 0 else thin_pen
            p.setPen(pen)
            x = gr.x() + i * cell_w
            p.drawLine(QPointF(x, gr.y()), QPointF(x, gr.y() + gr.height()))
            y = gr.y() + i * cell_h
            p.drawLine(QPointF(gr.x(), y), QPointF(gr.x() + gr.width(), y))

        # digits
        font_size = max(10, int(cell_w * 0.48))
        font = QFont("Menlo", font_size)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        for r in range(9):
            for c in range(9):
                v = self._board[r][c]
                if v == 0:
                    continue
                rect = QRectF(gr.x() + c * cell_w, gr.y() + r * cell_h, cell_w, cell_h)
                if (r, c) in self._errors:
                    p.setPen(_TEXT_ERROR)
                elif (r, c) in self._given:
                    p.setPen(_TEXT_GIVEN)
                else:
                    p.setPen(_TEXT_USER)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(v))

        # swimmer dots
        if self._solver and self._solving:
            p.setPen(Qt.PenStyle.NoPen)
            for r, c in self._solver.swimmers:
                cx = gr.x() + c * cell_w + cell_w / 2
                cy = gr.y() + r * cell_h + cell_h / 2
                rad = QRadialGradient(QPointF(cx, cy), cell_w * 0.18)
                rad.setColorAt(0, _SWIMMER_DOT)
                rad.setColorAt(1, QColor(255, 200, 80, 0))
                p.setBrush(QBrush(rad))
                p.drawEllipse(QPointF(cx, cy), cell_w * 0.12, cell_h * 0.12)

        # win banner
        if self._game_won:
            banner_h = 48
            banner_y = gr.y() + gr.height() / 2 - banner_h / 2
            p.fillRect(QRectF(gr.x(), banner_y, gr.width(), banner_h),
                       QColor(20, 20, 40, 220))
            p.setPen(QPen(_ACCENT, 1))
            win_font = QFont("Menlo", 22, QFont.Weight.Bold)
            p.setFont(win_font)
            p.drawText(QRectF(gr.x(), banner_y, gr.width(), banner_h),
                       Qt.AlignmentFlag.AlignCenter, "SOLVED")

        p.end()

    # ── focus + receipt ──────────────────────────────────────────

    def _publish(self, detail: str, meta: dict):
        if _publish_focus:
            try:
                _publish_focus("Stigmergic Sudoku", detail, metadata=meta)
            except Exception:
                pass

    def _write_receipt(self, action: str, data: dict):
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "app": "Stigmergic Sudoku",
            "action": action,
            "truth_label": TRUTH_LABEL,
            **data,
        }
        try:
            with open(_STATE / "sudoku_receipts.jsonl", "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    # ── lifecycle ────────────────────────────────────────────────

    def closeEvent(self, event):
        self._solve_timer.stop()
        self._clock_timer.stop()
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        # Remove from initialized set so a future fresh construction is not
        # incorrectly treated as re-entry (matches hardened §7.6.2 pattern).
        try:
            type(self)._initialized_instance_ids.discard(id(self))
        except Exception:
            pass
        super().closeEvent(event)


# ── standalone launch ────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = StigmergicSudokuWidget()
    w.resize(660, 760)
    w.show()
    sys.exit(app.exec())
