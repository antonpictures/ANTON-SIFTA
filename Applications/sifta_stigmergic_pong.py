#!/usr/bin/env python3
"""Stigmergic Carpenter Pong - two autonomous Carpenter-style swarms."""

from __future__ import annotations

import json
import math
import sys
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

from System.swarm_stigmergic_pong import (  # noqa: E402
    BALL_RADIUS,
    FIELD_BINS,
    PADDLE_HALF_HEIGHT,
    PADDLE_LEFT_X,
    PADDLE_RIGHT_X,
    StigmergicPongSimulation,
    SwarmState,
    TRUTH_LABEL,
)
from System.swarm_stigmergic_pong_chorus import (  # noqa: E402
    ask_local_ollama,
    build_chorus_prompt,
    canonical_stgm_read_only,
)

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover
    _publish_focus = None  # type: ignore[assignment]


APP_TITLE = "Stigmergic Carpenter Pong"
APP_ID = "sifta_stigmergic_pong"

BG_TOP = QColor(6, 9, 16)
BG_BOTTOM = QColor(15, 18, 29)
COURT = QColor(19, 25, 38)
LINE = QColor(107, 124, 151, 90)
TEXT = QColor(229, 235, 244)
DIM = QColor(145, 157, 178)
RED = QColor(244, 83, 78)
RED_HOT = QColor(255, 183, 91)
GREEN = QColor(73, 224, 153)
GREEN_HOT = QColor(76, 220, 242)
BALL = QColor(255, 239, 158)


def _write_receipt(event: str, payload: dict) -> str:
    receipt_id = f"carpenter-pong-{uuid.uuid4().hex[:12]}"
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
        "app": APP_TITLE,
        "event": event,
        **payload,
    }
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        path = _STATE / "carpenter_pong_receipts.jsonl"
        if append_line_locked is not None:
            append_line_locked(path, line)
        else:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except Exception:
        pass
    return receipt_id


def _focus(detail: str, metadata: Optional[dict] = None) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, metadata=metadata or {})
    except TypeError:
        try:
            _publish_focus(title=APP_TITLE, detail=detail, app_id=APP_ID)
        except Exception:
            pass
    except Exception:
        pass


