#!/usr/bin/env python3
"""
Colloid simulation embedded in Swarm OS MDI (no separate OS window).

Opened from Programs → Simulations when apps_manifest lists widget_class.
CLI users still run: python3 Applications/sifta_colloid_sim.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))
if str(_REPO / "Kernel") not in sys.path:
    sys.path.insert(0, str(_REPO / "Kernel"))

from sifta_colloid_sim import BG_COLOR, SIFTAColloidSimulation, build_renderer  # noqa: E402


class ColloidSimWidget(QWidget):
    """Cognitive colloid field — stays inside iSwarm OS."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sim = SIFTAColloidSimulation(demo_mode=True)
        self._figure = Figure(figsize=(15, 9), facecolor=BG_COLOR)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumSize(960, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        _, self._ani = build_renderer(self._sim, ext_figure=self._figure)
        self._canvas.draw_idle()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        try:
            if getattr(self, "_ani", None) is not None:
                self._ani.event_source.stop()
        except Exception:
            pass
        super().closeEvent(event)
