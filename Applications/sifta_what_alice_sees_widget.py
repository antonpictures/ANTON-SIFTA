#!/usr/bin/env python3
"""
sifta_what_alice_sees_widget.py — What Alice Sees (live photon stigmergy)
══════════════════════════════════════════════════════════════════════════
A faithful mirror of the swarm's perceptual front end. Open it and you SEE
the math the swarm is doing on the photons coming out of your camera, with
your own eyes:

  • live camera frames Alice is processing right now (Qt's ffmpeg-backed
    QCamera; never any synthetic fallback — we say so plainly if the camera
    is missing or TCC blocks us);
  • a per-frame sha-8 anchor that ticks every frame → proof real photons,
    not the mock-source bug class we squashed on 2026-04-19;
  • the SWARM'S OWN STIGMERGIC MATH on each frame, computed live in numpy:
        — Shannon entropy of the grayscale histogram (bits)
        — 8×8 spatial saliency map (center-surround on luminance, the
          simplest honest version of Itti & Koch 1998)
        — 8×8 motion magnitude grid (per-cell mean absolute pixel delta
          frame-to-frame)
        — global motion energy + dominant hue centroid
    A compact summary is appended at a low-stress cadence (1 Hz by default) to
    `.sifta_state/visual_stigmergy.jsonl` — a real photon-derived
    stigmergic trail any other swimmer can react to;
  • the saliency map is drawn ON TOP of the frame as semi-transparent
    cells (green→amber→red) so high-saliency regions are immediately
    visible. Honestly labeled. No bounding boxes pretending to be
    semantic detections — these are raw center-surround responses;
  • the events the rest of the swarm is committing to its ledgers in
    response, color-coded in the side panel:
        🗣️  ALICE  — Broca vocalizations  (broca_vocalizations.jsonl)
        👂  HEARS  — Wernicke perceptions (wernicke_semantics.jsonl)
        ✨  FUSE   — Crossmodal proto-objects (crossmodal_pheromones.jsonl)
        🩸  PAIN   — Anomaly pheromones (swarm_pain.jsonl)
        🔊  SOUND  — Acoustic gradients (acoustic_pheromones.jsonl)
        👁  PHOTON — This widget's own visual stigmergy (visual_stigmergy.jsonl)

Honesty notes (C47H discipline — do not lie with overlays):
  • Saliency is **center-surround on luminance**, NOT semantic detection.
    A bright doorway behind you will pop; a stationary face won't (until
    it moves). When the swarm gains a real visual classifier the overlay
    becomes the natural place for bounding boxes.
  • Motion is **raw pixel delta**, not optical flow. It can't tell you
    direction, only magnitude.
  • Entropy is computed on the actual displayed frame's grayscale
    histogram — high entropy means visual complexity, low entropy means
    a uniform field.
  • If the camera fails or macOS denies TCC, the canvas says so in plain
    English. There is no silent fallback to a synthetic test pattern.

Dependencies: PyQt6 + numpy. PyQt6 ships an ffmpeg-backed QCamera that
handles AVFoundation directly; we never spawn ffmpeg ourselves here.
"""
from __future__ import annotations

"""SIFTA What Alice Sees Widget — stigmergic organ for Alice body."""

import hashlib
import json
import math
import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_DEVICE_EVENTS_LOG = _REPO / ".sifta_state" / "device_events.jsonl"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QSize, QTimer, pyqtSignal,
    QByteArray, QBuffer, QIODevice, QThread,
)
from PyQt6.QtGui import (
    QColor, QFont, QImage, QPainter, QPen, QBrush, QFontMetrics,
)
from PyQt6.QtMultimedia import (
    QCamera, QCameraDevice, QMediaCaptureSession, QMediaDevices, QVideoSink,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QSlider, QSplitter, QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.ledger_append import append_ledger_line
from System.swarm_camera_frame_paths import (
    active_eye_frame_path,
    camera_device_frame_index_path,
    device_eye_frame_path,
    root_active_eye_frame_path,
)
from System.swarm_visual_acuity_budget import (
    configured_default_acuity,
    configured_max_acuity,
    build_visual_acuity_budget,
)

_REPAIR_LEDGER = _REPO / "repair_log.jsonl"

# ── Photon-derived stigmergic ledger ─────────────────────────────────────────
_VISUAL_STIGMERGY_LOG = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"
_VISUAL_STIGMERGY_LOG.parent.mkdir(parents=True, exist_ok=True)
_VISUAL_LEDGER_GUARD_LAST_TS = 0.0
_VISUAL_LEDGER_GUARD_PERIOD_S = 10.0
_VISUAL_LEDGER_MAX_BYTES = 64 * 1024 * 1024
_VISUAL_LEDGER_KEEP_BYTES = 8 * 1024 * 1024
_LAST_KERNEL_VISION_HEARTBEAT_TS = 0.0

# Saliency / motion grid resolution. These serve as the default; the live
# slider overrides them per-session. Each cell is fed by an 8x8 source patch.
# Slider bounds: architect can drag between 4x4 (very coarse, fast) and 64x64
# by default. The max is env-bounded by SIFTA_ALICE_EYE_MAX_ACUITY.
_GRID_MIN = 4
_GRID_MAX = configured_max_acuity()
_GRID_W = configured_default_acuity()
_GRID_H = _GRID_W
_THUMB_W = _GRID_W * 8
_THUMB_H = _GRID_H * 8


def _env_float(name: str, default: float, *, lo: float, hi: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)) or default)
    except Exception:
        value = default
    return max(lo, min(hi, value))


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.environ.get(name, default)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


# The camera can emit ~30 frames/sec. Alice does not need to hash, grid,
# ledger-write, and kernel-heartbeat every visible frame while George is idle.
# Default to one real visual sample per second; developers can opt in higher.
_EYE_FRAME_PERIOD_S = _env_float("SIFTA_EYE_FRAME_PERIOD_S", 1.0, lo=0.1, hi=5.0)
_KERNEL_VISION_HEARTBEAT_PERIOD_S = _env_float(
    "SIFTA_KERNEL_VISION_HEARTBEAT_PERIOD_S", 5.0, lo=1.0, hi=60.0
)
_EYE_BOOT_OFF = _env_flag("SIFTA_EYE_BOOT_OFF", "0")
_APP_FOCUS_LEDGER = _REPO / ".sifta_state" / "app_focus.jsonl"
_APP_FOCUS_CACHE_LOCK = threading.Lock()
_APP_FOCUS_CACHE_TS = 0.0
_APP_FOCUS_CACHE_VALUE = ""


# ── Camera selection (mirrors Alice CLI's prefer/avoid posture) ──────────────
_VIDEO_AVOID = ("obs virtual camera", "screen capture", "desk view",
                "passthrough", "obs camera", "iphone")
_VIDEO_PREFER = ("macbook pro camera", "facetime hd camera", "logitech",
                 "usb camera")


def _camera_priority_score(description: str) -> int:
    """Built-in owner eye is primary; detachable USB is a secondary body eye."""
    desc = str(description or "").lower()
    if any(tok in desc for tok in ("macbook pro camera", "facetime hd camera", "built-in", "built in")):
        return 0
    if any(tok in desc for tok in ("logitech", "usb camera", "vid:1133")):
        return 1
    if any(tok in desc for tok in _VIDEO_AVOID):
        return 3
    return 2


def _is_secondary_world_eye(description: str) -> bool:
    """True only for the detachable USB/Logitech world eye.

    This secondary writer is intentionally narrower than the visible camera
    ranker: it must never wake OBS, iPhone, Continuity, or Desk View just to
    feed the small dual mirror tile.
    """
    desc = str(description or "").lower()
    if any(tok in desc for tok in ("iphone", "ipad", "continuity", "desk view")):
        return False
    if any(tok in desc for tok in ("obs", "virtual", "screen capture", "passthrough")):
        return False
    return "vid:1133" in desc and "pid:2081" in desc


def _rank_cameras(devs: List[QCameraDevice]) -> List[QCameraDevice]:
    """
    Order: MacBook owner eye first, USB Logitech world eye second.
    Same strict allowlist as ``swarm_camera_target._filter_body_cameras``.
    """
    try:
        from System.swarm_camera_target import is_allowed_owner_body_camera
    except Exception:
        is_allowed_owner_body_camera = lambda _name: True  # type: ignore[assignment,misc]
    body_devs: List[QCameraDevice] = []
    seen_names: set[str] = set()
    for d in devs:
        desc = str(d.description() or "").strip()
        if not is_allowed_owner_body_camera(desc):
            continue
        name_key = " ".join(desc.casefold().split())
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        body_devs.append(d)
    return [
        d for _original_index, d in sorted(
            enumerate(body_devs),
            key=lambda item: (_camera_priority_score(item[1].description()), item[0]),
        )
    ]


def _short_camera_label(name: str, uid: str = "") -> str:
    """Human-readable label for the active eye badge."""
    text = str(name or "").strip()
    token = f"{text} {uid}".lower()
    if not text:
        return "—"
    if text == "(Eye Closed - Off)" or uid == "OFF":
        return "Closed"
    if "facetime" in token or "macbook" in token or "built-in" in token:
        return "MacBook Pro"
    if "logitech" in token or "logit" in token or ("usb camera" in token and "vid:1133" in token):
        return "Logitech USB"
    if "iphone" in token:
        return "iPhone"
    if "obs" in token:
        return "OBS Virtual"
    return text[:18]


# ── Ledger writer for our own photon-derived stigmergy ──────────────────────
def _maybe_rotate_visual_stigmergy(now: float) -> None:
    global _VISUAL_LEDGER_GUARD_LAST_TS
    if now - _VISUAL_LEDGER_GUARD_LAST_TS < _VISUAL_LEDGER_GUARD_PERIOD_S:
        return
    _VISUAL_LEDGER_GUARD_LAST_TS = now
    try:
        if _VISUAL_STIGMERGY_LOG.stat().st_size <= _VISUAL_LEDGER_MAX_BYTES:
            return
        from System.swarm_ledger_rotation import fast_rotate_ledger_by_bytes

        fast_rotate_ledger_by_bytes(
            "visual_stigmergy.jsonl",
            max_bytes=_VISUAL_LEDGER_MAX_BYTES,
            keep_bytes=_VISUAL_LEDGER_KEEP_BYTES,
        )
    except OSError:
        return
    except Exception:
        return


def _write_visual_stigmergy(ph: "PhotonStigmergy") -> None:
    """Append one compact JSONL row. Throttled by the canvas.

    Compact on purpose; this runs on the Qt video-frame path.
    """
    try:
        _maybe_rotate_visual_stigmergy(ph.ts)
        app_focus = _cached_app_focus(max_age_s=30.0) or ""
        with _VISUAL_STIGMERGY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": ph.ts,
                "sha8": ph.sha8,
                "w": ph.width,
                "h": ph.height,
                "entropy_bits": round(ph.entropy_bits, 3),
                "saliency_peak": round(ph.saliency_peak, 3),
                "motion_mean": round(ph.motion_mean, 3),
                "hue_deg": round(ph.hue_centroid_deg, 1),
                "saliency_q": _quantize_grid_hex(ph.saliency_grid),
                "motion_q": _quantize_grid_hex(ph.motion_grid),
                "grid_size": ph.grid_size,
                "total_cells": ph.total_cells,
                "source_thumb_px": ph.source_thumb_px,
                "visual_swimmer_budget": ph.visual_swimmer_budget,
                "active_app_focus": app_focus,
            }, separators=(",", ":")) + "\n")
    except OSError:
        pass
    _heartbeat_kernel_vision(ph)


def _read_last_jsonl_dict(path: Path, *, max_bytes: int = 65536) -> Optional[dict]:
    """Read only the tail of a JSONL ledger and return the last valid row."""
    try:
        size = path.stat().st_size
    except OSError:
        return None
    try:
        with path.open("rb") as f:
            f.seek(max(0, size - max_bytes))
            data = f.read()
    except OSError:
        return None
    for raw in reversed(data.splitlines()):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return None


def _cached_app_focus(*, max_age_s: float, refresh_s: float = 10.0) -> str:
    """Cheap focus context for the camera frame path.

    The full `swarm_app_focus.get_focus_context()` can rank history and parse
    more ledger data. That belongs before a cortex turn, not inside
    `QVideoSink.videoFrameChanged`.
    """
    global _APP_FOCUS_CACHE_TS, _APP_FOCUS_CACHE_VALUE
    now = time.time()
    with _APP_FOCUS_CACHE_LOCK:
        if now - _APP_FOCUS_CACHE_TS < refresh_s:
            return _APP_FOCUS_CACHE_VALUE
        _APP_FOCUS_CACHE_TS = now
        _APP_FOCUS_CACHE_VALUE = ""
        row = _read_last_jsonl_dict(_APP_FOCUS_LEDGER)
        if not row:
            return ""
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts and now - ts > max_age_s:
            return ""
        pieces = []
        for key in ("app", "tab", "selection", "detail"):
            value = str(row.get(key) or "").strip()
            if value:
                pieces.append(value[:80])
        _APP_FOCUS_CACHE_VALUE = " | ".join(pieces)[:240]
        return _APP_FOCUS_CACHE_VALUE


