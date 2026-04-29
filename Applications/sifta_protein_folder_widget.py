#!/usr/bin/env python3
"""
Applications/sifta_protein_folder_widget.py

Embedded Python/Qt protein folding viewer for SIFTA OS.

This used to generate an HTML/Three.js file and open it in a browser. That
breaks the Covenant's Python-first app surface: a core SIFTA organ must live
inside the desktop as a QWidget, not escape into Safari/Chrome.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

try:
    from System.sifta_peptide_backbone_demo import AA, fold
except ImportError as exc:  # pragma: no cover - import failure is fatal in app mode
    raise SystemExit(f"Could not import System.sifta_peptide_backbone_demo: {exc}") from exc

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover - desktop focus bus is optional in tests
    def _publish_focus(*_: Any, **__: Any) -> None:
        return None


BG = "#050713"
PANEL = "#0d1020"
PANEL_2 = "#12172b"
CYAN = "#35e7ff"
BLUE = "#6aa7ff"
GREEN = "#5cff9d"
AMBER = "#ffcc66"
RED = "#ff5c7a"
TEXT = "#e8ecff"
MUTED = "#8790b8"


@dataclass
class FoldViewResult:
    sequence: str
    trajectory: list[list[list[float]]]
    final_energy: float
    engine_label: str
    pdb_path: str = ""
    summary_path: str = ""


def _parse_pdb_ca(pdb_path: Path) -> np.ndarray:
    coords = []
    with pdb_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("ATOM") and " CA " in line:
                coords.append(
                    [
                        float(line[30:38]),
                        float(line[38:46]),
                        float(line[46:54]),
                    ]
                )
    if not coords:
        raise ValueError(f"No CA atoms found in {pdb_path}")
    arr = np.array(coords, dtype=float)
    return arr - arr.mean(axis=0, keepdims=True)


def _morph_trajectory(final_xyz: np.ndarray, frames: int = 90) -> list[list[list[float]]]:
    n = final_xyz.shape[0]
    start = np.zeros_like(final_xyz)
    start[:, 0] = np.arange(n, dtype=float) * 3.8
    start -= start.mean(axis=0, keepdims=True)
    out = []
    for k in range(frames):
        t = k / max(1, frames - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        xyz = (1.0 - smooth) * start + smooth * final_xyz
        out.append(xyz.tolist())
    return out


def _validate_sequence(seq: str) -> str:
    clean = "".join(ch for ch in seq.upper().strip() if ch.isalpha())
    if not clean:
        raise ValueError("Sequence is empty.")
    bad = sorted(set(clean) - set(AA))
    if bad:
        raise ValueError(f"Unsupported residue(s): {''.join(bad)}")
    if len(clean) < 3:
        raise ValueError("Use at least 3 residues for a visible backbone.")
    return clean


def run_c55m_george_batch(limit: int = 0, beam: int = 512) -> dict[str, Any]:
    from System.sifta_hp_lattice_folder import DEFAULT_PROTEIN_PANEL
    from System.sifta_protein_folding_broker import FoldingJob, ProteinFoldingBroker

    os.environ["SIFTA_HP_LATTICE_BEAM"] = str(int(beam))
    out_dir = _REPO / ".sifta_state" / "protein_folds"
    out_dir.mkdir(parents=True, exist_ok=True)
    broker = ProteinFoldingBroker()
    panel = DEFAULT_PROTEIN_PANEL[:limit] if limit and limit > 0 else DEFAULT_PROTEIN_PANEL
    folds = []
    for name, seq in panel:
        meta = broker.run(
            FoldingJob(
                sequence=seq,
                name=f"C55M + George :: {name}",
                engine="c55m_hp_lattice",
                out_dir=str(out_dir),
            )
        )
        folds.append(meta)

    summary = {
        "title": "C55M + George Protein Fold Colosseum",
        "engine": "c55m_hp_lattice",
        "beam_width": int(beam),
        "fold_count": len(folds),
        "folds": folds,
    }
    summary_path = out_dir / "c55m_george_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def fold_for_view(
    sequence: str,
    *,
    engine: str = "c55m_hp_lattice",
    beam: int = 1024,
    batch: bool = False,
    limit: int = 0,
) -> FoldViewResult:
    if batch:
        summary = run_c55m_george_batch(limit=limit, beam=beam)
        best = min(summary["folds"], key=lambda row: row.get("energy", 0))
        pdb_path = Path(best["pdb_path"])
        return FoldViewResult(
            sequence=str(best["sequence"]),
            trajectory=_morph_trajectory(_parse_pdb_ca(pdb_path)),
            final_energy=float(best["energy"]),
            engine_label="c55m_hp_lattice_batch_best",
            pdb_path=str(pdb_path),
            summary_path=str(summary["summary_path"]),
        )

    seq = _validate_sequence(sequence)
    if engine == "toy":
        _xyz, final_e, trajectory = fold(seq, steps=8000, temp=1.2, save_trajectory=True)
        return FoldViewResult(
            sequence=seq,
            trajectory=trajectory,
            final_energy=float(final_e),
            engine_label="toy_CA_backbone_monte_carlo",
        )

    from System.sifta_protein_folding_broker import FoldingJob, ProteinFoldingBroker

    os.environ["SIFTA_HP_LATTICE_BEAM"] = str(int(beam))
    broker = ProteinFoldingBroker()
    meta = broker.run(
        FoldingJob(
            sequence=seq,
            name="C55M + George co-signed fold",
            engine="c55m_hp_lattice",
        )
    )
    pdb_path = Path(meta["pdb_path"])
    return FoldViewResult(
        sequence=seq,
        trajectory=_morph_trajectory(_parse_pdb_ca(pdb_path)),
        final_energy=float(meta["energy"]),
        engine_label="c55m_hp_lattice_beam_search",
        pdb_path=str(pdb_path),
    )


class _FoldWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sequence: str, engine: str, beam: int, batch: bool, limit: int) -> None:
        super().__init__()
        self.sequence = sequence
        self.engine = engine
        self.beam = beam
        self.batch = batch
        self.limit = limit

    def run(self) -> None:
        try:
            self.finished.emit(
                fold_for_view(
                    self.sequence,
                    engine=self.engine,
                    beam=self.beam,
                    batch=self.batch,
                    limit=self.limit,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class ProteinFolderWidget(QWidget):
    """Python/Qt protein fold colosseum. No browser, no generated HTML."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProteinFolderWidget")
        self._result: FoldViewResult | None = None
        self._frame = 0
        self._auto_rotate = True
        self._worker_thread: QThread | None = None
        self._worker: _FoldWorker | None = None

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)
        QTimer.singleShot(100, self._run_fold)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{ background:{BG}; color:{TEXT}; font-family: Menlo, Monaco, monospace; }}
            QFrame#panel {{ background:{PANEL_2}; border:1px solid #26304e; border-radius:8px; }}
            QLabel#title {{ color:{CYAN}; font-size:18px; font-weight:700; }}
            QLabel#subtitle {{ color:{MUTED}; font-size:11px; }}
            QLabel#metricLabel {{ color:{MUTED}; font-size:11px; }}
            QLabel#metricValue {{ color:{GREEN}; font-size:13px; font-weight:700; }}
            QLineEdit, QComboBox, QSpinBox {{
                background:#080b18; border:1px solid #26304e; border-radius:6px;
                padding:6px; color:{TEXT};
            }}
            QPushButton {{
                background:#18213c; border:1px solid #314268; border-radius:7px;
                color:{TEXT}; padding:8px 10px; font-weight:700;
            }}
            QPushButton:hover {{ border-color:{CYAN}; color:{CYAN}; }}
            QPushButton:disabled {{ color:#536078; border-color:#1c2438; }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("panel")
        header_lay = QGridLayout(header)
        header_lay.setContentsMargins(12, 10, 12, 10)
        header_lay.setHorizontalSpacing(12)
        header_lay.setVerticalSpacing(8)

        title = QLabel("C55M + George Protein Fold Colosseum")
        title.setObjectName("title")
        subtitle = QLabel("Embedded Python/Qt viewer - HP lattice / toy CA backbone - no browser escape")
        subtitle.setObjectName("subtitle")
        header_lay.addWidget(title, 0, 0, 1, 5)
        header_lay.addWidget(subtitle, 1, 0, 1, 5)

        self.seq_input = QLineEdit("ACFLIVGPGKTYL")
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["c55m_hp_lattice", "toy"])
        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(16, 4096)
        self.beam_spin.setSingleStep(128)
        self.beam_spin.setValue(1024)
        self.run_btn = QPushButton("Run Fold")
        self.run_btn.clicked.connect(self._run_fold)
        self.replay_btn = QPushButton("Replay")
        self.replay_btn.clicked.connect(self._replay)
        self.auto_btn = QPushButton("Auto Rotate: ON")
        self.auto_btn.clicked.connect(self._toggle_auto_rotate)

        header_lay.addWidget(QLabel("sequence"), 2, 0)
        header_lay.addWidget(self.seq_input, 3, 0)
        header_lay.addWidget(QLabel("engine"), 2, 1)
        header_lay.addWidget(self.engine_combo, 3, 1)
        header_lay.addWidget(QLabel("beam"), 2, 2)
        header_lay.addWidget(self.beam_spin, 3, 2)
        header_lay.addWidget(self.run_btn, 3, 3)
        header_lay.addWidget(self.replay_btn, 3, 4)
        header_lay.addWidget(self.auto_btn, 3, 5)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(10)
        root.addLayout(body, 1)

        self.figure = Figure(figsize=(8.5, 6.0), facecolor=BG)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumSize(720, 520)
        self.ax = self.figure.add_subplot(111, projection="3d")
        body.addWidget(self.canvas, 1)

        side = QFrame()
        side.setObjectName("panel")
        side.setMinimumWidth(300)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(12, 12, 12, 12)
        side_lay.setSpacing(10)
        body.addWidget(side)

        self.metrics: dict[str, QLabel] = {}
        for key in ["truth", "residues", "engine", "energy", "step", "pdb"]:
            side_lay.addWidget(self._metric_row(key))

        cite = QLabel(
            "Research credit\\n"
            "Anfinsen 1973: thermodynamic hypothesis\\n"
            "Dill 1985: HP lattice abstraction\\n"
            "Jumper et al. 2021: AlphaFold comparison\\n\\n"
            "Truth label: REAL_LOCAL when the displayed fold is produced by "
            "the local Python engine or broker in this process."
        )
        cite.setWordWrap(True)
        cite.setStyleSheet(f"color:{MUTED}; line-height:1.35;")
        side_lay.addWidget(cite)
        side_lay.addStretch(1)

        self.status = QLabel("booting protein fold organ...")
        self.status.setStyleSheet(f"color:{AMBER};")
        root.addWidget(self.status)
        self._blank_plot("waiting for first fold")

    def _metric_row(self, key: str) -> QWidget:
        box = QFrame()
        box.setObjectName("panel")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(9, 7, 9, 7)
        label = QLabel(key.upper())
        label.setObjectName("metricLabel")
        value = QLabel("-")
        value.setObjectName("metricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(label)
        lay.addWidget(value, 1)
        self.metrics[key] = value
        return box

    def _set_running(self, running: bool) -> None:
        self.run_btn.setDisabled(running)
        self.seq_input.setDisabled(running)
        self.engine_combo.setDisabled(running)
        self.beam_spin.setDisabled(running)
        self.status.setText("folding..." if running else "ready")

    def _run_fold(self) -> None:
        if self._worker_thread is not None:
            return
        seq = self.seq_input.text()
        engine = self.engine_combo.currentText()
        beam = int(self.beam_spin.value())
        self._set_running(True)
        self._blank_plot("folding in worker thread")

        self._worker_thread = QThread(self)
        self._worker = _FoldWorker(seq, engine, beam, False, 0)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_fold_finished)
        self._worker.failed.connect(self._on_fold_failed)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._clear_worker)
        self._worker_thread.start()

    def _clear_worker(self) -> None:
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
        self._worker_thread = None
        self._worker = None
        self._set_running(False)

    def _on_fold_failed(self, message: str) -> None:
        self.status.setText(f"fold failed: {message}")
        QMessageBox.warning(self, "Protein fold failed", message)

    def _on_fold_finished(self, result: FoldViewResult) -> None:
        self._result = result
        self._frame = 0
        self._update_metrics()
        self._render_frame()
        self.status.setText("REAL_LOCAL fold rendered inside SIFTA OS")
        _publish_focus(
            "C55M + George Protein Fold Colosseum",
            f"Rendered {result.engine_label}: {len(result.sequence)} residues, E={result.final_energy:.3f}",
            tab="Python Qt Viewer",
            metadata={
                "truth": "REAL_LOCAL",
                "engine": result.engine_label,
                "residues": len(result.sequence),
                "energy": round(result.final_energy, 6),
                "pdb_path": result.pdb_path,
            },
        )

    def _update_metrics(self) -> None:
        if not self._result:
            return
        self.metrics["truth"].setText("REAL_LOCAL")
        self.metrics["residues"].setText(str(len(self._result.sequence)))
        self.metrics["engine"].setText(self._result.engine_label)
        self.metrics["energy"].setText(f"{self._result.final_energy:.4f}")
        self.metrics["step"].setText(str(self._frame))
        self.metrics["pdb"].setText(Path(self._result.pdb_path).name if self._result.pdb_path else "in-memory")

    def _blank_plot(self, message: str) -> None:
        self.ax.clear()
        self.ax.set_facecolor(BG)
        self.ax.text2D(0.5, 0.5, message, transform=self.ax.transAxes, ha="center", color=MUTED)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_zticks([])
        self.canvas.draw_idle()

    def _tick(self) -> None:
        if not self._result or not self._result.trajectory:
            return
        self._frame = min(self._frame + 1, len(self._result.trajectory) - 1)
        if self._frame % 2 == 0 or self._frame == len(self._result.trajectory) - 1:
            self._render_frame()

    def _replay(self) -> None:
        self._frame = 0
        self._render_frame()

    def _toggle_auto_rotate(self) -> None:
        self._auto_rotate = not self._auto_rotate
        self.auto_btn.setText(f"Auto Rotate: {'ON' if self._auto_rotate else 'OFF'}")

    def _render_frame(self) -> None:
        if not self._result or not self._result.trajectory:
            return

        coords = np.array(self._result.trajectory[self._frame], dtype=float)
        self.ax.clear()
        self.ax.set_facecolor(BG)
        self.figure.patch.set_facecolor(BG)

        span = max(8.0, float(np.max(np.ptp(coords, axis=0))) * 0.65)
        center = coords.mean(axis=0)
        for setter, c in [
            (self.ax.set_xlim, center[0]),
            (self.ax.set_ylim, center[1]),
            (self.ax.set_zlim, center[2]),
        ]:
            setter(c - span, c + span)

        colors = [GREEN if aa in "AILMFWV" else CYAN if aa in "STNQYC" else AMBER for aa in self._result.sequence]
        self.ax.plot(coords[:, 0], coords[:, 1], coords[:, 2], color=BLUE, linewidth=2.2, alpha=0.8)
        self.ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], s=82, c=colors, edgecolors="#d9f7ff", linewidths=0.7)

        if self._auto_rotate:
            self.ax.view_init(elev=22, azim=(self._frame * 3) % 360)
        else:
            self.ax.view_init(elev=22, azim=42)

        self.ax.set_title("Python Qt fold view - shape rendered from local coordinates", color=CYAN, pad=14)
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])
        self.ax.set_zticklabels([])
        self.ax.grid(color="#1b2440", linewidth=0.5)
        self.metrics["step"].setText(f"{self._frame}/{len(self._result.trajectory) - 1}")
        self.canvas.draw_idle()


