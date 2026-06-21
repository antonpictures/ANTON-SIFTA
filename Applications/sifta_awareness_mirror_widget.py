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
  - NO own QCamera — would conflict with the existing reader for live
    camera handles on macOS. Reads from disk only.
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

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

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
from System.swarm_camera_frame_paths import (
    active_eye_frame_path,
    device_eye_frame_path,
)
from System.swarm_app_hardening import record_app_hardening_event


# ── Frame source — the file the canonical camera worker writes ────
_FRAME_FILE = active_eye_frame_path()
_TOPOLOGY_FILE = _REPO / ".sifta_state" / "camera_topology_latest.json"
_EYE_REGISTRY_FILE = _REPO / ".sifta_state" / "eye_registry.json"
_ACTIVE_TARGET_FILE = _REPO / ".sifta_state" / "active_saccade_target.json"
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
    "and per-device frames under owner_body_vision_frames/by_device "
    "which are written by the canonical camera worker "
    "(WhatAliceSeesWidget / swarm_owner_vision_body_bridge). Purpose: "
    "behavior awareness for the human operator. Alice does NOT need "
    "this widget to see — she reads the same frame stigmergically."
)


# ── Default preview size ─────────────────────────────────────────
PREVIEW_W = 320
PREVIEW_H = 180
FRAME_FRESH_MAX_AGE_S = 5.0


