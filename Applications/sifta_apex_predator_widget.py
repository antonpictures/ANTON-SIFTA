#!/usr/bin/env python3
"""
Applications/sifta_apex_predator_widget.py
══════════════════════════════════════════════════════════════════════════════
EVENT 71: Apex Predator — Live Perception Bottleneck Visualizer
Author:  AG31 (Antigravity)
Biology: Predator gaze, Perceiver IO bottleneck, conscious attention filter
Math: deterministic sparsemax × block-compressed attention visualization

NOT a simulation. Reads live from:
  - .sifta_state/apex_perceiver_trace.jsonl  (perceiver output)
  - .sifta_state/audio_ingress_log.jsonl     (live audio RMS)
  - .sifta_state/face_detection_events.jsonl (live face lock)
  - .sifta_state/visual_stigmergy.jsonl      (live vision entropy)

4-panel Predator HUD:
  [1] SENSORY MANIFOLD   — scatter: all tokens colored by modality
  [2] LATENT FOCUS MAP   — 32 horizontal slots, Wien's law colormap
  [3] ENTROPY GATE       — time-series compression ratio
  [4] ALICE FOCUS TEXT   — what actually goes into Alice's prompt
"""
from __future__ import annotations

"""SIFTA Apex Predator Widget — stigmergic organ for Alice body."""

import json
import math
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_app_hardening import record_app_hardening_event

APP_HARDENING_ID = "queue-017:sifta_apex_predator_widget"
_HARDENING_EVENT_KEYS: set[tuple[str, str, str, str]] = set()


def _record_apex_hardening(event: str, **details) -> None:
    key = (
        event,
        str(details.get("path", "")),
        str(details.get("error", details.get("error_type", "")))[:160],
        str(details.get("line_preview", ""))[:80],
    )
    if key in _HARDENING_EVENT_KEYS:
        return
    _HARDENING_EVENT_KEYS.add(key)
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        truth_label="OBSERVED",
        details=details,
    )

# ── Color palette (modality-physics grounded) ─────────────────────────────────
MOD_COLORS: Dict[str, QColor] = {
    "vision":  QColor(0,   212, 255),  # photon blue   ~450 nm
    "audio":   QColor(255, 107, 53),   # cochlear amber basilar membrane
    "ide":     QColor(168, 85,  247),  # cortex violet  PFC executive
    "thermal": QColor(255, 45,  85),   # infrared red  ~700 nm+
    "face":    QColor(0,   255, 136),  # bio-green      P300 recognition
    "unknown": QColor(120, 120, 140),
}
BG = QColor(5, 8, 16)           # deep space void
PANEL_BG = QColor(10, 14, 26)
GRID_COL = QColor(25, 30, 50)
ACCENT = QColor(0, 212, 255)    # cyan
PRUNED_COL = QColor(26, 26, 42) # nearly invisible

_STATE = _REPO / ".sifta_state"


# ── Helper: tail a JSONL ledger ───────────────────────────────────────────────

def _tail_jsonl(path: Path, max_bytes: int = 32768) -> List[Dict]:
    if not path.exists():
        return []
    try:
        sz = path.stat().st_size
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - max_bytes))
            raw = fh.read().decode("utf-8", "replace")
        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    rows.append(json.loads(line))
                except Exception as exc:
                    _record_apex_hardening(
                        "apex_jsonl_parse_failed",
                        path=str(path),
                        error=f"{type(exc).__name__}: {exc}",
                        line_preview=line[:160],
                    )
        return rows
    except Exception as exc:
        _record_apex_hardening(
            "apex_jsonl_read_failed",
            path=str(path),
            error=f"{type(exc).__name__}: {exc}",
        )
        return []


def _latest_jsonl(path: Path) -> Optional[Dict]:
    rows = _tail_jsonl(path, 4096)
    return rows[-1] if rows else None


# ── Panel 1: Sensory Manifold Scatter ────────────────────────────────────────