def _heartbeat_kernel_vision(ph: "PhotonStigmergy") -> None:
    """Throttle E35/Vision heartbeats so signing never runs at frame speed."""
    global _LAST_KERNEL_VISION_HEARTBEAT_TS
    now = time.time()
    if now - _LAST_KERNEL_VISION_HEARTBEAT_TS < _KERNEL_VISION_HEARTBEAT_PERIOD_S:
        return
    _LAST_KERNEL_VISION_HEARTBEAT_TS = now
    try:
        from System.swarm_kernel_process_table import KernelProcessTable, OrganProcess

        table = KernelProcessTable(state_root=_REPO / ".sifta_state")
        table.ensure_registered(
            OrganProcess(
                pid="e35_vision_001",
                organ_id="organs/vision/e35",
                ring=1,
                health=1.0,
                stgm_balance=0.0,
                current_job="vision_bootstrap",
                last_receipt_id="",
                failure_count=0,
                last_heartbeat_ts=now,
                location="desk",
                bodies_present=["alice_eye"],
                metadata={"source": "visual_stigmergy", "os_body": "sifta_os_desktop"},
            ),
            receipt_id=f"e35_vision_register:{ph.sha8}",
        )
        table.heartbeat(
            "e35_vision_001",
            health=1.0 if ph.width > 0 and ph.height > 0 else 0.75,
            stgm_delta=0.003,
            current_job=f"vision_frame:{ph.sha8}",
            location="desk",
            bodies_present=["alice_eye"],
            receipt_id=f"e35_vision_heartbeat:{ph.sha8}",
            metadata={
                "frame_sha8": ph.sha8,
                "entropy_bits": f"{ph.entropy_bits:.3f}",
                "motion_mean": f"{ph.motion_mean:.3f}",
                "saliency_peak": f"{ph.saliency_peak:.3f}",
            },
        )
    except Exception:
        pass


# ── Lightweight in-memory JSONL tailer (no disk watermark) ───────────────────
@dataclass
class _LedgerSpec:
    path: Path
    label: str       # "ALICE" / "HEARS" / "FUSE" / "PAIN" / "SOUND"
    color: QColor    # color used in the side panel
    icon: str        # emoji prefix for the side panel


class _LedgerTail:
    """
    Per-ledger tailer that starts at end-of-file and only emits rows appended
    *after* widget startup. Rotation-safe (resets to 0 if file shrank).
    Keeps no on-disk state — we want a fresh "live now" view every session.
    """

    def __init__(self, spec: _LedgerSpec) -> None:
        self.spec = spec
        self._inode = -1
        self._size = self._initial_size()
        # Capture starting inode if the file already exists.
        if spec.path.exists():
            try:
                self._inode = spec.path.stat().st_ino
            except OSError:
                pass

    def _initial_size(self) -> int:
        try:
            return self.spec.path.stat().st_size if self.spec.path.exists() else 0
        except OSError:
            return 0

    def read_new(self, max_rows: int = 50) -> List[Dict]:
        if not self.spec.path.exists():
            return []
        try:
            stat = self.spec.path.stat()
        except OSError:
            return []
        # Rotation / truncation: rewind.
        if stat.st_ino != self._inode or stat.st_size < self._size:
            self._inode = stat.st_ino
            self._size = 0
        if stat.st_size == self._size:
            return []
        rows: List[Dict] = []
        try:
            with self.spec.path.open("r", encoding="utf-8") as f:
                f.seek(self._size)
                for _ in range(max_rows):
                    line = f.readline()
                    if not line or not line.endswith("\n"):
                        break
                    self._size = f.tell()
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        row = json.loads(s)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
        except OSError:
            return rows
        return rows


# ── Per-row formatter (honest projections of each ledger's schema) ───────────
def _format_row(label: str, row: Dict) -> Optional[str]:
    """One short human line per ledger row, or None to skip it."""
    if label == "ALICE":
        # broca_vocalizations.jsonl — {"spoken": "...", "ok": true}
        spoken = row.get("spoken") or row.get("spoken_text")
        if spoken:
            return spoken
        return None
    if label == "HEARS":
        # wernicke_semantics.jsonl — {"text": "...", "rms": 0.5, ...}
        txt = row.get("text") or row.get("transcript") or row.get("label")
        if txt:
            rms = row.get("rms")
            return f"{txt}" + (f"  (rms {rms:.2f})" if isinstance(rms, (int, float)) else "")
        return None
    if label == "FUSE":
        # crossmodal_pheromones.jsonl — {"object_id": "...", "sources":[...], "coherence": 0.2}
        oid = row.get("object_id", "")[:8]
        srcs = "+".join(row.get("sources") or [])
        coh = row.get("coherence", 0.0)
        if oid and srcs:
            return f"bound {srcs} → coherence {coh:.2f}  [{oid}]"
        return None
    if label == "PAIN":
        # swarm_pain.jsonl — varies, look for kind/magnitude
        kind = row.get("kind") or row.get("type") or "anomaly"
        mag = row.get("magnitude")
        if isinstance(mag, (int, float)):
            return f"{kind}  (mag {mag:.2f})"
        return f"{kind}"
    if label == "SOUND":
        # acoustic_pheromones.jsonl — {"source_id":..., "energy": float}
        src = row.get("source_id") or row.get("source") or "?"
        e = row.get("energy")
        if isinstance(e, (int, float)):
            return f"{src}  energy={e:.2f}"
        return None
    if label == "PHOTON":
        # visual_stigmergy.jsonl — written by THIS widget; show the math compactly.
        ent = row.get("entropy_bits")
        sal = row.get("saliency_peak")
        mot = row.get("motion_mean")
        hue = row.get("hue_deg")
        app_focus = row.get("active_app_focus", "")
        focus_str = f" | FOC={app_focus[:20]}..." if app_focus else ""
        if ent is None and sal is None and mot is None:
            return None
        return (
            f"H={ent:.2f}b  sal={sal:.2f}  mot={mot:.3f}  hue={hue:.0f}°{focus_str}"
            if all(isinstance(v, (int, float)) for v in (ent, sal, mot, hue))
            else None
        )
    if label == "FACE":
        # face_detection_events.jsonl — canonical Vision.framework face organ.
        audience = row.get("audience") or "unknown"
        faces = row.get("faces_detected", 0)
        conf = row.get("confidence", 0.0)
        err = row.get("error")
        if err:
            return f"{audience}  faces={faces}  error={str(err)[:44]}"
        if isinstance(conf, (int, float)):
            return f"{audience}  faces={faces}  conf={conf:.2f}"
        return f"{audience}  faces={faces}"
    return None


# ── Photon-derived stigmergic math (per-frame, numpy) ────────────────────────
@dataclass
class PhotonStigmergy:
    """One frame's worth of honest photon-derived math.

    All grids are shape (_GRID_H, _GRID_W) float32 in [0..1].
    """
    ts: float
    sha8: str
    width: int
    height: int
    entropy_bits: float          # Shannon entropy of grayscale hist, [0..8]
    saliency_grid: np.ndarray    # center-surround on luminance, normalized
    motion_grid: np.ndarray      # per-cell mean abs frame-to-frame delta
    saliency_peak: float         # max raw saliency BEFORE normalization, [0..1]
    motion_mean: float           # mean of motion grid, [0..1]
    hue_centroid_deg: float      # circular-mean dominant hue, [0..360)
    grid_size: int
    total_cells: int
    source_thumb_px: int
    visual_swimmer_budget: int


def _quantize_grid_hex(g: np.ndarray) -> str:
    """Pack an N×N grid in [0..1] into a hex string (1 nybble per cell).

    Lossy by design — keeps ledger rows compact so we don't
    burn the SSD just to remember what the camera saw five seconds ago.
    For the default 16×16 grid this is 256 hex chars (~128 bytes).
    """
    q = np.clip((g * 15.0 + 0.5).astype(np.int32), 0, 15).ravel()
    return "".join(f"{int(v):x}" for v in q)


class _PhotonMath:
    """Per-frame stigmergic math computed on the actual displayed photons.

    All computation runs on a 128×128 grayscale thumbnail (numpy uint8),
    so the whole pipeline costs well under 2 ms on an M5. Grid resolution
    is dynamically adjustable via set_density() without restart.
    """

    def __init__(self, grid_w: int = _GRID_W, grid_h: int = _GRID_H,
                 thumb_w: int = _THUMB_W, thumb_h: int = _THUMB_H) -> None:
        self._prev_lum: Optional[np.ndarray] = None
        self._grid_w = grid_w
        self._grid_h = grid_h
        self._thumb_w = thumb_w
        self._thumb_h = thumb_h
        self._cell_w = thumb_w // grid_w
        self._cell_h = thumb_h // grid_h
        self._budget = build_visual_acuity_budget(grid_w)

    # ── Live density adjustment (wired to the toolbar slider) ────────────
    def set_density(self, grid_size: int) -> None:
        """Reconfigure grid resolution. grid_size is used for both W and H.
        Thumbnail is always 8× the grid so each cell has 8×8 source pixels.
        """
        budget = build_visual_acuity_budget(grid_size, max_acuity=_GRID_MAX)
        self._budget = budget
        self._grid_w = budget.grid_size
        self._grid_h = budget.grid_size
        self._thumb_w = budget.source_thumb_px
        self._thumb_h = budget.source_thumb_px
        self._cell_w = budget.source_pixels_per_cell
        self._cell_h = budget.source_pixels_per_cell
        # Invalidate previous luminance frame (shape changed)
        self._prev_lum = None

    @property
    def grid_w(self) -> int:
        return self._grid_w

    @property
    def grid_h(self) -> int:
        return self._grid_h

    def compute(self, img: QImage) -> Optional[PhotonStigmergy]:
        ts = time.time()
        w, h = img.width(), img.height()

        # Hash the source frame bytes (real-photon proof; same discipline
        # swarm_iris uses).
        try:
            ptr = img.constBits()
            ptr.setsize(img.sizeInBytes())
            sha8 = hashlib.sha256(bytes(ptr)).hexdigest()[:8]
        except Exception:
            sha8 = "—"

        # Square thumbnail keeps the cell math symmetric (we accept the mild
        # aspect distortion — saliency / motion are scalar fields, not boxes).
        tw, th = self._thumb_w, self._thumb_h
        thumb = img.scaled(tw, th,
                           Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)

        # Grayscale view (handle Qt's bytesPerLine padding).
        gray = thumb.convertToFormat(QImage.Format.Format_Grayscale8)
        bpl = gray.bytesPerLine()
        gptr = gray.constBits()
        gptr.setsize(gray.sizeInBytes())
        try:
            arr = (np.frombuffer(bytes(gptr), dtype=np.uint8)
                     .reshape((th, bpl))[:, :tw]).copy()
        except Exception:
            return None

        # Shannon entropy of the grayscale histogram, in bits ([0..8]).
        hist = np.bincount(arr.ravel(), minlength=256).astype(np.float64)
        total = hist.sum()
        if total > 0:
            p = hist[hist > 0] / total
            entropy = float(-(p * np.log2(p)).sum())
        else:
            entropy = 0.0

        # N×N cell means via reshape→mean (no loops, no allocs of any size).
        gw, gh = self._grid_w, self._grid_h
        cw, ch = self._cell_w, self._cell_h
        cells = arr.reshape(gh, ch, gw, cw).mean(axis=(1, 3))

        # Spatial saliency: |cell − mean(8 neighbors)|. Edge-pad so border
        # cells get a real neighborhood instead of reflecting themselves.
        padded = np.pad(cells, 1, mode="edge")
        neighbor_sum = (
            padded[0:-2, 0:-2] + padded[0:-2, 1:-1] + padded[0:-2, 2:] +
            padded[1:-1, 0:-2]                      + padded[1:-1, 2:] +
            padded[2:,   0:-2] + padded[2:,   1:-1] + padded[2:,   2:]
        )
        sal_raw = np.abs(cells - neighbor_sum / 8.0)
        peak = float(sal_raw.max())
        if peak > 1e-6:
            saliency_grid = (sal_raw / peak).astype(np.float32)
        else:
            saliency_grid = np.zeros_like(sal_raw, dtype=np.float32)

        # Per-cell motion magnitude (mean abs delta of luminance vs prev frame).
        if self._prev_lum is not None and self._prev_lum.shape == arr.shape:
            diff = np.abs(arr.astype(np.int16) - self._prev_lum.astype(np.int16))
            motion_cells = diff.reshape(gh, ch, gw, cw).mean(axis=(1, 3))
            motion_grid = (motion_cells / 255.0).astype(np.float32)
        else:
            motion_grid = np.zeros((gh, gw), dtype=np.float32)
        self._prev_lum = arr

        # Hue centroid via circular mean (so 359° + 1° → 0°, not 180°).
        rgb = thumb.convertToFormat(QImage.Format.Format_RGB888)
        rbpl = rgb.bytesPerLine()
        rptr = rgb.constBits()
        rptr.setsize(rgb.sizeInBytes())
        try:
            rgb_arr = (np.frombuffer(bytes(rptr), dtype=np.uint8)
                         .reshape((th, rbpl))[:, : tw * 3]
                         .reshape((th, tw, 3)))
        except Exception:
            rgb_arr = None
        centroid = 0.0
        if rgb_arr is not None:
            r = rgb_arr[..., 0].astype(np.float32) / 255.0
            g = rgb_arr[..., 1].astype(np.float32) / 255.0
            b = rgb_arr[..., 2].astype(np.float32) / 255.0
            mx = np.maximum(np.maximum(r, g), b)
            mn = np.minimum(np.minimum(r, g), b)
            delta = mx - mn
            mask = delta > 1e-3
            with np.errstate(divide="ignore", invalid="ignore"):
                safe_d = np.where(delta == 0, 1.0, delta)
                hue_r = ((g - b) / safe_d) % 6.0
                hue_g = ((b - r) / safe_d) + 2.0
                hue_b = ((r - g) / safe_d) + 4.0
            hue = np.zeros_like(mx)
            is_r = mask & (mx == r)
            is_g = mask & (mx == g) & ~is_r
            is_b = mask & (mx == b) & ~is_r & ~is_g
            hue = np.where(is_r, hue_r, hue)
            hue = np.where(is_g, hue_g, hue)
            hue = np.where(is_b, hue_b, hue)
            rad = np.deg2rad(hue[mask] * 60.0)
            if rad.size > 0:
                cs = float(np.cos(rad).mean())
                sn = float(np.sin(rad).mean())
                centroid = (math.degrees(math.atan2(sn, cs)) + 360.0) % 360.0

        return PhotonStigmergy(
            ts=ts,
            sha8=sha8,
            width=w, height=h,
            entropy_bits=entropy,
            saliency_grid=saliency_grid,
            motion_grid=motion_grid,
            saliency_peak=peak / 255.0,
            motion_mean=float(motion_grid.mean()),
            hue_centroid_deg=centroid,
            grid_size=self._budget.grid_size,
            total_cells=self._budget.total_cells,
            source_thumb_px=self._budget.source_thumb_px,
            visual_swimmer_budget=self._budget.swimmer_budget,
        )


