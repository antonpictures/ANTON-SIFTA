#!/usr/bin/env python3
"""
Applications/sifta_nvidia_sifta_bridge_widget.py
══════════════════════════════════════════════════
NVIDIA × SIFTA Integration Dashboard

Truth labels (§8 Covenant):
  REAL   — package importable / API responds
  STUB   — interface defined, vendor runtime absent
  DEMO   — pure-Python proof (no GPU)
  BROKEN — import error / network failure

NPPL: simulation / research posture only.
Authors: AG31 (Antigravity / Gemini 2.5 Pro), Architect Ioan George Anton
Date: 2026-04-28
"""
from __future__ import annotations
import json, sys, threading, time, urllib.request, urllib.error
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QScrollArea, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_COLORS = {
    "REAL":  "#00ff88",
    "STUB":  "#ffaa00",
    "DEMO":  "#00d4ff",
    "BROKEN":"#ff4466",
    "?":     "#888888",
}

# ── NVIDIA asset registry ─────────────────────────────────────────────────────
NVIDIA_ASSETS = [
    {
        "name": "NVIDIA Warp",
        "pkg":  "warp",
        "desc": "GPU-accelerated numpy-like Python. Drop-in for VoxelField.fill_goal_potential().",
        "install": "pip install warp-lang",
        "url":  "https://github.com/NVIDIA/warp",
        "sifta_hook": "System/swarm_isaac_stigmergy_bridge.py → VoxelField (replaces O(N³) loop)",
    },
    {
        "name": "cuRobo",
        "pkg":  "curobo",
        "desc": "GPU collision-free trajectory optimisation. Upgrades ArmSegment.step() from finite-diff gradient to ms-scale GPU solve.",
        "install": "pip install curobo  # needs CUDA",
        "url":  "https://github.com/NVlabs/curobo",
        "sifta_hook": "System/swarm_isaac_stigmergy_bridge.py → ArmSegment (replaces naive gradient)",
    },
    {
        "name": "Isaac Lab",
        "pkg":  "omni.isaac.core",
        "desc": "Open-source robot RL framework. Activates IsaacStigmergicStub (currently STUB:isaac_pending).",
        "install": "See https://isaac-sim.github.io/IsaacLab/",
        "url":  "https://github.com/isaac-sim/IsaacLab",
        "sifta_hook": "System/swarm_isaac_stigmergy_bridge.py → IsaacStigmergicStub.is_available()",
    },
    {
        "name": "GR00T N1.7",
        "pkg":  "gr00t",
        "desc": "Open-weight humanoid policy (VLM+diffusion transformer). SIFTA design contrast: centralised vs stigmergic.",
        "install": "huggingface-cli download nvidia/GR00T-N1.7-3B",
        "url":  "https://huggingface.co/nvidia/GR00T-N1.7-3B",
        "sifta_hook": "Contrast reference in swarm_isaac_stigmergy_bridge.py docstring",
    },
    {
        "name": "NVIDIA Cosmos",
        "pkg":  "cosmos",
        "desc": "World foundation model — generates synthetic robot video. Future: synthetic training data for SIFTA gesture/face organ.",
        "install": "See https://developer.nvidia.com/cosmos",
        "url":  "https://developer.nvidia.com/cosmos",
        "sifta_hook": "Future: System/swarm_face_detection.py synthetic data augmentation",
    },
]

HF_API = "https://huggingface.co/api/models?author=nvidia&search=GR00T&limit=8"

SIFTA_VS_GROOT = """
╔══════════════════════════════════════════════════════════════════════╗
║          SIFTA Event 74  vs  NVIDIA GR00T N1.7                     ║
╠══════════════════════════════╦═══════════════════════════════════════╣
║  SIFTA (stigmergic)          ║  GR00T N1.7 (centralised)            ║
╠══════════════════════════════╬═══════════════════════════════════════╣
║ Pheromone field in 3D voxels ║ VLM vision encoder @ 10 Hz           ║
║ ArmSegment climbs gradient   ║ Diffusion transformer @ 120 Hz       ║
║ Environment computes motion  ║ Central brain computes all joints     ║
║ Pure Python / numpy          ║ Requires CUDA + Isaac Sim             ║
║ No training data needed      ║ Trained on 1M+ robot demos            ║
║ NPPL: sim-only               ║ Licensed for research                 ║
╠══════════════════════════════╬═══════════════════════════════════════╣
║  Truth: REAL:numpy_proof     ║  Truth: STUB (weights not local)      ║
╚══════════════════════════════╩═══════════════════════════════════════╝

SIFTA thesis: the environment carries the computation.
GR00T thesis: one large model computes every joint angle.

Both can be true at different scales. SIFTA's VoxelField can consume
GR00T's joint-angle output as a goal-pheromone source — the two
architectures are composable, not mutually exclusive.
"""