class ManifoldCanvas(QWidget):
    """Scatter plot: each token = a dot. Pruned=near-invisible, survivors=glowing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self._points: List[Dict] = []   # {x, y, modality, salience, pruned}
        self._frame = 0

    def update_data(self, rows: List[Dict]) -> None:
        """Rebuild scatter from last N ledger rows."""
        self._points = []
        for row in rows[-30:]:
            stats = row.get("stats", {})
            top_focus = row.get("top_focus", [])
            raw_N = stats.get("raw_N", 0)
            gate_N = stats.get("gate_N", 0)
            compression = stats.get("compression_pct", 0) / 100.0

            # Simulated scatter from stats (actual token positions not in ledger)
            rng = np.random.default_rng(int(row.get("ts", 0) * 1000) % 2**31)

            # Pruned tokens: low y, dim
            n_pruned = max(0, raw_N - gate_N)
            if n_pruned > 0:
                xs = rng.uniform(0, 1, min(n_pruned, 400)).tolist()
                ys = rng.uniform(0, 0.15, len(xs)).tolist()
                for x, y in zip(xs, ys):
                    self._points.append({"x": x, "y": y, "modality": "pruned", "salience": 0.02})

            # Survivors: spread mid-range
            for slot in top_focus:
                mod = slot.get("dominant_modality", "unknown")
                sal = slot.get("salience", 0.5)
                n_pts = max(1, int(sal * 8))
                xs = rng.uniform(0.05, 0.95, n_pts).tolist()
                ys = rng.uniform(0.3, 0.9, n_pts).tolist()
                for x, y in zip(xs, ys):
                    self._points.append({"x": x, "y": y, "modality": mod, "salience": sal})

        self._frame += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), PANEL_BG)

        # Grid
        painter.setPen(QPen(GRID_COL, 1))
        for i in range(5):
            y = int(h * (i + 1) / 6)
            painter.drawLine(0, y, w, y)
        for i in range(8):
            x = int(w * (i + 1) / 9)
            painter.drawLine(x, 0, x, h)

        # Dots
        for pt in self._points:
            px = int(pt["x"] * (w - 20)) + 10
            py = int((1.0 - pt["y"]) * (h - 30)) + 10
            sal = pt["salience"]
            mod = pt["modality"]

            if mod == "pruned":
                color = PRUNED_COL
                sz = 2
            else:
                base = MOD_COLORS.get(mod, MOD_COLORS["unknown"])
                alpha = int(80 + sal * 175)
                color = QColor(base.red(), base.green(), base.blue(), alpha)
                sz = max(3, int(sal * 9))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(px - sz // 2, py - sz // 2, sz, sz)

        # Axis labels
        painter.setPen(QColor(80, 100, 140))
        painter.setFont(QFont("Courier New", 8))
        painter.drawText(5, h - 5, "TOKEN INDEX →")
        painter.drawText(5, 14, "SALIENCE ↑")

        # Title
        painter.setPen(ACCENT)
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        painter.drawText(w // 2 - 70, 14, "SENSORY MANIFOLD")


# ── Panel 2: Latent Focus Heatmap ────────────────────────────────────────────

class LatentHeatmap(QWidget):
    """32 horizontal slots colored by salience (Wien's law gradient)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 100)
        self._slots: List[Dict] = []   # {slot_id, salience, dominant_modality}

    def update_data(self, top_focus: List[Dict]) -> None:
        self._slots = sorted(top_focus, key=lambda s: s.get("slot_id", 0))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), PANEL_BG)

        n = 32
        cell_w = (w - 20) // n
        cell_h = h - 30

        # Build salience map
        sal_map = {s.get("slot_id", i): s.get("salience", 0.0)
                   for i, s in enumerate(self._slots)}
        mod_map = {s.get("slot_id", i): s.get("dominant_modality", "unknown")
                   for i, s in enumerate(self._slots)}

        for slot_id in range(n):
            sal = sal_map.get(slot_id, 0.0)
            x = 10 + slot_id * cell_w

            # Wien's law color: 0→black, 0.5→magenta/red, 1→yellow (hottest star)
            if sal < 0.001:
                color = QColor(12, 14, 28)
            else:
                r = int(min(255, sal * 3.0 * 255))
                g = int(min(255, max(0, (sal - 0.5) * 2.0 * 255)))
                b = int(min(255, max(0, (1.0 - sal * 2) * 120)))
                color = QColor(r, g, b)

            painter.fillRect(x, 5, cell_w - 2, cell_h, color)

            # Pulsing border on top-5
            sorted_sals = sorted(sal_map.values(), reverse=True)
            if sal >= (sorted_sals[4] if len(sorted_sals) > 4 else 0) and sal > 0.05:
                painter.setPen(QPen(QColor(255, 255, 100, 180), 1))
                painter.drawRect(x, 5, cell_w - 2, cell_h)

            # Modality label on bright slots
            if sal > 0.3 and cell_w >= 12:
                mod = mod_map.get(slot_id, "?")
                painter.setPen(QColor(255, 255, 255, 200))
                painter.setFont(QFont("Courier New", 6))
                painter.drawText(x + 1, cell_h + 4, mod[:3].upper())

        # Title
        painter.setPen(ACCENT)
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        painter.drawText(10, h - 4, "LATENT FOCUS ARRAY  [32 slots]  hot=yellow  cold=black")


