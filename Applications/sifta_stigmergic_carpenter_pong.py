#!/usr/bin/env python3
"""SURGERY HISTORY — not the App Store launcher entry.

Canonical R1625 game (open this from Games):
  Applications/sifta_stigmergic_pong.py
  System/swarm_stigmergic_pong.py
  Manifest name: "Stigmergic Carpenter Pong"
  truth_label: STIGMERGIC_CARPENTER_PONG_V2

This V1 file (Grok prototype + Claude miss-score fix) is kept for regression
tests and history only. Do not re-register it in apps_manifest.

---
V1 notes: two swarms vote paddles (SIGGRAPH '91 → Alice body).
Truth label: STIGMERGIC_CARPENTER_PONG_V1
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
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

APP_TITLE = "Stigmergic Carpenter Pong"
APP_ID = "sifta_stigmergic_carpenter_pong"
TRUTH_LABEL = "STIGMERGIC_CARPENTER_PONG_V1"

# Court in logical units
COURT_W = 800.0
COURT_H = 480.0
PADDLE_W = 14.0
PADDLE_H = 90.0
BALL_R = 9.0
SWARM_SIZE = 48  # voters per side (Carpenter hall miniature)

_BG = QColor(8, 10, 18)
_COURT = QColor(14, 18, 30)
_LINE = QColor(55, 70, 100)
_TEXT = QColor(220, 228, 245)
_DIM = QColor(130, 145, 175)
_ACCENT = QColor(75, 235, 190)
_LEFT = QColor(255, 90, 100)  # red paddles / swarm
_RIGHT = QColor(70, 210, 255)  # cyan paddles / swarm
_BALL = QColor(255, 230, 120)
_PHERO = QColor(80, 255, 200, 40)


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
        with (_STATE / "carpenter_pong_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Engine — pure, testable without Qt
# ---------------------------------------------------------------------------


@dataclass
class Swimmer:
    """One voter. Unique id (crypto-rhyme uniqueness — not melt-mergeable)."""

    swimmer_id: str
    side: str  # "left" | "right"
    bias: float = 0.0  # individual quirk ∈ [-1,1]
    last_vote: float = 0.0  # -1 down, +1 up
    energy: float = 1.0


@dataclass
class CarpenterPongEngine:
    """Two swarms vote paddles; ball is the shared display (the hall screen)."""

    swarm_size: int = SWARM_SIZE
    left_swimmers: list[Swimmer] = field(default_factory=list)
    right_swimmers: list[Swimmer] = field(default_factory=list)
    # paddle centers y
    left_y: float = COURT_H / 2
    right_y: float = COURT_H / 2
    ball_x: float = COURT_W / 2
    ball_y: float = COURT_H / 2
    ball_vx: float = 5.2
    ball_vy: float = 3.1
    score_left: int = 0
    score_right: int = 0
    tick: int = 0
    last_left_votes_up: int = 0
    last_left_votes_down: int = 0
    last_right_votes_up: int = 0
    last_right_votes_down: int = 0
    # field: simple vertical pheromone bias per side (evaporates)
    left_field: float = 0.0
    right_field: float = 0.0
    noise: float = 0.35
    max_paddle_speed: float = 14.0

    def reset_match(self, *, seed: Optional[int] = None) -> None:
        if seed is not None:
            random.seed(seed)
        self.left_swimmers = [
            Swimmer(
                swimmer_id=f"L-{i:03d}-{uuid.uuid4().hex[:6]}",
                side="left",
                bias=random.uniform(-0.4, 0.4),
            )
            for i in range(self.swarm_size)
        ]
        self.right_swimmers = [
            Swimmer(
                swimmer_id=f"R-{i:03d}-{uuid.uuid4().hex[:6]}",
                side="right",
                bias=random.uniform(-0.4, 0.4),
            )
            for i in range(self.swarm_size)
        ]
        self.left_y = COURT_H / 2
        self.right_y = COURT_H / 2
        self.ball_x = COURT_W / 2
        self.ball_y = COURT_H / 2
        self.ball_vx = random.choice([-1.0, 1.0]) * 5.2
        self.ball_vy = random.uniform(-3.5, 3.5)
        self.score_left = 0
        self.score_right = 0
        self.tick = 0
        self.left_field = 0.0
        self.right_field = 0.0

    def _swarm_vote(self, side: str) -> float:
        """Return desired dy for paddle: average of local swimmer votes.

        Each swimmer votes UP (+1) or DOWN (-1) from:
          - ball relative to own paddle (local sense)
          - personal bias
          - side pheromone field (shared memory, not a boss script)
          - noise (stigmergic messiness)
        Carpenter: paddle = aggregate of many simple paddles.
        """
        swimmers = self.left_swimmers if side == "left" else self.right_swimmers
        paddle_y = self.left_y if side == "left" else self.right_y
        field = self.left_field if side == "left" else self.right_field
        up = down = 0
        total = 0.0
        for s in swimmers:
            if s.energy <= 0.05:
                s.last_vote = 0.0
                continue
            err = self.ball_y - paddle_y
            # local gradient toward ball + field + bias + noise
            signal = (
                0.55 * math.tanh(err / 60.0)
                + 0.25 * field
                + 0.15 * s.bias
                + self.noise * random.uniform(-1.0, 1.0)
            )
            vote = 1.0 if signal >= 0 else -1.0
            s.last_vote = vote
            s.energy = max(0.2, s.energy - 0.0008)
            total += vote
            if vote > 0:
                up += 1
            else:
                down += 1
        n = max(1, up + down)
        if side == "left":
            self.last_left_votes_up, self.last_left_votes_down = up, down
        else:
            self.last_right_votes_up, self.last_right_votes_down = up, down
        # vote average in [-1,1] → paddle velocity
        avg = total / n
        # reinforce field toward recent successful direction (deposit)
        if side == "left":
            self.left_field = 0.92 * self.left_field + 0.08 * avg
        else:
            self.right_field = 0.92 * self.right_field + 0.08 * avg
        return avg * self.max_paddle_speed

    def step(self) -> dict[str, Any]:
        self.tick += 1
        # evaporate field slightly
        self.left_field *= 0.995
        self.right_field *= 0.995

        ldy = self._swarm_vote("left")
        rdy = self._swarm_vote("right")
        half = PADDLE_H / 2
        self.left_y = min(COURT_H - half, max(half, self.left_y + ldy))
        self.right_y = min(COURT_H - half, max(half, self.right_y + rdy))

        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        # walls
        if self.ball_y - BALL_R <= 0:
            self.ball_y = BALL_R
            self.ball_vy = abs(self.ball_vy)
        elif self.ball_y + BALL_R >= COURT_H:
            self.ball_y = COURT_H - BALL_R
            self.ball_vy = -abs(self.ball_vy)

        scored = ""
        # left paddle collision — bounce only while the ball overlaps the paddle
        # band (x ∈ [28, 28+PADDLE_W]); once past it, the miss must reach the goal
        if (
            self.ball_vx < 0
            and self.ball_x - BALL_R <= 28 + PADDLE_W
            and self.ball_x + BALL_R >= 28
            and abs(self.ball_y - self.left_y) <= half + BALL_R
        ):
            self.ball_x = 28 + PADDLE_W + BALL_R
            self.ball_vx = abs(self.ball_vx) * 1.02
            self.ball_vy += (self.ball_y - self.left_y) * 0.06
            self.left_field += 0.15  # success deposit
        if self.ball_x + BALL_R < 0:
            self.score_right += 1
            scored = "right"
            self._serve(direction=1.0)

        # right paddle
        if (
            self.ball_vx > 0
            and self.ball_x + BALL_R >= COURT_W - 28 - PADDLE_W
            and self.ball_x - BALL_R <= COURT_W - 28
            and abs(self.ball_y - self.right_y) <= half + BALL_R
        ):
            self.ball_x = COURT_W - 28 - PADDLE_W - BALL_R
            self.ball_vx = -abs(self.ball_vx) * 1.02
            self.ball_vy += (self.ball_y - self.right_y) * 0.06
            self.right_field += 0.15
        if self.ball_x - BALL_R > COURT_W:
            self.score_left += 1
            scored = "left"
            self._serve(direction=-1.0)

        # cap speed
        sp = math.hypot(self.ball_vx, self.ball_vy)
        if sp > 14:
            self.ball_vx *= 14 / sp
            self.ball_vy *= 14 / sp

        return {
            "tick": self.tick,
            "score_left": self.score_left,
            "score_right": self.score_right,
            "scored": scored,
            "left_votes": (self.last_left_votes_up, self.last_left_votes_down),
            "right_votes": (self.last_right_votes_up, self.last_right_votes_down),
            "left_field": round(self.left_field, 3),
            "right_field": round(self.right_field, 3),
        }

    def _serve(self, direction: float) -> None:
        self.ball_x = COURT_W / 2
        self.ball_y = COURT_H / 2
        self.ball_vx = direction * 5.0
        self.ball_vy = random.uniform(-3.2, 3.2)

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "score": [self.score_left, self.score_right],
            "ball": [round(self.ball_x, 1), round(self.ball_y, 1)],
            "paddles": [round(self.left_y, 1), round(self.right_y, 1)],
            "swarm_size": self.swarm_size,
            "left_votes": [self.last_left_votes_up, self.last_left_votes_down],
            "right_votes": [self.last_right_votes_up, self.last_right_votes_down],
            "unique_left_ids": len({s.swimmer_id for s in self.left_swimmers}),
            "unique_right_ids": len({s.swimmer_id for s in self.right_swimmers}),
        }


# ---------------------------------------------------------------------------
# Qt canvas + widget
# ---------------------------------------------------------------------------


class _CourtCanvas(QWidget):
    def __init__(self, engine: CarpenterPongEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumSize(520, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, _BG)

        # court rect with margin
        m = 16
        cw, ch = w - 2 * m, h - 2 * m
        sx, sy = cw / COURT_W, ch / COURT_H
        p.fillRect(m, m, int(cw), int(ch), _COURT)

        def tx(x: float) -> float:
            return m + x * sx

        def ty(y: float) -> float:
            return m + y * sy

        # center line
        pen = QPen(_LINE, 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(int(tx(COURT_W / 2)), m, int(tx(COURT_W / 2)), m + int(ch))

        e = self.engine
        # vote bars (Carpenter crowd visible as up/down stacks)
        bar_w = 8
        lu, ld = e.last_left_votes_up, e.last_left_votes_down
        ru, rd = e.last_right_votes_up, e.last_right_votes_down
        max_v = max(1, e.swarm_size)
        # left swarm vote bars near left edge
        p.fillRect(2, m, bar_w, int(ch * lu / max_v), _LEFT)
        p.fillRect(2, m + int(ch) - int(ch * ld / max_v), bar_w, int(ch * ld / max_v), QColor(120, 40, 50))
        p.fillRect(w - 2 - bar_w, m, bar_w, int(ch * ru / max_v), _RIGHT)
        p.fillRect(
            w - 2 - bar_w,
            m + int(ch) - int(ch * rd / max_v),
            bar_w,
            int(ch * rd / max_v),
            QColor(30, 80, 110),
        )

        # paddles
        half = PADDLE_H / 2
        p.setBrush(QBrush(_LEFT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(
            QRectF(tx(28), ty(e.left_y - half), PADDLE_W * sx, PADDLE_H * sy),
            4,
            4,
        )
        p.setBrush(QBrush(_RIGHT))
        p.drawRoundedRect(
            QRectF(
                tx(COURT_W - 28 - PADDLE_W),
                ty(e.right_y - half),
                PADDLE_W * sx,
                PADDLE_H * sy,
            ),
            4,
            4,
        )

        # ball
        grad = QRadialGradient(tx(e.ball_x), ty(e.ball_y), BALL_R * max(sx, sy) * 1.4)
        grad.setColorAt(0.0, QColor(255, 250, 200))
        grad.setColorAt(1.0, _BALL)
        p.setBrush(QBrush(grad))
        r = BALL_R * max(sx, sy)
        p.drawEllipse(QRectF(tx(e.ball_x) - r, ty(e.ball_y) - r, 2 * r, 2 * r))

        # score
        p.setPen(_TEXT)
        p.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        p.drawText(int(tx(COURT_W / 2 - 80)), m + 28, str(e.score_left))
        p.drawText(int(tx(COURT_W / 2 + 60)), m + 28, str(e.score_right))
        p.end()


class StigmergicCarpenterPongWidget(QWidget):
    """SIFTA OS Games — auto-play stigmergic Carpenter Pong."""

    _live_instance: Optional["StigmergicCarpenterPongWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(APP_ID)
        self.setWindowTitle(APP_TITLE)
        self.engine = CarpenterPongEngine()
        self.engine.reset_match()
        self._auto = True
        self._ticks = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel(f"🎮 {APP_TITLE}")
        title.setStyleSheet(f"color: rgb({_ACCENT.red()},{_ACCENT.green()},{_ACCENT.blue()}); font-size: 16px; font-weight: 700;")
        root.addWidget(title)

        map_lbl = QLabel(
            "Carpenter hall 1991 → Alice body: red/green paddles = unique swimmers · "
            "screen paddle = vote average · shared field = STGM-style truth surface · "
            "no boss script — local sense + pheromone only. Auto two-swarm match."
        )
        map_lbl.setWordWrap(True)
        map_lbl.setStyleSheet(f"color: rgb({_DIM.red()},{_DIM.green()},{_DIM.blue()}); font-size: 11px;")
        root.addWidget(map_lbl)

        self._canvas = _CourtCanvas(self.engine)
        root.addWidget(self._canvas, stretch=1)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: rgb({_TEXT.red()},{_TEXT.green()},{_TEXT.blue()}); font-size: 12px;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        row = QHBoxLayout()
        self._btn_auto = QPushButton("Pause ⏸")
        self._btn_auto.clicked.connect(self._toggle_auto)
        self._btn_step = QPushButton("Step")
        self._btn_step.clicked.connect(self._step_once)
        self._btn_reset = QPushButton("New match")
        self._btn_reset.clicked.connect(self._new_match)
        for b in (self._btn_auto, self._btn_step, self._btn_reset):
            b.setStyleSheet(
                "QPushButton { background: #1a2030; color: #dce4f5; border: 1px solid #3a4560; "
                "padding: 6px 12px; border-radius: 6px; } "
                "QPushButton:hover { border-color: #4bebbf; }"
            )
            row.addWidget(b)
        row.addStretch(1)
        noise_lbl = QLabel("noise")
        noise_lbl.setStyleSheet(f"color: rgb({_DIM.red()},{_DIM.green()},{_DIM.blue()});")
        row.addWidget(noise_lbl)
        self._noise = QSlider(Qt.Orientation.Horizontal)
        self._noise.setRange(0, 100)
        self._noise.setValue(35)
        self._noise.setFixedWidth(100)
        self._noise.valueChanged.connect(self._on_noise)
        row.addWidget(self._noise)
        root.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(28)  # ~35 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._update_status()
        _write_receipt("open", {"swarm_size": self.engine.swarm_size})
        _publish_app_focus("Carpenter Pong auto-swarm match open")

        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

    def _on_noise(self, v: int) -> None:
        self.engine.noise = v / 100.0

    def _toggle_auto(self) -> None:
        self._auto = not self._auto
        if self._auto:
            self._timer.start()
            self._btn_auto.setText("Pause ⏸")
        else:
            self._timer.stop()
            self._btn_auto.setText("Auto ▶")
        _write_receipt("auto_toggle", {"auto": self._auto})

    def _step_once(self) -> None:
        info = self.engine.step()
        self._ticks += 1
        self._canvas.update()
        self._update_status(info)
        if info.get("scored"):
            _write_receipt("score", info)

    def _tick(self) -> None:
        if not self._auto:
            return
        info = self.engine.step()
        self._ticks += 1
        self._canvas.update()
        if self._ticks % 8 == 0:
            self._update_status(info)
        if info.get("scored"):
            _write_receipt("score", info)
            _publish_app_focus(
                f"score L{info['score_left']}-R{info['score_right']}"
            )

    def _new_match(self) -> None:
        self.engine.reset_match()
        self._ticks = 0
        self._canvas.update()
        self._update_status()
        _write_receipt("new_match", self.engine.snapshot())
        _publish_app_focus("new Carpenter Pong match")

    def _update_status(self, info: Optional[dict] = None) -> None:
        e = self.engine
        lu, ld = e.last_left_votes_up, e.last_left_votes_down
        ru, rd = e.last_right_votes_up, e.last_right_votes_down
        self._status.setText(
            f"LEFT swarm (red) votes ↑{lu} ↓{ld}  ·  RIGHT swarm (cyan) ↑{ru} ↓{rd}  ·  "
            f"unique swimmers L={len(e.left_swimmers)} R={len(e.right_swimmers)}  ·  "
            f"field L={e.left_field:+.2f} R={e.right_field:+.2f}  ·  tick {e.tick}  ·  "
            f"score {e.score_left}–{e.score_right}  ·  auto={'on' if self._auto else 'off'}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        _write_receipt("close", self.engine.snapshot())
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)


# Alias for manifest widget_class flexibility
CarpenterPongWidget = StigmergicCarpenterPongWidget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = StigmergicCarpenterPongWidget()
    win.resize(720, 520)
    win.show()
    sys.exit(app.exec())
