#!/usr/bin/env python3
"""
sifta_medscan_widget.py — Stigmergic Medical Scanner
═════════════════════════════════════════════════════════
Treat medical data as terrain.  Deploy swimmers.
They cluster around anomalies.  The swarm sees what humans miss.

Three terrain modes:
  TISSUE  — mammography cross-section with masses + microcalcifications
  GENOMIC — gene expression heatmap with anomalous regulation clusters
  BLOOD   — cell scatter field with morphologically abnormal cells

Four swimmer species:
  DiagnosticForager (teal ●)      — general anomaly detection via chemotaxis
  CalcificationHunter (red ◆)     — seeks bright micro-spot clusters
  MarginMapper (purple ▲)         — traces contours of detected masses
  PatrolSweeper (blue ■)          — systematic raster scan, marks coverage

The pheromone overlay is the diagnostic output: hot = high confidence anomaly.
"""
from __future__ import annotations

import sys
import time
import random
from pathlib import Path
from typing import List

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QPlainTextEdit, QComboBox,
    QCheckBox, QSplitter, QTabWidget, QTextEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from System.sifta_base_widget import SiftaBaseWidget
from System.diagnostic_swarm import (
    generate_tissue_terrain, generate_genomic_terrain, generate_blood_terrain,
    compute_anomaly_map, spawn_swimmers, step_swimmers, evaporate_pheromone,
    Anomaly, MedSwimmer,
)

# ── Custom colormaps ─────────────────────────────────────────────

TISSUE_CMAP = LinearSegmentedColormap.from_list("tissue", [
    (0.0, "#080810"), (0.2, "#1a1830"), (0.4, "#2a2845"),
    (0.6, "#4a4870"), (0.8, "#8888aa"), (1.0, "#ddddff"),
])

GENOMIC_CMAP = LinearSegmentedColormap.from_list("genomic", [
    (0.0, "#0a0a18"), (0.15, "#0a2040"), (0.3, "#0a4060"),
    (0.5, "#0a8060"), (0.7, "#20c040"), (0.85, "#80e020"),
    (1.0, "#ffff40"),
])

BLOOD_CMAP = LinearSegmentedColormap.from_list("blood", [
    (0.0, "#ffeedd"), (0.2, "#eeccaa"), (0.4, "#cc8888"),
    (0.6, "#aa4455"), (0.8, "#882244"), (1.0, "#440022"),
])

PHERO_CMAP = LinearSegmentedColormap.from_list("diag_phero", [
    (0.0, (0, 0, 0, 0)), (0.15, (1, 0.3, 0, 0.15)),
    (0.4, (1, 0.5, 0, 0.4)), (0.7, (1, 0.8, 0, 0.65)),
    (1.0, (1, 1, 0.3, 0.9)),
])

BG = "#060a12"

TERRAIN_CMAPS = {
    "TISSUE": TISSUE_CMAP,
    "GENOMIC": GENOMIC_CMAP,
    "BLOOD": BLOOD_CMAP,
}


# ── Canvas ───────────────────────────────────────────────────────