class _PongCanvas(QWidget):
    def __init__(self, owner: "StigmergicPongWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMinimumSize(820, 510)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _court_rect(self) -> QRectF:
        return QRectF(28.0, 48.0, max(1.0, self.width() - 56.0), max(1.0, self.height() - 86.0))

    @staticmethod
    def _point(court: QRectF, x: float, y: float) -> QPointF:
        return QPointF(court.left() + x * court.width(), court.top() + y * court.height())

    def paintEvent(self, _event) -> None:
        sim = self.owner.sim
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, BG_TOP)
        bg.setColorAt(1.0, BG_BOTTOM)
        painter.fillRect(self.rect(), bg)

        court = self._court_rect()
        court_grad = QLinearGradient(court.topLeft(), court.bottomRight())
        court_grad.setColorAt(0.0, COURT)
        court_grad.setColorAt(1.0, QColor(12, 17, 27))
        painter.setBrush(QBrush(court_grad))
        painter.setPen(QPen(QColor(95, 111, 139), 1.2))
        painter.drawRoundedRect(court, 6, 6)

        self._draw_court_lines(painter, court)
        if self.owner.show_field:
            self._draw_field(painter, court, sim.left, RED, 0.108)
            self._draw_field(painter, court, sim.right, GREEN, 0.892)
        self._draw_crowd(painter, court, sim.left, RED, RED_HOT)
        self._draw_crowd(painter, court, sim.right, GREEN, GREEN_HOT)
        self._draw_paddle(painter, court, sim.left, RED, RED_HOT, PADDLE_LEFT_X)
        self._draw_paddle(painter, court, sim.right, GREEN, GREEN_HOT, PADDLE_RIGHT_X)
        self._draw_ball(painter, court)
        self._draw_score(painter, court)
        self._draw_vote_balance(painter, court, sim.left, RED, court.left() + court.width() * 0.21)
        self._draw_vote_balance(painter, court, sim.right, GREEN, court.left() + court.width() * 0.71)
        self._draw_digest(painter, court)
        painter.end()

    def _draw_court_lines(self, painter: QPainter, court: QRectF) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(LINE, 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(court.center().x(), court.top()), QPointF(court.center().x(), court.bottom()))
        radius = min(court.width(), court.height()) * 0.10
        painter.drawEllipse(court.center(), radius, radius)
        painter.setPen(QPen(QColor(74, 88, 112, 45), 1))
        for index in range(1, 10):
            x = court.left() + court.width() * index / 10.0
            painter.drawLine(QPointF(x, court.top()), QPointF(x, court.bottom()))
        for index in range(1, 6):
            y = court.top() + court.height() * index / 6.0
            painter.drawLine(QPointF(court.left(), y), QPointF(court.right(), y))

    def _draw_field(
        self,
        painter: QPainter,
        court: QRectF,
        swarm: SwarmState,
        color: QColor,
        x_norm: float,
    ) -> None:
        max_value = max(max(swarm.pheromone), 0.001)
        strip_w = max(8.0, court.width() * 0.014)
        cell_h = court.height() / FIELD_BINS
        x = court.left() + x_norm * court.width() - strip_w / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        for index, value in enumerate(swarm.pheromone):
            strength = min(1.0, value / max_value)
            if strength <= 0.015:
                continue
            alpha = int(20 + 190 * math.sqrt(strength))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
            painter.drawRoundedRect(
                QRectF(x, court.top() + index * cell_h, strip_w, max(1.0, cell_h + 0.5)),
                1.5,
                1.5,
            )

    def _draw_crowd(
        self,
        painter: QPainter,
        court: QRectF,
        swarm: SwarmState,
        base: QColor,
        hot: QColor,
    ) -> None:
        left_side = swarm.side == "left"
        rail_x = court.left() + court.width() * (0.018 if left_side else 0.958)
        rail_w = court.width() * 0.025
        columns = 4
        rows = max(1, math.ceil(len(swarm.swimmers) / columns))
        dot = max(1.7, min(4.0, court.height() / max(34.0, rows * 2.2)))
        painter.setPen(Qt.PenStyle.NoPen)
        for index, swimmer in enumerate(swarm.swimmers):
            column = index % columns
            row = index // columns
            x = rail_x + (column / max(1, columns - 1)) * rail_w
            y = court.top() + (row + 0.7) / (rows + 0.4) * court.height()
            vote = swarm.last_votes[index] if index < len(swarm.last_votes) else 0
            mix = 0.76 if vote else 0.30
            color = QColor(
                int(base.red() * (1 - mix) + hot.red() * mix),
                int(base.green() * (1 - mix) + hot.green() * mix),
                int(base.blue() * (1 - mix) + hot.blue() * mix),
                225 if vote else 95,
            )
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), dot, dot)

    def _draw_paddle(
        self,
        painter: QPainter,
        court: QRectF,
        swarm: SwarmState,
        base: QColor,
        hot: QColor,
        x_norm: float,
    ) -> None:
        center = self._point(court, x_norm, swarm.paddle_y)
        width = max(9.0, court.width() * 0.012)
        height = court.height() * PADDLE_HALF_HEIGHT * 2.0
        glow = QRadialGradient(center, height * 0.8)
        glow.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 100))
        glow.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, height * 0.75, height * 0.75)
        gradient = QLinearGradient(center.x() - width, center.y(), center.x() + width, center.y())
        gradient.setColorAt(0.0, base)
        gradient.setColorAt(1.0, hot)
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 170), 1))
        painter.drawRoundedRect(
            QRectF(center.x() - width / 2.0, center.y() - height / 2.0, width, height),
            width / 2.0,
            width / 2.0,
        )

    def _draw_ball(self, painter: QPainter, court: QRectF) -> None:
        trail = self.owner.sim.ball_trail
        painter.setPen(Qt.PenStyle.NoPen)
        for index, (x, y) in enumerate(trail[:-1]):
            alpha = int(12 + 90 * (index + 1) / max(1, len(trail)))
            point = self._point(court, x, y)
            painter.setBrush(QColor(BALL.red(), BALL.green(), BALL.blue(), alpha))
            radius = 2.0 + 2.0 * (index + 1) / max(1, len(trail))
            painter.drawEllipse(point, radius, radius)
        ball = self.owner.sim.ball
        point = self._point(court, ball.x, ball.y)
        radius = max(5.0, min(court.width(), court.height()) * BALL_RADIUS)
        glow = QRadialGradient(point, radius * 3.2)
        glow.setColorAt(0.0, QColor(BALL.red(), BALL.green(), BALL.blue(), 235))
        glow.setColorAt(1.0, QColor(BALL.red(), BALL.green(), BALL.blue(), 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(point, radius * 3.2, radius * 3.2)
        painter.setBrush(BALL)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawEllipse(point, radius, radius)

    def _draw_score(self, painter: QPainter, court: QRectF) -> None:
        sim = self.owner.sim
        painter.setFont(QFont("Menlo", 28, QFont.Weight.Bold))
        painter.setPen(RED_HOT)
        painter.drawText(
            QRectF(court.center().x() - 100, court.top() - 43, 72, 38),
            Qt.AlignmentFlag.AlignCenter,
            str(sim.left_score),
        )
        painter.setPen(DIM)
        painter.drawText(
            QRectF(court.center().x() - 24, court.top() - 43, 48, 38),
            Qt.AlignmentFlag.AlignCenter,
            ":",
        )
        painter.setPen(GREEN_HOT)
        painter.drawText(
            QRectF(court.center().x() + 28, court.top() - 43, 72, 38),
            Qt.AlignmentFlag.AlignCenter,
            str(sim.right_score),
        )

    def _draw_vote_balance(
        self,
        painter: QPainter,
        court: QRectF,
        swarm: SwarmState,
        color: QColor,
        x: float,
    ) -> None:
        width = court.width() * 0.08
        y = court.top() - 24
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(54, 64, 83))
        painter.drawRoundedRect(QRectF(x, y, width, 6), 3, 3)
        magnitude = abs(swarm.vote_average)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 220))
        if swarm.vote_average >= 0:
            painter.drawRoundedRect(QRectF(x + width / 2, y, width / 2 * magnitude, 6), 3, 3)
        else:
            painter.drawRoundedRect(
                QRectF(x + width / 2 - width / 2 * magnitude, y, width / 2 * magnitude, 6),
                3,
                3,
            )

    def _draw_digest(self, painter: QPainter, court: QRectF) -> None:
        painter.setFont(QFont("Menlo", 8))
        painter.setPen(QColor(126, 139, 160))
        left = self.owner.sim.left.vote_digest[:10]
        right = self.owner.sim.right.vote_digest[:10]
        painter.drawText(
            QRectF(court.left(), court.bottom() + 9, court.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            f"{left}  |  {right}",
        )


class StigmergicPongWidget(QWidget):
    _live_instance: Optional["StigmergicPongWidget"] = None
    _initialized_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) in cls._initialized_ids:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None) -> None:
        if id(self) in type(self)._initialized_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_ids.add(id(self))

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(960, 680)
        self.resize(1080, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: #080b12; color: #e5ebf4; }"
            "QToolButton { background: #151c2a; border: 1px solid #3e4a61; border-radius: 4px; }"
            "QToolButton:hover { background: #243047; }"
            "QSpinBox { background: #121927; border: 1px solid #3e4a61; padding: 4px; }"
            "QCheckBox { color: #91a0b8; spacing: 6px; }"
            "QSlider::groove:horizontal { height: 4px; background: #303c52; border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #ffe298; border-radius: 7px; }"
        )

        self.sim = StigmergicPongSimulation(seed=1625, swimmers_per_side=64)
        self.running = True
        self.tempo = 1
        self.show_field = True
        self._chorus_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pong-chorus")
        self._chorus_future: Optional[Future] = None
        self._next_chorus_tick = 0
        self._chorus_prompt_size = 0
        self._stgm_body = canonical_stgm_read_only()
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        receipt = _write_receipt("game_opened", self.sim.snapshot())
        _focus(
            "two autonomous swarms are playing",
            {"receipt_id": receipt, "swimmers_per_side": self.sim.swimmers_per_side},
        )

    def _icon_button(self, icon: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setFixedSize(34, 34)
        button.setIconSize(QSize(19, 19))
        return button

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("STIGMERGIC CARPENTER PONG")
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffe298; background: transparent;")
        top.addWidget(title)
        self.mode_label = QLabel("AUTO / LIVE")
        self.mode_label.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        self.mode_label.setStyleSheet("color: #49e099; background: transparent;")
        top.addWidget(self.mode_label)
        top.addStretch(1)

        self.pause_button = self._icon_button(QStyle.StandardPixmap.SP_MediaPause, "Pause or resume")
        self.step_button = self._icon_button(QStyle.StandardPixmap.SP_MediaSkipForward, "Advance one simulation step")
        self.reset_button = self._icon_button(QStyle.StandardPixmap.SP_BrowserReload, "Start a new match")
        self.pause_button.clicked.connect(self._toggle_running)
        self.step_button.clicked.connect(self._single_step)
        self.reset_button.clicked.connect(self._reset_match)
        top.addWidget(self.pause_button)
        top.addWidget(self.step_button)
        top.addWidget(self.reset_button)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #354057;")
        top.addWidget(separator)

        swimmers_label = QLabel("SWIMMERS")
        swimmers_label.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        swimmers_label.setStyleSheet("color: #91a0b8; background: transparent;")
        top.addWidget(swimmers_label)
        self.swimmer_spin = QSpinBox(self)
        self.swimmer_spin.setRange(16, 128)
        self.swimmer_spin.setSingleStep(8)
        self.swimmer_spin.setValue(self.sim.swimmers_per_side)
        self.swimmer_spin.setFixedWidth(72)
        self.swimmer_spin.setToolTip("Unique swimmers per side")
        self.swimmer_spin.editingFinished.connect(self._resize_swarms)
        top.addWidget(self.swimmer_spin)

        tempo_label = QLabel("TEMPO")
        tempo_label.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        tempo_label.setStyleSheet("color: #91a0b8; background: transparent;")
        top.addWidget(tempo_label)
        self.tempo_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.tempo_slider.setRange(1, 4)
        self.tempo_slider.setValue(1)
        self.tempo_slider.setFixedWidth(90)
        self.tempo_slider.setToolTip("Simulation steps per frame")
        self.tempo_slider.valueChanged.connect(self._set_tempo)
        top.addWidget(self.tempo_slider)

        field_toggle = QCheckBox("FIELD", self)
        field_toggle.setChecked(True)
        field_toggle.setToolTip("Show or hide pheromone bands")
        field_toggle.toggled.connect(self._toggle_field)
        top.addWidget(field_toggle)

        self.stgm_toggle = QCheckBox("STGM", self)
        self.stgm_toggle.setChecked(True)
        self.stgm_toggle.setToolTip(
            "GAME_STGM economy: vote costs stake, saves pay correct voters "
            "(sandbox hive crypto — not body repair_log wallet)"
        )
        self.stgm_toggle.toggled.connect(self._toggle_stgm)
        top.addWidget(self.stgm_toggle)

        self.llm_toggle = QCheckBox("LLM CHORUS", self)
        self.llm_toggle.setChecked(False)
        self.llm_toggle.setToolTip(
            "Every swimmer contributes one observation to a batched local Ollama "
            "council; think=false, asynchronous, opt-in"
        )
        self.llm_toggle.toggled.connect(self._toggle_llm)
        top.addWidget(self.llm_toggle)
        root.addLayout(top)

        self.canvas = _PongCanvas(self)
        root.addWidget(self.canvas, 1)

        stats = QHBoxLayout()
        stats.setSpacing(22)
        self.left_stats = QLabel()
        self.center_stats = QLabel()
        self.right_stats = QLabel()
        for label in (self.left_stats, self.center_stats, self.right_stats):
            label.setFont(QFont("Menlo", 9))
            label.setStyleSheet("color: #91a0b8; background: transparent;")
        self.left_stats.setStyleSheet("color: #f49a73; background: transparent;")
        self.right_stats.setStyleSheet("color: #69dfb6; background: transparent;")
        stats.addWidget(self.left_stats)
        stats.addStretch(1)
        stats.addWidget(self.center_stats)
        stats.addStretch(1)
        stats.addWidget(self.right_stats)
        root.addLayout(stats)

        self.economy_stats = QLabel()
        self.economy_stats.setFont(QFont("Menlo", 8))
        self.economy_stats.setStyleSheet("color: #ffe298; background: transparent;")
        self.economy_stats.setWordWrap(True)
        self.economy_stats.setMinimumWidth(0)
        self.economy_stats.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        root.addWidget(self.economy_stats)
        self._refresh_stats()

    def _set_tempo(self, value: int) -> None:
        self.tempo = max(1, min(4, int(value)))

    def _toggle_field(self, checked: bool) -> None:
        self.show_field = bool(checked)
        self.canvas.update()

    def _toggle_stgm(self, checked: bool) -> None:
        self.sim.stgm_economy = bool(checked)
        if checked:
            if self.sim.economy is None:
                try:
                    from System.swarm_carpenter_pong_stgm import PongGameStgmEconomy

                    self.sim.economy = PongGameStgmEconomy(enabled=True)
                    self.sim._init_economy_wallets()
                except Exception:
                    self.stgm_toggle.setChecked(False)
                    return
            else:
                self.sim.economy.enabled = True
                self.sim._init_economy_wallets()
        elif self.sim.economy is not None:
            self.sim.economy.enabled = False
        self._refresh_stats()

    def _toggle_llm(self, checked: bool) -> None:
        self.sim.llm_microvote = bool(checked)
        if not checked:
            self.sim.llm_overrides = {}
            self.sim.left.chorus_confidence = 0.0
            self.sim.right.chorus_confidence = 0.0
        else:
            self._next_chorus_tick = self.sim.tick
        self._refresh_stats()

    def _resolve_chorus_model(self) -> str:
        try:
            from System.sifta_inference_defaults import resolve_live_local_ollama_default

            return str(resolve_live_local_ollama_default() or "ornith:latest")
        except Exception:
            return "ornith:latest"

    def _poll_chorus(self) -> None:
        future = self._chorus_future
        if future is not None and future.done():
            self._chorus_future = None
            try:
                advice = future.result()
                self.sim.apply_chorus_advice(
                    left_target=advice.left.target_y,
                    left_confidence=advice.left.confidence,
                    right_target=advice.right.target_y,
                    right_confidence=advice.right.confidence,
                    model=advice.model,
                    estimated_prompt_tokens=max(1, self._chorus_prompt_size // 4),
                )
                self.sim.llm_last_report = {
                    "ok": True,
                    "tick": self.sim.tick,
                    "n": self.sim.swimmers_per_side * 2,
                    "model": advice.model,
                    "latency_s": round(advice.latency_s, 3),
                    "digest": advice.council_digest,
                }
                _write_receipt("llm_chorus_advice", self.sim.llm_last_report)
            except Exception as exc:
                self.sim.llm_last_report = {
                    "ok": False,
                    "tick": self.sim.tick,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            self._next_chorus_tick = self.sim.tick + self.sim.llm_every_ticks

        if (
            self.sim.llm_microvote
            and self._chorus_future is None
            and self.sim.tick >= self._next_chorus_tick
        ):
            snapshot = self.sim.snapshot()
            observations = self.sim.council_observations()
            prompt = build_chorus_prompt(snapshot, observations)
            digest = uuid.uuid5(uuid.NAMESPACE_URL, prompt).hex[:16]
            model = self._resolve_chorus_model()
            self._chorus_prompt_size = len(prompt)
            self.sim.llm_last_report = {
                "ok": None,
                "tick": self.sim.tick,
                "n": self.sim.swimmers_per_side * 2,
                "model": model,
                "state": "thinking_without_cot",
                "digest": digest,
            }
            self._chorus_future = self._chorus_executor.submit(
                ask_local_ollama,
                prompt,
                model=model,
                council_digest=digest,
            )

    def _toggle_running(self) -> None:
        self.running = not self.running
        icon = QStyle.StandardPixmap.SP_MediaPause if self.running else QStyle.StandardPixmap.SP_MediaPlay
        self.pause_button.setIcon(self.style().standardIcon(icon))
        self.mode_label.setText("AUTO / LIVE" if self.running else "PAUSED")
        self.mode_label.setStyleSheet(
            "color: #49e099; background: transparent;"
            if self.running
            else "color: #ffe298; background: transparent;"
        )

    def _single_step(self) -> None:
        if self.running:
            self._toggle_running()
        self._advance(1)

    def _resize_swarms(self) -> None:
        count = int(self.swimmer_spin.value())
        if count == self.sim.swimmers_per_side:
            return
        self.sim.reset_match(seed=self.sim.seed + 1, swimmers_per_side=count)
        _write_receipt("swarm_resized", self.sim.snapshot())
        self._refresh_stats()
        self.canvas.update()

    def _reset_match(self) -> None:
        self.sim.reset_match(
            seed=self.sim.seed + 1,
            swimmers_per_side=int(self.swimmer_spin.value()),
        )
        _write_receipt("match_reset", self.sim.snapshot())
        self._refresh_stats()
        self.canvas.update()

    def _advance(self, steps: int) -> None:
        for _ in range(max(1, int(steps))):
            for event in self.sim.step():
                _write_receipt("goal", {**event, "snapshot": self.sim.snapshot()})
        self._refresh_stats()
        self.canvas.update()

    def _tick(self) -> None:
        if self.running:
            self._advance(self.tempo)
        self._poll_chorus()

    def _refresh_stats(self) -> None:
        left = self.sim.left
        right = self.sim.right
        self.left_stats.setText(
            f"RED  up {left.up_votes:02d}  down {left.down_votes:02d}  agree {left.agreement:0.2f}"
        )
        self.center_stats.setText(
            f"rally {self.sim.rally_hits:02d}  best {self.sim.longest_rally:02d}  round {self.sim.round_number:02d}"
        )
        self.right_stats.setText(
            f"GREEN  up {right.up_votes:02d}  down {right.down_votes:02d}  agree {right.agreement:0.2f}"
        )
        eco = self.sim.economy.snapshot() if self.sim.economy else {"enabled": False}
        llm = self.sim.llm_last_report or {}
        llm_bit = (
            f"  ·  CHORUS {'ok' if llm.get('ok') else llm.get('state', 'waiting')} "
            f"n={llm.get('n')} {llm.get('latency_s', '')}s"
            if self.sim.llm_microvote and llm
            else ("  ·  CHORUS off" if not self.sim.llm_microvote else "  ·  CHORUS waiting")
        )
        crypto = self.sim.snapshot().get("crypto", {})
        crypto_bit = (
            f"  ·  Ed25519 {crypto.get('verified_ballots', 0)}/"
            f"{self.sim.swimmers_per_side * 2} root={str(crypto.get('checkpoint_digest', ''))[:8]}"
        )
        body_bit = f"  ·  BODY {self._stgm_body.get('label')} read-only"
        if eco.get("enabled"):
            self.economy_stats.setText(
                f"GAME_STGM  sum={eco.get('sum')}  mean={eco.get('mean')}  "
                f"min={eco.get('min')}  spent={eco.get('total_spent')}  "
                f"earned={eco.get('total_earned')}  tx={eco.get('tx_count')}"
                f"{llm_bit}{crypto_bit}{body_bit}  ·  GAME_STGM sandbox"
            )
        else:
            self.economy_stats.setText(f"GAME_STGM off{llm_bit}{crypto_bit}{body_bit}")

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self._chorus_executor.shutdown(wait=False, cancel_futures=True)
        _write_receipt("game_closed", self.sim.snapshot())
        _focus("closed", {"score": [self.sim.left_score, self.sim.right_score]})
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_ids.discard(id(self))
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    widget = StigmergicPongWidget()
    widget.show()
    raise SystemExit(app.exec())


# Preserve the WCT R1625 public widget contract while using the richer V2 engine.
StigmergicCarpenterPongWidget = StigmergicPongWidget
