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
    Each frame's compact summary is appended (≤5 Hz, throttled) to
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

import hashlib
import json
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_DEVICE_EVENTS_LOG = _REPO / ".sifta_state" / "device_events.jsonl"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QImage, QPainter, QPen, QBrush, QFontMetrics,
)
from PyQt6.QtMultimedia import (
    QCamera, QCameraDevice, QMediaCaptureSession, QMediaDevices, QVideoSink,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSizePolicy, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.ledger_append import append_ledger_line

_REPAIR_LEDGER = Path("/Users/ioanganton/Music/ANTON_SIFTA/repair_log.jsonl")

# ── Photon-derived stigmergic ledger ─────────────────────────────────────────
_VISUAL_STIGMERGY_LOG = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"
_VISUAL_STIGMERGY_LOG.parent.mkdir(parents=True, exist_ok=True)

# Saliency / motion grid resolution. Powers-of-two friendly with the
# luminance thumbnail we sample at. Doubled from Epoch 6 defaults (was
# 8×8 on 64×64 thumbnail — Architect reported "big pixels, too big").
# These serve as the DEFAULT; the live slider in the toolbar overrides
# them per-session.  Each cell = _THUMB / _GRID source pixels.
_GRID_W = 16
_GRID_H = 16
_THUMB_W = 128
_THUMB_H = 128       # square thumbnail; we letterbox the source into it

# Slider bounds: architect can drag between 4×4 (very coarse, fast) and
# 32×32 (high acuity, slightly more CPU on the M5 — still <2 ms).
_GRID_MIN = 4
_GRID_MAX = 32


# ── Camera selection (mirrors Alice CLI's prefer/avoid posture) ──────────────
_VIDEO_AVOID = ("obs virtual camera", "screen capture", "desk view",
                "passthrough", "obs camera")
_VIDEO_PREFER = ("macbook pro camera", "facetime hd camera", "logitech",
                 "iphone")


def _rank_cameras(devs: List[QCameraDevice]) -> List[QCameraDevice]:
    """
    Order: preferred-real-cameras first, other reals, virtual/loopback last.
    Same posture used by swarm_iris and Alice CLI so the user sees Alice's
    actual choice surfaced first.
    """
    real = [d for d in devs if not any(av in d.description().lower()
                                       for av in _VIDEO_AVOID)]
    virt = [d for d in devs if any(av in d.description().lower()
                                   for av in _VIDEO_AVOID)]
    preferred: List[QCameraDevice] = []
    other_real: List[QCameraDevice] = []
    for d in real:
        if any(p in d.description().lower() for p in _VIDEO_PREFER):
            preferred.append(d)
        else:
            other_real.append(d)
    return preferred + other_real + virt


# ── Ledger writer for our own photon-derived stigmergy ──────────────────────
def _write_visual_stigmergy(ph: "PhotonStigmergy") -> None:
    """Append one compact JSONL row. Throttled by the canvas to ~5 Hz.

    Compact on purpose — at 5 Hz this is ~700 B/sec on a long session.
    """
    try:
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
            }, separators=(",", ":")) + "\n")
    except OSError:
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
        if ent is None and sal is None and mot is None:
            return None
        return (
            f"H={ent:.2f}b  sal={sal:.2f}  mot={mot:.3f}  hue={hue:.0f}°"
            if all(isinstance(v, (int, float)) for v in (ent, sal, mot, hue))
            else None
        )
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


