#!/usr/bin/env python3
"""
System/swarm_active_matter_vision.py

Active-matter-inspired compaction for Alice's photon stigmergy.

Boundary: this is software field dynamics over the existing camera-derived
``visual_stigmergy.jsonl`` rows. It is not physical active matter and it does
not claim biological sensing. The useful invariant is simple: persistent visual
attractors should survive frame noise while transient saliency decays.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISUAL_LEDGER = _STATE / "visual_stigmergy.jsonl"
_ACTIVE_LEDGER = _STATE / "visual_active_matter.jsonl"
_SCHEMA = "SIFTA_VISUAL_ACTIVE_MATTER_V1"
_MODULE_VERSION = "swarm_active_matter_vision.v1"


@dataclass(frozen=True)
class VisualFrame:
    ts: float
    saliency: np.ndarray
    motion: np.ndarray
    entropy_bits: float = 0.0
    hue_deg: float = 0.0
    sha8: str = ""


@dataclass(frozen=True)
class ActiveMatterSnapshot:
    ts: float
    field_energy: float
    attractor_x: float
    attractor_y: float
    persistence: float
    novelty: float
    hot_cells: int
    field_hash: str


def decode_quantized_grid(grid_hex: str) -> np.ndarray:
    """Decode the widget's one-nybble-per-cell grid into float32 [0, 1]."""
    text = (grid_hex or "").strip().lower()
    if not text:
        raise ValueError("empty visual grid")
    side = int(math.sqrt(len(text)))
    if side * side != len(text):
        raise ValueError(f"visual grid length {len(text)} is not square")
    try:
        values = np.fromiter((int(ch, 16) for ch in text), dtype=np.float32, count=len(text))
    except ValueError as exc:
        raise ValueError("visual grid contains non-hex nybble") from exc
    return (values.reshape(side, side) / 15.0).astype(np.float32)


def frame_from_row(row: Dict[str, Any]) -> VisualFrame:
    saliency = decode_quantized_grid(str(row.get("saliency_q") or ""))
    motion = decode_quantized_grid(str(row.get("motion_q") or "0" * saliency.size))
    if saliency.shape != motion.shape:
        raise ValueError("saliency and motion grids have different shapes")
    return VisualFrame(
        ts=float(row.get("ts") or 0.0),
        saliency=saliency,
        motion=motion,
        entropy_bits=float(row.get("entropy_bits") or 0.0),
        hue_deg=float(row.get("hue_deg") or 0.0),
        sha8=str(row.get("sha8") or ""),
    )


