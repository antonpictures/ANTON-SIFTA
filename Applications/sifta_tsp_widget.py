#!/usr/bin/env python3
"""
Applications/sifta_tsp_widget.py
══════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_TSP_WIDGET_V1

A concrete general-problem-solving demo for the Architect's question
"where is the app in the os?". Alice does NOT claim she solves
Traveling Salesman herself — she routes the problem to a deterministic
solver, returns the route, and writes a receipt naming the solver +
the input hash so the work is auditable.

Solvers
-------

The widget picks the strongest available solver at runtime:

  * OR-Tools (Google's combinatorial optimization library) if it
    is installed locally — produces an exact / high-quality route on
    small N.
  * Nearest-neighbour greedy + 2-opt local search — pure-Python
    fallback that is honest about being a heuristic. Always available.

Truth label: ``SIFTA_TSP_DEMO_V1``.

Architect 2026-05-13 (verbatim): *"traveling salesman app... where is
the app in the os?"*. This is the app.

Architect 2026-05-14 — **TSPLIB-class real instances**, gradient map,
triple-IDE co-build charter: see ``Documents/OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md`` **§4.10**.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from System.swarm_tsp_solver import TRUTH_LABEL, solve_tsp  # noqa: E402
from System.tsplib_parser import TsplibInstance, load_tsplib_path  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
TSP_LEDGER = _STATE / "tsp_runs.jsonl"
_BUNDLED_DEMO = _REPO / "assets" / "tsplib" / "sifta_demo12.tsp"


# ── solver layer ─────────────────────────────────────────────────────────
# The solver core lives in System/swarm_tsp_solver.py so it stays
# importable without PyQt6 (tests, CI, headless scripts).


def write_receipt(receipt: dict) -> None:
    try:
        with TSP_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── UI ─────────────────────────────────────────────────────────────────


class TSPCanvas(QWidget):
    """Matplotlib-free canvas: cities + closed tour + TSPLIB-style labels."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.coords: List[Tuple[float, float]] = []
        self.labels: List[str] = []
        self.tour: List[int] = []
        self.instance_title: str = ""
        self.setStyleSheet("background-color: #0a0d12; border-radius: 8px;")

    def set_data(
        self,
        coords: Sequence[Tuple[float, float]],
        tour: Sequence[int],
        *,
        labels: Sequence[str] | None = None,
        instance_title: str = "",
    ) -> None:
        self.coords = [tuple(c) for c in coords]
        self.labels = (
            list(labels) if labels is not None else [str(i) for i in range(len(self.coords))]
        )
        while len(self.labels) < len(self.coords):
            self.labels.append(str(len(self.labels)))
        self.tour = list(tour)
        self.instance_title = instance_title
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(2, 2, -2, -2)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(18, 22, 34))
        grad.setColorAt(0.45, QColor(12, 18, 28))
        grad.setColorAt(1.0, QColor(8, 12, 22))
        p.fillRect(self.rect(), grad)

        if not self.coords:
            p.setPen(QColor(140, 160, 190))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No cities — pick a preset or load .tsp")
            return

        margin = 36
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin
        xs = [c[0] for c in self.coords]
        ys = [c[1] for c in self.coords]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        xspan = max(1e-6, xmax - xmin)
        yspan = max(1e-6, ymax - ymin)
        pad = 0.04 * max(xspan, yspan)

        def project(c: Tuple[float, float]) -> QPointF:
            x = margin + ((c[0] - xmin + pad) / (xspan + 2 * pad)) * w
            y = margin + ((c[1] - ymin + pad) / (yspan + 2 * pad)) * h
            return QPointF(x, y)

        if self.instance_title:
            p.setPen(QColor(120, 200, 255))
            p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
            p.drawText(QRectF(12, 8, self.width() - 24, 22), self.instance_title)

        # Route glow + line
        if self.tour and len(self.tour) >= 2:
            pts = [project(self.coords[i]) for i in self.tour if 0 <= i < len(self.coords)]
            if len(pts) >= 2:
                pen_glow = QPen(QColor(0, 220, 200, 70), 8)
                p.setPen(pen_glow)
                poly = QPolygonF(pts)
                p.drawPolyline(poly)
                pen = QPen(QColor(64, 255, 220), 2.2)
                p.setPen(pen)
                p.drawPolyline(poly)

        # Cities
        for i, c in enumerate(self.coords):
            pt = project(c)
            lab = self.labels[i] if i < len(self.labels) else str(i)
            p.setPen(QPen(QColor(255, 200, 120), 1))
            p.setBrush(QColor(255, 210, 90))
            p.drawEllipse(pt, 5.5, 5.5)
            p.setPen(QColor(230, 235, 245))
            p.setFont(QFont("Menlo", 8))
            p.drawText(pt + QPointF(8, -8), lab)


