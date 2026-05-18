#!/usr/bin/env python3
"""Applications/sifta_fieldsight_widget.py — SIFTA FieldSight.

Qt surface for the lawful atmospheric-optics + SAR triage organs. The
widget runs the real turbulence and triage code on synthetic lawful
targets, renders the swimmer pheromone field, and writes a receipt row.

Truth label: ``SIFTA_FIELDSIGHT_WIDGET_V0``.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_DEMO_LEDGER = _STATE / "fieldsight_demo_receipts.jsonl"
_TRUTH_LABEL = "SIFTA_FIELDSIGHT_WIDGET_V0"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


class _FieldSightCanvas(QWidget):
    """Bright real-data visualization: r0 posterior + SAR bbox."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(310)
        self._result: Dict[str, Any] = {}

    def set_result(self, result: Dict[str, Any]) -> None:
        self._result = dict(result or {})
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#020307"))
        grad.setColorAt(0.45, QColor("#061827"))
        grad.setColorAt(1.0, QColor("#090A10"))
        p.fillRect(0, 0, w, h, QBrush(grad))

        p.setPen(QPen(QColor(0, 255, 204, 32), 1))
        for x in range(0, w, 36):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 30):
            p.drawLine(0, y, w, y)

        p.setPen(QPen(QColor("#00FFCC"), 2))
        p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        p.drawText(18, 28, "r0 PHEROMONE POSTERIOR")

        swimmers: List[Dict[str, Any]] = list(self._result.get("swimmers") or [])
        if swimmers:
            max_ph = max(float(s.get("pheromone", 0.0) or 0.0) for s in swimmers) or 1.0
            min_r0 = min(float(s.get("r0_m", 0.0) or 0.0) for s in swimmers)
            max_r0 = max(float(s.get("r0_m", 0.0) or 0.0) for s in swimmers)
            span = max(max_r0 - min_r0, 1e-6)
            base_y = h * 0.57
            for idx, s in enumerate(swimmers):
                r0 = float(s.get("r0_m", 0.0) or 0.0)
                ph = float(s.get("pheromone", 0.0) or 0.0)
                score = float(s.get("score", 0.0) or 0.0)
                x = 42 + (w - 84) * ((r0 - min_r0) / span)
                y = base_y - 105.0 * (ph / max_ph)
                radius = 4.0 + 11.0 * (ph / max_ph)
                hue = QColor("#00FF66") if score >= -0.8 else QColor("#FFCC00")
                hue.setAlpha(90 + int(150 * min(1.0, ph / max_ph)))
                p.setPen(QPen(hue, 1))
                p.setBrush(QBrush(hue))
                p.drawEllipse(QPointF(x, y), radius, radius)
            p.setPen(QPen(QColor("#00FF66"), 2))
            mean_r0 = float(self._result.get("posterior_mean_r0_m", 0.0) or 0.0)
            mx = 42 + (w - 84) * ((mean_r0 - min_r0) / span)
            p.drawLine(int(mx), 48, int(mx), int(h * 0.72))
            p.drawText(int(mx) + 8, 54, f"mean {mean_r0 * 100:.2f} cm")
        else:
            p.setPen(QPen(QColor("#FFCC00"), 1))
            p.drawText(22, 82, "Press Run FieldSight Demo. No synthetic frame has been processed yet.")

        box = self._result.get("top_bbox") or []
        present = bool(self._result.get("target_present"))
        score = float(self._result.get("triage_score", 0.0) or 0.0)
        p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#FFCC00"), 2))
        p.drawText(18, h - 92, "SAR TRIAGE FIELD")
        flag = "PRESENT" if present else "REVIEW"
        flag_color = QColor("#00FF66") if present else QColor("#FFCC00")
        p.setPen(QPen(flag_color, 2))
        p.drawText(18, h - 62, f"{flag}  score={score:.3f}")
        if len(box) == 4:
            p.setPen(QPen(flag_color, 2))
            bx = 0.68 * w
            by = h - 118
            p.drawRect(QRectF(bx, by, 120, 88))
            p.drawText(int(bx), int(by) - 8, f"bbox {tuple(box)}")