def _run_cli(args: argparse.Namespace) -> FoldViewResult:
    return fold_for_view(
        args.sequence,
        engine=args.engine,
        beam=args.beam,
        batch=args.batch,
        limit=args.limit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTA Python/Qt protein folding visualizer")
    parser.add_argument("sequence", nargs="?", default="ACFLIVGPGKTYL")
    parser.add_argument("--engine", default="c55m_hp_lattice", choices=["toy", "c55m_hp_lattice"])
    parser.add_argument("--beam", type=int, default=1024)
    parser.add_argument("--batch", action="store_true", help="Fold the default C55M + George protein panel first.")
    parser.add_argument("--limit", type=int, default=0, help="Limit batch fold count; 0 means all defaults.")
    parser.add_argument("--cli", action="store_true", help="Run the fold and print JSON without opening a window.")
    args = parser.parse_args()

    if args.cli:
        result = _run_cli(args)
        print(
            json.dumps(
                {
                    "truth": "REAL_LOCAL",
                    "sequence": result.sequence,
                    "residues": len(result.sequence),
                    "engine": result.engine_label,
                    "energy": result.final_energy,
                    "pdb_path": result.pdb_path,
                    "frames": len(result.trajectory),
                },
                indent=2,
            )
        )
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    widget = ProteinFolderWidget()
    widget.resize(1180, 760)
    widget.setWindowTitle("C55M + George - Protein Fold Colosseum")
    widget.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