class MedScanCanvas(FigureCanvas):
    """Four-panel medical display: terrain, anomaly map, pheromone overlay, swimmer trails."""

    def __init__(self, parent: QWidget | None = None):
        self._fig = Figure(figsize=(16, 10), facecolor=BG, dpi=85)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(900, 600)

        self._axes = self._fig.subplots(1, 3, gridspec_kw={"wspace": 0.08})
        for ax in self._axes:
            ax.set_facecolor(BG)
            ax.axis("off")

        self._terrain: np.ndarray | None = None
        self._anomaly_map: np.ndarray | None = None
        self._pheromone: np.ndarray | None = None
        self._swimmers: List[MedSwimmer] = []
        self._anomalies: List[Anomaly] = []
        self._terrain_mode = "TISSUE"
        self._tick = 0

        self._im_terrain = None
        self._im_anomaly = None
        self._im_phero = None

    def set_data(self, terrain, anomaly_map, pheromone, swimmers, anomalies, mode):
        self._terrain = terrain
        self._anomaly_map = anomaly_map
        self._pheromone = pheromone
        self._swimmers = swimmers
        self._anomalies = anomalies
        self._terrain_mode = mode

    def render_frame(self):
        if self._terrain is None:
            return
        self._tick += 1

        ax_t, ax_p, ax_o = self._axes
        for ax in self._axes:
            ax.clear()
            ax.set_facecolor(BG)
            ax.axis("off")

        cmap = TERRAIN_CMAPS.get(self._terrain_mode, TISSUE_CMAP)
        rows, cols = self._terrain.shape

        # ── Panel 1: Tissue + planted anomaly markers ────────
        ax_t.imshow(self._terrain, cmap=cmap, origin="lower", aspect="equal",
                     vmin=0, vmax=1, interpolation="bilinear")

        for a in self._anomalies:
            color = "#ff4444" if not a.detected else "#00ff88"
            marker = "+" if a.anomaly_type == "microcalc" else "o"
            ax_t.plot(a.cy, a.cx, marker, color=color, markersize=8,
                      markeredgewidth=1.5, alpha=0.7)

        ax_t.set_title("TISSUE TERRAIN", fontsize=8, color="#8090b0",
                        fontfamily="monospace", pad=4)

        # ── Panel 2: Pheromone diagnostic overlay on terrain ─
        ax_p.imshow(self._terrain, cmap=cmap, origin="lower", aspect="equal",
                     vmin=0, vmax=1, interpolation="bilinear", alpha=0.5)
        if self._pheromone.max() > 0.001:
            ax_p.imshow(self._pheromone, cmap=PHERO_CMAP, origin="lower",
                         aspect="equal", vmin=0, vmax=max(0.3, self._pheromone.max()),
                         interpolation="bilinear")

        # Draw swimmers on pheromone panel
        for sw in self._swimmers:
            pulse = 0.5 + 0.5 * (1 if self._tick % 6 < 3 else 0.6)
            ax_p.plot(sw.y, sw.x, sw.marker, color=sw.color,
                      markersize=3.5, alpha=pulse, markeredgewidth=0.5)
            # Short trail
            if len(sw.trail) > 3:
                trail = sw.trail[-15:]
                tx = [t[1] for t in trail]
                ty = [t[0] for t in trail]
                ax_p.plot(tx, ty, "-", color=sw.color, alpha=0.15, linewidth=0.5)

        ax_p.set_title("PHEROMONE DIAGNOSTIC", fontsize=8, color="#ffaa44",
                        fontfamily="monospace", pad=4)

        # ── Panel 3: Anomaly heatmap (statistical) ───────────
        ax_o.imshow(self._anomaly_map, cmap="inferno", origin="lower",
                     aspect="equal", vmin=0, vmax=0.8, interpolation="bilinear")

        detected = [a for a in self._anomalies if a.detected]
        for a in detected:
            circ = plt.Circle((a.cy, a.cx), a.radius * 1.5, fill=False,
                              color="#00ff88", linewidth=1.0, alpha=0.8, linestyle="--")
            ax_o.add_patch(circ)
            ax_o.text(a.cy, a.cx + a.radius * 1.8,
                      f"{a.anomaly_type}\n{a.confidence:.0%}",
                      fontsize=5, color="#00ff88", ha="center", va="bottom",
                      fontfamily="monospace", alpha=0.9)

        ax_o.set_title("ANOMALY MAP (STATISTICAL)", fontsize=8, color="#ff6644",
                        fontfamily="monospace", pad=4)

        # ── Global HUD ───────────────────────────────────────
        total_phero = self._pheromone.sum()
        coverage = np.count_nonzero(self._pheromone > 0.01) / max(1, rows * cols)
        n_detected = sum(1 for a in self._anomalies if a.detected)
        n_total = len(self._anomalies)
        total_anomalies_found = sum(sw.anomalies_found for sw in self._swimmers)

        hud = (
            f"STIGMERGIC MEDICAL SCANNER  |  "
            f"Mode: {self._terrain_mode}  |  "
            f"Swimmers: {len(self._swimmers)}  |  "
            f"Detected: {n_detected}/{n_total}  |  "
            f"Coverage: {coverage*100:.1f}%  |  "
            f"Pheromone: {total_phero:.1f}  |  "
            f"Tick: {self._tick}"
        )
        self._fig.suptitle(hud, fontsize=7, color="#00ffc8",
                           fontfamily="monospace", y=0.02)

        self._fig.tight_layout(rect=[0, 0.04, 1, 0.97], pad=1.0)
        self.draw_idle()