# ── Truth badge widget ────────────────────────────────────────────────────────
class TruthBadge(QLabel):
    def __init__(self, truth: str = "?", parent=None):
        super().__init__(parent)
        self.set_truth(truth)
        self.setFixedWidth(80)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Menlo", 10, QFont.Weight.Bold)
        self.setFont(font)

    def set_truth(self, truth: str):
        color = TRUTH_COLORS.get(truth, TRUTH_COLORS["?"])
        self.setText(truth)
        self.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; "
            f"border-radius: 3px; padding: 2px 4px;"
        )


# ── Asset row ─────────────────────────────────────────────────────────────────
class AssetRow(QWidget):
    def __init__(self, asset: dict, parent=None):
        super().__init__(parent)
        self.asset = asset
        self._badge = TruthBadge("?")
        self._status = QLabel("scanning…")
        self._status.setStyleSheet("color: #888;")

        name_lbl = QLabel(f"<b>{asset['name']}</b>")
        name_lbl.setStyleSheet("color: #e0e0e0;")
        hook_lbl = QLabel(f"<i>{asset['sifta_hook']}</i>")
        hook_lbl.setStyleSheet("color: #666; font-size: 10px;")
        hook_lbl.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(self._badge)
        col = QVBoxLayout()
        col.addWidget(name_lbl)
        col.addWidget(hook_lbl)
        col.addWidget(self._status)
        row.addLayout(col)
        row.addStretch()
        self.setLayout(row)

    def set_result(self, truth: str, msg: str):
        self._badge.set_truth(truth)
        color = TRUTH_COLORS.get(truth, "#888")
        self._status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._status.setText(msg)


