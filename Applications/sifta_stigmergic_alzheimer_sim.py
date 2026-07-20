#!/usr/bin/env python3
"""Stigmergic Alzheimer Network Lab.

Educational network-diffusion simulator for Alzheimer-like propagation across a
toy brain connectome. This is not a medical device, not diagnosis, and not
treatment guidance. It is a SIFTA research/learning surface for testing the
stigmergic idea: local deposits diffuse along a weighted network, vulnerable
regions amplify deposits, and clearance evaporates the field.
"""

from __future__ import annotations

import json
import math
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover - focus organ is optional for standalone runs
    _publish_focus = None  # type: ignore[assignment]


APP_TITLE = "Stigmergic Alzheimer Network Lab"
APP_ID = "sifta_stigmergic_alzheimer_sim"
TRUTH_LABEL = "STIGMERGIC_ALZHEIMER_NETWORK_SIM_V1"
MEDICAL_BOUNDARY = (
    "Educational synthetic simulation only. No PHI, no diagnosis, no treatment "
    "guidance, and no clinical decision support."
)


@dataclass(frozen=True)
class BrainRegion:
    """One toy connectome node."""

    name: str
    x: float
    y: float
    vulnerability: float
    cognitive_weight: float


@dataclass(frozen=True)
class ConnectomeEdge:
    """Undirected weighted path for local diffusion."""

    source: str
    target: str
    weight: float


@dataclass(frozen=True)
class SimulationParams:
    """Parameters for one network-diffusion step."""

    spread_rate: float = 0.18
    clearance_rate: float = 0.035
    vulnerability_gain: float = 0.08
    floor_decay: float = 0.004


@dataclass(frozen=True)
class SimulationSummary:
    """Compact report written to receipts and shown in the UI."""

    step: int
    total_pathology: float
    affected_regions: int
    cognitive_proxy: float
    hotspot: str
    entropy: float
    medical_boundary: str = MEDICAL_BOUNDARY


def demo_connectome() -> tuple[list[BrainRegion], list[ConnectomeEdge]]:
    """Return a small deterministic connectome for education and tests."""

    regions = [
        BrainRegion("Entorhinal L", 0.30, 0.56, 1.00, 0.13),
        BrainRegion("Entorhinal R", 0.70, 0.56, 1.00, 0.13),
        BrainRegion("Hippocampus L", 0.33, 0.67, 0.96, 0.15),
        BrainRegion("Hippocampus R", 0.67, 0.67, 0.96, 0.15),
        BrainRegion("Amygdala", 0.50, 0.72, 0.78, 0.06),
        BrainRegion("Posterior Cingulate", 0.50, 0.46, 0.82, 0.14),
        BrainRegion("Precuneus", 0.50, 0.34, 0.74, 0.10),
        BrainRegion("Temporal Cortex", 0.23, 0.43, 0.68, 0.10),
        BrainRegion("Parietal Cortex", 0.77, 0.42, 0.58, 0.06),
        BrainRegion("Frontal Cortex", 0.50, 0.18, 0.48, 0.06),
        BrainRegion("Occipital Cortex", 0.50, 0.86, 0.34, 0.02),
        BrainRegion("Thalamus", 0.50, 0.60, 0.62, 0.10),
    ]
    edges = [
        ConnectomeEdge("Entorhinal L", "Hippocampus L", 0.96),
        ConnectomeEdge("Entorhinal R", "Hippocampus R", 0.96),
        ConnectomeEdge("Hippocampus L", "Amygdala", 0.65),
        ConnectomeEdge("Hippocampus R", "Amygdala", 0.65),
        ConnectomeEdge("Hippocampus L", "Posterior Cingulate", 0.70),
        ConnectomeEdge("Hippocampus R", "Posterior Cingulate", 0.70),
        ConnectomeEdge("Posterior Cingulate", "Precuneus", 0.85),
        ConnectomeEdge("Precuneus", "Parietal Cortex", 0.62),
        ConnectomeEdge("Precuneus", "Frontal Cortex", 0.48),
        ConnectomeEdge("Posterior Cingulate", "Thalamus", 0.54),
        ConnectomeEdge("Thalamus", "Temporal Cortex", 0.44),
        ConnectomeEdge("Temporal Cortex", "Entorhinal L", 0.72),
        ConnectomeEdge("Temporal Cortex", "Hippocampus L", 0.52),
        ConnectomeEdge("Parietal Cortex", "Entorhinal R", 0.42),
        ConnectomeEdge("Parietal Cortex", "Hippocampus R", 0.46),
        ConnectomeEdge("Occipital Cortex", "Precuneus", 0.30),
        ConnectomeEdge("Frontal Cortex", "Parietal Cortex", 0.38),
        ConnectomeEdge("Frontal Cortex", "Posterior Cingulate", 0.40),
    ]
    return regions, edges