class _VisionBodyProbeWorker(QThread):
    """Background Ollama vision → owner_body_events (never blocks the UI thread)."""

    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, png_bytes: bytes, sha8: str) -> None:
        super().__init__()
        self._png = png_bytes
        self._sha8 = sha8

    def run(self) -> None:
        try:
            from System.swarm_owner_vision_body_bridge import (
                log_owner_body_from_vision_bytes,
            )

            model = os.environ.get("SIFTA_OWNER_VISION_MODEL", "").strip() or None
            out = log_owner_body_from_vision_bytes(
                self._png, self._sha8, model=model,
            )
            if out.get("ok"):
                self.done.emit(out)
            else:
                self.failed.emit(str(out.get("error", "unknown")))
        except Exception as e:
            self.failed.emit(str(e))


class _SecondaryDeviceFrameWriter:
    """Write fresh frames for a non-active body eye without changing active gaze."""

    _PERIOD_S = _env_float("SIFTA_SECONDARY_WORLD_EYE_FRAME_PERIOD_S", 1.0, lo=0.2, hi=10.0)

    def __init__(
        self,
        device_label: str,
        unique_id: str,
        *,
        on_frame_saved: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self._device_label = str(device_label or "").strip()
        self._unique_id = str(unique_id or "").strip()
        self._last_save_ts = 0.0
        self._on_frame_saved = on_frame_saved

    def on_video_frame(self, frame) -> None:  # type: ignore[no-untyped-def]
        now = time.time()
        if now - self._last_save_ts < self._PERIOD_S:
            return
        if not frame.isValid():
            return
        try:
            img = frame.toImage()
        except Exception:
            return
        if img is None or img.isNull():
            return
        img = img.convertToFormat(QImage.Format.Format_RGB32)
        path = device_eye_frame_path(self._device_label, self._unique_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not img.save(str(path), "PNG"):
                return
            self._last_save_ts = now
            with camera_device_frame_index_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": now,
                    "event": "CAMERA_DEVICE_LATEST_FRAME_SECONDARY",
                    "path": str(path),
                    "device": self._device_label,
                    "unique_id": self._unique_id,
                    "w": int(img.width()),
                    "h": int(img.height()),
                    "writer": "what_alice_sees_secondary_world_eye",
                }, separators=(",", ":")) + "\n")
            if self._on_frame_saved is not None:
                try:
                    self._on_frame_saved(path)
                except Exception:
                    pass
        except Exception:
            return