# ── Main Widget ─────────────────────────────────────────────────

class MedScanWidget(SiftaBaseWidget):
    """Stigmergic Medical Scanner — swarm anomaly detection on medical terrain."""
    APP_NAME = "Stigmergic Medical Scanner"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Controls ────────────────────────────────────────────
        ctrl = QHBoxLayout()

        self._btn_start = QPushButton("Deploy Swimmers")
        self._btn_start.clicked.connect(self._toggle_scan)
        ctrl.addWidget(self._btn_start)

        self._btn_reset = QPushButton("New Terrain")
        self._btn_reset.clicked.connect(self._regenerate)
        ctrl.addWidget(self._btn_reset)

        ctrl.addStretch()

        ctrl.addWidget(QLabel("Terrain:"))
        self._combo_mode = QComboBox()
        self._combo_mode.addItems(["TISSUE", "GENOMIC", "BLOOD"])
        self._combo_mode.currentTextChanged.connect(self._change_mode)
        ctrl.addWidget(self._combo_mode)

        self._chk_trails = QCheckBox("Show trails")
        self._chk_trails.setChecked(True)
        ctrl.addWidget(self._chk_trails)

        layout.addLayout(ctrl)

        # ── Splitter: canvas + right panel (log / swarm) ───────
        # Use _pane_splitter — base class owns _splitter for OS-level GCI.
        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = MedScanCanvas()
        self._pane_splitter.addWidget(self._canvas)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(6)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabBar::tab { font-size: 11px; padding: 6px 14px; min-width: 72px; }"
        )

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumWidth(280)
        self._log.setPlaceholderText("Diagnostic log...")
        tabs.addTab(self._log, "Console")

        swarm_tab = QWidget()
        swarm_l = QVBoxLayout(swarm_tab)
        swarm_l.setSpacing(8)
        intro = QLabel(
            "Global mesh chat lives in the OS shell — same channel as the rest of the Swarm."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8090b0; font-size: 11px;")
        swarm_l.addWidget(intro)
        btn_chat = QPushButton("Open SIFTA Swarm Chat")
        btn_chat.setToolTip("Opens the main swarm chat window (Ollama / GROUP / mesh)")
        btn_chat.clicked.connect(self._open_global_swarm_chat)
        swarm_l.addWidget(btn_chat)
        entity = QTextEdit()
        entity.setReadOnly(True)
        entity.setPlaceholderText("Entity channel — tie-in for diagnostic narration (optional).")
        entity.setPlainText(
            "[ENTITY]\n"
            "When you deploy swimmers, this scanner speaks in pheromone and coverage — "
            "for language, use Swarm Chat above.\n"
        )
        entity.setMaximumHeight(120)
        swarm_l.addWidget(entity)
        tabs.addTab(swarm_tab, "Swarm / Entity")

        right_l.addWidget(tabs)
        self._pane_splitter.addWidget(right)

        self._pane_splitter.setStretchFactor(0, 5)
        self._pane_splitter.setStretchFactor(1, 2)
        layout.addWidget(self._pane_splitter, 1)

        QTimer.singleShot(0, self._balance_pane_splitter)

        # ── Initialize ──────────────────────────────────────────
        self._mode = "TISSUE"
        self._terrain: np.ndarray | None = None
        self._anomaly_map: np.ndarray | None = None
        self._pheromone: np.ndarray | None = None
        self._swimmers: List[MedSwimmer] = []
        self._anomalies: List[Anomaly] = []
        self._running = False
        self._tick = 0
        self._timer: QTimer | None = None

        self._regenerate()
        self.set_status("Ready — click Deploy Swimmers")

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.72,
            min_right=260,
            min_left=300,
        )

    def _open_global_swarm_chat(self):
        """Reach SiftaDesktop.open_swarm_chat when embedded in the MDI shell."""
        p = self.parent()
        while p is not None:
            if hasattr(p, "open_swarm_chat") and callable(getattr(p, "open_swarm_chat")):
                p.open_swarm_chat()
                self.set_status("Swarm Chat opened")
                return
            p = p.parent()
        QMessageBox.information(
            self,
            "Swarm Chat",
            "Run this from SIFTA OS:\n"
            "SIFTA menu → Accessories → 🐜 Swarm Chat\n\n"
            "Standalone Medical Scanner has no embedded mesh window.",
        )

    def _regenerate(self):
        was_running = self._running
        if was_running:
            self._toggle_scan()

        seed = random.randint(0, 999999)
        if self._mode == "TISSUE":
            self._terrain, self._anomalies = generate_tissue_terrain(
                rows=200, cols=200, n_masses=3, n_calcifications=5, seed=seed)
        elif self._mode == "GENOMIC":
            self._terrain, self._anomalies = generate_genomic_terrain(
                rows=200, cols=200, n_clusters=6, seed=seed)
        else:
            self._terrain, self._anomalies = generate_blood_terrain(
                rows=200, cols=200, n_abnormal=8, seed=seed)

        self._anomaly_map = compute_anomaly_map(self._terrain, window=7)
        self._pheromone = np.zeros_like(self._terrain)
        self._swimmers = spawn_swimmers(*self._terrain.shape)
        self._tick = 0

        for a in self._anomalies:
            a.detected = False
            a.confidence = 0.0

        self._canvas.set_data(
            self._terrain, self._anomaly_map, self._pheromone,
            self._swimmers, self._anomalies, self._mode)
        self._canvas.render_frame()

        self._log_msg(f"NEW {self._mode} terrain generated (seed={seed})")
        self._log_msg(f"Planted {len(self._anomalies)} anomalies — swimmers ready")
        self.set_status("New terrain — click Deploy")

    def _change_mode(self, mode: str):
        self._mode = mode
        self._regenerate()

    def _toggle_scan(self):
        if self._running:
            self._running = False
            if self._timer:
                self._timer.stop()
                self._timer = None
            self._btn_start.setText("Deploy Swimmers")
            self.set_status("Scan paused")
        else:
            self._running = True
            self._timer = self.make_timer(60, self._tick_step)
            self._btn_start.setText("Pause Scan")
            self.set_status("Scanning...")
            self._log_msg("SWIMMERS DEPLOYED — scanning terrain...")

    def _tick_step(self):
        self._tick += 1

        step_swimmers(
            self._swimmers, self._terrain, self._anomaly_map,
            self._pheromone, dt=1.0)
        evaporate_pheromone(self._pheromone, decay=0.998)

        self._check_detections()

        n_det = sum(1 for a in self._anomalies if a.detected)
        n_tot = len(self._anomalies)
        coverage = np.count_nonzero(self._pheromone > 0.01) / max(1, self._terrain.size)
        total_deposit = sum(sw.pheromone_deposited for sw in self._swimmers)

        self.set_status(
            f"Tick {self._tick} | Detected: {n_det}/{n_tot} | "
            f"Coverage: {coverage*100:.1f}% | Pheromone: {total_deposit:.1f}")

        self._canvas.render_frame()

    def _check_detections(self):
        """Check if any anomaly has enough pheromone over it to count as 'detected'."""
        rows, cols = self._terrain.shape
        for a in self._anomalies:
            if a.detected:
                continue
            r = max(3, int(a.radius))
            x0, x1 = max(0, a.cx - r), min(rows, a.cx + r + 1)
            y0, y1 = max(0, a.cy - r), min(cols, a.cy + r + 1)
            region = self._pheromone[x0:x1, y0:y1]
            if region.size == 0:
                continue

            mean_phero = region.mean()
            max_phero = region.max()

            if mean_phero > 0.03 or max_phero > 0.12:
                a.detected = True
                a.confidence = min(1.0, mean_phero * 8.0 + max_phero * 2.0)
                self._log_msg(
                    f"DETECTED: {a.anomaly_type} at ({a.cx},{a.cy}) "
                    f"conf={a.confidence:.0%}")

                n_det = sum(1 for aa in self._anomalies if aa.detected)
                if n_det == len(self._anomalies):
                    self._log_msg("ALL ANOMALIES DETECTED — full diagnostic coverage achieved")

    def _log_msg(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self._log.appendPlainText(f"[{t}] {msg}")
        sb = self._log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())


# ── Standalone launch ────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MedScanWidget()
    w.setWindowTitle("Stigmergic Medical Scanner")
    w.resize(1440, 900)
    w.show()
    sys.exit(app.exec())