# ── Main Widget ───────────────────────────────────────────────────────────────
class NvidiaSiftaBridgeWidget(QWidget):
    """NVIDIA × SIFTA Integration Dashboard."""

    APP_NAME = "NVIDIA × SIFTA"

    # Signals for thread→UI
    _asset_ready   = pyqtSignal(int, str, str)   # idx, truth, msg
    _hf_ready      = pyqtSignal(str)             # json text
    _field_ready   = pyqtSignal(str)             # sim log text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NVIDIA × SIFTA Integration Dashboard")
        self.resize(1100, 720)
        self._asset_rows: list[AssetRow] = []
        self._build_ui()
        self._wire_signals()
        QTimer.singleShot(500, self._start_scan)

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background: #0a0a0f; color: #e0e0e0; font-family: 'SF Pro', 'Segoe UI', sans-serif; }
            QTabWidget::pane { border: 1px solid #1a1a2e; }
            QTabBar::tab { background: #0f0f1a; color: #888; padding: 8px 16px; border: 1px solid #1a1a2e; }
            QTabBar::tab:selected { background: #1a1a2e; color: #00ff88; border-bottom: 2px solid #00ff88; }
            QPushButton { background: #1a1a2e; color: #00ff88; border: 1px solid #00ff88;
                          border-radius: 4px; padding: 6px 14px; }
            QPushButton:hover { background: #00ff8822; }
            QPlainTextEdit { background: #050508; color: #00ff88; border: 1px solid #1a1a2e;
                             font-family: 'Menlo', 'Courier New', monospace; font-size: 11px; }
            QScrollArea { border: none; }
        """)

        main = QVBoxLayout(self)
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QLabel("  🟢 NVIDIA × SIFTA  — Integration Bridge")
        hdr.setStyleSheet(
            "background: #0f0f1a; color: #00ff88; font-size: 16px; font-weight: bold; padding: 12px;"
        )
        main.addWidget(hdr)

        # Tabs
        self._tabs = QTabWidget()
        main.addWidget(self._tabs)

        self._tabs.addTab(self._build_scanner_tab(), "🔍 Asset Scanner")
        self._tabs.addTab(self._build_contrast_tab(), "⚔ SIFTA vs GR00T")
        self._tabs.addTab(self._build_field_tab(),   "🧲 Live Field")
        self._tabs.addTab(self._build_hf_tab(),      "📦 HF Models")

    def _build_scanner_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        title = QLabel("NVIDIA Open Assets — Installation Truth Scan")
        title.setStyleSheet("font-size: 13px; color: #aaa;")
        top.addWidget(title)
        top.addStretch()
        btn = QPushButton("↺ Rescan")
        btn.clicked.connect(self._start_scan)
        top.addWidget(btn)
        v.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._asset_col = QVBoxLayout(container)
        self._asset_col.setSpacing(6)

        for i, asset in enumerate(NVIDIA_ASSETS):
            row = AssetRow(asset)
            self._asset_rows.append(row)
            self._asset_col.addWidget(row)

        self._asset_col.addStretch()
        scroll.setWidget(container)
        v.addWidget(scroll)

        note = QLabel(
            "Truth per §8 Covenant: REAL = importable now. "
            "STUB = interface defined, runtime absent. BROKEN = error."
        )
        note.setStyleSheet("color: #444; font-size: 10px; padding: 4px;")
        v.addWidget(note)
        return w

    def _build_contrast_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        lbl = QLabel("Architecture Contrast — SIFTA Stigmergic Field vs GR00T Centralised Stack")
        lbl.setStyleSheet("color: #aaa; font-size: 13px; padding-bottom: 6px;")
        v.addWidget(lbl)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(SIFTA_VS_GROOT)
        v.addWidget(txt)

        cite = QLabel(
            "Refs: Khatib (1986) IJRR 10.1177/027836498600500106 · "
            "Hochner (2012) 10.1016/j.cub.2012.09.001 · "
            "Grassé (1959) 10.1007/BF02223791 · "
            "NVIDIA GR00T N1 blog (vendor contrast, not peer claim)"
        )
        cite.setStyleSheet("color: #444; font-size: 10px;")
        cite.setWordWrap(True)
        v.addWidget(cite)
        return w

    def _build_field_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        lbl = QLabel("Event 74 — Live 3-D Stigmergic Field Simulation (REAL:numpy_proof, NPPL:sim_only)")
        lbl.setStyleSheet("color: #aaa; font-size: 12px;")
        top.addWidget(lbl)
        top.addStretch()
        run_btn = QPushButton("▶ Run Sim")
        run_btn.clicked.connect(self._run_field_sim)
        top.addWidget(run_btn)
        v.addLayout(top)

        self._field_log = QPlainTextEdit()
        self._field_log.setReadOnly(True)
        self._field_log.setPlainText("Press ▶ Run Sim to execute VoxelField gradient climb…")
        v.addWidget(self._field_log)

        # Last receipts
        lbl2 = QLabel("Recent sim receipts from .sifta_state/sim_receipts.jsonl:")
        lbl2.setStyleSheet("color: #666; font-size: 11px; margin-top: 8px;")
        v.addWidget(lbl2)
        self._receipt_log = QPlainTextEdit()
        self._receipt_log.setReadOnly(True)
        self._receipt_log.setMaximumHeight(120)
        v.addWidget(self._receipt_log)
        self._load_receipts()
        return w

    def _build_hf_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        lbl = QLabel("NVIDIA HuggingFace Models (live API)")
        lbl.setStyleSheet("color: #aaa; font-size: 13px;")
        top.addWidget(lbl)
        top.addStretch()
        btn = QPushButton("↺ Refresh")
        btn.clicked.connect(self._fetch_hf)
        top.addWidget(btn)
        v.addLayout(top)

        self._hf_log = QPlainTextEdit()
        self._hf_log.setReadOnly(True)
        self._hf_log.setPlainText("Fetching NVIDIA models from HuggingFace API…")
        v.addWidget(self._hf_log)

        url_lbl = QLabel(f"API: {HF_API}")
        url_lbl.setStyleSheet("color: #444; font-size: 10px;")
        v.addWidget(url_lbl)
        return w

    def _wire_signals(self):
        self._asset_ready.connect(self._on_asset_ready)
        self._hf_ready.connect(self._on_hf_ready)
        self._field_ready.connect(self._on_field_ready)

    # ── Scan ─────────────────────────────────────────────────────────────────
    def _start_scan(self):
        for row in self._asset_rows:
            row.set_result("?", "scanning…")
        threading.Thread(target=self._scan_worker, daemon=True).start()
        self._fetch_hf()

    def _scan_worker(self):
        for i, asset in enumerate(NVIDIA_ASSETS):
            pkg = asset["pkg"]
            try:
                __import__(pkg)
                self._asset_ready.emit(i, "REAL", f"✅ {pkg} importable")
            except ImportError as e:
                short = str(e)[:60]
                # Check if it's on HF (weights available but not installed)
                if pkg in ("gr00t", "cosmos"):
                    self._asset_ready.emit(i, "STUB",
                        f"Weights on HuggingFace — not installed locally")
                else:
                    self._asset_ready.emit(i, "STUB",
                        f"Not installed: {asset['install']}")
            except Exception as e:
                self._asset_ready.emit(i, "BROKEN", f"Error: {str(e)[:60]}")

    def _on_asset_ready(self, idx: int, truth: str, msg: str):
        if 0 <= idx < len(self._asset_rows):
            self._asset_rows[idx].set_result(truth, msg)

    # ── HF fetch ─────────────────────────────────────────────────────────────
    def _fetch_hf(self):
        self._hf_log.setPlainText("Fetching…")
        threading.Thread(target=self._hf_worker, daemon=True).start()

    def _hf_worker(self):
        try:
            req = urllib.request.Request(HF_API, headers={"User-Agent": "SIFTA/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            lines = [f"{'Model':<45} {'Downloads':>10}  {'Updated':<12}"]
            lines.append("─" * 72)
            for m in data:
                mid   = m.get("modelId", "?")[:44]
                dls   = m.get("downloads", 0)
                upd   = (m.get("lastModified") or "")[:10]
                lines.append(f"{mid:<45} {dls:>10,}  {upd:<12}")
            self._hf_ready.emit("\n".join(lines))
        except Exception as e:
            self._hf_ready.emit(f"BROKEN — {e}\n\nCheck network or HF API status.")

    def _on_hf_ready(self, txt: str):
        self._hf_log.setPlainText(txt)

    # ── Field sim ────────────────────────────────────────────────────────────
    def _run_field_sim(self):
        self._field_log.setPlainText("Running VoxelField simulation…")
        threading.Thread(target=self._field_worker, daemon=True).start()

    def _field_worker(self):
        try:
            sys.path.insert(0, str(_REPO))
            from System.swarm_isaac_stigmergy_bridge import run_sim, explain
            t0 = time.time()
            receipt = run_sim(write_receipt=True)
            elapsed = time.time() - t0
            lines = [
                explain(),
                "",
                f"Ticks:      {receipt.ticks}",
                f"Reached:    {receipt.reached}",
                f"Start:      {receipt.start}",
                f"Goal:       {receipt.goal}",
                f"Final pos:  {receipt.final_pos}",
                f"Path len:   {receipt.path_length}",
                f"Truth:      {receipt.truth}",
                f"Notes:      {receipt.notes}",
                f"Wall time:  {elapsed*1000:.1f} ms",
                "",
                "Receipt written to .sifta_state/sim_receipts.jsonl",
            ]
            self._field_ready.emit("\n".join(lines))
        except Exception as e:
            self._field_ready.emit(f"Error: {e}")

    def _on_field_ready(self, txt: str):
        self._field_log.setPlainText(txt)
        self._load_receipts()

    def _load_receipts(self):
        p = _STATE / "sim_receipts.jsonl"
        if not p.exists():
            self._receipt_log.setPlainText("No receipts yet.")
            return
        lines = [l for l in p.read_text().splitlines() if l.strip()][-5:]
        out = []
        for l in lines:
            try:
                r = json.loads(l)
                out.append(
                    f"ts={r.get('ts','?'):.0f}  "
                    f"reached={r.get('reached','?')}  "
                    f"ticks={r.get('ticks','?')}  "
                    f"truth={r.get('truth','?')}"
                )
            except Exception:
                out.append(l[:80])
        self._receipt_log.setPlainText("\n".join(out))


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication.instance() or QApplication(sys.argv)
    w = NvidiaSiftaBridgeWidget()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