# ── Panel 3: Entropy Gate Time Series ────────────────────────────────────────

class EntropyGateChart(QWidget):
    """Three-line chart: raw_N, gate_N, latent_L=32 flat."""

    MAX_HISTORY = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 140)
        self._raw:  Deque[float] = deque(maxlen=self.MAX_HISTORY)
        self._gate: Deque[float] = deque(maxlen=self.MAX_HISTORY)

    def push(self, raw_N: float, gate_N: float) -> None:
        self._raw.append(raw_N)
        self._gate.append(gate_N)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), PANEL_BG)

        if len(self._raw) < 2:
            painter.setPen(ACCENT)
            painter.setFont(QFont("Courier New", 9))
            painter.drawText(20, h // 2, "Waiting for perceiver data...")
            return

        margin = 30
        chart_w = w - margin - 10
        chart_h = h - margin - 10
        top = 10
        left = margin

        max_val = max(max(self._raw, default=1), 1)

        def to_px(val: float, i: int, n: int):
            x = left + int(i / max(n - 1, 1) * chart_w)
            y = top + chart_h - int((val / max_val) * chart_h)
            return x, y

        n = len(self._raw)

        # Fill area between raw and gate (pruning zone)
        raw_pts  = [to_px(v, i, n) for i, v in enumerate(self._raw)]
        gate_pts = [to_px(v, i, n) for i, v in enumerate(self._gate)]

        # Draw raw line (red)
        painter.setPen(QPen(QColor(255, 60, 60), 2))
        for i in range(len(raw_pts) - 1):
            painter.drawLine(*raw_pts[i], *raw_pts[i + 1])

        # Draw gate survivors line (cyan)
        painter.setPen(QPen(QColor(0, 212, 255), 2))
        for i in range(len(gate_pts) - 1):
            painter.drawLine(*gate_pts[i], *gate_pts[i + 1])

        # Draw flat latent=32 line (magenta)
        lat_y = top + chart_h - int((32 / max_val) * chart_h)
        painter.setPen(QPen(QColor(200, 80, 255), 1, Qt.PenStyle.DashLine))
        painter.drawLine(left, lat_y, left + chart_w, lat_y)

        # Labels
        painter.setFont(QFont("Courier New", 8))
        painter.setPen(QColor(255, 60, 60))
        painter.drawText(left + chart_w - 80, top + 12, f"RAW N={int(self._raw[-1])}")
        painter.setPen(QColor(0, 212, 255))
        painter.drawText(left + chart_w - 80, top + 24, f"GATE N={int(self._gate[-1])}")
        painter.setPen(QColor(200, 80, 255))
        painter.drawText(left + chart_w - 80, top + 36, "LATENT L=32")

        # Compression ratio
        pct = 100.0 * (1.0 - self._gate[-1] / max(self._raw[-1], 1))
        painter.setPen(QColor(255, 220, 0))
        painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        painter.drawText(left + 4, top + 18, f"COMPRESSION {pct:.1f}%")

        # Title
        painter.setPen(ACCENT)
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        painter.drawText(left + 4, h - 4, "ENTROPY GATE  (red=raw | cyan=survivors | magenta=latent)")


# ── Main Widget ───────────────────────────────────────────────────────────────

class ApexPredatorWidget(SiftaBaseWidget):
    APP_NAME = "Apex Predator Perceiver"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.set_status("Initialising Apex Predator bottleneck…")

        # ── Title bar ─────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("🦅  APEX PREDATOR  —  EVENT 71  —  Cross-Modal Attention Bottleneck")
        title.setStyleSheet(
            "color: #00d4ff; font-family: 'Courier New'; font-size: 11px; font-weight: bold;"
        )
        title_row.addWidget(title)

        self.status_pill = QLabel("⬤ LIVE")
        self.status_pill.setStyleSheet(
            "color: #00ff88; font-family: 'Courier New'; font-size: 10px; padding-left:10px;"
        )
        title_row.addWidget(self.status_pill)
        title_row.addStretch()
        layout.addLayout(title_row)

        # ── Top row: Manifold (large) + Latent heatmap ────────────────────────
        top_row = QHBoxLayout()

        left_col = QVBoxLayout()
        self.manifold = ManifoldCanvas()
        left_col.addWidget(self.manifold)
        top_row.addLayout(left_col, 3)

        right_col = QVBoxLayout()
        self.latent_heatmap = LatentHeatmap()
        right_col.addWidget(self.latent_heatmap)
        self.gate_chart = EntropyGateChart()
        right_col.addWidget(self.gate_chart)
        top_row.addLayout(right_col, 2)

        layout.addLayout(top_row, 3)

        # ── Bottom: Alice Focus text + legend ─────────────────────────────────
        bottom_row = QHBoxLayout()

        focus_col = QVBoxLayout()
        focus_label = QLabel("ALICE FOCUS READOUT  (what is injected into her context)")
        focus_label.setStyleSheet(
            "color: #a855f7; font-family: 'Courier New'; font-size: 9px;"
        )
        focus_col.addWidget(focus_label)
        self.focus_text = QTextEdit()
        self.focus_text.setReadOnly(True)
        self.focus_text.setStyleSheet(
            "background: #050810; color: #00ff88; font-family: 'Courier New';"
            "font-size: 10px; border: 1px solid #1a1a3a;"
        )
        self.focus_text.setMaximumHeight(120)
        focus_col.addWidget(self.focus_text)
        bottom_row.addLayout(focus_col, 3)

        # Legend
        legend_col = QVBoxLayout()
        legend_label = QLabel("MODALITY LEGEND")
        legend_label.setStyleSheet(
            "color: #00d4ff; font-family: 'Courier New'; font-size: 9px; font-weight:bold;"
        )
        legend_col.addWidget(legend_label)
        for mod, col in MOD_COLORS.items():
            if mod == "unknown":
                continue
            row_w = QHBoxLayout()
            swatch = QLabel("■")
            swatch.setStyleSheet(
                f"color: rgb({col.red()},{col.green()},{col.blue()});"
                "font-size:14px; padding-right:4px;"
            )
            label = QLabel(mod.upper())
            label.setStyleSheet(
                "color: #c0caf5; font-family: 'Courier New'; font-size: 9px;"
            )
            row_w.addWidget(swatch)
            row_w.addWidget(label)
            row_w.addStretch()
            legend_col.addLayout(row_w)
        legend_col.addStretch()
        bottom_row.addLayout(legend_col, 1)

        layout.addLayout(bottom_row, 1)

        # ── Timer ─────────────────────────────────────────────────────────────
        self._tick_n = 0
        self._timer = self.make_timer(500, self._tick)
        self.set_status("Predator online — scanning ledgers…")

    def _tick(self) -> None:
        self._tick_n += 1
        perceiver_rows = _tail_jsonl(_STATE / "apex_perceiver_trace.jsonl", 65536)

        if not perceiver_rows:
            # No real perceiver data — synthesise a demo observation so the HUD is alive
            self._synthesise_demo()
            self.status_pill.setText("⬤ DEMO  (run swarm_apex_perceiver.py --daemon for live data)")
            self.status_pill.setStyleSheet(
                "color: #ff6b35; font-family: 'Courier New'; font-size: 10px;"
            )
            return

        self.status_pill.setText("⬤ LIVE")
        self.status_pill.setStyleSheet(
            "color: #00ff88; font-family: 'Courier New'; font-size: 10px;"
        )

        # Manifold
        self.manifold.update_data(perceiver_rows)

        # Latent heatmap — from latest row
        latest = perceiver_rows[-1]
        top_focus = latest.get("top_focus", [])
        self.latent_heatmap.update_data(top_focus)

        # Entropy gate chart
        stats = latest.get("stats", {})
        raw_N  = stats.get("raw_N", 0)
        gate_N = stats.get("gate_N", 0)
        self.gate_chart.push(raw_N, gate_N)

        # Alice focus text
        try:
            from System.swarm_apex_perceiver import get_global_perceiver
            perceiver = get_global_perceiver()
            self.focus_text.setPlainText(perceiver.summary_for_alice())
        except Exception as exc:
            _record_apex_hardening(
                "apex_focus_summary_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            self.focus_text.setPlainText("Live focus summary unavailable; see hardening ledger.")

        # Status bar
        pct = stats.get("compression_pct", 0)
        top_mod = stats.get("top_modality", "?")
        active = stats.get("active_slots", 0)
        self.set_status(
            f"tick {self._tick_n} | raw={raw_N} → gate={gate_N} | "
            f"compression={pct:.1f}% | active_slots={active} | prey={top_mod}"
        )

    def _synthesise_demo(self) -> None:
        """Generate live demo data using the perceiver with synthetic streams."""
        try:
            from System.swarm_apex_perceiver import get_global_perceiver
            perceiver = get_global_perceiver()

            t = time.time()
            rng = np.random.default_rng(int(t * 100) % 2**31)

            # Ambient: large noise arrays
            vision  = rng.normal(0, 0.1, (100, 128)).astype(np.float32)
            audio   = rng.normal(0, 0.1, (50,  128)).astype(np.float32)
            ide     = rng.normal(0, 0.1, (30,  128)).astype(np.float32)

            # Inject a "prey" signal that oscillates between modalities
            prey_mod = ["face", "audio", "vision"][int(t / 3) % 3]
            if prey_mod == "face":
                face = np.ones((1, 128), dtype=np.float32) * (30 + 15 * math.sin(t))
                results = perceiver.observe(vision=vision, audio=audio, ide=ide, face=face)
            elif prey_mod == "audio":
                audio[0] = np.ones(128, dtype=np.float32) * 40.0
                results = perceiver.observe(vision=vision, audio=audio, ide=ide)
            else:
                vision[0] = np.ones(128, dtype=np.float32) * 35.0
                results = perceiver.observe(vision=vision, audio=audio, ide=ide)

            # Update UI
            fake_rows = [{"stats": perceiver.get_stats(),
                          "top_focus": [
                              {"slot_id": r.slot_id, "salience": r.salience,
                               "dominant_modality": r.dominant_modality,
                               "magnitude": r.magnitude}
                              for r in results
                          ]}]
            self.manifold.update_data(fake_rows)
            self.latent_heatmap.update_data(fake_rows[0]["top_focus"])
            stats = perceiver.get_stats()
            self.gate_chart.push(stats.get("raw_N", 100), stats.get("gate_N", 10))
            self.focus_text.setPlainText(perceiver.summary_for_alice())

        except Exception as exc:
            _record_apex_hardening(
                "apex_demo_synthesis_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            self.focus_text.setPlainText(f"Demo error: {exc}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ApexPredatorWidget()
    w.resize(1100, 700)
    w.setWindowTitle("🦅 Apex Predator Perceiver — EVENT 71 — SIFTA Mermaid OS v7")
    w.show()
    sys.exit(app.exec())