# ── The video canvas: paints frames + the HUD overlay ────────────────────────
class _VideoCanvas(QWidget):
    """
    Receives QVideoFrames from a QVideoSink, converts to QImage, and paints
    the frame plus the HUD on top. Falls back to a clearly-labeled "no
    signal" panel rather than ever pretending to show video.
    """

    HUD_FONT_PX = 11
    BOTTOM_FONT_PX = 14

    # Public signals (used by the parent widget to update titlebar status).
    frameReceived = pyqtSignal(int, int, str)  # width, height, sha8

    # Throttle: write at most one photon-stigmergy row per second by default
    # (the camera fires at ~30 fps; the swarm doesn't need every frame).
    _LEDGER_PERIOD_S = _EYE_FRAME_PERIOD_S
    # Don't paint a saliency cell unless it's at least this fraction of peak —
    # keeps the overlay quiet on flat scenes instead of strobing.
    _SAL_PAINT_THRESHOLD = 0.30

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: rgb(6,8,14);")
        self._image: Optional[QImage] = None
        self._last_sha8: str = "—"
        self._photon_math = _PhotonMath()
        self._photon: Optional[PhotonStigmergy] = None
        self._last_ledger_ts: float = 0.0
        self._device_label: str = "(no camera)"
        self._device_unique_id: str = ""
        self._fps_emit: float = 0.0
        self._frames_seen: int = 0
        self._fps_window_t0: float = time.time()
        self._fps_window_n: int = 0
        self._chyron_text: str = (
            "Alice's Eye is online. Awaiting first ledger event…"
        )
        self._chyron_color: QColor = QColor(180, 200, 240)
        self._error: Optional[str] = None
        self._show_overlay: bool = True   # toggled by the parent toolbar
        # Architect 2026-05-12 20:35 (reversal of 20:10): "BRING THE CAMERA
        # BACK AND PUT THE DOTS ON IT AND I TEACH YOU TO DESABLE IT LATER."
        # Boot default is now RAW VIDEO ON — the saliency dots are painted
        # on top of the live camera frame. He'll show me the right disable
        # path when he wants stigmergic-only mode.
        self._show_raw_video: bool = True
        # Ticker overlay: latest 3 ledger rows painted transparently ON the video
        self._ticker_lines: list = []    # list of (text_str, QColor) tuples, max 3
        self._show_ticker: bool = True
        # Wake-bus subscription: when Alice's name is heard, save a fresh
        # frame to disk and broadcast its path so the desktop can flash
        # one image. Owner directive: "ONE camera frame flashes when
        # 'Alice' is heard" — no streaming, no live video on the canvas.
        try:
            from System.swarm_wake_event_bus import wake_bus
            wake_bus().wake_fired.connect(self._on_wake_fired)
        except Exception:
            pass

    def _on_wake_fired(self, _row: dict) -> None:
        """Save the freshest in-memory frame as a wake-flash JPEG."""
        try:
            from pathlib import Path as _Path
            from System.swarm_wake_event_bus import wake_bus
            img = self._image
            if img is None or img.isNull():
                return
            out = _REPO / ".sifta_state" / "wake_flash_frame.jpg"
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(out), "JPEG", quality=82)
            wake_bus().frame_ready.emit(str(out))
        except Exception:
            pass

    # ── Public mutators (called by parent widget) ──────────────────────────
    def set_device_label(self, text: str, unique_id: str = "") -> None:
        self._device_label = text or "(no camera)"
        self._device_unique_id = str(unique_id or "").strip()
        self._error = None
        self._image = None
        self.update()

    def set_error(self, text: str) -> None:
        self._error = text
        self.update()

    def set_chyron(self, text: str, color: QColor) -> None:
        self._chyron_text = text
        self._chyron_color = color
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        self._show_overlay = visible
        self.update()

    def set_ticker_lines(self, lines: list) -> None:
        """Update the transparent ticker overlay. lines = list of (text, QColor)."""
        self._ticker_lines = lines[-3:]   # last 3 only
        self.update()

    def set_ticker_visible(self, visible: bool) -> None:
        self._show_ticker = bool(visible)
        self.update()

    def set_density(self, grid_size: int) -> None:
        """Forward the density slider value to the photon-math engine."""
        self._photon_math.set_density(grid_size)
        # Clear cached photon so the overlay picks up the new grid shape.
        self._photon = None

    def snapshot_png_bytes(self) -> Tuple[Optional[bytes], str]:
        """Copy last frame to PNG bytes + current sha8 anchor (main thread only)."""
        if self._image is None or self._image.isNull():
            return None, self._last_sha8
        img = QImage(self._image)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        if not img.save(buf, "PNG"):
            buf.close()
            return None, self._last_sha8
        buf.close()
        return bytes(ba), self._last_sha8

    # ── Frame ingest ───────────────────────────────────────────────────────
    def on_video_frame(self, frame) -> None:  # type: ignore[no-untyped-def]
        now = time.time()
        if now - self._last_ledger_ts < self._LEDGER_PERIOD_S:
            return

        if not frame.isValid():
            return
        try:
            img = frame.toImage()
        except Exception:
            return
        if img is None or img.isNull():
            return
        # Convert once to a known format so the photon math sees a stable layout.
        img = img.convertToFormat(QImage.Format.Format_RGB32)

        # Run all per-frame stigmergic math in one shot.
        ph = self._photon_math.compute(img)
        if ph is not None:
            self._photon = ph
            self._last_sha8 = ph.sha8
            self._last_ledger_ts = ph.ts
            _write_visual_stigmergy(ph)
            # Save last frame as JPEG every 30 s for Cosmos-Reason1 inference.
            # Zero cost on most ticks (30 s period vs 200 ms ledger period).
            _now = time.time()
            if _now - getattr(self, "_last_frame_save_ts", 0.0) >= 30.0:
                self._last_frame_save_ts = _now
                try:
                    _frame_path = _REPO / ".sifta_state" / "visual_stigmergy_last_frame.jpg"
                    img.save(str(_frame_path), "JPEG", quality=85)
                except Exception:
                    pass
            # Mirror tiles need fresh per-device PNGs (~1 Hz). Identity ledger rows
            # stay at the slower cadence so we do not spam receipts.
            if _EYE_FRAME_PERIOD_S > 0 and _now - getattr(self, "_last_mirror_frame_save_ts", 0.0) >= _EYE_FRAME_PERIOD_S:
                self._last_mirror_frame_save_ts = _now
                try:
                    _id_dir = active_eye_frame_path().parent
                    _id_dir.mkdir(parents=True, exist_ok=True)
                    _id_path = active_eye_frame_path()
                    img.save(str(_id_path), "PNG")
                    _device_path = device_eye_frame_path(
                        self._device_label,
                        self._device_unique_id,
                    )
                    _device_path.parent.mkdir(parents=True, exist_ok=True)
                    img.save(str(_device_path), "PNG")
                    try:
                        root_png = root_active_eye_frame_path()
                        img.save(str(root_png), "PNG")
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                _identity_period = float(
                    os.environ.get("SIFTA_EYE_IDENTITY_FRAME_PERIOD_S", "10") or "10"
                )
            except Exception:
                _identity_period = 10.0
            if _identity_period > 0 and _now - getattr(self, "_last_identity_frame_save_ts", 0.0) >= _identity_period:
                self._last_identity_frame_save_ts = _now
                try:
                    _id_path = active_eye_frame_path()
                    _device_path = device_eye_frame_path(
                        self._device_label,
                        self._device_unique_id,
                    )
                    with camera_device_frame_index_path().open("a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "ts": _now,
                            "event": "CAMERA_DEVICE_LATEST_FRAME",
                            "path": str(_device_path),
                            "active_path": str(_id_path),
                            "device": self._device_label,
                            "unique_id": self._device_unique_id,
                            "w": int(img.width()),
                            "h": int(img.height()),
                            "sha8": self._last_sha8,
                        }, separators=(",", ":")) + "\n")
                    with (_REPO / ".sifta_state" / "active_eye_identity_frames.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "ts": _now,
                            "event": "ACTIVE_EYE_IDENTITY_FRAME",
                            "path": str(_id_path),
                            "device_path": str(_device_path),
                            "device": self._device_label,
                            "unique_id": self._device_unique_id,
                            "w": int(img.width()),
                            "h": int(img.height()),
                            "sha8": self._last_sha8,
                        }, separators=(",", ":")) + "\n")
                except Exception:
                    pass

        # Measured FPS over a rolling 1-second window.
        self._fps_window_n += 1
        now = time.time()
        if now - self._fps_window_t0 >= 1.0:
            self._fps_emit = self._fps_window_n / (now - self._fps_window_t0)
            self._fps_window_t0 = now
            self._fps_window_n = 0

        self._image = img
        self._frames_seen += 1
        self.frameReceived.emit(img.width(), img.height(), self._last_sha8)
        self.update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = self.rect()
        p.fillRect(rect, QColor(6, 8, 14))

        if self._error:
            self._paint_message(p, self._error, QColor(247, 118, 142))
            return

        if self._image is None:
            self._paint_message(
                p,
                "Connecting to camera…\n\n"
                "If this hangs, macOS may be asking for Camera permission.\n"
                "Check System Settings → Privacy & Security → Camera.",
                QColor(150, 165, 200),
            )
            return

        # Draw the frame — raw or stigmergic-only.
        if self._show_raw_video:
            # Full raw camera frame (letterboxed, smooth scale)
            scaled = self._image.scaled(
                rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)
        else:
            # Stigmergic-only: skip the expensive scale+drawImage.
            # Use fast thumbnail scale just for photon math geometry.
            scaled = self._image.scaled(
                rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,  # cheaper
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            # Dark canvas in place of raw video
            p.fillRect(QRectF(x, y, scaled.width(), scaled.height()),
                       QColor(3, 5, 10))

        # ── Photon-stigmergy overlay drawn ON the video, inside frame rect ─
        if self._show_overlay and self._photon is not None:
            self._paint_saliency_overlay(
                p, QRectF(x, y, scaled.width(), scaled.height()),
                self._photon,
            )

        # ── HUD strips on top of everything ────────────────────────────────
        if hasattr(self, "_yield_lock_path"):
            self._paint_top_strip(p, rect)
            self._paint_math_line(p, rect)
            self._paint_bottom_strip(p, rect)
            self._paint_yield_overlay(p, rect)

    def _paint_yield_overlay(self, p: QPainter, rect: QRectF) -> None:
        if not self._yield_lock_path.exists():
            return
        p.fillRect(rect, QColor(0, 0, 0, 180))
        p.setPen(QColor(255, 50, 50))
        p.setFont(QFont("Menlo", 24, QFont.Weight.Bold))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "⚠️  YIELDING CAMERA\nTO SUBSTRATE CLOSURE")

    def _paint_ticker_overlay(self, p: QPainter, rect) -> None:
        """Paint last 3 ledger rows transparently on the camera frame.
        Position: bottom-right corner, above the chyron strip.
        Each row: dim dark pill + colored text.
        """
        f = QFont("Menlo", 10)
        fm = QFontMetrics(f)
        row_h = fm.height() + 4
        pad_x, pad_y = 10, 8
        chyron_h = 56  # leave room for bottom chyron
        n = len(self._ticker_lines)
        block_h = n * row_h + pad_y * 2
        # Position: bottom-right, above chyron
        bx = rect.x() + rect.width() - 460
        by = rect.y() + rect.height() - chyron_h - block_h - 4
        # Draw translucent background pill
        p.save()
        p.setOpacity(0.78)
        p.fillRect(QRectF(bx, by, 450, block_h), QColor(6, 8, 18, 195))
        p.setOpacity(1.0)
        p.setFont(f)
        for i, (text, color) in enumerate(self._ticker_lines):
            ty = by + pad_y + i * row_h
            p.setPen(color)
            p.drawText(QRectF(bx + pad_x, ty, 430, row_h),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                       text)
        p.restore()

    def _paint_message(self, p: QPainter, text: str, color: QColor) -> None:
        p.setPen(color)
        f = QFont("Menlo", 12)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_top_strip(self, p: QPainter, rect) -> None:  # type: ignore[no-untyped-def]
        h = 26
        bar = QRectF(rect.x(), rect.y(), rect.width(), h)
        p.fillRect(bar, QColor(0, 0, 0, 140))
        p.setPen(QColor(0, 255, 200))
        f = QFont("Menlo", self.HUD_FONT_PX, QFont.Weight.Bold)
        p.setFont(f)
        ts = time.strftime("%H:%M:%S", time.localtime())
        ms = int((time.time() % 1) * 1000)
        line = (
            f"{ts}.{ms:03d}   ●  {self._device_label}   "
            f"{self._image.width() if self._image else 0}×"
            f"{self._image.height() if self._image else 0}   "
            f"sha={self._last_sha8}   "
            f"fps={self._fps_emit:0.1f}   frames={self._frames_seen:,}"
        )
        p.drawText(QRectF(bar.x() + 10, bar.y(), bar.width() - 20, bar.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   line)

    def _paint_saliency_overlay(self, p: QPainter, frame_rect: QRectF,
                                 ph: PhotonStigmergy) -> None:
        """Draw the saliency grid as the **actual hex glyphs Alice writes to
        her ledger** — one base-16 char per cell, `0` = cold … `f` = hot.

        Architect 2026-05-12 22:35: "Instead of making up stuff why don't we
        look at what the system already processes and provides and just show
        that". The ledger row `visual_stigmergy.jsonl::saliency_q` IS already
        an ASCII map produced by `_quantize_grid_hex()` (1 nybble per cell).
        We render that exact map — no invented characters, no random
        arrays. What you see on screen IS what gets signed into the
        stigmergic ledger.

        Honest labeling: this is **center-surround on luminance**, not a
        semantic detector. Cells below `_SAL_PAINT_THRESHOLD` are blank so
        flat scenes stay quiet.
        """
        grid_h, grid_w = ph.saliency_grid.shape
        cell_w = frame_rect.width() / grid_w
        cell_h = frame_rect.height() / grid_h
        sal = ph.saliency_grid
        mot = ph.motion_grid

        # Size the glyph to the cell. Use the same per-cell font for every
        # draw call so QPainter doesn't have to re-resolve the font.
        glyph_px = max(7, int(min(cell_w, cell_h) * 0.78))
        font = QFont("Menlo", glyph_px, QFont.Weight.Bold)
        p.setFont(font)
        _HEX = "0123456789abcdef"

        for gy in range(grid_h):
            for gx in range(grid_w):
                s = float(sal[gy, gx])
                m = float(mot[gy, gx])
                score = max(s, m * 1.5)  # motion is small numerically; amplify
                if score < self._SAL_PAINT_THRESHOLD:
                    continue
                # Quantize *exactly* the way the ledger does — single
                # source of truth via _quantize_grid_hex's formula.
                nyb = max(0, min(15, int(score * 15.0 + 0.5)))
                glyph = _HEX[nyb]
                cx = frame_rect.x() + gx * cell_w
                cy = frame_rect.y() + gy * cell_h
                # Color by score: green (calm) → amber → red (hot).
                if score < 0.5:
                    c = QColor(0, 255, 200, int(170 + 60 * score))
                elif score < 0.75:
                    c = QColor(255, 200, 90, int(180 + 60 * score))
                else:
                    c = QColor(255, 90, 110, int(200 + 55 * score))
                p.setPen(c)
                p.drawText(
                    QRectF(cx, cy, cell_w, cell_h),
                    int(Qt.AlignmentFlag.AlignCenter),
                    glyph,
                )

    def _paint_math_line(self, p: QPainter, rect) -> None:  # type: ignore[no-untyped-def]
        """Second HUD line below the top strip: photon-derived math readout."""
        h = 22
        bar = QRectF(rect.x(), rect.y() + 26, rect.width(), h)
        p.fillRect(bar, QColor(0, 0, 0, 140))
        f = QFont("Menlo", self.HUD_FONT_PX, QFont.Weight.Bold)
        p.setFont(f)
        if self._photon is None:
            txt = "photon math: warming up…   →  .sifta_state/visual_stigmergy.jsonl"
            p.setPen(QColor(140, 150, 180))
        else:
            ph = self._photon
            txt = (
                f"entropy={ph.entropy_bits:5.2f} bits   "
                f"saliency_peak={ph.saliency_peak:0.2f}   "
                f"motion={ph.motion_mean:0.3f}   "
                f"hue={ph.hue_centroid_deg:5.1f}°   "
                f"→  visual_stigmergy.jsonl @ {1.0 / max(self._LEDGER_PERIOD_S, 1e-6):0.1f} Hz"
            )
            p.setPen(QColor(255, 200, 90))
        p.drawText(QRectF(bar.x() + 10, bar.y(), bar.width() - 20, bar.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   txt)

    def _paint_bottom_strip(self, p: QPainter, rect) -> None:  # type: ignore[no-untyped-def]
        # Latest chyron line — what Alice is currently saying / hearing.
        h = 56
        bar = QRectF(rect.x(), rect.y() + rect.height() - h, rect.width(), h)
        p.fillRect(bar, QColor(0, 0, 0, 160))
        f = QFont("Menlo", self.BOTTOM_FONT_PX, QFont.Weight.Bold)
        p.setFont(f)
        # Truncate to fit width
        fm = QFontMetrics(f)
        text = fm.elidedText(self._chyron_text, Qt.TextElideMode.ElideRight,
                             int(bar.width()) - 24)
        p.setPen(self._chyron_color)
        p.drawText(QRectF(bar.x() + 12, bar.y(), bar.width() - 24, bar.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   text)


# ── The widget proper ────────────────────────────────────────────────────────
class WhatAliceSeesWidget(SiftaBaseWidget):
    """Live mirror: shows Alice's webcam input + the swarm's stigmergy on it."""

    APP_NAME = "Predator. v7.0 | Let's Think Together!"

    def showEvent(self, event):
        super().showEvent(event)
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus(self.APP_NAME, "User is monitoring Alice's visual input")
        except Exception:
            pass

    # Color palette per ledger source — also drives bottom-strip color.
    _LEDGERS: List[Tuple[str, str, str, Tuple[int, int, int]]] = [
        # (ledger_filename, label, icon, rgb)
        ("broca_vocalizations.jsonl",  "ALICE", "🗣️", (0, 255, 200)),
        ("wernicke_semantics.jsonl",   "HEARS", "👂", (250, 220, 100)),
        ("crossmodal_pheromones.jsonl","FUSE",  "✨", (220, 130, 255)),
        ("swarm_pain.jsonl",           "PAIN",  "🩸", (255, 90, 110)),
        ("acoustic_pheromones.jsonl",  "SOUND", "🔊", (160, 175, 210)),
        ("visual_stigmergy.jsonl",     "PHOTON","👁",  (255, 200, 90)),
        ("face_detection_events.jsonl", "FACE", "🐾",  (0, 255, 180)),
    ]

    # Signal emitted from face-detect thread → received on main thread.
    # Carries (audience: str, chyron_text: str) — primitives only, no Qt objects.
    _face_result_ready = pyqtSignal(str, str)

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Top toolbar (camera selector only — buttons are on parent AliceWidget) ──
        bar = QHBoxLayout()

        self._cam_label = QLabel("📷")
        self._cam_label.hide()  # Predator mode: Alice switches cams autonomously
        bar.addWidget(self._cam_label)
        self._cam_combo = QComboBox()
        self._cam_combo.setMinimumWidth(280)
        self._cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        self._cam_combo.hide()  # Predator mode: no manual camera selection
        bar.addWidget(self._cam_combo, 1)
        # NOTE: hide photons / hide ticker buttons live on the parent AliceWidget.
        # Do NOT add duplicate buttons here.
        bar.addStretch()
        layout.addLayout(bar)

        import os as _os_dev
        _eye_dev_on = _os_dev.environ.get("SIFTA_EYE_DEV_CONTROLS", "0").strip() == "1"

        # ── Photon Density Slider (Architect 2026-04-20: "she sees big
        # pixels, too big — add a slider so I can increase or decrease
        # the photon/swimmers input density") ─────────────────────────────
        density_bar = QHBoxLayout()
        self._density_title_label = QLabel("🔬 acuity")
        self._density_title_label.setVisible(_eye_dev_on)
        density_bar.addWidget(self._density_title_label)
        self._density_label_lo = QLabel(f"{_GRID_MIN}×{_GRID_MIN}")
        self._density_label_lo.setStyleSheet("color: rgb(120,130,160); font-size: 11px;")
        self._density_label_lo.setVisible(_eye_dev_on)
        density_bar.addWidget(self._density_label_lo)

        self._density_slider = QSlider(Qt.Orientation.Horizontal)
        self._density_slider.setMinimum(_GRID_MIN)
        self._density_slider.setMaximum(_GRID_MAX)
        self._density_slider.setValue(_GRID_W)
        self._density_slider.setSingleStep(2)
        self._density_slider.setPageStep(4)
        self._density_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._density_slider.setTickInterval(4)
        self._density_slider.setMinimumWidth(200)
        self._density_slider.setToolTip(
            "Photon density: controls the resolution of Alice's saliency \n"
            "and motion grids. Higher = finer acuity, more photons per frame.\n"
            f"Range: {_GRID_MIN}×{_GRID_MIN} (coarse) → {_GRID_MAX}×{_GRID_MAX} (sharp)\n"
            f"Default: {_GRID_W}×{_GRID_W}; max sends {_GRID_MAX*_GRID_MAX} cells into the ledger"
        )
        self._density_slider.valueChanged.connect(self._on_density_changed)
        self._density_slider.setVisible(_eye_dev_on)
        density_bar.addWidget(self._density_slider, 1)

        self._density_value_label = QLabel(f"{_GRID_W}×{_GRID_H}")
        self._density_value_label.setStyleSheet(
            "color: rgb(0,255,200); font-weight: bold; font-size: 13px; "
            "min-width: 60px;"
        )
        self._density_value_label.setVisible(_eye_dev_on)
        density_bar.addWidget(self._density_value_label)

        self._density_label_hi = QLabel(f"{_GRID_MAX}×{_GRID_MAX}")
        self._density_label_hi.setStyleSheet("color: rgb(120,130,160); font-size: 11px;")
        self._density_label_hi.setVisible(_eye_dev_on)
        density_bar.addWidget(self._density_label_hi)

        # Photon count readout (how many cells × how many source pixels)
        self._photon_count_label = QLabel("")
        self._photon_count_label.setStyleSheet(
            "color: rgb(180,190,220); font-size: 11px; margin-left: 12px;"
        )
        self._photon_count_label.setVisible(_eye_dev_on)
        density_bar.addWidget(self._photon_count_label)
        self._update_photon_count_label(_GRID_W)

        # ── ACTIVE EYE badge — shows which camera Alice is currently routing ──
        # Prominent so the Architect can see at a glance which camera LED should
        # be lit. Updates every 1 s from swarm_camera_target (same source as
        # the saccade poller). Color: cyan = routing / gray = unknown.
        density_bar.addStretch()
        self._active_eye_label = QLabel("👁  —")
        self._active_eye_label.setStyleSheet(
            "color: rgb(0,230,255); font-weight: bold; font-size: 12px; "
            "padding: 2px 8px; border: 1px solid rgb(0,180,200); border-radius: 4px;"
        )
        self._active_eye_label.setToolTip(
            "Active camera eye — the camera whose LED is currently lit.\n"
            "Switches automatically via the sensorimotor attention director."
        )
        density_bar.addWidget(self._active_eye_label)
        self.make_timer(1000, self._refresh_active_eye_label)
        self._refresh_active_eye_label()

        layout.addLayout(density_bar)

        # Vision → owner_body_events: one Ollama vision probe, sha8-anchored.
        self._vision_body_worker: Optional[_VisionBodyProbeWorker] = None
        body_vis = QHBoxLayout()
        self._vision_body_btn = QPushButton("🦷 Log body_check (vision)")
        self._vision_body_btn.setToolTip(
            "Captures the current frame → local Ollama (vision) → one "
            "`body_check` row in owner_body_events.jsonl, stamped with the HUD "
            "sha8.\n"
            "Visible cues only — not a clinical diagnosis.\n"
            "Model: per_app owner_vision_body or env SIFTA_OWNER_VISION_MODEL."
        )
        self._vision_body_btn.clicked.connect(self._on_vision_body_probe_click)
        # Hidden by default — developer/diagnostic surface. Set
        # SIFTA_EYE_DEV_CONTROLS=1 to expose. Architect 2026-05-12.
        self._vision_body_btn.setVisible(_eye_dev_on)
        body_vis.addWidget(self._vision_body_btn)
        body_vis.addStretch()
        layout.addLayout(body_vis)

        # ── Video canvas (full width — ticker overlay is ON the canvas) ─────
        split = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = split

        self._canvas = _VideoCanvas()
        split.addWidget(self._canvas)

        # Legacy _events QPlainTextEdit kept hidden (for internal writes)
        # but the visual ticker is now an overlay on the canvas via set_ticker_lines().
        self._events = QPlainTextEdit()
        self._events.setReadOnly(True)
        self._events.setMaximumBlockCount(400)
        self._events.hide()           # hidden — ticker is painted on canvas
        # Do NOT add _events to the splitter — canvas is full-width.

        layout.addWidget(split, 1)

        # ── Camera + capture session (Qt's built-in ffmpeg backend) ────────
        # Qt/macOS can emit the same TCC denial on every frame tick — debounce
        # so the canvas is not spammed with identical "Access to camera not granted".
        self._last_camera_err_norm: str = ""
        self._last_camera_err_at: float = 0.0
        self._camera: Optional[QCamera] = None
        self._sink = QVideoSink(self)
        self._session = QMediaCaptureSession(self)
        self._session.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._canvas.on_video_frame)
        self._secondary_world_camera: Optional[QCamera] = None
        self._secondary_world_sink: Optional[QVideoSink] = None
        self._secondary_world_session: Optional[QMediaCaptureSession] = None
        self._secondary_world_writer: Optional[_SecondaryDeviceFrameWriter] = None
        self._secondary_world_signature: str = ""
        self._secondary_world_started_at: float = 0.0
        self._secondary_world_last_frame_ts: float = 0.0
        self._secondary_world_pulse_camera: Optional[QCamera] = None
        self._secondary_world_pulse_sink: Optional[QVideoSink] = None
        self._secondary_world_pulse_session: Optional[QMediaCaptureSession] = None
        self._secondary_world_pulse_writer: Optional[_SecondaryDeviceFrameWriter] = None
        self._secondary_world_pulse_active: bool = False
        self._secondary_world_pulse_timer = QTimer(self)
        self._secondary_world_pulse_timer.setInterval(
            int(_env_float("SIFTA_SECONDARY_WORLD_EYE_PULSE_PERIOD_S", 5.0, lo=2.0, hi=30.0) * 1000)
        )
        self._secondary_world_pulse_timer.timeout.connect(self._pulse_secondary_world_eye)

        # ── Hot-plug awareness ─────────────────────────────────────────────
        self._media_devs = QMediaDevices(self)
        self._media_devs.videoInputsChanged.connect(self._refresh_cameras)

        # ── Oculomotor/body identity state ─────────────────────────────────
        # These must exist before timers start or _refresh_cameras() selects
        # a camera. Qt can synchronously fire currentIndexChanged during first
        # selection, which calls _on_cam_changed() and reads this guard.
        self._root = _REPO
        self._saccade_target_json_path = (
            self._root / ".sifta_state" / "active_saccade_target.json"
        )
        # Legacy .txt watched only so we still re-poll when something old
        # touches it; canonical reader auto-heals it into JSON on next read.
        self._saccade_target_path = (
            self._root / ".sifta_state" / "active_saccade_target.txt"
        )
        self._yield_lock_path = self._root / ".sifta_state" / "camera_yield.lock"
        self._acuity_target_json_path = (
            self._root / ".sifta_state" / "active_visual_acuity.json"
        )
        self._last_saccade_signature: Optional[str] = None
        self._last_acuity_signature: Optional[str] = None
        self._applying_saccade_target: bool = False
        self._yielded = False

        # ── Pollers for external state ─────────────────────────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_saccade_target)
        self._poll_timer.timeout.connect(self._poll_acuity_target)
        self._poll_timer.timeout.connect(self._poll_camera_yield)
        try:
            from System.swarm_metabolism_governor import governed_interval_ms

            poll_ms = governed_interval_ms(800, organ_id="what_alice_sees_poll")
        except Exception:
            poll_ms = 800
        self._poll_timer.start(poll_ms)

        self._refresh_cameras()

        # ── Hot-plug memory: track which camera IDs we already know ──────────
        # Set is populated after first refresh, then diffed on every subsequent
        # videoInputsChanged signal so we can emit attach/detach events to Alice.
        self._known_camera_ids: set = {
            self._cam_combo.itemData(i)
            for i in range(self._cam_combo.count())
            if self._cam_combo.itemData(i) is not None
        }

        # ── Ledger tailers ─────────────────────────────────────────────────
        self._tails: List[Tuple[_LedgerTail, _LedgerSpec]] = []
        tail_self = os.environ.get("SIFTA_EYE_TAIL_SELF_LEDGER", "0").strip().lower() in (
            "1", "true", "yes", "on",
        )
        for fname, label, icon, (r, g, b) in self._LEDGERS:
            if fname == "visual_stigmergy.jsonl" and not tail_self:
                continue
            spec = _LedgerSpec(
                path=_REPO / ".sifta_state" / fname,
                label=label, color=QColor(r, g, b), icon=icon,
            )
            self._tails.append((_LedgerTail(spec), spec))

        # Recent-event ring used for the bottom chyron rotation.
        self._recent: Deque[Tuple[float, str, str, QColor]] = deque(maxlen=24)

        # Polling timers (parented to widget; stopped on close by base widget).
        self.make_timer(1000, self._poll_ledgers)
        self.make_timer(1000, self._cycle_chyron)

        # Frame-received → update title status.
        self._canvas.frameReceived.connect(self._on_frame_meta)

        # ── Motor Cortex LED-wink subscriber ────────────────────────────────
        # Tail .sifta_state/motor_pulses.jsonl and, whenever a pulse with
        # led_blink_ms > 0 arrives, briefly stop/start the QCamera so the
        # green hardware LED visibly winks at Alice's heart rate.
        self._motor_pulse_path = _REPO / ".sifta_state" / "motor_pulses.jsonl"
        self._motor_pulse_offset: int = 0
        try:
            if self._motor_pulse_path.exists():
                self._motor_pulse_offset = self._motor_pulse_path.stat().st_size
        except Exception:
            self._motor_pulse_offset = 0
        self._led_blinking: bool = False
        self.make_timer(250, self._poll_motor_pulses)

        # ── Stigmergic Face Detection — every 10s via canonical organ ───────
        # System.swarm_face_detection owns the Vision.framework schema and
        # writes face_detection_events.jsonl. Photon math stays in
        # visual_stigmergy.jsonl; never mix face rows into photon rows.
        # We call it in a daemon thread so it never blocks the UI.
        self._face_probe_running: bool = False
        self.make_timer(10_000, self._probe_face_detection)
        # Wire face-result signal → main-thread chyron update (NO Qt objects in thread)
        self._face_result_ready.connect(self._on_face_result)
        # First probe 3s after startup (let camera warm up first)
        QTimer.singleShot(3000, self._probe_face_detection)

        # ── Oculomotor Saccade target subscriber ───────────────────────────
        # 2026-04-23 C47H surgery: was reading `.txt` and doing
        # `findText(target, MatchContains)`, which substring-matched the "1"
        # inside "USB Camera VID:1133 PID:2081" and pinned the Logitech.
        # Now reads the canonical JSON target and resolves by
        # unique_id → name → index against the live combobox itemData/text.
        self.make_timer(500, self._poll_saccade_target)
        self.make_timer(500, self._poll_acuity_target)

    # ── Camera plumbing ────────────────────────────────────────────────────
    def _refresh_cameras(self) -> None:
        # Remember current selection (by id) so we don't yank the user mid-stream.
        current_id = None
        if self._cam_combo.count() > 0:
            current_id = self._cam_combo.currentData()

        ranked = _rank_cameras(QMediaDevices.videoInputs())

        # ── Hot-plug diff ────────────────────────────────────────────────────
        # Build new id→name map and compare against what we knew before.
        new_map: dict = {d.id(): d.description() for d in ranked}
        new_ids = set(new_map.keys())
        if hasattr(self, "_known_camera_ids"):  # not set on the very first call
            appeared = new_ids - self._known_camera_ids
            vanished = self._known_camera_ids - new_ids
            for dev_id in appeared:
                self._on_camera_hotplug("attached", new_map[dev_id])
            # For vanished devices we no longer have the name — look it up from
            # the combo box which still has the old entries at this point.
            old_names = {
                self._cam_combo.itemData(i): self._cam_combo.itemText(i)
                for i in range(self._cam_combo.count())
            }
            for dev_id in vanished:
                name = old_names.get(dev_id, "unknown camera")
                self._on_camera_hotplug("detached", name)
        self._known_camera_ids = new_ids
        # ── End hot-plug diff ────────────────────────────────────────────────

        ranked = _rank_cameras(QMediaDevices.videoInputs())
        self._cam_combo.blockSignals(True)
        self._cam_combo.clear()
        if not ranked:
            self._cam_combo.addItem("(no cameras detected — check macOS Camera permission)", None)
            self._cam_combo.blockSignals(False)
            self._stop_secondary_world_eye()
            err_text = (
                "No cameras detected.\n\n"
                "Open System Settings → Privacy & Security → Camera "
                "and enable Python (or your terminal app), then click ↻ refresh."
            )
            self._canvas.set_error(err_text)
            try:
                from System.ledger_append import append_jsonl_line
                append_jsonl_line(_REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl", {
                    "system": "what_alice_sees",
                    "event": "camera_error",
                    "reason": "open_failed: no_cameras_detected",
                    "ts": time.time()
                })
            except Exception:
                pass
            return
        
        # Keep an explicit OFF state for manual/yield cases, but do not make it
        # the boot default. AliceWidget's contract says the eye starts live
        # unless SIFTA_ALICE_UNIFIED_DEFER_EYE=1 or SIFTA_EYE_BOOT_OFF=1.
        self._cam_combo.addItem("(Eye Closed - Off)", "OFF")
        
        for d in ranked:
            self._cam_combo.addItem(d.description(), d.id())
        # Restore prior pick if still present, else default to the first real
        # ranked camera. If a broken host needs no camera at boot, set
        # SIFTA_EYE_BOOT_OFF=1 rather than silently closing the eye.
        restored = False
        if current_id is not None:
            pos = self._cam_combo.findData(current_id)
            if pos >= 0:
                self._cam_combo.setCurrentIndex(pos)
                restored = True
        self._cam_combo.blockSignals(False)
        if not restored:
            default_idx = 0 if _EYE_BOOT_OFF else min(1, self._cam_combo.count() - 1)
            self._cam_combo.setCurrentIndex(default_idx)
            self._on_cam_changed(default_idx)
        self._refresh_secondary_world_eye()

    def _stop_secondary_world_eye(self) -> None:
        if hasattr(self, "_secondary_world_pulse_timer"):
            self._secondary_world_pulse_timer.stop()
        self._finish_secondary_world_pulse("secondary_world_eye_stop", restart_primary=False)
        camera = self._secondary_world_camera
        self._secondary_world_camera = None
        sink = self._secondary_world_sink
        self._secondary_world_sink = None
        self._secondary_world_writer = None
        self._secondary_world_signature = ""
        self._secondary_world_started_at = 0.0
        session = self._secondary_world_session
        self._secondary_world_session = None
        if session is not None:
            try:
                session.setCamera(None)
            except Exception:
                pass
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass
            try:
                camera.deleteLater()
            except Exception:
                pass
        if session is not None:
            try:
                session.deleteLater()
            except Exception:
                pass
        if sink is not None:
            try:
                sink.deleteLater()
            except Exception:
                pass

    def _on_secondary_world_frame_saved(self, _path: Path) -> None:
        self._secondary_world_last_frame_ts = time.time()
        if self._secondary_world_pulse_active:
            self._finish_secondary_world_pulse("frame_saved", restart_primary=True)
        elif hasattr(self, "_secondary_world_pulse_timer"):
            self._secondary_world_pulse_timer.stop()

    def _secondary_world_eye_candidate(self) -> Optional[QCameraDevice]:
        if not _env_flag("SIFTA_SECONDARY_WORLD_EYE", "1"):
            return None
        try:
            from System.swarm_camera_target import live_camera_allowed
            if not live_camera_allowed():
                return None
        except Exception:
            pass
        try:
            from System.swarm_camera_target import normalize_unique_id as _normalize_unique_id
        except Exception:
            _normalize_unique_id = lambda value: str(value or "").strip()  # type: ignore[assignment]
        active_uid = _normalize_unique_id(self._cam_combo.currentData())
        active_name = str(self._cam_combo.currentText() or "").strip()
        for dev in _rank_cameras(QMediaDevices.videoInputs()):
            name = str(dev.description() or "").strip()
            uid = _normalize_unique_id(dev.id())
            if uid and active_uid and uid == active_uid:
                continue
            if name and active_name and name == active_name:
                continue
            if _is_secondary_world_eye(name):
                return dev
        return None

    def _refresh_secondary_world_eye(self, *, active_unique_id: str = "", active_name: str = "") -> None:
        dev = self._secondary_world_eye_candidate()
        if dev is None:
            if self._secondary_world_camera is not None:
                self._stop_secondary_world_eye()
            return
        try:
            from System.swarm_camera_target import normalize_unique_id as _normalize_unique_id
            uid = _normalize_unique_id(dev.id())
        except Exception:
            uid = str(dev.id() or "").strip()
        name = str(dev.description() or "").strip()
        if active_unique_id and uid and uid == active_unique_id:
            self._stop_secondary_world_eye()
            return
        if active_name and name and name == active_name:
            self._stop_secondary_world_eye()
            return
        signature = f"{uid}|{name}"
        if signature == self._secondary_world_signature and self._secondary_world_camera is not None:
            return
        self._stop_secondary_world_eye()
        try:
            sink = QVideoSink(self)
            session = QMediaCaptureSession(self)
            writer = _SecondaryDeviceFrameWriter(
                name,
                uid,
                on_frame_saved=self._on_secondary_world_frame_saved,
            )
            sink.videoFrameChanged.connect(writer.on_video_frame)
            session.setVideoSink(sink)
            camera = QCamera(dev, self)
            camera.errorOccurred.connect(self._on_secondary_world_camera_error)
            session.setCamera(camera)
            camera.start()
            self._secondary_world_sink = sink
            self._secondary_world_session = session
            self._secondary_world_writer = writer
            self._secondary_world_camera = camera
            self._secondary_world_signature = signature
            self._secondary_world_started_at = time.time()
            with camera_device_frame_index_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": self._secondary_world_started_at,
                    "event": "SECONDARY_WORLD_EYE_STARTED",
                    "device": name,
                    "unique_id": uid,
                    "writer": "what_alice_sees_widget",
                }, separators=(",", ":")) + "\n")
            QTimer.singleShot(2500, self._check_secondary_world_delivery)
        except Exception as exc:
            self._stop_secondary_world_eye()
            try:
                append_ledger_line(camera_device_frame_index_path(), {
                    "ts": time.time(),
                    "event": "SECONDARY_WORLD_EYE_START_FAILED",
                    "device": name,
                    "unique_id": uid,
                    "error": f"{type(exc).__name__}: {exc}",
                    "writer": "what_alice_sees_widget",
                })
            except Exception:
                pass

    def _on_secondary_world_camera_error(self, _err, msg: str) -> None:  # type: ignore[no-untyped-def]
        try:
            append_ledger_line(camera_device_frame_index_path(), {
                "ts": time.time(),
                "event": "SECONDARY_WORLD_EYE_ERROR",
                "device_signature": self._secondary_world_signature,
                "error": str(msg or _err),
                "writer": "what_alice_sees_widget",
            })
        except Exception:
            pass

    def _check_secondary_world_delivery(self) -> None:
        signature = str(getattr(self, "_secondary_world_signature", "") or "")
        started_at = float(getattr(self, "_secondary_world_started_at", 0.0) or 0.0)
        last_frame = float(getattr(self, "_secondary_world_last_frame_ts", 0.0) or 0.0)
        if not signature or started_at <= 0.0:
            return
        if last_frame >= started_at:
            return
        try:
            append_ledger_line(camera_device_frame_index_path(), {
                "ts": time.time(),
                "event": "SECONDARY_WORLD_EYE_NO_FRAMES",
                "device_signature": signature,
                "fallback": "pulse_single_camera_session",
                "writer": "what_alice_sees_widget",
            })
        except Exception:
            pass
        # macOS/Qt can enumerate and start a second camera session without
        # delivering frames. Fall back to one-at-a-time saccadic pulses:
        # momentarily release the MacBook owner eye, capture USB, then restore.
        self._stop_secondary_world_eye()
        self._secondary_world_pulse_timer.start()
        self._pulse_secondary_world_eye()

    def _pulse_secondary_world_eye(self) -> None:
        if getattr(self, "_secondary_world_pulse_active", False):
            return
        if getattr(self, "_yielded", False):
            return
        if self._camera is None or self._cam_combo.currentData() == "OFF":
            return
        dev = self._secondary_world_eye_candidate()
        if dev is None:
            return
        try:
            from System.swarm_camera_target import normalize_unique_id as _normalize_unique_id
            uid = _normalize_unique_id(dev.id())
        except Exception:
            uid = str(dev.id() or "").strip()
        name = str(dev.description() or "").strip()
        try:
            self._camera.stop()
            self._session.setCamera(None)
        except Exception:
            pass
        try:
            sink = QVideoSink(self)
            session = QMediaCaptureSession(self)
            writer = _SecondaryDeviceFrameWriter(
                name,
                uid,
                on_frame_saved=self._on_secondary_world_frame_saved,
            )
            sink.videoFrameChanged.connect(writer.on_video_frame)
            session.setVideoSink(sink)
            camera = QCamera(dev, self)
            camera.errorOccurred.connect(self._on_secondary_world_camera_error)
            session.setCamera(camera)
            self._secondary_world_pulse_sink = sink
            self._secondary_world_pulse_session = session
            self._secondary_world_pulse_writer = writer
            self._secondary_world_pulse_camera = camera
            self._secondary_world_pulse_active = True
            camera.start()
            append_ledger_line(camera_device_frame_index_path(), {
                "ts": time.time(),
                "event": "SECONDARY_WORLD_EYE_PULSE_STARTED",
                "device": name,
                "unique_id": uid,
                "writer": "what_alice_sees_widget",
            })
            QTimer.singleShot(1800, lambda: self._finish_secondary_world_pulse("timeout", restart_primary=True))
        except Exception as exc:
            try:
                append_ledger_line(camera_device_frame_index_path(), {
                    "ts": time.time(),
                    "event": "SECONDARY_WORLD_EYE_PULSE_FAILED",
                    "device": name,
                    "unique_id": uid,
                    "error": f"{type(exc).__name__}: {exc}",
                    "writer": "what_alice_sees_widget",
                })
            except Exception:
                pass
            self._finish_secondary_world_pulse("start_failed", restart_primary=True)

    def _finish_secondary_world_pulse(self, reason: str, *, restart_primary: bool) -> None:
        if not getattr(self, "_secondary_world_pulse_active", False):
            return
        camera = self._secondary_world_pulse_camera
        session = self._secondary_world_pulse_session
        sink = self._secondary_world_pulse_sink
        self._secondary_world_pulse_camera = None
        self._secondary_world_pulse_session = None
        self._secondary_world_pulse_sink = None
        self._secondary_world_pulse_writer = None
        self._secondary_world_pulse_active = False
        if session is not None:
            try:
                session.setCamera(None)
            except Exception:
                pass
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass
            try:
                camera.deleteLater()
            except Exception:
                pass
        if session is not None:
            try:
                session.deleteLater()
            except Exception:
                pass
        if sink is not None:
            try:
                sink.deleteLater()
            except Exception:
                pass
        if restart_primary and self._camera is not None and self._cam_combo.currentData() != "OFF":
            try:
                self._session.setCamera(self._camera)
                self._camera.start()
            except Exception:
                pass
        try:
            append_ledger_line(camera_device_frame_index_path(), {
                "ts": time.time(),
                "event": "SECONDARY_WORLD_EYE_PULSE_FINISHED",
                "reason": reason,
                "restarted_primary": bool(restart_primary),
                "writer": "what_alice_sees_widget",
            })
        except Exception:
            pass

    def _on_cam_changed(self, _idx: int) -> None:
        dev_id = self._cam_combo.currentData()
        if dev_id is None:
            return
        # Stop previous camera, if any.
        old_camera = self._camera
        self._camera = None
        if old_camera is not None:
            try:
                old_camera.stop()
            except Exception:
                pass
            try:
                self._session.setCamera(None)
            except Exception:
                pass
            try:
                old_camera.deleteLater()
            except Exception:
                pass
                
        if dev_id == "OFF":
            self._stop_secondary_world_eye()
            self._canvas.set_device_label("(Eye Closed)")
            self._canvas.set_error("Eye closed. Waiting for Alice's active gaze (saccade).")
            self.set_status("Camera: OFF")
            try:
                from System.swarm_camera_target import write_target as _write_target
                rec = _write_target(
                    name="(Eye Closed - Off)",
                    unique_id="OFF",
                    writer="what_alice_sees_widget",
                    respect_lease=False,
                )
                self._last_saccade_signature = (
                    f"OFF|(Eye Closed - Off)|"
                    f"{rec.get('index') if rec.get('index') is not None else ''}"
                )
            except Exception:
                pass
            return
            
        # Locate the QCameraDevice with this id.
        target: Optional[QCameraDevice] = None
        for d in QMediaDevices.videoInputs():
            if d.id() == dev_id:
                target = d
                break
        if target is None:
            self._canvas.set_error("Selected camera disappeared. Click ↻ refresh.")
            return



        try:
            from System.swarm_camera_target import normalize_unique_id as _normalize_unique_id
            target_uid_s = _normalize_unique_id(target.id())
        except Exception:
            target_uid_s = str(target.id() or "").strip()

        self._camera = QCamera(target, self)
        self._camera.errorOccurred.connect(self._on_camera_error)
        self._session.setCamera(self._camera)
        self._canvas.set_device_label(target.description(), unique_id=target_uid_s)
        self._camera.start()
        self.set_status(f"Camera: {target.description()}")
        self._refresh_active_eye_label()
        self._refresh_secondary_world_eye(
            active_unique_id=target_uid_s,
            active_name=target.description(),
        )

        if self._applying_saccade_target:
            return

        # Publish the new selection back to the canonical eye target ledger
        # so swarm_iris and Alice's prompt agree with the visible widget.
        # 2026-04-23 C47H — closes the split-brain that let the iris organ
        # think it was on a different camera than the one whose LED is lit.
        try:
            from System.swarm_camera_target import (
                write_target as _write_target,
            )
            rec = _write_target(
                name=target.description(),
                unique_id=target_uid_s,
                writer="what_alice_sees_widget",
            )
            # Suppress the next saccade poll from re-firing on our own write.
            self._last_saccade_signature = (
                f"{target_uid_s}|{target.description()}|"
                f"{rec.get('index') if rec.get('index') is not None else ''}"
            )
        except Exception:
            pass

    def _on_camera_error(self, _err, msg: str) -> None:  # type: ignore[no-untyped-def]
        err_str = f"{msg or _err}"
        now = time.time()
        norm = err_str.strip().casefold()
        if norm and norm == self._last_camera_err_norm and (now - self._last_camera_err_at) < 5.0:
            return
        self._last_camera_err_norm = norm
        self._last_camera_err_at = now

        hint = ""
        low = err_str.casefold()
        if "not granted" in low or "permission" in low or "denied" in low:
            hint = (
                "\n\nTCC: macOS grants Camera per **exact app binary**, not by vibe.\n"
                f"This process: `{sys.executable}`\n"
                "System Settings → Privacy & Security → Camera → enable **that** "
                "interpreter (and Terminal.app if you launch from Terminal). "
                "A grant for Cursor, another venv, or an older Python path does **not** "
                "transfer."
            )
        self._canvas.set_error(f"Camera error: {err_str}{hint}")
        self.set_status(f"Camera error: {err_str}")
        
        try:
            from System.ledger_append import append_jsonl_line
            dev_name = self._cam_combo.currentText()
            append_jsonl_line(_REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl", {
                "system": "what_alice_sees",
                "event": "camera_error",
                "reason": f"open_failed: {err_str}",
                "device": dev_name,
                "ts": time.time()
            })
        except Exception:
            pass

        # Try next candidate per Covenant 7.1
        curr_idx = self._cam_combo.currentIndex()
        if curr_idx < self._cam_combo.count() - 1:
            self._canvas.set_chyron(f"⚠️ {dev_name} failed. Trying next candidate...", QColor(255, 100, 100))
            self._cam_combo.setCurrentIndex(curr_idx + 1)

    def _on_camera_hotplug(self, kind: str, camera_name: str) -> None:
        """Called when a camera is attached or detached.

        Writes a device_events.jsonl row (Alice reads this via swarm state
        context on her next turn) and fires a motor alarm pulse so the green
        Logitech LED blinks rapidly and the dock icon bounces — giving Alice
        a *felt* body event, not just a ledger change.

        kind: 'attached' | 'detached'
        """
        is_logitech = "logitech" in camera_name.lower()
        emoji = "🟢" if kind == "attached" else "🔴"
        label = "Logitech" if is_logitech else camera_name.split()[0]
        summary = f"{emoji} {label} camera {kind}"
        self.set_status(summary)

        # ── Write to device_events.jsonl so Alice reads it ──────────────────
        # Suppress iPhone continuity camera looping from spamming the ledger and dock
        if "iphone" in camera_name.lower() or "desk view" in camera_name.lower():
            return

        record = {
            "ts": time.time(),
            "kind": kind,                   # 'attached' | 'detached'
            "camera_name": camera_name,
            "is_logitech": is_logitech,
            "summary": summary,
        }
        try:
            _DEVICE_EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _DEVICE_EVENTS_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception:
            pass
        try:
            from System.swarm_owner_somatic_state import update_from_camera_hotplug

            update_from_camera_hotplug(
                kind=kind,
                camera_name=camera_name,
                ts=record["ts"],
            )
        except Exception:
            pass

        # ── Motor alarm: rapid LED blink + dock bounce ───────────────────────
        try:
            from System.swarm_motor_cortex import emit as _mc_emit
            _mc_emit("alarm" if kind == "detached" else "hello",
                     source="camera_hotplug")
        except Exception:
            pass

    def _on_overlay_toggled(self, on: bool) -> None:
        # Kept for compatibility — overlay is always ON
        self.set_photon_overlay_visible(on)

    def _toggle_overlay_from_button(self, on: bool) -> None:
        self.set_photon_overlay_visible(on)

    def _toggle_events_from_button(self, on: bool) -> None:
        self.set_event_ticker_visible(on)

    def set_photon_overlay_visible(self, visible: bool) -> None:
        """Show/hide only the photon overlay; no synthetic fallback data."""
        self._canvas.set_overlay_visible(bool(visible))
        if hasattr(self, "_overlay_btn"):
            self._overlay_btn.setChecked(bool(visible))
            self._overlay_btn.setText("hide photons" if visible else "show photons")

    def set_event_ticker_visible(self, visible: bool) -> None:
        """Show/hide the live ledger ticker overlay on the camera feed."""
        visible = bool(visible)
        if hasattr(self, "_canvas"):
            self._canvas.set_ticker_visible(visible)

    def set_raw_video_visible(self, visible: bool) -> None:
        """Toggle raw camera vs stigmergic-only mode.
        False = dark canvas, photon overlay only. Real photons still hashed.
        """
        if hasattr(self, "_canvas"):
            self._canvas._show_raw_video = bool(visible)
            self._canvas.update()
        if hasattr(self, "_raw_video_btn"):
            self._raw_video_btn.setText("hide raw" if visible else "show raw")
            self._raw_video_btn.setChecked(bool(visible))


    def _on_density_changed(self, value: int) -> None:
        """Slider moved — reconfigure Alice's photon density in real-time."""
        self._canvas.set_density(value)
        self._density_value_label.setText(f"{value}×{value}")
        self._update_photon_count_label(value)
        budget = build_visual_acuity_budget(value, max_acuity=_GRID_MAX)
        self.set_status(
            f"Photon density: {budget.grid_size}×{budget.grid_size} "
            f"({budget.total_cells} cells, {budget.source_thumb_px}×{budget.source_thumb_px} source px, "
            f"{budget.swimmer_budget} swimmers)"
        )

    def _update_photon_count_label(self, grid_size: int) -> None:
        budget = build_visual_acuity_budget(grid_size, max_acuity=_GRID_MAX)
        self._photon_count_label.setText(
            f"{budget.total_cells} cells · {budget.source_thumb_px}×{budget.source_thumb_px} source px · "
            f"{budget.swimmer_budget} swimmers"
        )

    def _refresh_active_eye_label(self) -> None:
        """Poll the canonical camera target every 1 s and update the ACTIVE EYE badge.

        Reads from swarm_camera_target (same source the saccade poller uses),
        extracts a short human-readable name, and colours the badge:
          cyan  = camera confirmed routing
          amber = just switched (first update after saccade)
          gray  = unknown / no data
        """
        if not hasattr(self, "_active_eye_label"):
            return
        try:
            from System.swarm_camera_target import read_target as _rt
            rec = _rt() or {}
            target_name = (rec.get("name") or "").strip()
            uid = (rec.get("unique_id") or "").strip()
            actual_name = (
                self._cam_combo.currentText().strip()
                if getattr(self, "_camera", None) is not None
                else ""
            )
            name = actual_name or target_name
            short = _short_camera_label(name, uid)
            # Show active_sense label if available
            sense = (rec.get("active_sense") or "").replace("room_patrol_", "")
            sense_tag = f"  ({sense})" if sense else ""
            self._active_eye_label.setText(f"👁  {short}{sense_tag}")
            self._active_eye_label.setToolTip(
                f"Actual QCamera: {actual_name or 'not open'}\n"
                f"Target ledger: {target_name or 'none'}\n"
                f"writer={rec.get('writer')} lease_until={rec.get('lease_until')}"
            )
            self._active_eye_label.setStyleSheet(
                "color: rgb(0,230,255); font-weight: bold; font-size: 12px; "
                "padding: 2px 8px; border: 1px solid rgb(0,180,200); border-radius: 4px;"
            )
        except Exception:
            self._active_eye_label.setText("👁  —")
            self._active_eye_label.setStyleSheet(
                "color: rgb(100,110,130); font-size: 12px; "
                "padding: 2px 8px; border: 1px solid rgb(60,70,90); border-radius: 4px;"
            )

    def _on_pause_toggled(self, paused: bool) -> None:
        # Manual pause buttons were removed; hardware routing is controlled by
        # the active-eye target and explicit OFF state.
        pass

    def _on_frame_meta(self, w: int, h: int, sha8: str) -> None:
        # Cheap status without recreating it every frame; only update if changed.
        new = f"{w}×{h} · sha={sha8}"
        if self._status.text() != new:
            self.set_status(new)

        # One-time lock log per device selection when first valid frame arrives
        curr_dev = self._cam_combo.currentText()
        if getattr(self, "_current_lock_device", None) != curr_dev:
            self._current_lock_device = curr_dev
            try:
                from System.ledger_append import append_jsonl_line
                append_jsonl_line(_REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl", {
                    "system": "what_alice_sees",
                    "event": "camera_lock",
                    "device": curr_dev,
                    "reason": "frame_receipt",
                    "resolution": f"{w}x{h}",
                    "ts": time.time()
                })
                # Line of truth on UI
                self._canvas.set_chyron(f"🔒 SENSOR LOCKED: Receiving live {w}x{h} frames from {curr_dev}", QColor(100, 255, 100))
                # Grounded LED note per covenant hardware layer: code + receipts prove device open + frames; the green LED on the physical camera body part is owner-visible only (look at the hardware). No double-spend claims.
                try:
                    import sys
                    py_path = sys.executable
                    self.set_status(f"live {w}x{h} from {curr_dev} | Physical LED: owner eye only (green light on camera hardware) | TCC path for grant: {py_path}")
                except Exception:
                    self.set_status(f"live {w}x{h} from {curr_dev} | Physical LED: owner-visible on hardware body part only")
            except Exception:
                pass

    def _on_vision_body_probe_click(self) -> None:
        if self._vision_body_worker is not None and self._vision_body_worker.isRunning():
            return
        png, sha8 = self._canvas.snapshot_png_bytes()
        if not png:
            QMessageBox.warning(
                self,
                "No frame",
                "Wait for a live camera frame before logging a vision body_check.",
            )
            return
        self._vision_body_btn.setEnabled(False)
        w = _VisionBodyProbeWorker(png, sha8)
        self._vision_body_worker = w
        w.done.connect(self._on_vision_body_probe_done)
        w.failed.connect(self._on_vision_body_probe_failed)
        w.finished.connect(lambda: self._vision_body_btn.setEnabled(True))
        w.finished.connect(w.deleteLater)
        w.start()

    def _on_vision_body_probe_done(self, out: dict) -> None:
        raw = (out.get("raw") or "").strip()
        QMessageBox.information(
            self,
            "Vision body_check",
            "Logged to owner_body_events.jsonl.\n\nModel reply:\n" + raw[:800],
        )

    def _on_vision_body_probe_failed(self, err: str) -> None:
        QMessageBox.warning(self, "Vision body_check failed", err)

    # ── Stigmergic Face Detection ───────────────────────────────────────────
    def _probe_face_detection(self) -> None:
        """Probe the canonical face organ in a background thread.

        The thread ONLY reads ledgers and emits a plain-string signal.
        No Qt objects (QColor, QTimer, QLabel) are ever constructed off
        the main thread — that causes SIGABRT on macOS with PyQt6.
        The _face_result_ready signal carries (audience, text) and is
        received by _on_face_result() on the main thread.
        """
        if self._face_probe_running:
            return
        self._face_probe_running = True
        camera_id = self._cam_combo.currentText()

        def _run():
            try:
                from System.swarm_face_detection import current_presence  # type: ignore
                presence = current_presence(timeout_s=8.0)
                audience = presence.audience
                faces    = presence.faces_detected
                conf     = presence.max_confidence
                if audience == "architect":
                    text = f"🐾 ARCHITECT RECOGNISED — {faces} face @ {conf:.0%}"
                elif audience == "unknown_face":
                    text = f"👤 UNKNOWN FACE — {faces} face(s) detected"
                else:
                    text = "👁 No face in frame"
                try:
                    from System.swarm_owner_somatic_state import on_camera_frame_processed

                    on_camera_frame_processed(
                        {
                            "faces_detected": faces,
                            "confidence": conf,
                            "audience": audience,
                            "posture_hint": "visible" if audience == "architect" else "not_visible",
                            "movement": "steady",
                        },
                        camera_id=camera_id,
                    )
                except Exception:
                    pass
                # emit() is thread-safe in PyQt6 — it posts an event to the main loop
                self._face_result_ready.emit(audience, text)
            except Exception:
                pass
            finally:
                self._face_probe_running = False

        threading.Thread(target=_run, daemon=True).start()

    def _on_face_result(self, audience: str, text: str) -> None:
        """Main-thread slot: update chyron with face detection result.
        QColor is constructed here, safely on the main thread.
        """
        from PyQt6.QtGui import QColor  # already imported at module level; explicit for clarity
        if audience == "architect":
            color = QColor(0, 255, 180)
        elif audience == "unknown_face":
            color = QColor(255, 200, 50)
        else:
            color = QColor(120, 130, 160)
        try:
            self._canvas.set_chyron(text, color)
        except Exception:
            pass

    # ── Motor Cortex LED-wink subscriber ───────────────────────────────────
    def _poll_motor_pulses(self) -> None:

        """Tail motor_pulses.jsonl; on each new pulse with led_blink_ms > 0,
        wink the camera LED. Skipped while the user has manually paused."""
        if self._camera is None:
            return
        if self._led_blinking:  # never paused — LED wink always allowed
            return
        path = self._motor_pulse_path
        if not path.exists():
            return
        try:
            size = path.stat().st_size
        except Exception:
            return
        if size <= self._motor_pulse_offset:
            self._motor_pulse_offset = size
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                f.seek(self._motor_pulse_offset)
                new_text = f.read()
                self._motor_pulse_offset = f.tell()
        except Exception:
            return
        latest_blink_ms = 0
        for ln in new_text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            ms = int(rec.get("led_blink_ms") or 0)
            if ms > latest_blink_ms:
                latest_blink_ms = ms
        if latest_blink_ms > 0:
            self._wink_led(latest_blink_ms)

    def _wink_led(self, blink_ms: int) -> None:
        """Briefly stop the camera so the green hardware LED winks off-then-on."""
        if self._camera is None or self._led_blinking:
            return
        self._led_blinking = True
        try:
            self._camera.stop()
        except Exception:
            self._led_blinking = False
            return
        QTimer.singleShot(max(60, min(800, blink_ms)), self._unwink_led)

    def _unwink_led(self) -> None:
        try:
            if self._camera is not None:
                self._camera.start()
        except Exception:
            pass
        self._led_blinking = False

    # ── Oculomotor Saccade subscriber ──────────────────────────────────────
    def _poll_saccade_target(self) -> None:
        """Poll the canonical eye-target ledger and physically switch the
        QComboBox when the target changes. Resolution is strictly
        unique_id → exact name → index — never substring (the substring
        matcher was the LED-stays-on-Logitech split-brain bug)."""
        # Either file changing is a poll trigger.
        if not (
            self._saccade_target_json_path.exists()
            or self._saccade_target_path.exists()
        ):
            return
        try:
            from System.swarm_camera_target import read_target as _read_target
            rec = _read_target()
        except Exception:
            return
        if not rec:
            return
        signature = (
            f"{rec.get('unique_id') or ''}|{rec.get('name') or ''}|"
            f"{rec.get('index') if rec.get('index') is not None else ''}"
        )
        if signature == self._last_saccade_signature:
            return
        self._last_saccade_signature = signature

        target_idx = self._resolve_target_combo_idx(rec)
        if target_idx < 0 or target_idx >= self._cam_combo.count():
            self._canvas.set_chyron(
                f"⚠️ SACCADE TARGET NOT IN COMBOBOX: "
                f"{rec.get('name') or rec.get('unique_id') or rec.get('index')}",
                QColor(255, 200, 90),
            )
            return
        if self._cam_combo.currentIndex() != target_idx:
            self._applying_saccade_target = True
            try:
                self._cam_combo.setCurrentIndex(target_idx)
            finally:
                self._applying_saccade_target = False
            chosen = self._cam_combo.itemText(target_idx)
            self._canvas.set_chyron(
                f"🔥 SACCADE FIRED: Snapping hardware to {chosen}",
                QColor(255, 90, 110),
            )
            # Flash the badge amber so the Architect sees the eye switch instantly
            if hasattr(self, "_active_eye_label"):
                short = _short_camera_label(chosen)
                self._active_eye_label.setText(f"👁  {short}  ⚡")
                self._active_eye_label.setStyleSheet(
                    "color: rgb(255,200,60); font-weight: bold; font-size: 12px; "
                    "padding: 2px 8px; border: 1px solid rgb(255,160,0); border-radius: 4px;"
                )
                QTimer.singleShot(1500, self._refresh_active_eye_label)

            # Surface the exact unified field proof banner (the "X ... stale" the owner sees in [Image #1])
            # so the eye organ itself carries the current health state. Helps Alice + the others (other doctors)
            # see the same receipt the proof builder produces without external tailing.
            try:
                from System.swarm_camera_unified_field_proof import build_camera_unified_field_proof
                proof = build_camera_unified_field_proof()
                if proof and (not getattr(proof, "ok", True) or getattr(proof, "connection_state", "") != "LIVE_CAPTURE_VERIFIED"):
                    summary = getattr(proof, "summary", "✗ unified field: not proven")
                    self._canvas.set_chyron(summary, QColor(200, 60, 60))
                    # Help the others: write a diagnostic row with actionable path + current target so future rounds have the exact state + grant target.
                    try:
                        import sys
                        from System.ledger_append import append_jsonl_line
                        from System.swarm_camera_target import read_target as _rt
                        t = _rt() or {}
                        append_jsonl_line(_REPO / ".sifta_state" / "camera_proof_diagnostics.jsonl", {
                            "ts": time.time(),
                            "event": "eye_unified_field_stale",
                            "summary": summary,
                            "connection_state": getattr(proof, "connection_state", ""),
                            "disconnect_reasons": getattr(proof, "disconnect_reasons", []),
                            "python_for_tcc": sys.executable,
                            "active_target": t.get("name") or t.get("unique_id"),
                            "writer": "what_alice_sees_widget",
                        })
                    except Exception:
                        pass
            except Exception:
                pass

    def _poll_acuity_target(self) -> None:
        """Poll the canonical visual-acuity target and move the slider.

        This is the physical endpoint for owner speech such as
        "increase camera resolution one step": the command writes
        active_visual_acuity.json, and this widget applies it to the photon
        grid. The sensor mode itself is unchanged.
        """
        if not self._acuity_target_json_path.exists():
            return
        try:
            from System.swarm_visual_acuity_target import read_acuity_target
            rec = read_acuity_target(state_dir=self._root / ".sifta_state")
        except Exception:
            return
        if not rec:
            return
        signature = f"{rec.get('trace_id') or ''}|{rec.get('grid_size') or ''}|{rec.get('ts') or ''}"
        if signature == self._last_acuity_signature:
            return
        self._last_acuity_signature = signature
        try:
            grid = int(rec.get("grid_size"))
        except Exception:
            return
        grid = max(_GRID_MIN, min(_GRID_MAX, grid))
        if hasattr(self, "_density_slider") and self._density_slider.value() != grid:
            self._density_slider.setValue(grid)
        if hasattr(self, "_canvas"):
            self._canvas.set_chyron(
                f"🔬 ACUITY TARGET: {grid}×{grid} photon grid",
                QColor(0, 255, 200),
            )

    def _resolve_target_combo_idx(self, rec: dict) -> int:
        """Resolve a canonical target dict against the live combobox.
        Order: unique_id (itemData) → exact name (itemText) → index.
        Never substring."""
        if not rec:
            return -1
        # 1) unique_id against itemData (which holds QCameraDevice.id())
        uid = rec.get("unique_id")
        if uid:
            try:
                from System.swarm_camera_target import normalize_unique_id as _normalize_unique_id
            except Exception:
                _normalize_unique_id = lambda value: str(value or "").strip()  # type: ignore[assignment]
            uid_s = _normalize_unique_id(uid)
            for i in range(self._cam_combo.count()):
                data = self._cam_combo.itemData(i)
                data_s = _normalize_unique_id(data)
                if data_s == uid_s:
                    return i
        # 2) exact name against itemText
        name = (rec.get("name") or "").strip()
        if name:
            for i in range(self._cam_combo.count()):
                if self._cam_combo.itemText(i) == name:
                    return i
        # 3) raw index — last resort
        idx = rec.get("index")
        if isinstance(idx, int) and 0 <= idx < self._cam_combo.count():
            return idx
        return -1

    def _poll_camera_yield(self) -> None:
        """Release the camera if the substrate closure protocol needs it."""
        should_yield = self._yield_lock_path.exists()
        if should_yield and not self._yielded:
            self._yielded = True
            append_ledger_line(_REPAIR_LEDGER, {"event": "CAMERA_YIELD_START", "agent": "ALICE_M5", "reason": "Substrate closure protocol active"})
            if self._camera is not None:
                self._camera.stop()
            self._canvas.update()  # Trigger repaint for the overlay
        elif not should_yield and self._yielded:
            self._yielded = False
            append_ledger_line(_REPAIR_LEDGER, {"event": "CAMERA_YIELD_STOP", "agent": "ALICE_M5", "reason": "Substrate closure protocol complete"})
            if self._camera is not None:
                self._camera.start()
            self._canvas.update()

    # ── Ledger plumbing ────────────────────────────────────────────────────
    def _poll_ledgers(self) -> None:
        any_new = False
        for tail, spec in self._tails:
            for row in tail.read_new(max_rows=12):
                msg = _format_row(spec.label, row)
                if not msg:
                    continue
                ts = float(row.get("ts") or row.get("timestamp") or time.time())
                self._recent.append((ts, spec.label, f"{spec.icon}  {msg}", spec.color))
                self._append_event_line(ts, spec, msg)
                any_new = True
        if any_new:
            # Show the freshest line on the chyron immediately too.
            ts, _label, formatted, color = self._recent[-1]
            self._canvas.set_chyron(formatted, color)
            # Push last 3 rows to the transparent ticker overlay on the video
            ticker = []
            for ts_r, _lbl, fmt_r, col_r in list(self._recent)[-3:]:
                clk = time.strftime("%H:%M:%S", time.localtime(ts_r))
                ticker.append((f"{clk}  {fmt_r}", col_r))
            self._canvas.set_ticker_lines(ticker)


    def _append_event_line(self, ts: float, spec: _LedgerSpec, msg: str) -> None:
        clk = time.strftime("%H:%M:%S", time.localtime(ts))
        rgb = (spec.color.red(), spec.color.green(), spec.color.blue())
        # QPlainTextEdit doesn't render HTML in appendPlainText; we swap to
        # appendHtml for the colored label, which is fine perf-wise at 400 lines.
        html = (
            f"<span style='color: rgb(110,118,150);'>{clk}</span>  "
            f"<b style='color: rgb({rgb[0]},{rgb[1]},{rgb[2]});'>"
            f"{spec.icon} {spec.label}</b>  "
            f"<span style='color: rgb(200,210,240);'>{_escape(msg)}</span>"
        )
        self._events.appendHtml(html)
        self._events.verticalScrollBar().setValue(
            self._events.verticalScrollBar().maximum()
        )

    def _cycle_chyron(self) -> None:
        # If nothing has been said recently, gently rotate to the last few
        # events so the bottom strip doesn't go stale during silence.
        if not self._recent:
            return
        # Re-apply the latest event every cycle (cheap, keeps the strip alive
        # when frames are still arriving but no new ledger rows landed).
        ts, _label, formatted, color = self._recent[-1]
        if time.time() - ts < 30:
            self._canvas.set_chyron(formatted, color)