def _tail_lines(path: Path, max_lines: int) -> List[str]:
    if max_lines <= 0 or not path.exists():
        return []
    block_size = 65536
    data = b""
    with path.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        while pos > 0 and data.count(b"\n") <= max_lines:
            step = min(block_size, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    return [line.decode("utf-8", errors="replace") for line in data.splitlines()[-max_lines:]]


def read_recent_visual_frames(
    *,
    visual_path: Optional[Path] = None,
    limit: int = 64,
    max_age_s: Optional[float] = 30.0,
) -> List[VisualFrame]:
    path = Path(visual_path) if visual_path is not None else _VISUAL_LEDGER
    now = time.time()
    frames: List[VisualFrame] = []
    for line in _tail_lines(path, limit):
        try:
            row = json.loads(line)
            frame = frame_from_row(row)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if max_age_s is not None and now - frame.ts > max_age_s:
            continue
        frames.append(frame)
    return frames


def _diffuse(field: np.ndarray, diffusion: float) -> np.ndarray:
    if diffusion < 0.0 or diffusion > 0.25:
        raise ValueError("diffusion must be in [0, 0.25]")
    padded = np.pad(field, 1, mode="edge")
    neighbors = (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
    )
    return ((1.0 - 4.0 * diffusion) * field) + (diffusion * neighbors)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-12:
        return 0.0
    return float(np.clip(float(np.sum(a * b)) / denom, 0.0, 1.0))


def _field_hash(field: np.ndarray) -> str:
    packed = np.clip(field * 255.0 + 0.5, 0, 255).astype(np.uint8).tobytes()
    return hashlib.sha256(packed).hexdigest()


class ActiveMatterVisionField:
    """
    Particle-free active field over saliency and motion.

    The field is a trail: each frame injects stimulus, old energy diffuses
    locally and decays. Stable visual regions become attractors; one-frame
    flashes wash out.
    """

    def __init__(
        self,
        *,
        decay: float = 0.86,
        diffusion: float = 0.10,
        injection: float = 0.35,
        saliency_gain: float = 0.70,
        motion_gain: float = 0.30,
    ) -> None:
        if not 0.0 <= decay <= 1.0:
            raise ValueError("decay must be in [0, 1]")
        if not 0.0 <= injection <= 1.0:
            raise ValueError("injection must be in [0, 1]")
        _diffuse(np.zeros((1, 1), dtype=np.float32), diffusion)
        self.decay = decay
        self.diffusion = diffusion
        self.injection = injection
        self.saliency_gain = saliency_gain
        self.motion_gain = motion_gain
        self.trail: Optional[np.ndarray] = None
        self._prev_stimulus: Optional[np.ndarray] = None

    def update(self, frame: VisualFrame) -> ActiveMatterSnapshot:
        stimulus = np.clip(
            (self.saliency_gain * frame.saliency) + (self.motion_gain * frame.motion),
            0.0,
            1.0,
        ).astype(np.float32)
        if self.trail is None:
            prior = np.zeros_like(stimulus, dtype=np.float32)
        else:
            if self.trail.shape != stimulus.shape:
                raise ValueError("frame grid shape changed within active field")
            prior = self.trail

        diffused = _diffuse(prior, self.diffusion)
        self.trail = np.clip((self.decay * diffused) + (self.injection * stimulus), 0.0, 1.0)
        novelty = (
            0.0
            if self._prev_stimulus is None
            else float(np.mean(np.abs(stimulus - self._prev_stimulus)))
        )
        self._prev_stimulus = stimulus

        energy = float(np.mean(self.trail))
        persistence = _cosine(prior, self.trail)
        total = float(np.sum(self.trail))
        if total <= 1e-12:
            attractor_x = 0.0
            attractor_y = 0.0
        else:
            ys, xs = np.indices(self.trail.shape, dtype=np.float32)
            max_x = max(float(self.trail.shape[1] - 1), 1.0)
            max_y = max(float(self.trail.shape[0] - 1), 1.0)
            attractor_x = float(np.sum(xs * self.trail) / total / max_x)
            attractor_y = float(np.sum(ys * self.trail) / total / max_y)

        threshold = max(float(np.mean(self.trail) + np.std(self.trail)), float(np.max(self.trail) * 0.55))
        hot_cells = int(np.count_nonzero(self.trail >= threshold)) if threshold > 0.0 else 0
        return ActiveMatterSnapshot(
            ts=frame.ts,
            field_energy=energy,
            attractor_x=attractor_x,
            attractor_y=attractor_y,
            persistence=persistence,
            novelty=novelty,
            hot_cells=hot_cells,
            field_hash=_field_hash(self.trail),
        )


def summarize_frames(frames: Iterable[VisualFrame]) -> Optional[ActiveMatterSnapshot]:
    field = ActiveMatterVisionField()
    snapshot: Optional[ActiveMatterSnapshot] = None
    for frame in frames:
        snapshot = field.update(frame)
    return snapshot


def row_from_snapshot(
    snapshot: ActiveMatterSnapshot,
    *,
    frames_observed: int,
    source_tail_sha8: str,
) -> Dict[str, Any]:
    return {
        "event": "visual_active_matter_update",
        "schema": _SCHEMA,
        "module_version": _MODULE_VERSION,
        "source_ledger": "visual_stigmergy.jsonl",
        "frames_observed": int(frames_observed),
        "field_energy": round(snapshot.field_energy, 6),
        "attractor_x": round(snapshot.attractor_x, 6),
        "attractor_y": round(snapshot.attractor_y, 6),
        "persistence": round(snapshot.persistence, 6),
        "novelty": round(snapshot.novelty, 6),
        "hot_cells": int(snapshot.hot_cells),
        "field_hash": snapshot.field_hash,
        "source_tail_sha8": source_tail_sha8,
        "ts": time.time(),
    }


def append_active_matter_row(
    *,
    visual_path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    limit: int = 64,
    max_age_s: Optional[float] = 30.0,
) -> Optional[Dict[str, Any]]:
    frames = read_recent_visual_frames(visual_path=visual_path, limit=limit, max_age_s=max_age_s)
    if not frames:
        return None
    snapshot = summarize_frames(frames)
    if snapshot is None:
        return None
    row = row_from_snapshot(
        snapshot,
        frames_observed=len(frames),
        source_tail_sha8=frames[-1].sha8,
    )
    target = Path(ledger_path) if ledger_path is not None else _ACTIVE_LEDGER
    append_line_locked(target, json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    result = append_active_matter_row(max_age_s=None)
    print(json.dumps(result or {"event": "visual_active_matter_update", "status": "no_recent_frames"}, indent=2))