class SiftaFieldSightWidget(QWidget):
    """Real FieldSight demo surface, no biometrics, no faces."""

    _live_instance: "SiftaFieldSightWidget | None" = None

    def __new__(cls, *args, **kwargs):
        if cls._live_instance is not None:
            try:
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except RuntimeError:
                cls._live_instance = None
        inst = super().__new__(cls, *args, **kwargs)
        cls._live_instance = inst
        return inst

    def __init__(self, parent=None) -> None:
        if getattr(self, "_initialized", False):
            return
        super().__init__(parent)
        self._initialized = True
        self.setWindowTitle("SIFTA FieldSight")
        self.setMinimumSize(1120, 780)
        self.setStyleSheet("background-color: #05070B; color: #E8FFF8;")

        title = QLabel("SIFTA FieldSight")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #00FFCC; "
            "padding: 12px; background: rgba(0,255,204,0.08); border-radius: 8px;"
        )

        subtitle = QLabel(
            "Atmospheric optics + lawful SAR triage. Synthetic target, real swimmers, real receipts."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #BFE9FF; font-size: 13px; padding: 4px;")

        self._canvas = _FieldSightCanvas(self)
        self._metrics = QTextEdit(self)
        self._metrics.setReadOnly(True)
        self._metrics.setMinimumHeight(210)
        self._metrics.setStyleSheet(
            "QTextEdit { background-color: #000000; color: #00FF66; "
            "border: 1px solid rgba(0,255,204,0.25); border-radius: 8px; "
            "font-family: Menlo, Monaco, monospace; font-size: 12px; padding: 10px; }"
        )
        self._metrics.setPlainText("Ready. Press Run FieldSight Demo.")

        self._run_btn = QPushButton("Run FieldSight Demo")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setStyleSheet(
            "QPushButton { background: #00CC99; color: #02110D; font-weight: 800; "
            "padding: 10px 16px; border-radius: 8px; }"
            "QPushButton:pressed { background: #00FFCC; }"
        )
        self._run_btn.clicked.connect(self._run_demo)

        self._status = QLabel("Truth label: SIFTA_FIELDSIGHT_WIDGET_V0")
        self._status.setStyleSheet("color: #FFCC00; font-size: 11px;")

        controls = QHBoxLayout()
        controls.addWidget(self._run_btn)
        controls.addWidget(self._status, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._canvas, 2)
        layout.addLayout(controls)
        layout.addWidget(self._metrics, 1)

        QTimer.singleShot(250, self._run_demo)

    def _run_demo(self) -> None:
        self._run_btn.setEnabled(False)
        self._status.setText("Running swimmers...")
        QApplication.processEvents()
        try:
            result = self._compute_demo()
            self._canvas.set_result(result)
            self._metrics.setPlainText(self._format_metrics(result))
            self._status.setText(f"Receipt: {result.get('receipt_id')}")
        except Exception as exc:
            self._metrics.setPlainText(f"FieldSight demo failed: {type(exc).__name__}: {exc}")
            self._status.setText("FieldSight error")
        finally:
            self._run_btn.setEnabled(True)

    def _compute_demo(self) -> Dict[str, Any]:
        from System.swarm_sar_triage_organ import triage
        from System.swarm_turbulence_organ import run_swarm
        from System.swarm_turbulence_substrate import TurbulenceParams, degrade, synthetic_target

        grid = 64
        target = synthetic_target(kind="rescue_hiker", grid=grid)
        planted = TurbulenceParams(cn2=6e-15)
        degraded, _psf = degrade(target, params=planted, seed=42, noise_sigma=0.005)
        r0_grid = list(np.geomspace(0.008, 0.20, 16))
        recon = run_swarm(
            degraded,
            n_swimmers=len(r0_grid),
            r0_grid_m=r0_grid,
            ticks=3,
            planted_params=planted,
            write_ledger=True,
        )
        tri = triage(recon.restored_image, positions_per_axis=7, write_ledger=True)
        swimmers = [
            {
                "swimmer_id": sw.swimmer_id,
                "r0_m": sw.r0_m,
                "pheromone": sw.pheromone,
                "score": sw.last_score,
            }
            for sw in recon.swimmers
        ]
        row = {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "receipt_id": f"fieldsight-{int(time.time() * 1000)}",
            "planted_cn2": planted.cn2,
            "planted_r0_m": planted.r0,
            "posterior_mean_r0_m": recon.posterior_mean_r0_m,
            "posterior_std_r0_m": recon.posterior_std_r0_m,
            "posterior_mean_cn2": recon.posterior_mean_cn2,
            "posterior_std_cn2": recon.posterior_std_cn2,
            "psnr_db": recon.psnr_db,
            "triage_score": tri.triage_score,
            "target_present": tri.target_present,
            "top_kind": tri.top_kind,
            "top_bbox": list(tri.top_bbox),
            "swimmer_count": len(swimmers),
            "swimmers": swimmers,
        }
        _append_jsonl(_DEMO_LEDGER, row)
        return row

    def _format_metrics(self, row: Dict[str, Any]) -> str:
        planted_r0_cm = float(row.get("planted_r0_m", 0.0) or 0.0) * 100.0
        mean_r0_cm = float(row.get("posterior_mean_r0_m", 0.0) or 0.0) * 100.0
        std_r0_cm = float(row.get("posterior_std_r0_m", 0.0) or 0.0) * 100.0
        cn2 = float(row.get("posterior_mean_cn2", 0.0) or 0.0)
        cn2_std = float(row.get("posterior_std_cn2", 0.0) or 0.0)
        return "\n".join(
            [
                f"{_TRUTH_LABEL}",
                f"receipt_id:          {row.get('receipt_id')}",
                f"planted r0:          {planted_r0_cm:.2f} cm",
                f"posterior r0:        {mean_r0_cm:.2f} +/- {std_r0_cm:.2f} cm",
                f"posterior Cn2:       {cn2:.3e} +/- {cn2_std:.3e}",
                f"psnr:                {float(row.get('psnr_db', 0.0) or 0.0):.2f} dB",
                f"triage:              {row.get('top_kind')} score={float(row.get('triage_score', 0.0) or 0.0):.3f}",
                f"target_present:      {bool(row.get('target_present'))}",
                f"bbox:                {tuple(row.get('top_bbox') or [])}",
                f"swimmers:            {int(row.get('swimmer_count', 0) or 0)}",
                "boundary:            lawful synthetic SAR target, no identity head",
            ]
        )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    w = SiftaFieldSightWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
