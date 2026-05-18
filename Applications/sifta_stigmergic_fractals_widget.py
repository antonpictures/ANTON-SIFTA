#!/usr/bin/env python3
"""Applications/sifta_stigmergic_fractals_widget.py — Stigmergic Fractals.

Architect 2026-05-17 (verbatim, abridged):
    "Is this now an app in SIFTA OS with graphics and data? Call it
    Stigmergic Fractals."

Live visualization of SIFTA's fractal stigmergy organs:
  * the Sierpinski gasket substrate (System/swarm_fractal_substrate.py)
  * the random-walking swimmers (System/swarm_fractal_walker_organ.py)
  * the persistent-homology topology pass
    (System/swarm_fractal_topology_organ.py)

Visual layout — top to bottom:
  1. Header strip — name + measured walk dimension + expected closed-form
  2. Big render area — the gasket structure in dim blue, swimmers as
     bright dots, pheromone heat as a red glow proportional to per-site
     visit count
  3. Topology strip — Betti-0 (component count) and Betti-1 (loop count)
     curves over the density-threshold sweep, plus a sparkline of the
     mean-square displacement that drives the walk-dimension fit
  4. Footer — SIFTA / Coleman Beeson 2026 copyright

Truth label: ``STIGMERGIC_FRACTALS_APP_V0``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_fractal_substrate import SierpinskiGasket
from System.swarm_fractal_walker_organ import (
    _gate_stamp as _walker_gate_stamp,
    _write_pheromone,
    _euclidean_r2,
)

# Optional — the topology organ runs offline on the ledger.
try:
    from System.swarm_fractal_topology_organ import compute_persistence
except Exception:
    compute_persistence = None


# ── visual constants ──────────────────────────────────────────────────────
_BG = QColor(8, 10, 24)
_GASKET_EDGE = QColor(60, 90, 140, 130)
_GASKET_NODE = QColor(120, 160, 220, 200)
_SWIMMER = QColor(255, 230, 80, 235)
_PHEROMONE = QColor(255, 80, 60)
_HEADER_BG = QColor(28, 22, 56, 220)
_HEADER_TEXT = QColor(190, 230, 255)
_HEADER_ACCENT = QColor(255, 210, 63)
_TOPOLOGY_AXIS = QColor(120, 130, 170, 180)
_BETTI0_LINE = QColor(120, 220, 255)
_BETTI1_LINE = QColor(255, 140, 200)
_MSD_LINE = QColor(180, 255, 160)


class _GasketCanvas(QWidget):
    """The big render area: gasket + swimmers + pheromone heat."""

    def __init__(self, gasket: SierpinskiGasket, parent=None):
        super().__init__(parent)
        self._gasket = gasket
        self._swimmers: List[Tuple[int, int]] = []
        self._pheromone: Dict[Tuple[int, int], int] = {}
        self.setMinimumHeight(380)
        self.setStyleSheet("background-color: #08081A;")

    def set_swimmers(self, sites: List[Tuple[int, int]]) -> None:
        self._swimmers = sites
        self.update()

    def add_pheromone(self, site: Tuple[int, int]) -> None:
        self._pheromone[site] = self._pheromone.get(site, 0) + 1

    def reset_pheromone(self) -> None:
        self._pheromone.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QBrush(_BG))

        # Compute screen mapping. Gasket lives in (x, y) ∈ [0,1] × [0, √3/2]
        margin_x = 18
        margin_top = 12
        margin_bottom = 12
        gasket_w = max(1, w - 2 * margin_x)
        gasket_h = max(1, h - margin_top - margin_bottom)
        # Preserve aspect (Sierpinski triangle is wider than tall by 1 / (√3/2) ≈ 1.155).
        scale = min(gasket_w, gasket_h / (math.sqrt(3) / 2))
        ox = (w - scale) / 2
        oy = (h - scale * math.sqrt(3) / 2) / 2

        def to_screen(xy: Tuple[float, float]) -> QPointF:
            return QPointF(ox + xy[0] * scale, oy + xy[1] * scale)

        # 1) Pheromone heat — radial gradient at each visited site,
        #    intensity scaled to max visit count.
        if self._pheromone:
            max_visits = max(self._pheromone.values())
            for site, count in self._pheromone.items():
                xy = self._gasket.coords(site)
                center = to_screen(xy)
                intensity = count / max_visits if max_visits else 0
                r = 3 + 14 * (intensity ** 0.5)
                grad = QRadialGradient(center, r)
                grad.setColorAt(
                    0.0,
                    QColor(_PHEROMONE.red(), _PHEROMONE.green(),
                           _PHEROMONE.blue(), int(180 * intensity)),
                )
                grad.setColorAt(1.0,
                                QColor(_PHEROMONE.red(), _PHEROMONE.green(),
                                       _PHEROMONE.blue(), 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(center, r, r)

        # 2) Gasket edges in dim blue.
        p.setPen(QPen(_GASKET_EDGE, 0.8))
        drawn_edges: set = set()
        for site in self._gasket.sites():
            xy = self._gasket.coords(site)
            for n in self._gasket.neighbors(site):
                key = tuple(sorted((site, n)))
                if key in drawn_edges:
                    continue
                drawn_edges.add(key)
                xy2 = self._gasket.coords(n)
                p.drawLine(to_screen(xy), to_screen(xy2))

        # 3) Gasket nodes.
        p.setBrush(QBrush(_GASKET_NODE))
        p.setPen(Qt.PenStyle.NoPen)
        node_r = 1.7
        for site in self._gasket.sites():
            xy = self._gasket.coords(site)
            p.drawEllipse(to_screen(xy), node_r, node_r)

        # 4) Swimmers.
        if self._swimmers:
            p.setBrush(QBrush(_SWIMMER))
            p.setPen(QPen(QColor(40, 36, 14), 0.4))
            for site in self._swimmers:
                xy = self._gasket.coords(site)
                p.drawEllipse(to_screen(xy), 3.6, 3.6)


class _TopologyStrip(QWidget):
    """Bottom strip: Betti-0 curve + Betti-1 curve + MSD sparkline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._betti0: List[int] = []
        self._betti1: List[int] = []
        self._msd_series: List[Tuple[int, float]] = []
        self._measured_dw: Optional[float] = None
        self._expected_dw: Optional[float] = None
        self.setFixedHeight(150)
        self.setStyleSheet("background-color: #0E0C24;")

    def update_topology(self, betti0: List[int], betti1: List[int]) -> None:
        self._betti0 = list(betti0)
        self._betti1 = list(betti1)
        self.update()

    def update_msd(
        self, series: List[Tuple[int, float]],
        measured_dw: float, expected_dw: float,
    ) -> None:
        self._msd_series = list(series)
        self._measured_dw = measured_dw
        self._expected_dw = expected_dw
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QBrush(QColor(14, 12, 36)))

        # Three panels side by side.
        panel_w = w / 3.0
        self._draw_betti_panel(p, 0, panel_w, h, "β₀  (components)",
                                self._betti0, _BETTI0_LINE)
        self._draw_betti_panel(p, panel_w, panel_w, h, "β₁  (loops)",
                                self._betti1, _BETTI1_LINE)
        self._draw_msd_panel(p, 2 * panel_w, panel_w, h)

    def _draw_betti_panel(self, p: QPainter, x0: float, pw: float, ph: float,
                          title: str, series: List[int], color: QColor) -> None:
        p.setPen(QPen(_HEADER_TEXT, 1))
        f = QFont(); f.setPointSize(9); f.setBold(True)
        p.setFont(f)
        p.drawText(int(x0 + 8), 16, title)
        # Axes
        ax_x0 = x0 + 28
        ax_y0 = 30
        ax_x1 = x0 + pw - 12
        ax_y1 = ph - 12
        p.setPen(QPen(_TOPOLOGY_AXIS, 0.8))
        p.drawLine(int(ax_x0), int(ax_y1), int(ax_x1), int(ax_y1))
        p.drawLine(int(ax_x0), int(ax_y1), int(ax_x0), int(ax_y0))
        if not series:
            p.setPen(QPen(QColor(150, 150, 180, 140), 1))
            f2 = QFont(); f2.setPointSize(8)
            p.setFont(f2)
            p.drawText(int(ax_x0 + 8), int((ax_y0 + ax_y1) / 2),
                       "no topology yet — waiting for pheromone")
            return
        max_v = max(max(series), 1)
        n = len(series)
        # Plot line
        p.setPen(QPen(color, 1.6))
        prev = None
        for i, v in enumerate(series):
            x = ax_x0 + (i / max(1, n - 1)) * (ax_x1 - ax_x0)
            y = ax_y1 - (v / max_v) * (ax_y1 - ax_y0)
            cur = QPointF(x, y)
            if prev is not None:
                p.drawLine(prev, cur)
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cur, 1.8, 1.8)
            p.setPen(QPen(color, 1.6))
            prev = cur
        # Max-value label
        f3 = QFont(); f3.setPointSize(7)
        p.setFont(f3)
        p.setPen(QPen(_HEADER_TEXT, 1))
        p.drawText(int(x0 + 8), int(ax_y0 + 8), f"max {max_v}")

    def _draw_msd_panel(self, p: QPainter, x0: float, pw: float, ph: float) -> None:
        p.setPen(QPen(_HEADER_TEXT, 1))
        f = QFont(); f.setPointSize(9); f.setBold(True)
        p.setFont(f)
        p.drawText(int(x0 + 8), 16, "⟨r²(t)⟩  →  d_w")
        ax_x0 = x0 + 28
        ax_y0 = 30
        ax_x1 = x0 + pw - 12
        ax_y1 = ph - 12
        p.setPen(QPen(_TOPOLOGY_AXIS, 0.8))
        p.drawLine(int(ax_x0), int(ax_y1), int(ax_x1), int(ax_y1))
        p.drawLine(int(ax_x0), int(ax_y1), int(ax_x0), int(ax_y0))
        if self._msd_series:
            ts = [t for t, _ in self._msd_series]
            rs = [r for _, r in self._msd_series]
            t_min, t_max = min(ts), max(ts)
            r_min, r_max = min(rs), max(rs)
            r_max = max(r_max, r_min + 1e-9)
            t_span = max(1, t_max - t_min)
            p.setPen(QPen(_MSD_LINE, 1.4))
            prev = None
            for t, r in self._msd_series:
                x = ax_x0 + ((t - t_min) / t_span) * (ax_x1 - ax_x0)
                y = ax_y1 - ((r - r_min) / (r_max - r_min)) * (ax_y1 - ax_y0)
                cur = QPointF(x, y)
                if prev is not None:
                    p.drawLine(prev, cur)
                prev = cur
        if self._measured_dw is not None and self._expected_dw is not None:
            f4 = QFont(); f4.setPointSize(8); f4.setBold(True)
            p.setFont(f4)
            err_pct = abs(self._measured_dw - self._expected_dw) / self._expected_dw * 100
            p.setPen(QPen(_HEADER_ACCENT, 1))
            p.drawText(int(ax_x0 + 6), int(ax_y0 + 12),
                       f"d_w meas {self._measured_dw:.3f}")
            p.setPen(QPen(_HEADER_TEXT, 1))
            p.drawText(int(ax_x0 + 6), int(ax_y0 + 26),
                       f"d_w expect {self._expected_dw:.3f}   err {err_pct:.2f}%")