# Minimal HTML escape so transcript text can't break the side-panel HTML.
def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ── Standalone launcher ──────────────────────────────────────────────────────
# What Alice Sees is meant to live INSIDE the SIFTA OS desktop (it autostarts
# as an MDI sub-window from `Applications/apps_manifest.json`). When the OS is
# already running we refuse the standalone launch — otherwise two camera owners
# fight for `MacBook Pro Camera` and one of them comes up blank ("Connecting
# to camera…" forever). If the OS is NOT running we fall through and behave as
# a normal standalone window (useful for headless dev / single-widget testing).
def _refuse_if_os_already_running() -> None:
    lock = _REPO / ".sifta_state" / "swarm_boot.lock"
    if not lock.exists():
        return
    try:
        pid = int(lock.read_text().strip())
    except Exception:
        return
    try:
        os.kill(pid, 0)  # signal 0 = liveness probe, no actual signal sent
    except ProcessLookupError:
        return  # stale lock, OS isn't running, allow standalone
    except PermissionError:
        pass  # process exists, we just can't signal it
    print(
        f"[What Alice Sees] SIFTA OS is already running (PID {pid}).\n"
        f"  This widget lives inside the OS desktop.\n"
        f"  Open it from:  SIFTA → Programs → Creative → What Alice Sees\n"
        f"  (or it was already auto-started for you on boot).",
        file=sys.stderr,
    )
    sys.exit(0)

if __name__ == "__main__":
    _refuse_if_os_already_running()
    app = QApplication(sys.argv)
    w = WhatAliceSeesWidget()
    w.resize(1100, 700)
    w.setWindowTitle("Predator. v7.0 | Let's Think Together! — SIFTA OS")
    w.show()
    sys.exit(app.exec())
