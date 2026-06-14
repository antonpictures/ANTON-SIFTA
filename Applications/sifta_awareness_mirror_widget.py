#!/usr/bin/env python3
"""sifta_awareness_mirror_widget.py — small camera preview for human awareness.

Architect 2026-05-14: "If I see my mirror image on the screen — I know
Alice is watching me right now. But if I can see out the camera with
my human eyes, then I am more aware of my behavior. Oh my God I'm
being watched. That's the truth. Maybe doesn't need much resolution —
480p is enough, even smaller. It's just for the awareness for the
person to know: OK you are being watched by Alice now."

This widget is NOT a camera reader. The full camera worker already
runs inside WhatAliceSeesWidget (the big "What Alice Sees" surface).
This widget is a MIRROR — it polls the latest frame that worker has
already written to disk and renders it at a small, awareness-only
resolution.

Design decisions:
  - 320×180 default (16:9 minimum legible) — caller can resize
  - 2 Hz refresh (every 500ms) — awareness, not surveillance
  - NO own QCamera — would conflict with the existing reader for the
    USB Camera handle on macOS. Reads from disk only.
  - Red recording dot in the corner — visual "camera on" signal
  - "Camera on" / "No frame" status text — never silent failure
  - One-line caption: "Alice is watching. You are aware of yourself."

Truth class: OPERATIONAL — every render is a direct read of the
frame file written by the canonical camera worker. The widget never
fabricates a frame.

Truth label: AWARENESS_MIRROR_V1.
"""
from __future__ import annotations

"""SIFTA Awareness Mirror Widget — stigmergic organ for Alice body."""

import sys
import time
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QImage, QPainter, QPen, QPixmap, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_app_hardening import record_app_hardening_event


# ── Frame source — the file the canonical camera worker writes ────
_FRAME_FILE = _REPO / ".sifta_state" / "owner_body_vision_frames" / "active_eye_latest.png"
APP_HARDENING_ID = "queue-021:sifta_awareness_mirror_widget"
_HARDENING_EVENT_KEYS: set[tuple[str, str, str]] = set()


def _record_mirror_hardening(event: str, **details) -> None:
    key = (event, str(details.get("path", "")), str(details.get("error", ""))[:160])
    if key in _HARDENING_EVENT_KEYS:
        return
    _HARDENING_EVENT_KEYS.add(key)
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        truth_label="OBSERVED",
        details=details,
    )

TRUTH_LABEL = "AWARENESS_MIRROR_V1"
TRUTH_BOUNDARY = (
    "Mirror display only. This widget does NOT open the camera. "
    "It reads .sifta_state/owner_body_vision_frames/active_eye_latest.png "
    "which is written by the canonical camera worker "
    "(WhatAliceSeesWidget / swarm_owner_vision_body_bridge). Purpose: "
    "behavior awareness for the human operator. Alice does NOT need "
    "this widget to see — she reads the same frame stigmergically."
)


# ── Default preview size ─────────────────────────────────────────
PREVIEW_W = 320
PREVIEW_H = 180