class StigmergicFractalsWidget(QWidget):
    """Live visual: the Sierpinski substrate, swimmers, pheromones, topology."""

    _live_instance: Optional["StigmergicFractalsWidget"] = None
    _initialized_instance_ids: set = set()

    def __new__(cls, *args, **kwargs):  # noqa: D401
        if cls._live_instance is not None:
            try:
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except Exception:
                pass
        inst = super().__new__(cls)
        cls._live_instance = inst
        return inst

    def __init__(self, parent: Optional[QWidget] = None,
                 *, depth: int = 5, walkers: int = 80, write_pheromone: bool = False):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        self.setWindowTitle("Stigmergic Fractals")
        self.resize(820, 720)
        self.setStyleSheet("background-color: #08081A; color: #DDEAFF;")

        self._gasket = SierpinskiGasket(depth=depth)
        self._rng = random.Random(time.time_ns() & 0xFFFFFFFF)
        spawn = self._gasket.corner_sites()[0]
        self._spawn_xy = self._gasket.coords(spawn)
        self._swimmers: List[Tuple[int, int]] = [spawn for _ in range(walkers)]
        self._steps: List[int] = [0] * walkers
        self._msd_sum: Dict[int, float] = {}
        self._msd_count: Dict[int, int] = {}
        self._write_pheromone = bool(write_pheromone)
        self._tick_interval_ms = 120
        self._ticks_per_frame = 4    # 4 walker-steps per repaint
        self._max_steps = 4000       # auto-stop after this many steps each

        # ── header ─────────────────────────────────────────────────────
        title = QLabel("Stigmergic Fractals")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 19px; font-weight: 700; padding: 8px; "
            "color: #BFE9FF; background: rgba(28,22,56,0.78); "
            "border-radius: 12px;"
        )

        self._status_lbl = QLabel(
            "Sierpinski gasket — depth {d}, {n} sites, {w} swimmers. "
            "Expected d_w = log(5)/log(2) ≈ 2.3219".format(
                d=depth, n=len(self._gasket), w=walkers,
            )
        )
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "color: #BFE9FF; font-size: 11px; padding: 4px 8px; "
            "background: rgba(91,208,255,0.06); border-radius: 8px;"
        )

        # ── controls row ───────────────────────────────────────────────
        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pause.setStyleSheet(self._btn_style())
        self._btn_pause.clicked.connect(self._toggle_pause)

        self._btn_reset = QPushButton("↺  Reset")
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.setStyleSheet(self._btn_style())
        self._btn_reset.clicked.connect(self._reset)

        self._btn_topology = QPushButton("∂  Topology pass")
        self._btn_topology.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_topology.setStyleSheet(self._btn_style())
        self._btn_topology.clicked.connect(self._run_topology_pass)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_reset)
        controls.addWidget(self._btn_topology)
        controls.addStretch(1)

        # ── canvas + topology strip ────────────────────────────────────
        self._canvas = _GasketCanvas(self._gasket, self)
        self._canvas.set_swimmers(self._swimmers)
        self._topology = _TopologyStrip(self)

        # ── footer ─────────────────────────────────────────────────────
        footer = QLabel("🐝   © 2026 SIFTA  ·  Coleman Beeson   🐝")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "color: #FFD23F; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1.5px; padding: 6px;"
        )

        # ── layout ─────────────────────────────────────────────────────
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        lay.addWidget(title)
        lay.addWidget(self._status_lbl)
        lay.addLayout(controls)
        lay.addWidget(self._canvas, 3)
        lay.addWidget(self._topology, 1)
        lay.addWidget(footer)

        # ── tick timer ─────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.setInterval(self._tick_interval_ms)
        self._timer.timeout.connect(self._step_swarm)
        self._paused = False
        self._timer.start()

        type(self)._initialized_instance_ids.add(id(self))

    # ── walker dynamics ─────────────────────────────────────────────────
    def _step_swarm(self) -> None:
        if self._paused:
            return
        anyone_alive = False
        for _ in range(self._ticks_per_frame):
            for w, site in enumerate(self._swimmers):
                if self._steps[w] >= self._max_steps:
                    continue
                anyone_alive = True
                nbrs = self._gasket.neighbors(site)
                if not nbrs:
                    continue
                nxt = self._rng.choice(nbrs)
                self._swimmers[w] = nxt
                self._steps[w] += 1
                t = self._steps[w]
                r2 = _euclidean_r2(self._gasket.coords(nxt), self._spawn_xy)
                self._msd_sum[t] = self._msd_sum.get(t, 0.0) + r2
                self._msd_count[t] = self._msd_count.get(t, 0) + 1
                self._canvas.add_pheromone(nxt)
                if self._write_pheromone:
                    row = {
                        "ts": time.time(),
                        "schema": "FRACTAL_PHEROMONE_STEP_V0",
                        "truth_label": "SIFTA_FRACTAL_WALKER_V0",
                        "run_id": "live-app",
                        "walker_id": f"live-app-w{w:04d}",
                        "t": t,
                        "site_x": nxt[0], "site_y": nxt[1],
                        "coord_x": round(self._gasket.coords(nxt)[0], 6),
                        "coord_y": round(self._gasket.coords(nxt)[1], 6),
                        "scale": self._gasket.scale(nxt),
                        "r2": round(r2, 8),
                    }
                    try:
                        _walker_gate_stamp(row, lane="fractal.pheromone")
                        _write_pheromone(row)
                    except Exception:
                        pass
        self._canvas.set_swimmers(self._swimmers)
        self._update_msd_panel()
        if not anyone_alive:
            self._timer.stop()
            self._status_lbl.setText("Walk complete. Press 'Topology pass' to compute Betti curves.")

    def _update_msd_panel(self) -> None:
        # Build ⟨r²(t)⟩ series.
        ts_sorted = sorted(self._msd_sum.keys())
        if len(ts_sorted) < 8:
            return
        series = [(t, self._msd_sum[t] / max(1, self._msd_count[t]))
                  for t in ts_sorted if self._msd_count[t] > 0]
        # Fit on inner log-time window.
        T = float(max(t for t, _ in series))
        t_lo = max(2.0, T ** 0.25)
        t_hi = max(t_lo + 1.0, T ** 0.75)
        fit = [(t, r) for t, r in series if t_lo <= t <= t_hi and r > 0]
        if len(fit) < 4:
            self._topology.update_msd(series, 0.0, self._gasket.walk_dim)
            return
        # log-log linear fit
        xs = [math.log(t) for t, _ in fit]
        ys = [math.log(r) for _, r in fit]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n))
        alpha = num / den if den else 0.0
        dw_measured = 2.0 / alpha if alpha > 0 else 0.0
        self._topology.update_msd(series, dw_measured, self._gasket.walk_dim)
        if dw_measured > 0:
            err = abs(dw_measured - self._gasket.walk_dim) / self._gasket.walk_dim * 100
            self._status_lbl.setText(
                f"d_w measured {dw_measured:.4f}  |  expected {self._gasket.walk_dim:.4f}  "
                f"|  error {err:.2f}%  |  steps {max(self._steps)}"
            )

    # ── controls ─────────────────────────────────────────────────────────
    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._btn_pause.setText("▶  Resume" if self._paused else "⏸  Pause")

    def _reset(self) -> None:
        self._paused = False
        self._btn_pause.setText("⏸  Pause")
        spawn = self._gasket.corner_sites()[0]
        self._swimmers = [spawn for _ in range(len(self._swimmers))]
        self._steps = [0] * len(self._swimmers)
        self._msd_sum.clear()
        self._msd_count.clear()
        self._canvas.reset_pheromone()
        self._canvas.set_swimmers(self._swimmers)
        self._topology.update_msd([], 0.0, self._gasket.walk_dim)
        self._topology.update_topology([], [])
        if not self._timer.isActive():
            self._timer.start()

    def _run_topology_pass(self) -> None:
        if compute_persistence is None:
            self._status_lbl.setText("Topology module unavailable.")
            return
        try:
            receipt = compute_persistence()
        except Exception as exc:
            self._status_lbl.setText(f"Topology pass failed: {exc}")
            return
        b0 = receipt.get("betti_0_curve") or []
        b1 = receipt.get("betti_1_curve") or []
        self._topology.update_topology(b0, b1)
        nrows = receipt.get("total_pheromone_rows", "?")
        sites = receipt.get("unique_sites", "?")
        self._status_lbl.setText(
            f"Topology: {nrows} rows, {sites} sites, "
            f"max β₀={max(b0) if b0 else 0}, max β₁={max(b1) if b1 else 0}"
        )

    # ── styling helper ───────────────────────────────────────────────────
    @staticmethod
    def _btn_style() -> str:
        return (
            "QPushButton {"
            " background: rgba(91,208,255,0.10);"
            " color: #BFE9FF;"
            " border: 1px solid rgba(91,208,255,0.35);"
            " border-radius: 10px;"
            " padding: 6px 14px;"
            " font-size: 12px;"
            " font-weight: 600;"
            "}"
            "QPushButton:hover { background: rgba(91,208,255,0.20); }"
            "QPushButton:pressed { background: rgba(91,208,255,0.32); }"
        )


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    w = StigmergicFractalsWidget(depth=5, walkers=80, write_pheromone=False)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
