#!/usr/bin/env python3
"""Stigmergic Reaction-Diffusion Calculator.

Operands are injected as pulse trains into a BZ-style excitable medium. The
field has no arithmetic answer path: horizontal and vertical waves propagate,
modify refractory state, collide, locally annihilate, and leave a stable
precipitate at collision sites. The displayed result is a readout of that
precipitate pattern.

This stays inside the PyQt6 SIFTA organism as an embedded QWidget, writes
app-specific receipts, and publishes focus without opening a second chat.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover - desktop organ can be absent in tests
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Stigmergic Reaction-Diffusion Calculator"
APP_ID = "sifta_reaction_diffusion_calculator"
TRUTH_LABEL = "STIGMERGIC_REACTION_DIFFUSION_CALCULATOR_V1"

GRID_W = 136
GRID_H = 96
MAX_OPERAND = 12
WAVE_THRESHOLD = 0.30
PRECIP_THRESHOLD = 0.50

_BG_TOP = QColor(7, 9, 16)
_BG_BOTTOM = QColor(17, 19, 29)
_PANEL = QColor(19, 22, 34)
_PANEL_BORDER = QColor(61, 73, 103)
_TEXT = QColor(222, 229, 242)
_DIM = QColor(142, 153, 181)
_ACCENT = QColor(74, 229, 204)
_PRECIP = QColor(255, 218, 92)
_ROW = QColor(69, 224, 233)
_COL = QColor(206, 116, 255)
_REFRACTORY = QColor(212, 70, 68)


def _publish_app_focus(detail: str, metadata: Optional[dict] = None) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(title=APP_TITLE, detail=detail, app_id=APP_ID, metadata=metadata or {})
    except TypeError:
        try:
            _publish_focus(APP_TITLE, detail, metadata=metadata or {})
        except Exception:
            pass
    except Exception:
        pass


def _write_app_receipt(event: str, payload: dict) -> None:
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
        with (_STATE / "reaction_diffusion_calculator_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    except Exception:
        pass


def _centered_slots(limit: int, count: int, margin: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [limit // 2]
    lo = margin
    hi = max(margin + 1, limit - margin - 1)
    span = hi - lo
    return [int(round(lo + span * (idx / (count - 1)))) for idx in range(count)]


def _dilate(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


class ReactionDiffusionField:
    """Excitable medium whose collision precipitate is the calculator readout."""

    def __init__(self, width: int = GRID_W, height: int = GRID_H, max_operand: int = MAX_OPERAND):
        self.width = width
        self.height = height
        self.max_operand = max_operand
        self.row_slots = _centered_slots(height, max_operand, 12)
        self.col_slots = _centered_slots(width, max_operand, 18)
        self.reset()

    def reset(self) -> None:
        shape = (self.height, self.width)
        self.row_wave = np.zeros(shape, dtype=np.float32)
        self.col_wave = np.zeros(shape, dtype=np.float32)
        self.refractory = np.zeros(shape, dtype=np.float32)
        self.precipitate = np.zeros(shape, dtype=np.float32)
        self.spent = np.zeros(shape, dtype=bool)
        self.row_tracks = np.zeros(shape, dtype=bool)
        self.col_tracks = np.zeros(shape, dtype=bool)
        self.intersections = np.zeros(shape, dtype=bool)
        self.selected_rows: list[int] = []
        self.selected_cols: list[int] = []
        self.left_operand = 0
        self.right_operand = 0
        self.ticks = 0
        self.emission_remaining = 0
        self.last_new_precipitate = 0
        self.last_collision_count = 0
        self.phase = "rest"

    def inject_operands(self, left: int, right: int) -> None:
        self.reset()
        self.left_operand = max(0, min(self.max_operand, int(left)))
        self.right_operand = max(0, min(self.max_operand, int(right)))
        self.selected_rows = self.row_slots[: self.left_operand]
        self.selected_cols = self.col_slots[: self.right_operand]
        for row in self.selected_rows:
            self.row_tracks[row, 4 : self.width - 4] = True
        for col in self.selected_cols:
            self.col_tracks[4 : self.height - 4, col] = True
        self.intersections = self.row_tracks & self.col_tracks
        self.emission_remaining = self.width + self.height
        self.phase = "emitting"
        _write_app_receipt(
            "operands_injected_as_excitation_pulses",
            {
                "left_operand": self.left_operand,
                "right_operand": self.right_operand,
                "selected_rows": self.selected_rows,
                "selected_cols": self.selected_cols,
                "answer_path": "field_precipitate_readout",
            },
        )

    def _emit_boundary_pulses(self) -> None:
        if self.emission_remaining <= 0:
            return
        for row in self.selected_rows:
            self.row_wave[row, 4:7] = 1.0
        for col in self.selected_cols:
            self.col_wave[4:7, col] = 1.0
        self.emission_remaining -= 1
        if self.emission_remaining <= 0:
            self.phase = "settling"

    def step(self) -> dict:
        self._emit_boundary_pulses()

        old_row = self.row_wave
        old_col = self.col_wave

        row_next = old_row * 0.18
        row_shift = np.zeros_like(old_row)
        row_shift[:, 1:] = np.maximum(old_row[:, :-1] * 0.995, (old_row[:, :-1] > 0.20) * 0.86)
        row_next = np.maximum(row_next, row_shift)

        col_next = old_col * 0.18
        col_shift = np.zeros_like(old_col)
        col_shift[1:, :] = np.maximum(old_col[:-1, :] * 0.995, (old_col[:-1, :] > 0.20) * 0.86)
        col_next = np.maximum(col_next, col_shift)

        refractory_gate = np.clip(1.0 - self.refractory * 0.72, 0.0, 1.0)
        row_next *= self.row_tracks
        col_next *= self.col_tracks
        row_next *= refractory_gate
        col_next *= refractory_gate

        collisions = (
            self.intersections
            & (~self.spent)
            & (row_next > WAVE_THRESHOLD)
            & (col_next > WAVE_THRESHOLD)
            & (self.refractory < 0.88)
        )
        new_precipitate = int(np.count_nonzero(collisions))
        if new_precipitate:
            self.precipitate[collisions] = 1.0
            self.spent[collisions] = True
            cooled = _dilate(collisions)
            row_next[cooled] *= 0.18
            col_next[cooled] *= 0.18
            self.refractory[cooled] = np.maximum(self.refractory[cooled], 1.0)

        wave_heat = np.maximum(row_next, col_next)
        self.refractory = np.maximum(self.refractory * 0.965, wave_heat * 0.22)
        self.row_wave = np.clip(row_next, 0.0, 1.0)
        self.col_wave = np.clip(col_next, 0.0, 1.0)
        self.ticks += 1
        self.last_new_precipitate = new_precipitate
        self.last_collision_count += new_precipitate
        if self.emission_remaining <= 0 and float(np.max(wave_heat)) < 0.04:
            self.phase = "quiet"
        return self.signature()

    def run_until_quiet(self, max_steps: int = 360) -> dict:
        stable_ticks = 0
        last_count = self.precipitate_count()
        for _ in range(max_steps):
            sig = self.step()
            count = self.precipitate_count()
            max_wave = sig["max_wave"]
            if count == last_count and self.emission_remaining <= 0 and max_wave < 0.06:
                stable_ticks += 1
            else:
                stable_ticks = 0
            last_count = count
            if stable_ticks >= 8:
                break
        return self.signature()

    def precipitate_count(self) -> int:
        return int(np.count_nonzero(self.precipitate > PRECIP_THRESHOLD))

    def signature(self) -> dict:
        wave = np.maximum(self.row_wave, self.col_wave)
        return {
            "ticks": self.ticks,
            "phase": self.phase,
            "precipitate_count": self.precipitate_count(),
            "new_precipitate": self.last_new_precipitate,
            "max_wave": round(float(np.max(wave)), 5),
            "refractory_mass": round(float(np.sum(self.refractory > 0.18)), 5),
            "wave_mass": round(float(np.sum(wave)), 5),
            "answer_source": "precipitate_count_from_field",
        }

    def render_rgb(self) -> np.ndarray:
        row = np.clip(self.row_wave, 0.0, 1.0)
        col = np.clip(self.col_wave, 0.0, 1.0)
        ref = np.clip(self.refractory, 0.0, 1.0)
        precip = np.clip(self.precipitate, 0.0, 1.0)
        tracks = (self.row_tracks | self.col_tracks).astype(np.float32)

        rgb = np.zeros((self.height, self.width, 3), dtype=np.float32)
        rgb[..., 0] = 10 + tracks * 18 + ref * 130 + precip * 245 + col * 70
        rgb[..., 1] = 13 + tracks * 24 + row * 205 + precip * 205 + col * 62
        rgb[..., 2] = 24 + tracks * 42 + row * 205 + col * 215 + precip * 68 - ref * 30

        collision_glow = _dilate(self.precipitate > PRECIP_THRESHOLD)
        rgb[collision_glow, 0] += 70
        rgb[collision_glow, 1] += 46
        rgb[collision_glow, 2] += 8
        return np.clip(rgb, 0, 255).astype(np.uint8)


class _FieldCanvas(QWidget):
    def __init__(self, owner: "StigmergicReactionDiffusionCalculatorWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self._image_bytes = b""
        self.setMinimumSize(720, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _event) -> None:
        field = self.owner.field
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, _BG_TOP)
        bg.setColorAt(1.0, _BG_BOTTOM)
        p.fillRect(self.rect(), bg)

        rgb = field.render_rgb()
        self._image_bytes = rgb.tobytes()
        image = QImage(
            self._image_bytes,
            field.width,
            field.height,
            field.width * 3,
            QImage.Format.Format_RGB888,
        )
        target = self._target_rect(field.width, field.height)
        p.drawImage(target, image)

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawRect(target)
        self._draw_readout(p, target)
        p.end()

    def _target_rect(self, grid_w: int, grid_h: int) -> QRectF:
        margin = 18.0
        usable_w = max(1.0, self.width() - margin * 2)
        usable_h = max(1.0, self.height() - margin * 2)
        scale = min(usable_w / grid_w, usable_h / grid_h)
        w = grid_w * scale
        h = grid_h * scale
        return QRectF((self.width() - w) / 2.0, (self.height() - h) / 2.0, w, h)

    def _draw_readout(self, p: QPainter, rect: QRectF) -> None:
        field = self.owner.field
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QPen(_PRECIP, 1))
        count_text = f"precipitate readout: {field.precipitate_count()}"
        phase_text = f"t={field.ticks}  phase={field.phase}"
        p.drawText(QRectF(rect.left() + 10, rect.top() + 9, rect.width() - 20, 22), Qt.AlignmentFlag.AlignLeft, count_text)
        p.setPen(QPen(_DIM, 1))
        p.drawText(QRectF(rect.left() + 10, rect.top() + 30, rect.width() - 20, 22), Qt.AlignmentFlag.AlignLeft, phase_text)

        legend_y = rect.bottom() + 8
        if legend_y + 20 < self.height():
            p.setFont(QFont("Menlo", 9))
            x = rect.left()
            for label, color in (("row wave", _ROW), ("column wave", _COL), ("refractory trace", _REFRACTORY), ("precipitate", _PRECIP)):
                p.setPen(QPen(color, 4))
                p.drawLine(QPointF(x, legend_y + 8), QPointF(x + 18, legend_y + 8))
                p.setPen(QPen(_DIM, 1))
                p.drawText(QRectF(x + 24, legend_y, 130, 18), Qt.AlignmentFlag.AlignLeft, label)
                x += 154


class StigmergicReactionDiffusionCalculatorWidget(QWidget):
    """PyQt6 SIFTA widget with class-side singleton hardening."""

    _live_instance: Optional["StigmergicReactionDiffusionCalculatorWidget"] = None
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

    def __init__(self, parent=None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1030, 690)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {_BG_TOP.name()};")

        self.field = ReactionDiffusionField()
        self.running = True
        self.last_signature: dict = {}

        self.canvas = _FieldCanvas(self)
        self._build_ui()
        self._inject_from_controls()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._evolve_step)
        self._timer.start(36)

        _publish_app_focus("opened", {"truth_label": TRUTH_LABEL})
        _write_app_receipt("widget_boot", {"default_operands": [7, 8]})

    def closeEvent(self, event) -> None:
        self.running = False
        self._timer.stop()
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        _publish_app_focus("closed", {"ticks": self.field.ticks})
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)
        root.addWidget(self.canvas, 1)

        panel = QFrame()
        panel.setFixedWidth(286)
        panel.setStyleSheet(
            f"QFrame {{ background-color: {_PANEL.name()}; border: 1px solid {_PANEL_BORDER.name()}; border-radius: 5px; }}"
            "QLabel { border: none; }"
            "QPushButton { color: rgb(222,229,242); background: #20263a; border: 1px solid #4c5878; padding: 6px 10px; border-radius: 3px; }"
            "QPushButton:hover { background: #2a314a; }"
            "QSpinBox { color: rgb(222,229,242); background: #101522; border: 1px solid #4c5878; padding: 4px; }"
        )
        side = QVBoxLayout(panel)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(8)

        title = QLabel(APP_TITLE)
        title.setWordWrap(True)
        title.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT.name()};")
        side.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.left_spin = QSpinBox()
        self.right_spin = QSpinBox()
        for spin, value in ((self.left_spin, 7), (self.right_spin, 8)):
            spin.setRange(0, MAX_OPERAND)
            spin.setValue(value)
            spin.valueChanged.connect(self._inject_from_controls)
        grid.addWidget(self._label("Left pulses"), 0, 0)
        grid.addWidget(self.left_spin, 0, 1)
        grid.addWidget(self._label("Top pulses"), 1, 0)
        grid.addWidget(self.right_spin, 1, 1)
        side.addLayout(grid)

        self.demo_btn = QPushButton("7x8 Demo")
        self.demo_btn.clicked.connect(self._run_demo_7x8)
        self.inject_btn = QPushButton("Inject Pulses")
        self.inject_btn.clicked.connect(self._inject_from_controls)
        self.run_btn = QPushButton("Pause")
        self.run_btn.clicked.connect(self._toggle_run)
        self.step_btn = QPushButton("Single Step")
        self.step_btn.clicked.connect(self._manual_step)
        self.settle_btn = QPushButton("Run To Quiet")
        self.settle_btn.clicked.connect(self._run_to_quiet)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear)
        for btn in (self.demo_btn, self.inject_btn, self.run_btn, self.step_btn, self.settle_btn, self.clear_btn):
            side.addWidget(btn)

        self.count_label = self._metric("precipitate", "0")
        self.phase_label = self._metric("phase", "rest")
        self.wave_label = self._metric("wave mass", "0")
        self.ref_label = self._metric("refractory", "0")
        for label in (self.count_label, self.phase_label, self.wave_label, self.ref_label):
            side.addWidget(label)

        note = QLabel("Readout is the stable precipitate pattern left by wave collisions.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {_DIM.name()}; font: 10px Menlo;")
        side.addWidget(note)
        side.addStretch()
        root.addWidget(panel)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {_TEXT.name()}; font: 10px Menlo;")
        return label

    def _metric(self, name: str, value: str) -> QLabel:
        label = QLabel(f"{name}: {value}")
        label.setStyleSheet(f"color: {_TEXT.name()}; font: 10px Menlo; padding: 3px 0;")
        return label

    def _inject_from_controls(self) -> None:
        self.field.inject_operands(self.left_spin.value(), self.right_spin.value())
        self.running = True
        if hasattr(self, "run_btn"):
            self.run_btn.setText("Pause")
        self._refresh()
        _publish_app_focus(
            "operands injected",
            {"left": self.left_spin.value(), "right": self.right_spin.value(), "truth_label": TRUTH_LABEL},
        )

    def _run_demo_7x8(self) -> None:
        self.left_spin.blockSignals(True)
        self.right_spin.blockSignals(True)
        self.left_spin.setValue(7)
        self.right_spin.setValue(8)
        self.left_spin.blockSignals(False)
        self.right_spin.blockSignals(False)
        self.field.inject_operands(7, 8)
        self.running = True
        self.run_btn.setText("Pause")
        self._refresh()
        _write_app_receipt("demo_7x8_started", {"answer_source": "field_precipitate_readout"})

    def _toggle_run(self) -> None:
        self.running = not self.running
        self.run_btn.setText("Pause" if self.running else "Run")

    def _manual_step(self) -> None:
        self.field.step()
        self._refresh()

    def _evolve_step(self) -> None:
        if not self.running:
            return
        sig = self.field.step()
        if sig["phase"] == "quiet":
            self.running = False
            self.run_btn.setText("Run")
            _write_app_receipt(
                "field_quiet",
                {
                    "left_operand": self.field.left_operand,
                    "right_operand": self.field.right_operand,
                    "precipitate_count": self.field.precipitate_count(),
                    "ticks": self.field.ticks,
                    "answer_source": "field_precipitate_readout",
                },
            )
        self._refresh(sig)

    def _run_to_quiet(self) -> None:
        sig = self.field.run_until_quiet()
        self.running = False
        self.run_btn.setText("Run")
        self._refresh(sig)
        _write_app_receipt(
            "run_to_quiet",
            {
                "left_operand": self.field.left_operand,
                "right_operand": self.field.right_operand,
                "precipitate_count": self.field.precipitate_count(),
                "ticks": self.field.ticks,
                "answer_source": "field_precipitate_readout",
            },
        )

    def _clear(self) -> None:
        self.field.reset()
        self.running = False
        self.run_btn.setText("Run")
        self._refresh()
        _write_app_receipt("field_cleared", {})

    def _refresh(self, sig: Optional[dict] = None) -> None:
        self.last_signature = sig or self.field.signature()
        self.count_label.setText(f"precipitate: {self.last_signature['precipitate_count']}")
        self.phase_label.setText(f"phase: {self.last_signature['phase']} / t={self.last_signature['ticks']}")
        self.wave_label.setText(f"wave mass: {self.last_signature['wave_mass']}")
        self.ref_label.setText(f"refractory: {self.last_signature['refractory_mass']}")
        self.canvas.update()


SiftaReactionDiffusionCalculator = StigmergicReactionDiffusionCalculatorWidget


def create_widget(parent=None):
    return StigmergicReactionDiffusionCalculatorWidget(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = StigmergicReactionDiffusionCalculatorWidget()
    widget.show()
    sys.exit(app.exec())
