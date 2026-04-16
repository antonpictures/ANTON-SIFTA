#!/usr/bin/env python3
"""Stigmergic Edge Vision — embedded in iSwarm OS (QtAgg)."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
_SYS = _REPO / "System"
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from sim_lab_theme import (  # noqa: E402
    apply_matplotlib_lab_style,
    cmap_terrain_lab,
    ensure_matplotlib,
    neon_suptitle,
    style_axis_lab,
)
from vision_processor_worker import VisionConfig, VisionProcessorWorker, synth_topography  # noqa: E402


class VisionSimWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensure_matplotlib("Edge Vision embed")
        apply_matplotlib_lab_style()

        self._ticks = 12000
        self._render_every = 10
        self._t = 0
        self._mint_accum = 0

        w, h = 280, 200
        self._cfg = VisionConfig(width=w, height=h, swimmers=900, seed=1337)
        img = synth_topography(w, h, 1337)
        self._worker = VisionProcessorWorker(img, self._cfg)

        gx = np.abs(np.diff(self._worker.img, axis=1, prepend=self._worker.img[:, :1]))
        gy = np.abs(np.diff(self._worker.img, axis=0, prepend=self._worker.img[:1, :]))
        self._grad_mag = np.sqrt(gx * gx + gy * gy)

        self._figure = Figure(figsize=(14, 10))
        self._canvas = FigureCanvas(self._figure)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        axes = self._figure.subplots(2, 2)
        neon_suptitle(
            self._figure,
            "DISTRIBUTED VISION LAB",
            "topography | τ edges | RGB fusion | |∇I| oracle",
        )
        tmap = cmap_terrain_lab()
        self._im0 = axes[0, 0].imshow(self._worker.img, cmap=tmap, vmin=0, vmax=1, interpolation="nearest")
        style_axis_lab(axes[0, 0], "Drop zone")
        axes[0, 0].axis("off")
        self._im1 = axes[0, 1].imshow(self._worker.pher, cmap="magma", vmin=0, vmax=2.5, interpolation="nearest")
        style_axis_lab(axes[0, 1], "τ skeleton")
        axes[0, 1].axis("off")
        blend = np.stack(
            [
                self._worker.img,
                np.clip(self._worker.pher / 2.5, 0, 1),
                0.25 * np.ones_like(self._worker.img),
            ],
            axis=-1,
        )
        self._im2 = axes[1, 0].imshow(blend, interpolation="nearest")
        self._sc = axes[1, 0].scatter(
            self._worker.sx, self._worker.sy, s=1, c="#73daca", alpha=0.4, linewidths=0
        )
        style_axis_lab(axes[1, 0], "Swimmers × structure")
        axes[1, 0].axis("off")
        self._im3 = axes[1, 1].imshow(self._grad_mag, cmap="inferno", interpolation="nearest")
        style_axis_lab(axes[1, 1], "|∇I|")
        axes[1, 1].axis("off")
        self._axes = axes
        self._hud = self._figure.text(0.5, 0.02, "", ha="center", color="#bb9af7", fontsize=10, family="monospace")
        self._figure.tight_layout(rect=[0, 0.04, 1, 0.92])

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(22)

    def _tick(self) -> None:
        self._t += 1
        if self._t > self._ticks:
            self._timer.stop()
            return
        m = self._worker.step()
        self._mint_accum += int(m["edge_hits_now"])

        if self._t % max(1, self._render_every) != 0 and self._t != 1:
            self._canvas.draw_idle()
            return

        vmax = max(float(np.percentile(self._worker.pher, 99.5)), 0.5)
        self._im1.set_clim(0, vmax)
        self._im1.set_data(self._worker.pher)
        blend = np.stack(
            [
                self._worker.img,
                np.clip(self._worker.pher / max(vmax, 1e-6), 0, 1),
                0.25 * np.ones_like(self._worker.img),
            ],
            axis=-1,
        )
        self._im2.set_data(blend)
        self._sc.set_offsets(np.c_[self._worker.sx, self._worker.sy])
        self._hud.set_text(
            f"t {self._t}/{self._ticks}  edges/s {m['edge_hits_now']}  τ_peak {m['pher_peak']:.3f}"
        )
        self._canvas.draw_idle()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().closeEvent(event)