class TSPWidget(QWidget):
    """SIFTA Traveling Salesman demo widget (singleton per §7.6.2)."""

    _live_instance: Optional["TSPWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):  # noqa: ANN002
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # Keep the singleton re-entry guard outside the PyQt object.
        # Accessing Python attrs before QWidget.__init__ can trip SIP's
        # "super-class __init__ was never called" check on fresh wrappers.
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)

        self.setWindowTitle("SIFTA — Traveling Salesman")
        self.resize(780, 620)

        self._rng = random.Random(0)
        self._labels: List[str] = []
        self._time_limit = 2.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(8)

        title = QLabel("SIFTA — Traveling Salesman")
        title.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        outer.addWidget(title)

        sub = QLabel(
            "Alice routes the problem to the strongest available solver "
            "(stigmergic swimmers → OR-Tools → nearest-neighbour+2-opt) and "
            "returns the route + a signed receipt. Load **TSPLIB** "
            "``EUC_2D`` instances or the bundled demo — see optimization plan **§4.10**."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#aab;")
        outer.addWidget(sub)

        links = QLabel(
            "<span style='color:#8ab4ff'>Data:</span> "
            "<a href='http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/'>TSPLIB95</a> · "
            "<a href='https://www.math.uwaterloo.ca/tsp/world/country.html'>National TSP (Waterloo)</a> · "
            "<span style='color:#8ab4ff'>Solvers:</span> pip install <b>ortools</b> · "
            "GA research lane = <b>HYPOTHESIS</b> (not shipped in v1 widget)."
        )
        links.setOpenExternalLinks(True)
        links.setWordWrap(True)
        outer.addWidget(links)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset = QComboBox()
        self.preset.addItems(
            [
                "Random Euclidean (spinbox N)",
                "Bundled TSPLIB — sifta_demo12 (12 cities)",
                "Load .tsp file…",
            ]
        )
        self.preset.setCurrentIndex(1)
        self.preset.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset, 1)
        outer.addLayout(preset_row)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("N (random):"))
        self.n_spin = QSpinBox()
        self.n_spin.setRange(3, 60)
        self.n_spin.setValue(12)
        self.n_spin.valueChanged.connect(self._maybe_refresh_random)
        controls.addWidget(self.n_spin)
        self.btn_random = QPushButton("Random + Solve")
        self.btn_random.clicked.connect(self._solve_random)
        controls.addWidget(self.btn_random)
        self.btn_solve_preset = QPushButton("Solve preset")
        self.btn_solve_preset.clicked.connect(self._solve_from_preset)
        controls.addWidget(self.btn_solve_preset)
        controls.addStretch(1)
        outer.addLayout(controls)

        self.canvas = TSPCanvas()
        outer.addWidget(self.canvas, 1)

        self.receipt_view = QTextEdit()
        self.receipt_view.setReadOnly(True)
        self.receipt_view.setFont(QFont("Menlo", 10))
        self.receipt_view.setFixedHeight(130)
        outer.addWidget(self.receipt_view)

        self._solve_from_preset()
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

    def closeEvent(self, event) -> None:  # noqa: N802
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)

    def _on_preset_changed(self, _idx: int) -> None:
        self.n_spin.setEnabled(self.preset.currentIndex() == 0)

    def _maybe_refresh_random(self) -> None:
        if self.preset.currentIndex() == 0:
            self._solve_random()

    def _solve_random(self) -> None:
        n = int(self.n_spin.value())
        coords = [
            (self._rng.uniform(0.0, 100.0), self._rng.uniform(0.0, 100.0))
            for _ in range(n)
        ]
        self._labels = [str(i) for i in range(n)]
        receipt = solve_tsp(coords, time_limit_s=self._time_limit, instance_name=f"random_euclidean_n{n}")
        write_receipt(receipt)
        self.canvas.set_data(
            coords,
            receipt["tour"],
            labels=self._labels,
            instance_title=f"Random Euclidean · N={n}",
        )
        self._show_receipt(receipt)

    def _solve_from_preset(self) -> None:
        idx = self.preset.currentIndex()
        if idx == 0:
            self._solve_random()
            return
        if idx == 1:
            if not _BUNDLED_DEMO.is_file():
                self.receipt_view.setPlainText(f"Missing bundled file: {_BUNDLED_DEMO}")
                return
            inst = load_tsplib_path(_BUNDLED_DEMO)
            self._run_instance(inst)
            return
        if idx == 2:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open TSPLIB .tsp",
                str(_REPO / "assets" / "tsplib"),
                "TSPLIB (*.tsp);;All (*)",
            )
            if not path:
                return
            inst = load_tsplib_path(Path(path))
            self._run_instance(inst)

    def _run_instance(self, inst: TsplibInstance) -> None:
        self._labels = list(inst.labels)
        n = len(inst.coords)
        # Large TSPLIB: give OR-Tools more time when N > 30
        tl = 4.0 if n > 40 else self._time_limit
        receipt = solve_tsp(
            inst.coords,
            time_limit_s=tl,
            instance_name=inst.name,
        )
        write_receipt(receipt)
        title = inst.name
        if inst.source_path:
            title = f"{inst.name}  ·  {Path(inst.source_path).name}"
        self.canvas.set_data(
            inst.coords,
            receipt["tour"],
            labels=self._labels,
            instance_title=title,
        )
        self._show_receipt(receipt, extra_source=inst.source_path)

    def _show_receipt(self, receipt: dict, extra_source: str | None = None) -> None:
        lines = [
            f"INSTANCE: {receipt.get('instance_name', '(random)')}",
            f"SOLVER: {receipt['solver']}",
            f"N: {receipt['n']}",
            f"TOTAL_DISTANCE: {receipt['total_distance']:.4f}",
            f"INPUT_SHA: {receipt.get('input_sha12', '')}",
            f"TRUTH_LABEL: {receipt.get('truth_label', TRUTH_LABEL)}",
        ]
        if receipt.get("exact_distance") is not None:
            lines.append(f"EXACT_DISTANCE: {receipt['exact_distance']:.4f}")
        if receipt.get("exact_gap") is not None:
            lines.append(f"EXACT_GAP: {receipt['exact_gap']:.4f}")
        lines.extend(
            [
                f"TRUTH_NOTE: {receipt['truth_note']}",
                f"TRACE_ID: {receipt['trace_id']}",
            ]
        )
        if extra_source:
            lines.append(f"SOURCE_FILE: {extra_source}")
        self.receipt_view.setPlainText("\n".join(lines))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    w = TSPWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