class _MirrorCanvas(QWidget):
    """The actual pixel surface — paints the latest camera frame +
    a red recording dot in the corner."""

    def __init__(
        self,
        parent=None,
        *,
        frame_file: Path | None = None,
        label: str = "",
    ):
        super().__init__(parent)
        self._frame_file = Path(frame_file) if frame_file is not None else _FRAME_FILE
        self._label_text = str(label or "").strip()
        self._pixmap: Optional[QPixmap] = None
        self._last_load_ts: float = 0.0
        self._fresh: bool = False
        self._status_text: str = self._format_status("No live camera frame")
        self.setMinimumSize(PREVIEW_W, PREVIEW_H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # Black background so a missing frame is obvious
        self.setAutoFillBackground(True)
        self.setStyleSheet("background: #000000;")

    def set_source(self, frame_file: Path, label: str = "") -> None:
        frame_file = Path(frame_file)
        label = str(label or "").strip()
        if frame_file == self._frame_file and label == self._label_text:
            return
        self._frame_file = frame_file
        self._label_text = label
        self._pixmap = None
        self._last_load_ts = 0.0
        self._fresh = False
        self._status_text = self._format_status("No live camera frame")
        self.update()

    def _format_status(self, text: str) -> str:
        if self._label_text:
            return f"{self._label_text}\n{text}"
        return text

    def update_frame_from_disk(self) -> bool:
        """Load only fresh camera frames from disk.

        Stale pixels are deliberately not displayed: an old camera frame is
        worse than a blank mirror because it looks like a live eye.
        """
        frame_file = self._frame_file
        if not frame_file.exists():
            self._pixmap = None
            self._fresh = False
            self._status_text = self._format_status("No live camera frame")
            self.update()
            _record_mirror_hardening("awareness_frame_missing", path=str(frame_file))
            return False
        try:
            mtime = frame_file.stat().st_mtime
            age_s = max(0.0, time.time() - mtime)
            if age_s >= FRAME_FRESH_MAX_AGE_S:
                self._pixmap = None
                self._last_load_ts = mtime
                self._fresh = False
                self._status_text = self._format_status(
                    f"Camera frame stale\nlast update {int(age_s)}s ago"
                )
                self.update()
                return False
            # Skip if we already have THIS frame loaded
            if mtime == self._last_load_ts and self._pixmap is not None:
                self._fresh = True
                self._status_text = self._format_status("Live camera frame")
                self.update()
                return True
            pixmap = QPixmap(str(frame_file))
            if pixmap.isNull():
                self._pixmap = None
                self._fresh = False
                self._status_text = self._format_status("Camera frame decode failed")
                self.update()
                _record_mirror_hardening("awareness_frame_decode_failed", path=str(frame_file))
                return False
            # Scale to widget size, keep aspect, smooth
            self._pixmap = pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._last_load_ts = mtime
            self._fresh = True
            self._status_text = self._format_status("Live camera frame")
            self.update()
            return True
        except Exception as exc:
            self._pixmap = None
            self._fresh = False
            self._status_text = self._format_status("Camera frame load failed")
            self.update()
            _record_mirror_hardening(
                "awareness_frame_load_failed",
                path=str(frame_file),
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
            if self._label_text:
                p.fillRect(0, self.height() - 18, self.width(), 18, QColor(0, 0, 0, 170))
                p.setPen(QColor("#ffffff"))
                p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
                p.drawText(6, self.height() - 6, self._label_text[:34])
        else:
            p.setPen(QColor("#888888"))
            p.setFont(QFont("Menlo", 9))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       self._status_text or "No live camera frame")

        self._draw_eye_live_badge(p, live=bool(self._fresh))
        p.end()

    @staticmethod
    def _draw_eye_live_badge(p: QPainter, *, live: bool) -> None:
        """Eye badge top-left: 👁 with red pupil dot when live (replaces REC text)."""
        p.save()
        p.setFont(QFont("Apple Color Emoji", 13))
        p.setPen(QColor("#cccccc" if live else "#666666"))
        p.drawText(3, 17, "👁")
        pupil_color = QColor("#ff3030") if live else QColor("#555555")
        p.setBrush(pupil_color)
        p.setPen(QPen(QColor("#ffffff"), 1) if live else Qt.PenStyle.NoPen)
        p.drawEllipse(11, 10, 5, 5)
        p.restore()


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

def _active_eye_display_bundle() -> tuple[Path, str]:
    """Single mirror tile: the eye Alice is routed through right now."""
    target = _active_target_device()
    name = str(target.get("name") or "").strip()
    if not name:
        return _FRAME_FILE, "active eye"
    dev = {
        "name": name,
        "display_name": _display_name_for_camera(name),
        "unique_id": str(target.get("unique_id") or ""),
        "role": _display_role_for_camera(name),
    }
    label = _camera_tile_label(dev, 0)
    if label.startswith("owner eye:"):
        label = "active eye:" + label[len("owner eye:") :]
    elif label.startswith("world eye:"):
        label = "active eye:" + label[len("world eye:") :]
    elif not label.lower().startswith("active eye"):
        label = f"active eye: {dev['display_name']}"
    return _frame_source_for_device(dev), label


class AwarenessMirrorWidget(QFrame):
    """Embeddable corner-of-desktop / chat-sidebar version.

    One camera at a time: reads the active saccade target and shows only the
    frame Alice is seeing now. Stale tiles hide by default in Talk embeds.

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
        hide_when_stale: bool = True,
    ) -> None:
        super().__init__(parent)
        self._hide_when_stale = bool(hide_when_stale)
        self._topology_tick = 0
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
        self._refresh_active_source()
        self._sync_visibility(self._canvas.update_frame_from_disk())

    def _refresh_active_source(self) -> None:
        frame_path, label = _active_eye_display_bundle()
        self._canvas.set_source(frame_path, label)

    def _tick(self) -> None:
        self._topology_tick += 1
        if self._topology_tick % 10 == 0:
            self._refresh_active_source()
        self._sync_visibility(self._canvas.update_frame_from_disk())

    def _sync_visibility(self, fresh: bool) -> None:
        """Embeds should not display a stale camera tile as a third eye.

        The standalone AwarenessMirrorApp still paints the explicit STALE
        diagnostic. The Talk/desktop embed is an awareness signal only: when
        the canonical frame writer is not fresh, the tile disappears.
        """
        if self._hide_when_stale:
            self.setVisible(bool(fresh))
        else:
            self.setVisible(True)


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _norm_device_text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _camera_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_uid = str(left.get("unique_id") or "").strip()
    right_uid = str(right.get("unique_id") or "").strip()
    if left_uid and right_uid and left_uid == right_uid:
        return True
    return bool(_norm_device_text(left.get("name")) and _norm_device_text(left.get("name")) == _norm_device_text(right.get("name")))


def _is_excluded_aux_camera(name: Any) -> bool:
    try:
        from System.swarm_camera_target import is_allowed_owner_body_camera

        return not is_allowed_owner_body_camera(str(name or "").strip())
    except Exception:
        text = _norm_device_text(name)
        return any(
            token in text
            for token in (
                "obs",
                "virtual",
                "iphone",
                "ipad",
                "continuity",
                "desk view",
            )
        )


def _display_role_for_camera(name: Any) -> str:
    text = _norm_device_text(name)
    if any(token in text for token in ("macbook pro camera", "facetime", "built in", "built-in")):
        return "owner_eye"
    if any(token in text for token in ("logitech", "usb", "vid:1133", "external", "webcam")):
        return "world_eye"
    return "camera"


def _display_name_for_camera(name: Any) -> str:
    raw = str(name or "").strip()
    text = _norm_device_text(raw)
    if "vid:1133" in text and "pid:2081" in text:
        return "Logitech USB"
    return raw


def _active_target_device() -> dict[str, Any]:
    row = _read_json_file(_ACTIVE_TARGET_FILE)
    return {
        "name": row.get("name") or "",
        "unique_id": row.get("unique_id") or "",
    }


def _dual_camera_devices() -> list[dict[str, Any]]:
    """Return owner/world camera rows for display, identity-bound, never index-bound."""
    devices: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    registry = _read_json_file(_EYE_REGISTRY_FILE)
    eyes = registry.get("eyes") if isinstance(registry.get("eyes"), list) else []
    role_order = {"owner_eye": 0, "world_eye": 1, "aux_eye": 2}
    for eye in sorted(
        (eye for eye in eyes if isinstance(eye, dict)),
        key=lambda eye: (role_order.get(str(eye.get("role") or ""), 9), str(eye.get("eye_id") or "")),
    ):
        if eye.get("connection_state") != "LIVE":
            continue
        role = str(eye.get("role") or "camera")
        if role not in {"owner_eye", "world_eye"}:
            continue
        identity = eye.get("device_identity") if isinstance(eye.get("device_identity"), dict) else {}
        name = str(eye.get("device_name") or "").strip()
        uid = str(identity.get("unique_id") or "").strip()
        if not name or _is_excluded_aux_camera(name):
            continue
        key = (uid, _norm_device_text(name))
        if key in seen:
            continue
        seen.add(key)
        devices.append({
            "name": name,
            "display_name": _display_name_for_camera(name),
            "unique_id": uid,
            "role": role,
        })
        if len(devices) >= 2:
            return devices

    topology = _read_json_file(_TOPOLOGY_FILE)
    topo_devices = topology.get("devices") if isinstance(topology.get("devices"), list) else []
    ranked_topology: list[dict[str, Any]] = []
    for dev in topo_devices:
        if not isinstance(dev, dict):
            continue
        name = str(dev.get("name") or "").strip()
        uid = str(dev.get("unique_id") or "").strip()
        if not name or _is_excluded_aux_camera(name):
            continue
        role = _display_role_for_camera(name)
        if role not in {"owner_eye", "world_eye"}:
            continue
        ranked_topology.append({
            "name": name,
            "display_name": _display_name_for_camera(name),
            "unique_id": uid,
            "role": role,
        })

    role_rank = {"owner_eye": 0, "world_eye": 1}
    for dev in sorted(ranked_topology, key=lambda d: (role_rank.get(str(d.get("role")), 9), _norm_device_text(d.get("name")))):
        name = str(dev.get("name") or "").strip()
        uid = str(dev.get("unique_id") or "").strip()
        key = (uid, _norm_device_text(name))
        if key in seen:
            continue
        seen.add(key)
        devices.append(dev)
        if len(devices) >= 2:
            break
    return devices


def _frame_mtime(path: Path) -> float:
    try:
        return float(path.stat().st_mtime) if path.exists() else 0.0
    except Exception:
        return 0.0


def _frame_source_for_device(device: dict[str, Any]) -> Path:
    """Pick the freshest on-disk frame for one camera tile.

    Owner-eye per-device PNGs used to update only every 10 s while the mirror
    stale gate is 5 s, which blanked the left MacBook tile even though the
    active-eye file was still fresh. Prefer the newest path among per-device
    and active-eye when both refer to the same live target.
    """
    device_path = device_eye_frame_path(device.get("name"), device.get("unique_id"))
    candidates: list[Path] = []
    if device_path.exists():
        candidates.append(device_path)
    if _camera_matches(device, _active_target_device()) and _FRAME_FILE.exists():
        candidates.append(_FRAME_FILE)
    if not candidates:
        if _camera_matches(device, _active_target_device()):
            return _FRAME_FILE
        return device_path
    return max(candidates, key=_frame_mtime)


def _camera_tile_label(device: dict[str, Any], index: int) -> str:
    role = str(device.get("role") or "").replace("_", " ").strip()
    name = str(device.get("display_name") or device.get("name") or f"Camera {index + 1}").strip()
    if role and role != "camera":
        return f"{role}: {name}"
    return name


# George 2026-06-18 (r1286): one active camera at a time — Talk uses
# AwarenessMirrorWidget only. Dual strip kept for legacy hosts/tests.
ActiveAwarenessMirrorWidget = AwarenessMirrorWidget


class DualAwarenessMirrorWidget(QFrame):
    """Legacy two-camera strip — deprecated in Talk (r1286).

    Global chat now shows a single ActiveAwarenessMirrorWidget bound to
    active_saccade_target.json. This dual strip remains for older embeds.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        size: tuple[int, int] = (240, 90),
        refresh_ms: int = 500,
        hide_when_all_stale: bool = False,
    ) -> None:
        super().__init__(parent)
        self._hide_when_all_stale = bool(hide_when_all_stale)
        self._canvases: list[_MirrorCanvas] = []
        self._topology_tick = 0
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "border: 1px solid #1e2a44; border-radius: 4px; background: #000000;"
        )
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)
        for i in range(2):
            canvas = _MirrorCanvas(self, label=f"Camera {i + 1}")
            self._canvases.append(canvas)
            self._lay.addWidget(canvas)
        self.set_compact_size(size)
        self._refresh_sources()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(refresh_ms))
        self._sync_visibility(self._tick_frames())

    def set_compact_size(self, size: tuple[int, int]) -> None:
        width = max(160, int(size[0]))
        height = max(72, int(size[1]))
        self.setFixedSize(width, height)
        tile_w = max(76, (width - 4) // 2)
        for canvas in self._canvases:
            canvas.setFixedSize(tile_w, height)

    def _refresh_sources(self) -> None:
        devices = _dual_camera_devices()[:2]
        for i, canvas in enumerate(self._canvases):
            if i < len(devices):
                dev = devices[i]
                canvas.set_source(_frame_source_for_device(dev), _camera_tile_label(dev, i))
            else:
                missing = _REPO / ".sifta_state" / "owner_body_vision_frames" / "missing_camera_slot.png"
                canvas.set_source(missing, f"Camera {i + 1}")

    def _tick_frames(self) -> bool:
        fresh_any = False
        for canvas in self._canvases:
            fresh_any = bool(canvas.update_frame_from_disk()) or fresh_any
        return fresh_any

    def _tick(self) -> None:
        self._topology_tick += 1
        if self._topology_tick % 10 == 0:
            self._refresh_sources()
        self._sync_visibility(self._tick_frames())

    def _sync_visibility(self, fresh_any: bool) -> None:
        if self._hide_when_all_stale:
            self.setVisible(bool(fresh_any))
        else:
            self.setVisible(True)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = AwarenessMirrorApp()
    w.resize(720, 520)
    w.setWindowTitle("Awareness Mirror — Alice is watching")
    w.show()
    sys.exit(app.exec())