def _quantize_grid_hex(g: np.ndarray) -> str:
    """Pack an N×N grid in [0..1] into a hex string (1 nybble per cell).

    Lossy by design — keeps ledger rows compact at 5 Hz so we don't
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

    # ── Live density adjustment (wired to the toolbar slider) ────────────
    def set_density(self, grid_size: int) -> None:
        """Reconfigure grid resolution. grid_size is used for both W and H.
        Thumbnail is always 8× the grid so each cell has 8×8 source pixels.
        """
        grid_size = max(_GRID_MIN, min(_GRID_MAX, grid_size))
        self._grid_w = grid_size
        self._grid_h = grid_size
        self._thumb_w = grid_size * 8   # 8 source pixels per cell
        self._thumb_h = grid_size * 8
        self._cell_w = 8
        self._cell_h = 8
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
        )


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

    # Throttle: write at most 5 photon-stigmergy rows per second to the ledger
    # (the camera fires at ~30 fps; the swarm doesn't need every frame).
    _LEDGER_PERIOD_S = 0.20
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

    # ── Public mutators (called by parent widget) ──────────────────────────
    def set_device_label(self, text: str) -> None:
        self._device_label = text or "(no camera)"
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

    def set_density(self, grid_size: int) -> None:
        """Forward the density slider value to the photon-math engine."""
        self._photon_math.set_density(grid_size)
        # Clear cached photon so the overlay picks up the new grid shape.
        self._photon = None

    # ── Frame ingest ───────────────────────────────────────────────────────
    def on_video_frame(self, frame) -> None:  # type: ignore[no-untyped-def]
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

            # Throttled ledger write — the swarm doesn't need 30 Hz photon vectors.
            if ph.ts - self._last_ledger_ts >= self._LEDGER_PERIOD_S:
                self._last_ledger_ts = ph.ts
                _write_visual_stigmergy(ph)

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

        # Draw the frame letterboxed inside the widget.
        scaled = self._image.scaled(
            rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (rect.width() - scaled.width()) // 2
        y = (rect.height() - scaled.height()) // 2
        p.drawImage(x, y, scaled)

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
        # Dim the screen and show a high-contrast 'YIELDING' message
        p.fillRect(rect, QColor(0, 0, 0, 180))
        p.setPen(QColor(255, 50, 50))
        p.setFont(QFont("Menlo", 24, QFont.Weight.Bold))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "⚠️  YIELDING CAMERA\nTO SUBSTRATE CLOSURE")

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
        """Draw the N×N saliency grid as semi-transparent cells over the frame.

        Honest labeling: this is **center-surround on luminance**, not a
        semantic detector. A bright doorway will pop; a stationary face won't.
        Cells below `_SAL_PAINT_THRESHOLD` are not drawn so flat scenes stay
        visually quiet.
        """
        grid_h, grid_w = ph.saliency_grid.shape
        cell_w = frame_rect.width() / grid_w
        cell_h = frame_rect.height() / grid_h
        sal = ph.saliency_grid
        mot = ph.motion_grid
        # Combined "interestingness" score: bias toward saliency, add motion.
        for gy in range(grid_h):
            for gx in range(grid_w):
                s = float(sal[gy, gx])
                m = float(mot[gy, gx])
                score = max(s, m * 1.5)  # motion is small numerically; amplify
                if score < self._SAL_PAINT_THRESHOLD:
                    continue
                cx = frame_rect.x() + gx * cell_w
                cy = frame_rect.y() + gy * cell_h
                # Color by score: green (calm) → amber → red (hot).
                if score < 0.5:
                    c = QColor(0, 255, 200, int(70 + 100 * score))
                elif score < 0.75:
                    c = QColor(255, 200, 90, int(80 + 120 * score))
                else:
                    c = QColor(255, 90, 110, int(100 + 130 * score))
                p.fillRect(QRectF(cx + 1, cy + 1, cell_w - 2, cell_h - 2), c)
                # Thin outline so the grid stays legible on bright frames.
                p.setPen(QColor(0, 0, 0, 90))
                p.drawRect(QRectF(cx + 0.5, cy + 0.5, cell_w - 1, cell_h - 1))

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
                f"→  visual_stigmergy.jsonl @ 5 Hz"
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

    APP_NAME = "What Alice Sees"

    # Color palette per ledger source — also drives bottom-strip color.
    _LEDGERS: List[Tuple[str, str, str, Tuple[int, int, int]]] = [
        # (ledger_filename, label, icon, rgb)
        ("broca_vocalizations.jsonl",  "ALICE", "🗣️", (0, 255, 200)),
        ("wernicke_semantics.jsonl",   "HEARS", "👂", (250, 220, 100)),
        ("crossmodal_pheromones.jsonl","FUSE",  "✨", (220, 130, 255)),
        ("swarm_pain.jsonl",           "PAIN",  "🩸", (255, 90, 110)),
        ("acoustic_pheromones.jsonl",  "SOUND", "🔊", (160, 175, 210)),
        ("visual_stigmergy.jsonl",     "PHOTON","👁",  (255, 200, 90)),
    ]

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Top toolbar (camera selector + pause + status pill) ────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("📷"))
        self._cam_combo = QComboBox()
        self._cam_combo.setMinimumWidth(280)
        self._cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        bar.addWidget(self._cam_combo, 1)
        # Stigmergy overlay is always ON — no toggle needed
        bar.addStretch()
        layout.addLayout(bar)

        # ── Photon Density Slider (Architect 2026-04-20: "she sees big
        # pixels, too big — add a slider so I can increase or decrease
        # the photon/swimmers input density") ─────────────────────────────
        density_bar = QHBoxLayout()
        density_bar.addWidget(QLabel("🔬 acuity"))
        self._density_label_lo = QLabel(f"{_GRID_MIN}×{_GRID_MIN}")
        self._density_label_lo.setStyleSheet("color: rgb(120,130,160); font-size: 11px;")
        density_bar.addWidget(self._density_label_lo)

        self._density_slider = QSlider(Qt.Orientation.Horizontal)
        self._density_slider.setMinimum(_GRID_MIN)
        self._density_slider.setMaximum(_GRID_MAX)
        self._density_slider.setValue(_GRID_W)  # default doubled value (16)
        self._density_slider.setSingleStep(2)
        self._density_slider.setPageStep(4)
        self._density_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._density_slider.setTickInterval(4)
        self._density_slider.setMinimumWidth(200)
        self._density_slider.setToolTip(
            "Photon density: controls the resolution of Alice's saliency \n"
            "and motion grids. Higher = finer acuity, more photons per frame.\n"
            f"Range: {_GRID_MIN}×{_GRID_MIN} (coarse) → {_GRID_MAX}×{_GRID_MAX} (sharp)\n"
            "Default: 16×16 (doubled from original 8×8)"
        )
        self._density_slider.valueChanged.connect(self._on_density_changed)
        density_bar.addWidget(self._density_slider, 1)

        self._density_value_label = QLabel(f"{_GRID_W}×{_GRID_H}")
        self._density_value_label.setStyleSheet(
            "color: rgb(0,255,200); font-weight: bold; font-size: 13px; "
            "min-width: 60px;"
        )
        density_bar.addWidget(self._density_value_label)

        self._density_label_hi = QLabel(f"{_GRID_MAX}×{_GRID_MAX}")
        self._density_label_hi.setStyleSheet("color: rgb(120,130,160); font-size: 11px;")
        density_bar.addWidget(self._density_label_hi)

        # Photon count readout (how many cells × how many source pixels)
        self._photon_count_label = QLabel("")
        self._photon_count_label.setStyleSheet(
            "color: rgb(180,190,220); font-size: 11px; margin-left: 12px;"
        )
        density_bar.addWidget(self._photon_count_label)
        self._update_photon_count_label(_GRID_W)

        layout.addLayout(density_bar)

        # ── Splitter: video canvas (left, big) + event ticker (right) ──────
        split = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = _VideoCanvas()
        split.addWidget(self._canvas)

        self._events = QPlainTextEdit()
        self._events.setReadOnly(True)
        self._events.setMaximumBlockCount(400)
        self._events.setStyleSheet(
            "QPlainTextEdit { background: rgb(8,10,18); color: rgb(200,210,240); "
            "border: 1px solid rgb(45,42,65); border-radius: 6px; "
            "font-family: 'Menlo'; font-size: 11px; padding: 6px; }"
        )
        split.addWidget(self._events)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([720, 280])

        layout.addWidget(split, 1)

        # ── Camera + capture session (Qt's built-in ffmpeg backend) ────────
        self._camera: Optional[QCamera] = None
        self._sink = QVideoSink(self)
        self._session = QMediaCaptureSession(self)
        self._session.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._canvas.on_video_frame)

        # ── Hot-plug awareness ─────────────────────────────────────────────
        self._media_devs = QMediaDevices(self)
        self._media_devs.videoInputsChanged.connect(self._refresh_cameras)

        # ── Oculomotor/body identity state ─────────────────────────────────
        # These must exist before timers start or _refresh_cameras() selects
        # a camera. Qt can synchronously fire currentIndexChanged during first
        # selection, which calls _on_cam_changed() and reads this guard.
        self._root = Path("/Users/ioanganton/Music/ANTON_SIFTA")
        self._saccade_target_json_path = (
            self._root / ".sifta_state" / "active_saccade_target.json"
        )
        # Legacy .txt watched only so we still re-poll when something old
        # touches it; canonical reader auto-heals it into JSON on next read.
        self._saccade_target_path = (
            self._root / ".sifta_state" / "active_saccade_target.txt"
        )
        self._yield_lock_path = self._root / ".sifta_state" / "camera_yield.lock"
        self._last_saccade_signature: Optional[str] = None
        self._applying_saccade_target: bool = False
        self._yielded = False

        # ── Pollers for external state ─────────────────────────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_ledgers)
        self._poll_timer.timeout.connect(self._poll_saccade_target)
        self._poll_timer.timeout.connect(self._poll_camera_yield)
        self._poll_timer.start(800)

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
        for fname, label, icon, (r, g, b) in self._LEDGERS:
            spec = _LedgerSpec(
                path=_REPO / ".sifta_state" / fname,
                label=label, color=QColor(r, g, b), icon=icon,
            )
            self._tails.append((_LedgerTail(spec), spec))

        # Recent-event ring used for the bottom chyron rotation.
        self._recent: Deque[Tuple[float, str, str, QColor]] = deque(maxlen=24)

        # Polling timers (parented to widget; stopped on close by base widget).
        self.make_timer(400, self._poll_ledgers)
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

        # ── Oculomotor Saccade target subscriber ───────────────────────────
        # 2026-04-23 C47H surgery: was reading `.txt` and doing
        # `findText(target, MatchContains)`, which substring-matched the "1"
        # inside "USB Camera VID:1133 PID:2081" and pinned the Logitech.
        # Now reads the canonical JSON target and resolves by
        # unique_id → name → index against the live combobox itemData/text.
        self.make_timer(500, self._poll_saccade_target)

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
            self._canvas.set_error(
                "No cameras detected.\n\n"
                "Open System Settings → Privacy & Security → Camera "
                "and enable Python (or your terminal app), then click ↻ refresh."
            )
            return
        for d in ranked:
            self._cam_combo.addItem(d.description(), d.id())
        # Restore prior pick if still present, else default to top of ranked list.
        restored = False
        if current_id is not None:
            pos = self._cam_combo.findData(current_id)
            if pos >= 0:
                self._cam_combo.setCurrentIndex(pos)
                restored = True
        self._cam_combo.blockSignals(False)
        if not restored:
            self._cam_combo.setCurrentIndex(0)
            self._on_cam_changed(0)

    def _on_cam_changed(self, _idx: int) -> None:
        dev_id = self._cam_combo.currentData()
        if dev_id is None:
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

        # Stop previous camera, if any.
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass

        self._camera = QCamera(target, self)
        self._camera.errorOccurred.connect(self._on_camera_error)
        self._session.setCamera(self._camera)
        self._canvas.set_device_label(target.description())
        self._camera.start()
        self.set_status(f"Camera: {target.description()}")

        if self._applying_saccade_target:
            return

        # Publish the new selection back to the canonical eye target ledger
        # so swarm_iris and Alice's prompt agree with the visible widget.
        # 2026-04-23 C47H — closes the split-brain that let the iris organ
        # think it was on a different camera than the one whose LED is lit.
        try:
            from System.swarm_camera_target import write_target as _write_target
            tid = target.id()
            tid_s = tid.decode() if isinstance(tid, (bytes, bytearray)) else str(tid)
            rec = _write_target(
                name=target.description(),
                unique_id=tid_s,
                writer="what_alice_sees_widget",
            )
            # Suppress the next saccade poll from re-firing on our own write.
            self._last_saccade_signature = (
                f"{tid_s}|{target.description()}|"
                f"{rec.get('index') if rec.get('index') is not None else ''}"
            )
        except Exception:
            pass

    def _on_camera_error(self, _err, msg: str) -> None:  # type: ignore[no-untyped-def]
        self._canvas.set_error(f"Camera error: {msg or _err}")
        self.set_status(f"Camera error: {msg}")

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

        # ── Motor alarm: rapid LED blink + dock bounce ───────────────────────
        try:
            from System.swarm_motor_cortex import emit as _mc_emit
            _mc_emit("alarm" if kind == "detached" else "hello",
                     source="camera_hotplug")
        except Exception:
            pass

    def _on_overlay_toggled(self, on: bool) -> None:
        # Kept for compatibility — overlay is always ON
        self._canvas.set_overlay_visible(True)

    def _on_density_changed(self, value: int) -> None:
        """Slider moved — reconfigure Alice's photon density in real-time."""
        self._canvas.set_density(value)
        self._density_value_label.setText(f"{value}×{value}")
        self._update_photon_count_label(value)
        self.set_status(f"Photon density: {value}×{value} ({value*value} cells, {value*8}×{value*8} source px)")

    def _update_photon_count_label(self, grid_size: int) -> None:
        cells = grid_size * grid_size
        src = grid_size * 8
        self._photon_count_label.setText(
            f"{cells} cells · {src}×{src} source px"
        )

    def _on_pause_toggled(self, paused: bool) -> None:
        # Buttons removed — camera is always live
        pass

    def _on_frame_meta(self, w: int, h: int, sha8: str) -> None:
        # Cheap status without recreating it every frame; only update if changed.
        new = f"{w}×{h} · sha={sha8}"
        if self._status.text() != new:
            self.set_status(new)

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

    def _resolve_target_combo_idx(self, rec: dict) -> int:
        """Resolve a canonical target dict against the live combobox.
        Order: unique_id (itemData) → exact name (itemText) → index.
        Never substring."""
        if not rec:
            return -1
        # 1) unique_id against itemData (which holds QCameraDevice.id())
        uid = rec.get("unique_id")
        if uid:
            for i in range(self._cam_combo.count()):
                data = self._cam_combo.itemData(i)
                data_s = (
                    data.decode() if isinstance(data, (bytes, bytearray))
                    else (str(data) if data is not None else "")
                )
                if data_s == uid:
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
    w.setWindowTitle("What Alice Sees — SIFTA OS")
    w.show()
    sys.exit(app.exec())