def seed_state(regions: Iterable[BrainRegion], seed_region: str = "Entorhinal L", amount: float = 0.32) -> dict[str, float]:
    """Create a pathology map with one seeded source."""

    state = {region.name: 0.0 for region in regions}
    if seed_region not in state:
        raise ValueError(f"unknown seed region: {seed_region}")
    state[seed_region] = _clamp(amount)
    return state


def adjacency(edges: Iterable[ConnectomeEdge]) -> dict[str, list[tuple[str, float]]]:
    """Build symmetric adjacency lists."""

    out: dict[str, list[tuple[str, float]]] = {}
    for edge in edges:
        weight = max(0.0, float(edge.weight))
        out.setdefault(edge.source, []).append((edge.target, weight))
        out.setdefault(edge.target, []).append((edge.source, weight))
    return out


def step_network_diffusion(
    state: dict[str, float],
    regions: list[BrainRegion],
    edges: list[ConnectomeEdge],
    params: SimulationParams = SimulationParams(),
) -> dict[str, float]:
    """Advance one stigmergic pathology step.

    Local rule:
      retained deposit = old value minus clearance
      neighbor pressure = weighted average of connected deposits
      vulnerable tissue amplifies local deposits
      a tiny floor decay prevents low-level noise from staying forever
    """

    graph = adjacency(edges)
    region_by_name = {region.name: region for region in regions}
    next_state: dict[str, float] = {}
    for name, region in region_by_name.items():
        current = _clamp(state.get(name, 0.0))
        neighbors = graph.get(name, [])
        total_weight = sum(weight for _, weight in neighbors) or 1.0
        incoming = sum(_clamp(state.get(other, 0.0)) * weight for other, weight in neighbors) / total_weight
        retained = current * (1.0 - params.clearance_rate)
        diffusion = params.spread_rate * region.vulnerability * max(0.0, incoming - current * 0.15)
        amplification = params.vulnerability_gain * region.vulnerability * current * (1.0 - current)
        evaporated = retained + diffusion + amplification - params.floor_decay
        next_state[name] = _clamp(evaporated)
    return next_state


def run_simulation(
    *,
    steps: int = 24,
    seed_region: str = "Entorhinal L",
    params: SimulationParams = SimulationParams(),
) -> list[dict[str, float]]:
    """Run a deterministic synthetic simulation and return every state."""

    regions, edges = demo_connectome()
    states = [seed_state(regions, seed_region=seed_region)]
    for _ in range(max(0, int(steps))):
        states.append(step_network_diffusion(states[-1], regions, edges, params))
    return states


def summarize_state(state: dict[str, float], regions: list[BrainRegion], step: int) -> SimulationSummary:
    """Compute educational summary metrics from a pathology map."""

    values = [_clamp(state.get(region.name, 0.0)) for region in regions]
    total = sum(values)
    affected = sum(1 for value in values if value >= 0.15)
    weighted_cognitive_load = sum(
        _clamp(state.get(region.name, 0.0)) * region.cognitive_weight for region in regions
    )
    cognitive_proxy = _clamp(1.0 - weighted_cognitive_load / max(0.01, sum(r.cognitive_weight for r in regions)))
    hotspot = max(regions, key=lambda region: state.get(region.name, 0.0)).name if regions else "none"
    entropy = _normalized_entropy(values)
    return SimulationSummary(
        step=int(step),
        total_pathology=round(total, 4),
        affected_regions=affected,
        cognitive_proxy=round(cognitive_proxy, 4),
        hotspot=hotspot,
        entropy=round(entropy, 4),
    )