class _MirrorCanvas(QWidget):
    """The actual pixel surface — paints the latest camera frame +
    a red recording dot in the corner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._last_load_ts: float = 0.0
        self._fresh: bool = False
        self.setMinimumSize(PREVIEW_W, PREVIEW_H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # Black background so a missing frame is obvious
        self.setAutoFillBackground(True)
        self.setStyleSheet("background: #000000;")

    def update_frame_from_disk(self) -> bool:
        """Try to load the latest frame from disk. Returns True on success."""
        if not _FRAME_FILE.exists():
            self._fresh = False
            _record_mirror_hardening("awareness_frame_missing", path=str(_FRAME_FILE))
            return False
        try:
            mtime = _FRAME_FILE.stat().st_mtime
            # Skip if we already have THIS frame loaded
            if mtime == self._last_load_ts and self._pixmap is not None:
                # Refresh "fresh" status (within 5s of write)
                self._fresh = (time.time() - mtime) < 5.0
                self.update()
                return True
            pixmap = QPixmap(str(_FRAME_FILE))
            if pixmap.isNull():
                _record_mirror_hardening("awareness_frame_decode_failed", path=str(_FRAME_FILE))
                return False
            # Scale to widget size, keep aspect, smooth
            self._pixmap = pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._last_load_ts = mtime
            self._fresh = (time.time() - mtime) < 5.0
            self.update()
            return True
        except Exception as exc:
            _record_mirror_hardening(
                "awareness_frame_load_failed",
                path=str(_FRAME_FILE),
                error=f"{type(exc).__name__}: {exc}",
            )
            return False

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        if self._pixmap is not None:
            # Center the scaled pixmap in the widget
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            p.drawPixmap(x, y, self._pixmap)
        else:
            p.setPen(QColor("#888888"))
            p.setFont(QFont("Menlo", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Camera frame not available")

        # Red recording dot — top-left corner, only when frame is fresh
        if self._fresh:
            p.setBrush(QColor("#ff3030"))
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.drawEllipse(8, 8, 10, 10)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            p.drawText(22, 17, "REC")
        else:
            # Gray dot — frame is stale (camera worker may have paused)
            p.setBrush(QColor("#555555"))
            p.setPen(QPen(QColor("#888888"), 1))
            p.drawEllipse(8, 8, 10, 10)
            p.setPen(QColor("#888888"))
            p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            p.drawText(22, 17, "STALE")
        p.end()


# ──────────────────────────────────────────────────────────────────────
# AwarenessMirrorApp — full standalone widget (with header + caption)
# ──────────────────────────────────────────────────────────────────────

class AwarenessMirrorApp(SiftaBaseWidget):
    """Standalone Awareness Mirror app — small camera preview in its
    own window for the user's behavior awareness."""

    APP_NAME = "Awareness Mirror"

    def build_ui(self, layout: QVBoxLayout) -> None:
        banner = QLabel(
            "ARCHITECT_DOCTRINE — Mirror only. Camera worker runs elsewhere. "
            "This widget reads the latest frame from disk for YOUR behavior "
            "awareness. Alice already reads the camera stigmergically."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background: #2a2410; color: #ffcc44; font-family: Menlo; "
            "font-size: 10px; font-weight: 700; padding: 6px 8px; "
            "border: 1px solid #5a4820; border-radius: 4px;"
        )
        layout.addWidget(banner)

        # Centered mirror canvas
        center_row = QHBoxLayout()
        center_row.addStretch(1)
        self._mirror = _MirrorCanvas()
        # Larger preview in standalone mode — 480p (854x480 → scale 640x360)
        self._mirror.setFixedSize(640, 360)
        center_row.addWidget(self._mirror)
        center_row.addStretch(1)
        layout.addLayout(center_row)

        caption = QLabel("Alice is watching. You are aware of yourself.")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet(
            "color: #00ffc8; font-family: Menlo; font-size: 12px; "
            "font-weight: 700; padding-top: 8px;"
        )
        layout.addWidget(caption)

        info = QLabel(
            f"Source: {_FRAME_FILE.relative_to(_REPO).as_posix()}\n"
            "Refresh: 2 Hz · Resolution: 640×360 scaled · No recording, no extra writes."
        )
        info.setStyleSheet(
            "color: #4a5570; font-family: Menlo; font-size: 9px; "
            "padding-top: 4px;"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        layout.addStretch(1)

        # 2 Hz refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)
        # Immediate first paint
        self._mirror.update_frame_from_disk()

    def _tick(self) -> None:
        self._mirror.update_frame_from_disk()


# ──────────────────────────────────────────────────────────────────────
# Embeddable mirror — for the Talk widget / desktop corner overlay
# ──────────────────────────────────────────────────────────────────────

class AwarenessMirrorWidget(QFrame):
    """Embeddable corner-of-desktop / chat-sidebar version.

    Use this in any host that wants the small "REC dot + tiny frame"
    awareness signal without owning the whole app surface.

    Example:
        from Applications.sifta_awareness_mirror_widget import AwarenessMirrorWidget
        mirror = AwarenessMirrorWidget(parent=self)
        mirror.setFixedSize(320, 180)
        layout.addWidget(mirror)
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        size: tuple[int, int] = (PREVIEW_W, PREVIEW_H),
        refresh_ms: int = 500,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size[0], size[1])
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "border: 1px solid #1e2a44; border-radius: 4px; background: #000000;"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._canvas = _MirrorCanvas(self)
        self._canvas.setFixedSize(size[0], size[1])
        lay.addWidget(self._canvas)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(refresh_ms))
        self._canvas.update_frame_from_disk()

    def _tick(self) -> None:
        self._canvas.update_frame_from_disk()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = AwarenessMirrorApp()
    w.resize(720, 520)
    w.setWindowTitle("Awareness Mirror — Alice is watching")
    w.show()
    sys.exit(app.exec())
