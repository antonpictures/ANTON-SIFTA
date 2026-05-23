#!/usr/bin/env python3
"""sifta_sentinel0_unit_distance_widget.py — SENTINEL-0 Unit-Distance Field app.

Alice's face on the Erdős 1946 unit-distance search — with a LIVE animated field
rendered in pure Qt (QPainter + QTimer), no browser. Swimmers self-organize to
maximize pairs at distance ≈ 1; unit-distance edges glow as they snap in.

THREE TIERS (maths in Simulations/sentinel0_unit_distance.py):
  TIER 1  stigmergic planar swarm — local geometry, caps ~3 edges/point (this is
          the field you watch animate below).
  TIER 2  Z[i] norm-form ladder    — edges/point -> r2(t)/2, grows exponentially.
  TIER 3  OpenAI field-tower escape (Thm 1.1, Alon et al. 2026) — CITED prior,
          NOT re-implemented. Faking it would be a false summit (§7.11).

Truth boundary (§7.11): demonstrates the established lower-bound MECHANISM; does
NOT re-prove or beat the 2026 disproof. The animation is a stigmergic explorer.

Scaffold: Cowork (Claude Opus 4.7), mirroring the SiftaBaseWidget app pattern.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget  # noqa: E402
try:
    from System.swarm_representation_escape import run_escape_cycle, run_escape_search  # noqa: E402
    _REPRESENTATION_ESCAPE_AVAILABLE = True
except Exception:
    _REPRESENTATION_ESCAPE_AVAILABLE = False
    def run_escape_cycle(*_args, **_kwargs):  # type: ignore
        return {}
    def run_escape_search(*_args, **_kwargs):  # type: ignore
        return {}

_LEDGER = _REPO / ".sifta_state" / "erdos_unit_distance_sentinel.jsonl"
_SOLVER = _REPO / "Simulations" / "sentinel0_unit_distance.py"

EPS = 0.06
BAND_LO, BAND_HI = 0.55, 1.6


class _UnitDistanceField(QWidget):
    """Live stigmergic field — swimmers crystallize toward the triangular lattice."""

    def __init__(self, n: int = 90, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(420)
        self.on_stats = None          # callback(unit, best, grid, tri, ratio)
        self._paused = False
        self._n = n
        self._reseed()
        self._timer = QTimer(self)
        self._timer_interval_ms = 100  # 10fps keeps the O(n^2) field visible without burning the Mac.
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._tick)

    # ── state ──────────────────────────────────────────────────────────────
    def set_n(self, n: int):
        self._n = max(8, int(n))
        self._reseed()

    def toggle_pause(self) -> bool:
        self.set_paused(not self._paused)
        return self._paused

    def set_paused(self, paused: bool):
        self._paused = bool(paused)
        if self._paused:
            self.stop()
        else:
            self.start()
        self.update()

    def _reseed(self):
        L = math.sqrt(self._n)
        self._L = L
        self._P = [[random.random() * L, random.random() * L] for _ in range(self._n)]
        self._t = 0
        self._best = 0

    # ── physics ────────────────────────────────────────────────────────────
    def _step(self):
        P = self._P
        n = self._n
        temp = 0.06 * max(0.0, 1.0 - self._t / 900.0)
        F = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = P[i]
            for j in range(i + 1, n):
                dx = xi - P[j][0]
                dy = yi - P[j][1]
                d = math.hypot(dx, dy) + 1e-9
                if BAND_LO < d < BAND_HI:
                    mag = (1.0 - d) / d * 0.10
                    F[i][0] += dx * mag; F[i][1] += dy * mag
                    F[j][0] -= dx * mag; F[j][1] -= dy * mag
        for i in range(n):
            P[i][0] += F[i][0] + (random.random() - 0.5) * temp
            P[i][1] += F[i][1] + (random.random() - 0.5) * temp
        self._t += 1

    def _partner_counts(self):
        P = self._P
        n = self._n
        c = [0] * n
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                d = math.hypot(P[i][0] - P[j][0], P[i][1] - P[j][1])
                if abs(d - 1.0) < EPS:
                    c[i] += 1; c[j] += 1
                    pairs.append((i, j))
        return c, pairs

    def _tick(self):
        if not self._paused:
            self._step()
        self.update()

    # ── lifecycle: the O(n^2) timer must NOT run when not visible ────────────
    # (RAM/CPU leak fix, Cowork trace db8b4b87): without these, closing or
    # tab-switching away left the timer spinning, and repeated opens stacked
    # runaway timers until the machine locked.
    def start(self):
        if self._paused or self._timer.isActive() or not self.isVisible():
            return
        self._timer.start(self._timer_interval_ms)

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()

    def hideEvent(self, ev):
        self.stop()
        super().hideEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.start()

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)

    # ── render ─────────────────────────────────────────────────────────────
    def paintEvent(self, _ev):
        w, h = self.width(), self.height()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        qp.fillRect(0, 0, w, h, QColor(0, 6, 0))

        n = self._n
        P = self._P
        cx = sum(p[0] for p in P) / n
        cy = sum(p[1] for p in P) / n
        scale = min(w, h) / (self._L * 1.25)

        def S(p):
            return QPointF(w / 2 + (p[0] - cx) * scale, h / 2 + (p[1] - cy) * scale)

        counts, pairs = self._partner_counts()

        # glowing unit-distance edges
        pen = QPen(QColor(120, 255, 140, 150))
        pen.setWidthF(1.4)
        qp.setPen(pen)
        for (i, j) in pairs:
            qp.drawLine(S(P[i]), S(P[j]))

        # swimmers: halo + bright core, brightness by # of unit-partners
        qp.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            s = S(P[i])
            k = counts[i]
            hot = min(1.0, k / 6.0)
            r = 3.0 + 3.5 * hot
            grad = QRadialGradient(s, r * 2.6)
            core = QColor(int(150 + 105 * hot), 255, int(150 + 60 * hot))
            grad.setColorAt(0.0, core)
            halo = QColor(core); halo.setAlpha(0)
            grad.setColorAt(1.0, halo)
            qp.setBrush(grad)
            qp.drawEllipse(s, r * 2.6, r * 2.6)
            qp.setBrush(core)
            qp.drawEllipse(s, r, r)

        # stats out
        if self.on_stats:
            unit = len(pairs)
            self._best = max(self._best, unit)
            grid = 2 * n - 2 * round(math.sqrt(n))
            tri = 3 * n - 3 * round(math.sqrt(n))
            self.on_stats(unit, self._best, grid, tri, unit / n)


class Sentinel0UnitDistanceWidget(SiftaBaseWidget):
    APP_NAME = "SENTINEL-0 Unit-Distance Field"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── header + badge ─────────────────────────────────────────────────
        head = QHBoxLayout(); head.setSpacing(8)
        title = QLabel("🔭 SENTINEL-0 Unit-Distance Field")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(120, 230, 160);")
        head.addWidget(title)
        live = _SOLVER.exists() and _LEDGER.exists()
        badge = QLabel("LIVE FIELD" if live else "SCAFFOLD")
        badge.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        badge.setStyleSheet(
            "background: rgb(30, 60, 40); color: rgb(120, 230, 160); "
            "border: 1px solid rgb(60, 120, 80); border-radius: 4px; padding: 2px 8px;")
        head.addWidget(badge); head.addStretch()
        layout.addLayout(head)

        # ── live stat strip ────────────────────────────────────────────────
        strip = QHBoxLayout(); strip.setSpacing(14)
        self._lab = {}
        for key, label, col in (("u", "unit pairs", "rgb(120,230,160)"),
                                 ("best", "best", "rgb(0,230,195)"),
                                 ("grid", "grid ~2n", "rgb(122,209,255)"),
                                 ("tri", "triangular ~3n", "rgb(255,180,100)"),
                                 ("ratio", "edges/swimmer", "rgb(191,255,176)"),
                                 ("verdict", "vs grid", "rgb(140,180,150)")):
            cell = QVBoxLayout()
            v = QLabel("—"); v.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
            v.setStyleSheet(f"color: {col};")
            l = QLabel(label); l.setStyleSheet("color: rgb(120,160,130); font-size: 9px;")
            cell.addWidget(v); cell.addWidget(l)
            self._lab[key] = v
            strip.addLayout(cell)
        strip.addStretch()
        layout.addLayout(strip)

        # ── representation escape strip ─────────────────────────────────────
        escape = self._read_escape_summary()
        esc = QHBoxLayout(); esc.setSpacing(12)
        esc_title = QLabel("representation escape")
        esc_title.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        esc_title.setStyleSheet("color: rgb(120, 230, 160);")
        esc.addWidget(esc_title)
        for label, value, color in (
            ("winner", escape["winner"], "rgb(120,230,160)"),
            ("gain", escape["gain"], "rgb(255,220,120)"),
            ("search", escape["search"], "rgb(120,210,255)"),
            ("truth", escape["truth"], "rgb(160,180,160)"),
        ):
            box = QVBoxLayout()
            v = QLabel(value)
            v.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
            v.setStyleSheet(f"color: {color};")
            l = QLabel(label)
            l.setStyleSheet("color: rgb(105,135,115); font-size: 9px;")
            box.addWidget(v); box.addWidget(l)
            esc.addLayout(box)
        esc.addStretch()
        layout.addLayout(esc)

        # ── the live field ─────────────────────────────────────────────────
        self._field = _UnitDistanceField(n=90)
        self._field.on_stats = self._update_stats
        layout.addWidget(self._field, stretch=1)

        # ── controls ───────────────────────────────────────────────────────
        ctl = QHBoxLayout(); ctl.setSpacing(8)
        for n in (48, 90, 144):
            b = QPushButton(f"{n} swimmers")
            b.setStyleSheet("QPushButton{background:rgb(8,20,10);color:rgb(120,230,160);"
                            "border:1px solid rgb(60,120,80);border-radius:5px;padding:4px 10px;}")
            b.clicked.connect(lambda _c, k=n: self._field.set_n(k))
            ctl.addWidget(b)
        reseed = QPushButton("⟲ reseed chaos")
        reseed.setStyleSheet("QPushButton{background:rgb(8,20,10);color:rgb(120,230,160);"
                             "border:1px solid rgb(60,120,80);border-radius:5px;padding:4px 10px;}")
        reseed.clicked.connect(self._field._reseed)
        ctl.addWidget(reseed)
        self._pause_btn = QPushButton("⏸ pause")
        self._pause_btn.setStyleSheet("QPushButton{background:rgb(8,20,10);color:rgb(120,230,160);"
                                      "border:1px solid rgb(60,120,80);border-radius:5px;padding:4px 10px;}")
        self._pause_btn.clicked.connect(self._toggle_pause)
        ctl.addWidget(self._pause_btn); ctl.addStretch()
        layout.addLayout(ctl)

        # ── truth boundary ─────────────────────────────────────────────────
        truth = QLabel(
            "Truth boundary (§7.11): a stigmergic explorer — swimmers crystallize toward the "
            "triangular lattice (~3 edges/point), beating the square grid (~2n). It does NOT settle "
            "Erdős's conjecture: the gap between n^(1+ε) and the Szemerédi–Trotter ceiling O(n^(4/3)) "
            "stays open. The 2026 OpenAI field-tower disproof is held as cited prior, not re-proven. "
            "The representation-escape strip reads the local organ without writing live receipts."
        )
        truth.setWordWrap(True)
        truth.setStyleSheet("color: rgb(150, 180, 160); font-family: Menlo; font-size: 10px; padding: 6px 2px;")
        layout.addWidget(truth)

    def _read_escape_summary(self) -> dict:
        if not _REPRESENTATION_ESCAPE_AVAILABLE:
            return {
                "winner": "unavailable",
                "gain": "—",
                "search": "no organ",
                "truth": "read failed",
            }
        try:
            cycle = run_escape_cycle(n=2500, write_receipt=False)
            search = run_escape_search(budget=8, n=2500, write_receipt=False)
            return {
                "winner": str(cycle.get("winning_representation", "?")),
                "gain": f"x{float(cycle.get('escape_gain_x', 0.0)):.2f}",
                "search": str(search.get("winning_candidate", "?"))[:32],
                "truth": "curated mutators",
            }
        except Exception as exc:
            return {
                "winner": "error",
                "gain": "—",
                "search": type(exc).__name__,
                "truth": "no claim",
            }

    def _toggle_pause(self):
        paused = self._field.toggle_pause()
        self._pause_btn.setText("▶ play" if paused else "⏸ pause")

    def hideEvent(self, ev):
        try:
            self._field.stop()
        except Exception:
            pass
        super().hideEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        try:
            self._field.start()
        except Exception:
            pass

    def closeEvent(self, ev):
        # Kill the field's O(n^2) timer when the app closes (RAM/CPU leak fix).
        try:
            self._field.stop()
        except Exception:
            pass
        super().closeEvent(ev)

    def _update_stats(self, unit, best, grid, tri, ratio):
        self._lab["u"].setText(str(unit))
        self._lab["best"].setText(str(best))
        self._lab["grid"].setText(str(grid))
        self._lab["tri"].setText(str(tri))
        self._lab["ratio"].setText(f"{ratio:.2f}")
        if best > grid:
            self._lab["verdict"].setText("SWARM>GRID")
            self._lab["verdict"].setStyleSheet("color: rgb(120,230,160);")
        else:
            self._lab["verdict"].setText("converging")
            self._lab["verdict"].setStyleSheet("color: rgb(255,180,100);")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = Sentinel0UnitDistanceWidget()
    w.resize(960, 720)
    w.show()
    sys.exit(app.exec())