def write_sim_receipt(
    summary: SimulationSummary,
    *,
    params: SimulationParams,
    seed_region: str,
    state_dir: Path | str | None = None,
    event: str = "sim_snapshot",
) -> Path:
    """Append one simulator receipt and return the ledger path."""

    state_root = Path(state_dir) if state_dir is not None else _STATE
    state_root.mkdir(parents=True, exist_ok=True)
    ledger = state_root / "alzheimer_stigmergic_sim_receipts.jsonl"
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "app": APP_TITLE,
        "event": event,
        "truth_label": TRUTH_LABEL,
        "seed_region": seed_region,
        "params": asdict(params),
        "summary": asdict(summary),
        "medical_boundary": MEDICAL_BOUNDARY,
    }
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return ledger


def _publish_app_focus(detail: str, metadata: dict | None = None) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, app_id=APP_ID, metadata=metadata or {})
    except TypeError:
        _publish_focus(APP_TITLE, detail, metadata=metadata or {})
    except Exception:
        pass


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _normalized_entropy(values: list[float]) -> float:
    total = sum(max(0.0, value) for value in values)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in values:
        p = max(0.0, value) / total
        if p > 0:
            entropy -= p * math.log(p)
    return entropy / max(1.0, math.log(len(values)))


class _ConnectomeCanvas(QWidget):
    """Draw the toy connectome and current deposits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(680, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.regions, self.edges = demo_connectome()
        self.state = seed_state(self.regions)
        self.step = 0

    def set_field(self, state: dict[str, float], step: int) -> None:
        self.state = dict(state)
        self.step = int(step)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        bg = QLinearGradient(0, 0, 0, rect.height())
        bg.setColorAt(0, QColor(8, 14, 22))
        bg.setColorAt(1, QColor(14, 20, 25))
        painter.fillRect(rect, bg)

        field = rect.adjusted(36, 34, -36, -34)
        painter.setPen(QPen(QColor(40, 78, 88), 1))
        painter.drawRoundedRect(field, 8, 8)

        positions = {region.name: self._point(field, region) for region in self.regions}
        self._draw_edges(painter, positions)
        self._draw_regions(painter, positions)
        self._draw_header(painter, field)
        painter.end()

    def _point(self, rect, region: BrainRegion) -> QPointF:
        return QPointF(
            rect.left() + region.x * rect.width(),
            rect.top() + region.y * rect.height(),
        )

    def _draw_edges(self, painter: QPainter, positions: dict[str, QPointF]) -> None:
        for edge in self.edges:
            source = positions[edge.source]
            target = positions[edge.target]
            source_load = self.state.get(edge.source, 0.0)
            target_load = self.state.get(edge.target, 0.0)
            heat = _clamp((source_load + target_load) / 2.0)
            alpha = int(70 + 130 * heat)
            pen = QPen(QColor(74 + int(140 * heat), 126, 146, alpha), max(1.0, 1.2 + 5.0 * edge.weight * heat))
            painter.setPen(pen)
            painter.drawLine(source, target)

    def _draw_regions(self, painter: QPainter, positions: dict[str, QPointF]) -> None:
        label_font = QFont("Menlo", 9)
        value_font = QFont("Menlo", 8)
        for region in self.regions:
            pos = positions[region.name]
            value = _clamp(self.state.get(region.name, 0.0))
            radius = 11 + 24 * value
            color = QColor(
                int(70 + 170 * value),
                int(170 - 70 * value),
                int(210 - 160 * value),
            )
            ring = QColor(240, 210, 90) if value >= 0.50 else QColor(95, 170, 190)
            painter.setPen(QPen(ring, 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pos, radius, radius)

            painter.setFont(value_font)
            painter.setPen(QColor(8, 12, 16))
            painter.drawText(QRectF(pos.x() - radius, pos.y() - 7, radius * 2, 14), Qt.AlignmentFlag.AlignCenter, f"{value:.2f}")

            painter.setFont(label_font)
            painter.setPen(QColor(217, 231, 232))
            label_rect = QRectF(pos.x() - 70, pos.y() + radius + 3, 140, 30)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, region.name)

    def _draw_header(self, painter: QPainter, field: QRectF) -> None:
        painter.setPen(QColor(222, 232, 230))
        painter.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        painter.drawText(QRectF(field.left() + 12, field.top() + 10, field.width() - 24, 24), "Connectome diffusion field")
        painter.setFont(QFont("Menlo", 10))
        painter.setPen(QColor(151, 176, 174))
        painter.drawText(QRectF(field.left() + 12, field.top() + 34, field.width() - 24, 22), f"step {self.step} | local deposits, weighted edges, vulnerable amplification, clearance evaporation")


class StigmergicAlzheimerNetworkLabWidget(QWidget):
    """Qt educational simulator for Alzheimer-like network diffusion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StigmergicAlzheimerNetworkLabWidget")
        self.setWindowTitle(APP_TITLE)
        self.regions, self.edges = demo_connectome()
        self.seed_region = "Entorhinal L"
        self.params = SimulationParams()
        self.state = seed_state(self.regions, self.seed_region)
        self.step = 0

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(420)
        self._timer.timeout.connect(self._run_step)
        self._render()
        _publish_app_focus("opened Alzheimer-like synthetic network diffusion simulator", {"truth_label": TRUTH_LABEL})

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: rgb(9, 13, 18); color: rgb(222, 232, 230); font-family: Menlo, monospace; }
            QFrame#panel { background: rgb(16, 24, 28); border: 1px solid rgb(46, 86, 92); border-radius: 8px; }
            QLabel#title { font-size: 20px; font-weight: 800; color: rgb(144, 226, 203); }
            QLabel#guard { color: rgb(247, 205, 112); font-weight: 700; }
            QPushButton { background: rgb(31, 78, 84); border: 1px solid rgb(82, 155, 156); border-radius: 6px; padding: 8px 10px; }
            QPushButton:hover { background: rgb(40, 96, 102); }
            QComboBox { background: rgb(12, 18, 22); border: 1px solid rgb(72, 116, 120); padding: 6px; }
            QTextEdit { background: rgb(7, 10, 14); color: rgb(202, 232, 218); border: 1px solid rgb(44, 76, 76); }
            QSlider::groove:horizontal { height: 6px; background: rgb(45, 58, 62); border-radius: 3px; }
            QSlider::handle:horizontal { width: 16px; margin: -6px 0; background: rgb(149, 220, 196); border-radius: 8px; }
            """
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.canvas = _ConnectomeCanvas(self)
        root.addWidget(self.canvas, 3)

        panel = QFrame(self)
        panel.setObjectName("panel")
        panel.setMinimumWidth(390)
        panel.setMaximumWidth(470)
        side = QVBoxLayout(panel)
        side.setContentsMargins(14, 14, 14, 14)
        side.setSpacing(10)
        root.addWidget(panel, 1)

        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        title.setWordWrap(True)
        side.addWidget(title)

        guard = QLabel(MEDICAL_BOUNDARY)
        guard.setObjectName("guard")
        guard.setWordWrap(True)
        side.addWidget(guard)

        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel("Seed"))
        self.seed_combo = QComboBox()
        for region in self.regions:
            self.seed_combo.addItem(region.name, region.name)
        self.seed_combo.currentIndexChanged.connect(self._reset)
        seed_row.addWidget(self.seed_combo, 1)
        side.addLayout(seed_row)

        self.spread_slider = self._add_slider(side, "Spread", 1, 45, 18, self._params_changed)
        self.clearance_slider = self._add_slider(side, "Clearance", 0, 20, 4, self._params_changed)
        self.vulnerability_slider = self._add_slider(side, "Vulnerability", 0, 24, 8, self._params_changed)

        buttons = QGridLayout()
        self.step_button = QPushButton("Step")
        self.step_button.clicked.connect(self._run_step)
        buttons.addWidget(self.step_button, 0, 0)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._toggle_run)
        buttons.addWidget(self.run_button, 0, 1)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset)
        buttons.addWidget(self.reset_button, 1, 0)

        self.receipt_button = QPushButton("Export Receipt")
        self.receipt_button.clicked.connect(lambda: self._write_receipt("manual_export"))
        buttons.addWidget(self.receipt_button, 1, 1)
        side.addLayout(buttons)

        self.metrics = QLabel("")
        self.metrics.setWordWrap(True)
        self.metrics.setStyleSheet("font-size: 12px; line-height: 1.35;")
        side.addWidget(self.metrics)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        side.addWidget(self.log, 1)

    def _add_slider(
        self,
        layout: QVBoxLayout,
        label: str,
        min_value: int,
        max_value: int,
        value: int,
        callback,
    ) -> QSlider:
        row = QHBoxLayout()
        caption = QLabel(f"{label}:")
        caption.setMinimumWidth(112)
        row.addWidget(caption)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setValue(value)
        slider.valueChanged.connect(callback)
        row.addWidget(slider, 1)
        layout.addLayout(row)
        return slider

    def _params_changed(self, *_args) -> None:
        self.params = SimulationParams(
            spread_rate=self.spread_slider.value() / 100.0,
            clearance_rate=self.clearance_slider.value() / 100.0,
            vulnerability_gain=self.vulnerability_slider.value() / 100.0,
        )
        self._render()

    def _toggle_run(self, *_args) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.run_button.setText("Run")
            return
        self._timer.start()
        self.run_button.setText("Pause")

    def _reset(self, *_args) -> None:
        self.seed_region = str(self.seed_combo.currentData() or "Entorhinal L")
        self.state = seed_state(self.regions, self.seed_region)
        self.step = 0
        self._write_receipt("reset")
        self._render()

    def _run_step(self, *_args) -> None:
        self._params_changed()
        self.state = step_network_diffusion(self.state, self.regions, self.edges, self.params)
        self.step += 1
        if self.step % 8 == 0:
            self._write_receipt("auto_snapshot")
        self._render()

    def _render(self) -> None:
        summary = summarize_state(self.state, self.regions, self.step)
        self.canvas.set_field(self.state, self.step)
        self.metrics.setText(
            "\n".join(
                [
                    f"Truth label: {TRUTH_LABEL}",
                    f"Total pathology: {summary.total_pathology:.3f}",
                    f"Affected regions: {summary.affected_regions}/{len(self.regions)}",
                    f"Cognitive proxy: {summary.cognitive_proxy:.3f}",
                    f"Hotspot: {summary.hotspot}",
                    f"Spread entropy: {summary.entropy:.3f}",
                    f"Params: spread {self.params.spread_rate:.2f}, clearance {self.params.clearance_rate:.2f}, vulnerability {self.params.vulnerability_gain:.2f}",
                ]
            )
        )
        ranked = sorted(self.state.items(), key=lambda item: item[1], reverse=True)[:8]
        self.log.setPlainText(
            "Top deposits\n"
            + "\n".join(f"{name:24s} {value:.3f}" for name, value in ranked)
            + "\n\nBoundary\n"
            + MEDICAL_BOUNDARY
            + "\n\nNext data hook\nImport OASIS/ADNI-style longitudinal rows only as de-identified research features; keep receipts separate from any clinical claim."
        )

    def _write_receipt(self, event: str) -> None:
        summary = summarize_state(self.state, self.regions, self.step)
        ledger = write_sim_receipt(summary, params=self.params, seed_region=self.seed_region, event=event)
        self.log.append(f"\nReceipt: {ledger.name} step={self.step} event={event}")


def create_widget(parent: QWidget | None = None) -> StigmergicAlzheimerNetworkLabWidget:
    return StigmergicAlzheimerNetworkLabWidget(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = StigmergicAlzheimerNetworkLabWidget()
    widget.resize(1180, 760)
    widget.show()
    sys.exit(app.exec())
