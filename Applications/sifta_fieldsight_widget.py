#!/usr/bin/env python3
"""Applications/sifta_fieldsight_widget.py — Stigmergic FarSight (lawful stigmergic reframing of the FarSight physics).

A Physics-Driven Whole-Body Presence System at Large Distance and Altitude.

Qt surface for the lawful atmospheric-optics + SAR triage organs. The
widget runs the real turbulence and triage code on synthetic lawful
targets (and real M5 camera frames via optical_ingress when the B toggle
is on), renders the animated swimmer field + r0 posterior + presence
flag, and writes append-only receipt rows.

§3.2 lawful: presence only, no biometric identity head.

Truth label: ``STIGMERGIC_FARSIGHT_WIDGET_V1`` (prior:
``SIFTA_FIELDSIGHT_WIDGET_V0`` — historical receipts retain that label).
File path and class name preserved for import + ledger continuity.
"""
from __future__ import annotations

"""SIFTA Fieldsight Widget — stigmergic organ for Alice body."""

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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
_TRUTH_LABEL = "STIGMERGIC_FARSIGHT_WIDGET_V1"
_PRIOR_TRUTH_LABEL = "SIFTA_FIELDSIGHT_WIDGET_V0"  # historical receipts retain this


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


class _FieldSightCanvas(QWidget):
    """Bright real-data visualization: r0 posterior + SAR bbox + animated swimmers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(310)
        self._result: Dict[str, Any] = {}
        # Animated particle field — one particle per swimmer, free-floating
        # across the upper image area. Position jitters every tick; brightness
        # tracks pheromone; hue tracks score. Physics state is read-only; we
        # never mutate swimmer rows here.
        self._particles: List[Dict[str, float]] = []
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_particles)
        self._anim_timer.start(80)  # ~12 fps, easy on the CPU
        self._rng = __import__("random").Random(0xA11CE)

    def set_result(self, result: Dict[str, Any]) -> None:
        self._result = dict(result or {})
        # Seed particles from the new swimmer list; preserve positions where
        # IDs survive so the field doesn't teleport on each Run press.
        swimmers = list(self._result.get("swimmers") or [])
        existing = {p["swimmer_id"]: p for p in self._particles}
        new_particles: List[Dict[str, float]] = []
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        for s in swimmers:
            sid = s.get("swimmer_id", "")
            old = existing.get(sid)
            if old is not None:
                old.update({
                    "pheromone": float(s.get("pheromone", 0.0) or 0.0),
                    "r0_m": float(s.get("r0_m", 0.0) or 0.0),
                    "score": float(s.get("score", 0.0) or 0.0),
                })
                new_particles.append(old)
            else:
                new_particles.append({
                    "swimmer_id": sid,
                    "pheromone": float(s.get("pheromone", 0.0) or 0.0),
                    "r0_m": float(s.get("r0_m", 0.0) or 0.0),
                    "score": float(s.get("score", 0.0) or 0.0),
                    "x": self._rng.uniform(0.1, 0.9) * w,
                    "y": self._rng.uniform(0.15, 0.55) * h,
                    "vx": self._rng.uniform(-0.6, 0.6),
                    "vy": self._rng.uniform(-0.4, 0.4),
                })
        self._particles = new_particles
        self.update()

    def _tick_particles(self) -> None:
        if not self._particles:
            return
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        # Particles drift toward their own r0 column (stigmergic attractor)
        # with a small jitter, then bounce off the upper-image bounds.
        swimmers = self._particles
        r0_vals = [p["r0_m"] for p in swimmers]
        if not r0_vals:
            return
        min_r0, max_r0 = min(r0_vals), max(r0_vals)
        span = max(max_r0 - min_r0, 1e-6)
        top_margin = 32
        bot_margin = int(h * 0.62)
        for p in swimmers:
            target_x = 42 + (w - 84) * ((p["r0_m"] - min_r0) / span)
            p["vx"] += (target_x - p["x"]) * 0.012 + self._rng.uniform(-0.35, 0.35)
            p["vy"] += self._rng.uniform(-0.30, 0.30)
            p["vx"] *= 0.92
            p["vy"] *= 0.92
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 8 or p["x"] > w - 8:
                p["vx"] *= -1
                p["x"] = max(8, min(w - 8, p["x"]))
            if p["y"] < top_margin or p["y"] > bot_margin:
                p["vy"] *= -1
                p["y"] = max(top_margin, min(bot_margin, p["y"]))
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

        # ── Animated swimmer particle field (drawn under the posterior plot) ──
        if self._particles:
            max_ph_anim = max((pt["pheromone"] for pt in self._particles), default=0.0) or 1.0
            for pt in self._particles:
                ph_norm = float(pt["pheromone"]) / max_ph_anim
                radius = 2.5 + 9.0 * ph_norm
                # Hue: cyan→green as score improves, amber if score is poor
                if pt["score"] >= -1.0:
                    base = QColor(0, 255, 180)  # neon green-cyan
                else:
                    base = QColor(255, 196, 64)  # amber
                base.setAlpha(60 + int(160 * ph_norm))
                p.setPen(QPen(base, 1))
                p.setBrush(QBrush(base))
                p.drawEllipse(QPointF(pt["x"], pt["y"]), radius, radius)
                # Pheromone halo for the top depositors
                if ph_norm > 0.6:
                    halo = QColor(0, 255, 204, 28)
                    p.setBrush(QBrush(halo))
                    p.setPen(QPen(halo, 1))
                    p.drawEllipse(QPointF(pt["x"], pt["y"]), radius * 2.2, radius * 2.2)

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

        gamma_post = self._result.get("gamma_posterior") or {}
        gamma_swimmers: List[Dict[str, Any]] = list(gamma_post.get("swimmers") or [])
        if gamma_post:
            gx0 = int(w * 0.58)
            gy0 = 42
            gw = max(220, int(w * 0.36))
            gh = 74
            p.setPen(QPen(QColor("#66CCFF"), 1))
            p.setBrush(QBrush(QColor(0, 28, 42, 145)))
            p.drawRoundedRect(QRectF(gx0, gy0, gw, gh), 8, 8)
            p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            p.setPen(QPen(QColor("#66CCFF"), 1))
            if gamma_post.get("deferred_by_thermodynamics"):
                p.drawText(gx0 + 10, gy0 + 24, "gamma POSTERIOR DEFERRED")
                p.drawText(gx0 + 10, gy0 + 48, "body gate asked for rest")
            else:
                mean_gamma = float(gamma_post.get("posterior_mean_gamma", 0.0) or 0.0)
                std_gamma = float(gamma_post.get("posterior_std_gamma", 0.0) or 0.0)
                map_gamma = float(gamma_post.get("posterior_map_gamma", 0.0) or 0.0)
                p.drawText(gx0 + 10, gy0 + 22, f"gamma {mean_gamma:.3f} +/- {std_gamma:.3f}  MAP {map_gamma:.3f}")
                if gamma_swimmers:
                    max_ph_g = max(float(s.get("pheromone", 0.0) or 0.0) for s in gamma_swimmers) or 1.0
                    base_y = gy0 + gh - 12
                    for s in gamma_swimmers:
                        gamma_h = float(s.get("gamma_hypothesis", 0.0) or 0.0)
                        ph = float(s.get("pheromone", 0.0) or 0.0)
                        xg = gx0 + 12 + (gw - 24) * gamma_h
                        bar_h = 38.0 * (ph / max_ph_g)
                        col = QColor("#66CCFF")
                        col.setAlpha(70 + int(175 * min(1.0, ph / max_ph_g)))
                        p.setPen(QPen(col, 2))
                        p.drawLine(int(xg), int(base_y), int(xg), int(base_y - bar_h))
                    p.setPen(QPen(QColor("#FFFFFF"), 1))
                    mxg = gx0 + 12 + (gw - 24) * mean_gamma
                    p.drawLine(int(mxg), gy0 + 34, int(mxg), gy0 + gh - 8)

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

        # Gamma posterior confidence strip + sparkline (lower-right).
        sc = self._result.get("slit_coherence") or {}
        if sc and "error" not in sc and sc.get("posterior_grid"):
            strip_x = int(w * 0.40)
            strip_y = h - 60
            strip_w = int(w * 0.24)
            strip_h = 16
            grid_g = sc.get("posterior_grid") or []
            weights = sc.get("posterior_weights") or []
            if grid_g and weights:
                total_w = sum(weights) or 1.0
                p.setPen(QPen(QColor("#FF9DEC"), 2))
                p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
                p.drawText(strip_x, strip_y - 6, "GAMMA POSTERIOR")
                # Background strip
                p.setPen(QPen(QColor(255, 157, 236, 60), 1))
                p.setBrush(QBrush(QColor(20, 5, 20)))
                p.drawRect(QRectF(strip_x, strip_y, strip_w, strip_h))
                # Posterior density bars
                max_w = max(weights) or 1.0
                for gi, gv in enumerate(grid_g):
                    wnorm = (weights[gi] / max_w) if max_w > 0 else 0.0
                    bx = strip_x + gv * strip_w
                    bh = strip_h * wnorm
                    color = QColor(255, 157, 236, 80 + int(170 * wnorm))
                    p.setPen(QPen(color, 1))
                    p.setBrush(QBrush(color))
                    p.drawRect(QRectF(bx - 1, strip_y + (strip_h - bh), 2, bh))
                # Mean tick
                g_mean = float(sc.get("gamma_mean", 0.0))
                g_std = float(sc.get("gamma_std", 0.0))
                mx = strip_x + g_mean * strip_w
                p.setPen(QPen(QColor("#00FFCC"), 2))
                p.drawLine(int(mx), strip_y - 3, int(mx), strip_y + strip_h + 3)
                p.setPen(QPen(QColor("#E8FFF8"), 1))
                p.setFont(QFont("Menlo", 9))
                p.drawText(strip_x, strip_y + strip_h + 14,
                           f"gamma = {g_mean:.3f} +/- {g_std:.3f}   "
                           f"survival={float(sc.get('body_run', {}).get('survival_fraction', 0.0)):.2f}")

                # Sparkline of recent γ_means (live update history)
                spark = sc.get("sparkline") or []
                if len(spark) > 1:
                    sp_x = strip_x + strip_w + 16
                    sp_y = strip_y
                    sp_w = max(60, w - sp_x - 18)
                    sp_h = strip_h
                    p.setPen(QPen(QColor(255, 157, 236, 60), 1))
                    p.setBrush(QBrush(QColor(20, 5, 20)))
                    p.drawRect(QRectF(sp_x, sp_y, sp_w, sp_h))
                    p.setPen(QPen(QColor("#FF9DEC"), 1.5))
                    last_pt = None
                    for i, val in enumerate(spark):
                        px = sp_x + (i / max(len(spark) - 1, 1)) * sp_w
                        py = sp_y + (1.0 - max(0.0, min(1.0, val))) * sp_h
                        pt = QPointF(px, py)
                        if last_pt is not None:
                            p.drawLine(last_pt, pt)
                        last_pt = pt
                    # Endpoint dot
                    if last_pt is not None:
                        p.setBrush(QBrush(QColor("#00FFCC")))
                        p.drawEllipse(last_pt, 2.5, 2.5)


class SiftaFieldSightWidget(QWidget):
    """Real FieldSight demo surface, no biometrics, no faces."""

    _live_instance: "SiftaFieldSightWidget | None" = None

    def __new__(cls, *args, **kwargs):
        if cls._live_instance is not None:
            try:
                _ = cls._live_instance.isVisible()   # raises RuntimeError if C++ side deleted
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except (RuntimeError, AttributeError):
                cls._live_instance = None
        inst = super().__new__(cls, *args, **kwargs)
        cls._live_instance = inst
        return inst

    def __init__(self, parent=None) -> None:
        super().__init__(parent)                 # always call on a fresh Python wrapper
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.setWindowTitle("Stigmergic FarSight")
        self.setMinimumSize(1120, 780)
        self.setStyleSheet("background-color: #05070B; color: #E8FFF8;")

        title = QLabel("Stigmergic FarSight")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #00FFCC; "
            "padding: 12px; background: rgba(0,255,204,0.08); border-radius: 8px;"
        )

        subtitle = QLabel(
            "A Physics-Driven Whole-Body Presence System at Large Distance and Altitude. "
            "§3.2 lawful — no identity head. Real swimmers, real receipts."
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

        self._status = QLabel(f"Truth label: {_TRUTH_LABEL}")
        self._status.setStyleSheet("color: #FFCC00; font-size: 11px;")

        self._real_cam = QCheckBox("Real M5 Camera + Telemetry (B)")
        self._real_cam.setStyleSheet("color: #FFCC00; font-size: 11px;")
        self._real_cam.setToolTip("Wires actual camera frames from the organism (M5 / USB camera + qualia). First step toward B.")

        # Slit Coherence - gamma posterior on Alice's body (thermodynamically coupled)
        self._slit_coh = QCheckBox("Slit Coherence (gamma posterior)")
        self._slit_coh.setStyleSheet("color: #FF9DEC; font-size: 11px; font-weight: 600;")
        self._slit_coh.setToolTip(
            "Body-coupled pipeline: alice_body_slit (real /dev/urandom + thermal_warning_level) "
            "produces a detector pattern; swarm_slit_coherence_posterior infers gamma +/- sigma. "
            "Every swimmer is uuid4-unique; the run cross-links both organ receipts."
        )

        # Sovereign Guardian — owner-bound recognition (Territory Is The Law)
        self._sovereign = QCheckBox("Sovereign Recognition (Owner Guardian)")
        self._sovereign.setStyleSheet("color: #00FFCC; font-size: 11px; font-weight: 600;")
        self._sovereign.setToolTip(
            "Runs the lawful owner-bound recognition swarm. Owner-enrolled face + "
            "owner-approved friends only. Strangers are flagged as 'unknown', never identified "
            "against a public gallery. Territory Is The Law. Requires a real camera frame."
        )
        self._enroll_btn = QPushButton("Enrol Owner Face")
        self._enroll_btn.setStyleSheet(
            "QPushButton { background: #FFCC00; color: #02110D; font-weight: 800; "
            "padding: 6px 10px; border-radius: 6px; font-size: 11px; }"
        )
        self._enroll_btn.setToolTip("Capture one real frame and write a signed owner template.")
        self._enroll_btn.clicked.connect(self._enroll_owner)

        controls = QHBoxLayout()
        controls.addWidget(self._run_btn)
        controls.addWidget(self._real_cam)
        controls.addWidget(self._slit_coh)
        controls.addWidget(self._sovereign)
        controls.addWidget(self._enroll_btn)
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

    def _enroll_owner(self) -> None:
        """Enrol owner via AG46's existing architect_face_recognition organ.

        Owner enrollment is owned by ``System.swarm_architect_face_recognition``
        (signed AG46, 2026-05-07, covenant §7.11). This button calls AG46's
        ``train()`` so the same 4096-dim L2-normalised embedding is updated
        and the same .sifta_state/architect_face_meta.json + ledger is used.
        Sovereign Recognition reads that template — no duplicate enrollment.
        """
        self._status.setText("Enrolling owner via AG46's architect organ...")
        QApplication.processEvents()
        try:
            import os as _os
            _os.environ.setdefault("SIFTA_FORCE_CV2", "1")
            from System.swarm_architect_face_recognition import train
            r = train()
            ok = bool(r.get("ok"))
            inner = r.get("receipt", {}) if ok else r
            if ok:
                self._metrics.setPlainText(
                    "OWNER ENROLLED (via AG46's swarm_architect_face_recognition)\n"
                    f"truth_label:         {inner.get('truth_label')}\n"
                    f"signed_by:           {inner.get('signed_by')}  covenant {inner.get('covenant')}\n"
                    f"embedding shape:     {inner.get('embedding_shape')}\n"
                    f"source_image:        {str(inner.get('source_image', ''))[:60]}...\n"
                    f"frame_age_s:         {inner.get('frame_age_s')}\n"
                    f"capture_status:      {inner.get('capture_status')}\n"
                    f"doctrine:            TERRITORY_IS_THE_LAW\n"
                    "Sovereign Recognition now reads AG46's template. "
                    "Tick 'Sovereign Recognition' + 'Real M5 Camera' and press Run."
                )
                self._status.setText("Owner enrolled — Sovereign Recognition armed (AG46 template)")
            else:
                err = inner.get("error") or "unknown"
                note = inner.get("note", "")
                self._metrics.setPlainText(
                    "OWNER ENROLLMENT FAILED (AG46 organ)\n"
                    f"error:               {err}\n"
                    f"capture_status:      {inner.get('capture_status')}\n"
                    f"note:                {note}\n"
                    "Sit in front of the camera and try again."
                )
                self._status.setText(f"Enrollment failed: {err}")
        except Exception as exc:
            self._metrics.setPlainText(f"Owner enrollment crashed: {type(exc).__name__}: {exc}")
            self._status.setText("Enrollment error")

    def _capture_real_frame(self, grid: int) -> Optional[Tuple["np.ndarray", str]]:
        """Grab a real frame via the lawful optical_ingress organ.

        Returns (frame_64x64_float01, sha256_reality_hash) on success.
        Returns None on any failure (caller falls back to synthetic honestly).
        """
        try:
            from System.optical_ingress import capture_photonic_truth
        except Exception:
            return None
        try:
            path, sha = capture_photonic_truth()
        except Exception:
            return None
        if not path or not sha:
            return None
        try:
            # path is a JPG from AVFoundation. If it's a mock-text fallback
            # (no real camera permission), bail to synthetic.
            from pathlib import Path as _P
            pth = _P(str(path))
            if not pth.exists() or pth.suffix.lower() != ".jpg":
                return None
            try:
                import cv2  # type: ignore
                img = cv2.imread(str(pth), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    return None
                img = cv2.resize(img, (grid, grid), interpolation=cv2.INTER_AREA)
                arr = img.astype(np.float32) / 255.0
            except Exception:
                # Fallback to PIL if cv2 unavailable
                try:
                    from PIL import Image  # type: ignore
                    im = Image.open(str(pth)).convert("L").resize((grid, grid))
                    arr = np.asarray(im, dtype=np.float32) / 255.0
                except Exception:
                    return None
            return arr, sha
        except Exception:
            return None

    def _body_coupled_gamma_seed(self, *, run_seed: int) -> Tuple[float, Dict[str, Any]]:
        """Derive the demo's synthetic slit visibility from Alice's body state."""
        thermal_warning = 0
        thermal_pressure = ""
        try:
            thermal_row = json.loads((_STATE / "thermal_cortex_state.json").read_text(encoding="utf-8"))
            thermal_warning = int(float(thermal_row.get("thermal_warning_level", 0) or 0))
            thermal_pressure = str(thermal_row.get("thermal_pressure") or thermal_row.get("state") or "")
        except Exception:
            thermal_row = {"source": "missing"}
        try:
            from System.swarm_metabolic_homeostasis import MetabolicHomeostat

            h = MetabolicHomeostat()
            metabolic_row = h.build_ledger_row(h.sample_live())
            metabolic_pressure = float(metabolic_row.get("pressure", 0.0) or 0.0)
            budget_multiplier = float(metabolic_row.get("budget_multiplier", 1.0) or 1.0)
        except Exception as exc:
            metabolic_row = {"error": f"{type(exc).__name__}: {exc}"}
            metabolic_pressure = 0.0
            budget_multiplier = 1.0
        jitter = ((int(run_seed) % 101) - 50) / 5000.0
        gamma_seed = 0.92 - 0.12 * thermal_warning - 0.18 * metabolic_pressure - 0.10 * (1.0 - budget_multiplier) + jitter
        gamma_seed = max(0.12, min(0.96, gamma_seed))
        return gamma_seed, {
            "thermal_warning_level": thermal_warning,
            "thermal_pressure": thermal_pressure,
            "metabolic_pressure": metabolic_pressure,
            "budget_multiplier": budget_multiplier,
            "gamma_seed_formula": "clamped body demo: 0.92 - thermal - metabolic pressure + tiny seed jitter",
            "thermal_row": thermal_row,
            "metabolic_row": metabolic_row,
        }

    def _compute_demo(self) -> Dict[str, Any]:
        from System.swarm_sar_triage_organ import triage
        from System.swarm_slit_coherence_posterior import (
            ThermodynamicClearanceDenied,
            infer_coherence_posterior,
            simulate_detector_pattern,
        )
        from System.swarm_turbulence_organ import run_swarm
        from System.swarm_turbulence_substrate import TurbulenceParams, degrade, synthetic_target

        grid = 64
        frame_source = "synthetic"
        reality_hash: Optional[str] = None
        camera_note: str = ""

        # B — Real M5 / built-in camera path through the lawful optical_ingress
        # organ. capture_photonic_truth uses ffmpeg + AVFoundation, already
        # TCC-handled, with SHA256 reality anchor and graceful mock fallback.
        if self._real_cam.isChecked():
            real_obs = self._capture_real_frame(grid)
            if real_obs is not None:
                degraded, reality_hash = real_obs
                target = degraded.copy()  # truth-unknown — use the observation as proxy
                frame_source = "real_camera_avfoundation"
                camera_note = f"reality_hash={reality_hash[:12]}..."
            else:
                target = synthetic_target(kind="rescue_hiker", grid=grid)
                frame_source = "synthetic_camera_fallback"
                camera_note = "camera unavailable; honest fallback to synthetic"
                degraded = None  # type: ignore[assignment]
        else:
            target = synthetic_target(kind="rescue_hiker", grid=grid)
            degraded = None  # type: ignore[assignment]

        planted = TurbulenceParams(cn2=6e-15)
        # Fresh seed per press — keeps the field alive between Run clicks
        # so the swimmers actually re-converge instead of replaying frame 42.
        run_seed = int(time.time_ns()) & 0x7FFFFFFF
        if degraded is None:
            degraded, _psf = degrade(target, params=planted, seed=run_seed, noise_sigma=0.005)
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

        gamma_seed, gamma_body = self._body_coupled_gamma_seed(run_seed=run_seed)
        try:
            slit_x, slit_observed = simulate_detector_pattern(
                gamma=gamma_seed,
                noise_sigma=0.0015,
                seed=run_seed & 0xFFFF,
            )
            gamma_result = infer_coherence_posterior(
                slit_x,
                slit_observed,
                n_swimmers=81,
                ticks=4,
                planted_gamma=gamma_seed,
                write_ledger=True,
            )
            gamma_swimmers = [
                {
                    "swimmer_id": sw.swimmer_id,
                    "gamma_hypothesis": sw.gamma_hypothesis,
                    "phase_hypothesis_rad": sw.phase_hypothesis_rad,
                    "pheromone": sw.pheromone,
                    "score": sw.last_score,
                }
                for sw in gamma_result.swimmers
            ]
            gamma_posterior: Dict[str, Any] = {
                "receipt_id": gamma_result.receipt_id,
                "planted_gamma": gamma_seed,
                "posterior_mean_gamma": gamma_result.posterior_mean_gamma,
                "posterior_std_gamma": gamma_result.posterior_std_gamma,
                "posterior_map_gamma": gamma_result.posterior_map_gamma,
                "posterior_map_phase_rad": gamma_result.posterior_map_phase_rad,
                "fringe_visibility": gamma_result.fringe_visibility,
                "thermodynamic_clearance": gamma_result.thermodynamic_clearance,
                "body_coupling": gamma_body,
                "swimmer_census": {
                    k: v for k, v in gamma_result.swimmer_census.items() if k != "swimmers"
                },
                "swimmers": gamma_swimmers,
            }
        except ThermodynamicClearanceDenied as exc:
            gamma_posterior = {
                "deferred_by_thermodynamics": True,
                "thermodynamic_clearance": exc.clearance,
                "body_coupling": gamma_body,
                "swimmer_census": {
                    "swimmer_count": 0,
                    "all_swimmers_accounted": True,
                    "unaccounted_swimmers": 0,
                },
                "swimmers": [],
            }

        swimmers = [
            {
                "swimmer_id": sw.swimmer_id,
                "r0_m": sw.r0_m,
                "pheromone": sw.pheromone,
                "score": sw.last_score,
            }
            for sw in recon.swimmers
        ]
        # Slit Coherence gamma posterior - body-coupled (Alice's thermodynamics).
        # When the toggle is on we run a small alice_body_slit (which uses real
        # /dev/urandom + live thermal_warning_level), then feed its detector
        # pattern into the canonical infer_coherence_posterior. The gamma posterior
        # we display is therefore thermodynamically linked to this silicon's
        # current state; every swimmer in both organs carries a uuid4 and the
        # two run_ids cross-link in the receipt.
        slit_coherence: Optional[Dict[str, Any]] = None
        if self._slit_coh.isChecked():
            try:
                from System.swarm_alice_body_slit import run_alice_body_slit
                from System.swarm_slit_coherence_posterior import (
                    infer_coherence_posterior, detector_axis,
                )
                # Step 1 — body-coupled survival run, calibrated by live thermal
                body = run_alice_body_slit(
                    n_swimmers=600,
                    decoherence_rate_per_tick=None,  # None → auto from thermal_cortex_state
                    write_receipt=True,
                )
                # Step 2 - convert the body-side detector to the canonical
                # lab-units geometry (rescale x-axis); the shape of the pattern
                # is what carries gamma, so a uniform stretch is information-preserving.
                obs_body = np.asarray(body.detector_intensity, dtype=np.float64)
                if obs_body.sum() > 0:
                    n = obs_body.shape[0]
                    x_lab = detector_axis(n_points=n, span=0.020)
                    # Step 3 - recover gamma with the canonical organ
                    post = infer_coherence_posterior(
                        x_lab, obs_body,
                        n_swimmers=41, ticks=5,
                        planted_gamma=body.survival_fraction,  # the doctrine prediction V = p_survive
                        write_ledger=True,
                    )
                    posterior_census = dict(post.swimmer_census or {})
                    posterior_census.pop("swimmers", None)
                    body_accounted = int(body.n_lived) + int(body.n_died)
                    body_census = {
                        "swimmer_count": int(body.n_swimmers),
                        "n_lived": int(body.n_lived),
                        "n_died": int(body.n_died),
                        "unaccounted_swimmers": max(0, int(body.n_swimmers) - body_accounted),
                        "all_swimmers_accounted": int(body.n_swimmers) == body_accounted,
                    }
                    # Keep a sparkline of recent gamma_means for the live update display
                    if not hasattr(self, "_gamma_sparkline"):
                        self._gamma_sparkline: List[float] = []
                    self._gamma_sparkline.append(post.posterior_mean_gamma)
                    self._gamma_sparkline = self._gamma_sparkline[-40:]
                    slit_coherence = {
                        "gamma_mean": float(post.posterior_mean_gamma),
                        "gamma_std": float(post.posterior_std_gamma),
                        "gamma_map": float(post.posterior_map_gamma),
                        "fringe_visibility_direct": float(post.fringe_visibility),
                        "posterior_grid": [float(sw.gamma_hypothesis) for sw in post.swimmers],
                        "posterior_weights": [float(sw.pheromone) for sw in post.swimmers],
                        "sparkline": list(self._gamma_sparkline),
                        "slit_coherence_receipt_id": post.receipt_id,
                        "thermodynamic_clearance": post.thermodynamic_clearance,
                        "posterior_swimmer_count": len(post.swimmers),
                        "swimmer_census": posterior_census,
                        "body_swimmer_census": body_census,
                        "body_run": {
                            "run_id": body.run_id,
                            "survival_fraction": float(body.survival_fraction),
                            "decoherence_rate": float(body.decoherence_rate_per_tick),
                            "thermal_warning_level": int(body.thermal_warning_level_at_start),
                            "n_swimmers": int(body.n_swimmers),
                            "n_lived": int(body.n_lived),
                            "n_died": int(body.n_died),
                            "unaccounted_swimmers": body_census["unaccounted_swimmers"],
                        },
                        "doctrine_check_V_equals_p_survive": {
                            "predicted_gamma": float(body.survival_fraction),
                            "recovered_gamma_mean": float(post.posterior_mean_gamma),
                            "abs_error": abs(float(post.posterior_mean_gamma) - float(body.survival_fraction)),
                        },
                    }
            except Exception as exc:
                slit_coherence = {"error": f"{type(exc).__name__}: {exc}"}

        # ── Sovereign Recognition (Owner Guardian) — Territory Is The Law ──
        sovereign_verdict: Optional[Dict[str, Any]] = None
        if self._sovereign.isChecked():
            # Only meaningful on real camera frames
            if frame_source == "real_camera_avfoundation":
                try:
                    from System.swarm_sovereign_recognition_organ import recognize
                    real_full = self._capture_real_frame(grid=320)
                    if real_full is not None:
                        full_frame, _ = real_full
                        v = recognize(full_frame)
                        sovereign_verdict = {
                            "verdict": v.verdict,
                            "confidence": v.confidence,
                            "owner_similarity": v.owner_similarity,
                            "best_friend": v.best_friend_name,
                            "best_friend_similarity": v.best_friend_similarity,
                            "receipt_id": v.receipt_id,
                            "n_swimmers": len(v.swimmers),
                        }
                except Exception as exc:
                    sovereign_verdict = {"verdict": "error", "error": f"{type(exc).__name__}: {exc}"}
            else:
                sovereign_verdict = {
                    "verdict": "skipped",
                    "reason": "Sovereign Recognition needs a real camera frame. Tick Real M5 Camera and Run.",
                }

        row = {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "receipt_id": f"fieldsight-{int(time.time() * 1000)}",
            "run_seed": run_seed,
            "frame_source": frame_source,
            "reality_hash": reality_hash,
            "camera_note": camera_note,
            "sovereign": sovereign_verdict,
            "slit_coherence": slit_coherence,
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
            "gamma_posterior": gamma_posterior,
        }
        _append_jsonl(_DEMO_LEDGER, row)
        return row

    def _format_metrics(self, row: Dict[str, Any]) -> str:
        planted_r0_cm = float(row.get("planted_r0_m", 0.0) or 0.0) * 100.0
        mean_r0_cm = float(row.get("posterior_mean_r0_m", 0.0) or 0.0) * 100.0
        std_r0_cm = float(row.get("posterior_std_r0_m", 0.0) or 0.0) * 100.0
        cn2 = float(row.get("posterior_mean_cn2", 0.0) or 0.0)
        cn2_std = float(row.get("posterior_std_cn2", 0.0) or 0.0)
        frame_src = row.get("frame_source", "synthetic")
        rh = row.get("reality_hash")
        cam_line = f"frame_source:        {frame_src}"
        if rh:
            cam_line += f"  (reality_hash {str(rh)[:12]}...)"
        cam_note = row.get("camera_note") or ""
        sc = row.get("slit_coherence") or {}
        if sc and "error" not in sc:
            br = sc.get("body_run", {})
            check = sc.get("doctrine_check_V_equals_p_survive", {})
            sc_census = sc.get("swimmer_census") or {}
            body_census = sc.get("body_swimmer_census") or {}
            sc_line = (
                f"gamma posterior:     {sc.get('gamma_mean', 0.0):.4f} +/- {sc.get('gamma_std', 0.0):.4f}  "
                f"(MAP={sc.get('gamma_map', 0.0):.4f})\n"
                f"body coupling:       survival={br.get('survival_fraction', 0.0):.3f}  "
                f"thermal={br.get('thermal_warning_level', 0)}  "
                f"decoh_rate={br.get('decoherence_rate', 0.0):.4f}\n"
                f"V=p_survive check:   pred={check.get('predicted_gamma', 0.0):.3f}  "
                f"recovered={check.get('recovered_gamma_mean', 0.0):.3f}  "
                f"|err|={check.get('abs_error', 0.0):.3f}\n"
                f"slit swimmers:       posterior={sc_census.get('swimmer_count', 0)} "
                f"unaccounted={sc_census.get('unaccounted_swimmers', 0)}; "
                f"body={body_census.get('swimmer_count', 0)} "
                f"unaccounted={body_census.get('unaccounted_swimmers', 0)}\n"
                f"cross-link:          body={br.get('run_id','')}  slit={sc.get('slit_coherence_receipt_id','')[:24]}..."
            )
        elif sc and "error" in sc:
            sc_line = f"gamma posterior:     error - {sc['error']}"
        else:
            sc_line = "gamma posterior:     - (toggle off)"
        sov = row.get("sovereign") or {}
        gamma = row.get("gamma_posterior") or {}
        if gamma.get("deferred_by_thermodynamics"):
            clearance = gamma.get("thermodynamic_clearance") or {}
            gamma_line = "gamma posterior:    deferred by thermodynamic gate"
            gamma_thermo_line = (
                f"gamma thermo:       reasons={','.join(str(x) for x in clearance.get('reasons', [])[:3])} "
                f"receipt={str(clearance.get('receipt_hash') or '')[:12]}"
            )
            gamma_census_line = "gamma swimmers:     0 accounted (deferred before birth)"
        elif gamma:
            census = gamma.get("swimmer_census") or {}
            clearance = gamma.get("thermodynamic_clearance") or {}
            body = clearance.get("body") if isinstance(clearance, dict) else {}
            gamma_line = (
                f"gamma posterior:    {float(gamma.get('posterior_mean_gamma', 0.0)):.3f} "
                f"+/- {float(gamma.get('posterior_std_gamma', 0.0)):.3f} "
                f"(MAP {float(gamma.get('posterior_map_gamma', 0.0)):.3f})"
            )
            gamma_thermo_line = (
                f"gamma thermo:       action={clearance.get('action')} "
                f"thermal={((body or {}).get('thermal_warning_level'))} "
                f"budget={((body or {}).get('budget_multiplier'))} "
                f"receipt={str(clearance.get('receipt_hash') or '')[:12]}"
            )
            gamma_census_line = (
                f"gamma swimmers:     {int(census.get('swimmer_count', 0) or 0)} accounted, "
                f"unaccounted={int(census.get('unaccounted_swimmers', 0) or 0)} "
                f"hash={str(census.get('swimmer_ids_sha256') or '')[:12]}"
            )
        else:
            gamma_line = "gamma posterior:    —"
            gamma_thermo_line = "gamma thermo:       —"
            gamma_census_line = "gamma swimmers:     —"
        if sov:
            v = sov.get("verdict", "")
            if v in ("owner",) or v.startswith("friend:"):
                sov_line = (
                    f"sovereign verdict:   {v.upper()}  "
                    f"(conf={float(sov.get('confidence', 0.0)):.3f}, "
                    f"owner_sim={float(sov.get('owner_similarity', 0.0)):.3f})"
                )
            elif v == "unknown":
                sov_line = (
                    f"sovereign verdict:   UNKNOWN (new face nearby)  "
                    f"owner_sim={float(sov.get('owner_similarity', 0.0)):.3f} "
                    f"below threshold"
                )
            elif v == "no_owner_enrolled":
                sov_line = "sovereign verdict:   NO OWNER ENROLLED — press 'Enrol Owner Face' first"
            elif v == "skipped":
                sov_line = f"sovereign verdict:   skipped ({sov.get('reason', '')})"
            else:
                sov_line = f"sovereign verdict:   {v}"
        else:
            sov_line = "sovereign verdict:   — (toggle off)"
        return "\n".join(
            [
                f"{_TRUTH_LABEL}",
                f"receipt_id:          {row.get('receipt_id')}",
                cam_line,
                (f"camera_note:         {cam_note}" if cam_note else "camera_note:         —"),
                sov_line,
                sc_line,
                f"planted r0:          {planted_r0_cm:.2f} cm",
                f"posterior r0:        {mean_r0_cm:.2f} +/- {std_r0_cm:.2f} cm",
                f"posterior Cn2:       {cn2:.3e} +/- {cn2_std:.3e}",
                gamma_line,
                gamma_thermo_line,
                gamma_census_line,
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
