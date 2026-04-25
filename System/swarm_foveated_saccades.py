#!/usr/bin/env python3
"""
Foveated Swarm Saccades: two-tier active vision over a nutrient landscape.

This module optimizes local visual digestion. It does not switch physical
cameras; `swarm_oculomotor_saccades.py` owns that separate body-level behavior.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

try:
    from scipy.ndimage import gaussian_filter as _gaussian_filter
except Exception:  # pragma: no cover - only used in dependency-thin runtimes.
    _gaussian_filter = None

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked
from System.swarm_physarum_retina import SwarmPhysarumRetina

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "foveated_saccades.jsonl"
_SCHEMA = "SIFTA_FOVEATED_SACCADES_V1"
_MODULE_VERSION = "swarm_foveated_saccades.v1"


@dataclass(frozen=True)
class SaccadeTarget:
    y: int
    x: int
    salience: float


@dataclass(frozen=True)
class FoveatedSaccadeResult:
    target: SaccadeTarget
    foveal_positions: np.ndarray
    foveal_memory: np.ndarray
    foveal_digest: List[Dict[str, Any]]


@dataclass(frozen=True)
class FoveatedSaccadeConfig:
    scouts: int = 80
    foveal_agents: int = 240
    peripheral_steps: int = 10
    foveal_steps: int = 16
    peripheral_sigma: float = 5.0
    foveal_sigma: float = 4.0
    scout_jump: int = 14
    foveal_window: int = 4
    inhibition_radius: int = 14
    inhibition_decay: float = 0.92
    inhibition_strength: float = 0.75
    motion_weight: float = 1.25
    edge_weight: float = 0.75
    intensity_weight: float = 0.50
    novelty_weight: float = 0.55
    memory_penalty: float = 0.40
    saliency_threshold: float = 0.05
    eps: float = 1e-8
    seed: Optional[int] = None


def _blur(field: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0.0:
        return field.astype(np.float32)
    if _gaussian_filter is not None:
        return _gaussian_filter(field, sigma=sigma).astype(np.float32)

    # Tiny fallback: separable box blur, enough for tests without scipy.
    radius = max(1, int(round(sigma)))
    out = field.astype(np.float32)
    for axis in (0, 1):
        acc = np.zeros_like(out)
        count = 0
        for shift in range(-radius, radius + 1):
            acc += np.roll(out, shift, axis=axis)
            count += 1
        out = acc / max(count, 1)
    return out


def _normalize(field: np.ndarray) -> np.ndarray:
    max_value = float(np.max(field)) if field.size else 0.0
    if max_value <= 1e-12:
        return np.zeros_like(field, dtype=np.float32)
    return (field / max_value).astype(np.float32)


class FoveatedSwarmSaccades:
    """
    Stateful two-tier gaze for live simulation fields.

    The older `SwarmSaccadicVision` class below digests static images into an
    audit row. This class is the online loop organ: a cheap peripheral swarm
    finds a salience peak, then a dense foveal swarm writes memory around that
    peak and marks inhibition-of-return so the next glance can move on.
    """

    def __init__(self, width: int, height: int, cfg: Optional[FoveatedSaccadeConfig] = None) -> None:
        if width <= 1 or height <= 1:
            raise ValueError("width and height must be > 1")
        self.width = int(width)
        self.height = int(height)
        self.cfg = cfg or FoveatedSaccadeConfig()
        if self.cfg.scouts <= 0 or self.cfg.foveal_agents <= 0:
            raise ValueError("scouts and foveal_agents must be positive")
        if self.cfg.peripheral_steps < 0 or self.cfg.foveal_steps < 0:
            raise ValueError("step counts must be >= 0")
        if self.cfg.saliency_threshold < 0.0:
            raise ValueError("saliency_threshold must be >= 0")

        self.prev_frame: Optional[np.ndarray] = None
        self.saliency = np.zeros((self.height, self.width), dtype=np.float32)
        self.inhibition = np.zeros((self.height, self.width), dtype=np.float32)
        self.foveal_memory = np.zeros((self.height, self.width), dtype=np.float32)
        self.last_target: Optional[SaccadeTarget] = None
        self.saccade_count = 0
        self._rng = np.random.default_rng(self.cfg.seed)

    def reset(self) -> None:
        self.prev_frame = None
        self.saliency.fill(0.0)
        self.inhibition.fill(0.0)
        self.foveal_memory.fill(0.0)
        self.last_target = None
        self.saccade_count = 0

    def _validate_frame(self, frame: np.ndarray) -> np.ndarray:
        arr = np.asarray(frame, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr.mean(axis=2)
        if arr.shape != (self.height, self.width):
            raise ValueError(f"frame must have shape {(self.height, self.width)}")
        return np.clip(arr, 0.0, None).astype(np.float32)

    def _edge_energy(self, frame: np.ndarray) -> np.ndarray:
        gy, gx = np.gradient(frame)
        return _normalize(np.sqrt((gx * gx) + (gy * gy)).astype(np.float32))

    def build_nutrient_landscape(self, frame: np.ndarray) -> np.ndarray:
        frame = _normalize(self._validate_frame(frame))
        edges = self._edge_energy(frame)
        if self.prev_frame is None:
            motion = np.zeros_like(frame)
        else:
            motion = _normalize(np.abs(frame - self.prev_frame))

        evidence = np.clip(
            self.cfg.motion_weight * motion
            + self.cfg.edge_weight * edges
            + self.cfg.intensity_weight * frame,
            0.0,
            None,
        )
        self.prev_frame = frame.copy()
        if float(evidence.max()) <= self.cfg.eps:
            return np.zeros_like(frame, dtype=np.float32)

        novelty = evidence / (1.0 + self.foveal_memory)
        nutrient = (
            evidence
            + self.cfg.novelty_weight * novelty
            - self.cfg.inhibition_strength * self.inhibition
        )
        return _normalize(np.maximum(nutrient, 0.0))

    def _weighted_initial_positions(self, nutrient: np.ndarray, count: int) -> Tuple[np.ndarray, np.ndarray]:
        weights = np.clip(nutrient, 0.0, None).astype(np.float64).ravel()
        if float(weights.sum()) <= 1e-12:
            ys = self._rng.integers(0, self.height, count)
            xs = self._rng.integers(0, self.width, count)
            return ys.astype(np.float32), xs.astype(np.float32)
        probs = weights / float(weights.sum())
        indices = self._rng.choice(self.height * self.width, size=count, replace=True, p=probs)
        ys, xs = np.divmod(indices, self.width)
        return ys.astype(np.float32), xs.astype(np.float32)

    @staticmethod
    def _nearest_peak(patch: np.ndarray, center_y: int, center_x: int) -> Tuple[int, int]:
        max_value = float(np.max(patch))
        candidates = np.argwhere(patch >= max_value)
        deltas = candidates - np.array([center_y, center_x])
        best = int(np.argmin(np.sum(deltas * deltas, axis=1)))
        y, x = candidates[best]
        return int(y), int(x)

    def glance(self, nutrient: np.ndarray) -> SaccadeTarget:
        nutrient = self._validate_frame(nutrient)
        self.saliency.fill(0.0)
        if float(nutrient.max()) <= self.cfg.eps:
            target = SaccadeTarget(y=self.height // 2, x=self.width // 2, salience=0.0)
            self.last_target = target
            return target

        ys, xs = self._weighted_initial_positions(nutrient, self.cfg.scouts)
        for _ in range(self.cfg.peripheral_steps):
            for idx in range(self.cfg.scouts):
                y = int(np.clip(ys[idx], 0, self.height - 1))
                x = int(np.clip(xs[idx], 0, self.width - 1))
                radius = self.cfg.scout_jump
                y0 = max(0, y - radius)
                y1 = min(self.height, y + radius + 1)
                x0 = max(0, x - radius)
                x1 = min(self.width, x + radius + 1)
                patch = nutrient[y0:y1, x0:x1]
                if patch.size:
                    py, px = self._nearest_peak(patch, y - y0, x - x0)
                    ys[idx] = y0 + py
                    xs[idx] = x0 + px
                self.saliency[int(ys[idx]), int(xs[idx])] += 1.0

        self.saliency = _normalize(_blur(self.saliency, self.cfg.peripheral_sigma))
        combined = self.saliency * nutrient
        target_y, target_x = np.unravel_index(int(np.argmax(combined)), combined.shape)
        target = SaccadeTarget(
            y=int(target_y),
            x=int(target_x),
            salience=float(combined[target_y, target_x]),
        )
        self.last_target = target
        return target

    def saccade(self, nutrient: np.ndarray, target_y: int, target_x: int) -> np.ndarray:
        nutrient = self._validate_frame(nutrient)
        target_y = int(np.clip(target_y, 0, self.height - 1))
        target_x = int(np.clip(target_x, 0, self.width - 1))
        ys = np.clip(self._rng.normal(target_y, self.cfg.foveal_sigma, self.cfg.foveal_agents), 0, self.height - 1)
        xs = np.clip(self._rng.normal(target_x, self.cfg.foveal_sigma, self.cfg.foveal_agents), 0, self.width - 1)

        for _ in range(self.cfg.foveal_steps):
            for idx in range(self.cfg.foveal_agents):
                y = int(np.clip(ys[idx], 0, self.height - 1))
                x = int(np.clip(xs[idx], 0, self.width - 1))
                radius = self.cfg.foveal_window
                y0 = max(0, y - radius)
                y1 = min(self.height, y + radius + 1)
                x0 = max(0, x - radius)
                x1 = min(self.width, x + radius + 1)
                fitness = (
                    nutrient[y0:y1, x0:x1]
                    - self.cfg.memory_penalty * self.foveal_memory[y0:y1, x0:x1]
                )
                if fitness.size:
                    py, px = self._nearest_peak(fitness, y - y0, x - x0)
                    ys[idx] = y0 + py
                    xs[idx] = x0 + px
                self.foveal_memory[int(ys[idx]), int(xs[idx])] += 1.0

        self._mark_inhibition(target_y, target_x)
        self.saccade_count += 1
        return np.column_stack((ys.astype(int), xs.astype(int)))

    def _mark_inhibition(self, y: int, x: int) -> None:
        self.inhibition *= self.cfg.inhibition_decay
        radius = max(1, int(self.cfg.inhibition_radius))
        y0 = max(0, int(y) - radius)
        y1 = min(self.height, int(y) + radius + 1)
        x0 = max(0, int(x) - radius)
        x1 = min(self.width, int(x) + radius + 1)
        self.inhibition[y0:y1, x0:x1] += 1.0
        self.inhibition = _normalize(_blur(self.inhibition, sigma=max(1.0, radius / 2.0)))

    def observe(self, frame: np.ndarray) -> Dict[str, Any]:
        nutrient = self.build_nutrient_landscape(frame)
        target = self.glance(nutrient)
        fired = target.salience >= self.cfg.saliency_threshold
        points = np.zeros((0, 2), dtype=np.int32)
        if fired:
            points = self.saccade(nutrient, target.y, target.x)

        if len(points):
            y0, x0 = np.min(points, axis=0)
            y1, x1 = np.max(points, axis=0)
            box: Optional[Dict[str, int]] = {
                "x0": int(x0),
                "y0": int(y0),
                "x1": int(x1),
                "y1": int(y1),
                "count": int(len(points)),
            }
        else:
            box = None

        target_norm = (
            float(target.x / max(1, self.width - 1)),
            float(target.y / max(1, self.height - 1)),
        )
        return {
            "saccade_fired": bool(fired),
            "target_x": int(target.x),
            "target_y": int(target.y),
            "target_norm": target_norm,
            "saliency_peak": float(target.salience),
            "saccade_count": int(self.saccade_count),
            "foveal_points": points,
            "foveal_box": box,
            "saliency": self.saliency.copy(),
            "memory": self.foveal_memory.copy(),
            "inhibition": self.inhibition.copy(),
        }

    def glyph(self, mode: str = "saliency") -> str:
        if mode == "saliency":
            field = self.saliency
        elif mode == "memory":
            field = self.foveal_memory
        elif mode == "inhibition":
            field = self.inhibition
        else:
            raise ValueError("mode must be one of: saliency, memory, inhibition")

        if field.size == 0 or float(field.max()) <= self.cfg.eps:
            return ""
        norm = field / (float(field.max()) + self.cfg.eps)
        chars = np.array(list(" .:-=+*#%@"))
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)
        return "\n".join("".join(chars[row]) for row in idx[::-1])


class SwarmSaccadicVision:
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        *,
        seed: Optional[int] = None,
        peripheral_window: int = 20,
        peripheral_blur_sigma: float = 15.0,
        foveal_window: int = 3,
        foveal_sigma: float = 10.0,
        crowding_penalty: float = 0.5,
    ) -> None:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("screen_width and screen_height must be positive")
        if peripheral_window < 0 or foveal_window < 0:
            raise ValueError("window sizes must be >= 0")
        self.width = int(screen_width)
        self.height = int(screen_height)
        self.peripheral_window = int(peripheral_window)
        self.peripheral_blur_sigma = float(peripheral_blur_sigma)
        self.foveal_window = int(foveal_window)
        self.foveal_sigma = float(foveal_sigma)
        self.crowding_penalty = float(crowding_penalty)
        self.saliency_map = np.zeros((self.height, self.width), dtype=np.float32)
        self._rng = np.random.default_rng(seed)

    def _validate_landscape(self, nutrient_landscape: np.ndarray) -> np.ndarray:
        landscape = np.asarray(nutrient_landscape, dtype=np.float32)
        if landscape.shape != (self.height, self.width):
            raise ValueError(
                "nutrient_landscape shape must match "
                f"(screen_height, screen_width)={(self.height, self.width)}"
            )
        return np.clip(landscape, 0.0, None)

    def _weighted_initial_positions(self, landscape: np.ndarray, count: int) -> Tuple[np.ndarray, np.ndarray]:
        weights = landscape.ravel().astype(np.float64)
        if float(weights.sum()) <= 1e-12:
            agents_y = self._rng.integers(0, self.height, count).astype(np.float32)
            agents_x = self._rng.integers(0, self.width, count).astype(np.float32)
            return agents_y, agents_x
        probs = weights / float(weights.sum())
        indices = self._rng.choice(self.height * self.width, size=count, replace=True, p=probs)
        agents_y, agents_x = np.divmod(indices, self.width)
        return agents_y.astype(np.float32), agents_x.astype(np.float32)

    @staticmethod
    def _nearest_peak(local: np.ndarray, center_y: int, center_x: int) -> Tuple[int, int]:
        """
        Pick a local maximum without top-left plateau bias.

        `np.argmax` always returns the first max, which makes agents drift toward
        the upper-left corner of flat high-salience objects. Selecting the max
        closest to the agent preserves lock on broad windows and panels.
        """
        max_value = float(np.max(local))
        candidates = np.argwhere(local >= max_value)
        deltas = candidates - np.array([center_y, center_x])
        best = int(np.argmin(np.sum(deltas * deltas, axis=1)))
        y, x = candidates[best]
        return int(y), int(x)

    def glance_peripheral(
        self,
        nutrient_landscape: np.ndarray,
        *,
        num_scouts: int = 50,
        steps: int = 15,
    ) -> SaccadeTarget:
        """
        Fast sparse pass that selects one macroscopic saliency target.
        """
        if num_scouts <= 0:
            raise ValueError("num_scouts must be positive")
        if steps < 0:
            raise ValueError("steps must be >= 0")
        landscape = self._validate_landscape(nutrient_landscape)
        self.saliency_map.fill(0.0)
        agents_y, agents_x = self._weighted_initial_positions(landscape, num_scouts)

        for _ in range(steps):
            for idx in range(num_scouts):
                y = int(np.clip(agents_y[idx], 0, self.height - 1))
                x = int(np.clip(agents_x[idx], 0, self.width - 1))
                y0 = max(0, y - self.peripheral_window)
                y1 = min(self.height, y + self.peripheral_window + 1)
                x0 = max(0, x - self.peripheral_window)
                x1 = min(self.width, x + self.peripheral_window + 1)
                local = landscape[y0:y1, x0:x1]
                if local.size:
                    local_y, local_x = self._nearest_peak(local, y - y0, x - x0)
                    agents_y[idx] = y0 + int(local_y)
                    agents_x[idx] = x0 + int(local_x)
                self.saliency_map[int(agents_y[idx]), int(agents_x[idx])] += 1.0

        self.saliency_map = _normalize(_blur(self.saliency_map, self.peripheral_blur_sigma))
        peak_y, peak_x = np.unravel_index(int(np.argmax(self.saliency_map)), self.saliency_map.shape)
        return SaccadeTarget(
            y=int(peak_y),
            x=int(peak_x),
            salience=float(self.saliency_map[peak_y, peak_x]),
        )

    def saccade_foveal(
        self,
        nutrient_landscape: np.ndarray,
        target_y: int,
        target_x: int,
        *,
        num_foveal: int = 300,
        steps: int = 25,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Dense high-resolution swarm around the selected saliency target.
        """
        if num_foveal <= 0:
            raise ValueError("num_foveal must be positive")
        if steps < 0:
            raise ValueError("steps must be >= 0")
        landscape = self._validate_landscape(nutrient_landscape)
        target_y = int(np.clip(target_y, 0, self.height - 1))
        target_x = int(np.clip(target_x, 0, self.width - 1))

        agents_y = np.clip(self._rng.normal(target_y, self.foveal_sigma, num_foveal), 0, self.height - 1)
        agents_x = np.clip(self._rng.normal(target_x, self.foveal_sigma, num_foveal), 0, self.width - 1)
        memory = np.zeros_like(landscape, dtype=np.float32)

        for _ in range(steps):
            for idx in range(num_foveal):
                y = int(np.clip(agents_y[idx], 0, self.height - 1))
                x = int(np.clip(agents_x[idx], 0, self.width - 1))
                y0 = max(0, y - self.foveal_window)
                y1 = min(self.height, y + self.foveal_window + 1)
                x0 = max(0, x - self.foveal_window)
                x1 = min(self.width, x + self.foveal_window + 1)
                fitness = landscape[y0:y1, x0:x1] - (self.crowding_penalty * memory[y0:y1, x0:x1])
                if fitness.size:
                    local_y, local_x = self._nearest_peak(fitness, y - y0, x - x0)
                    agents_y[idx] = y0 + int(local_y)
                    agents_x[idx] = x0 + int(local_x)
                memory[int(agents_y[idx]), int(agents_x[idx])] += 0.5

        return np.column_stack((agents_y.astype(int), agents_x.astype(int))), memory

    def foveal_digest(
        self,
        foveal_positions: np.ndarray,
        *,
        grid_size: int = 24,
        top_n: int = 16,
    ) -> List[Dict[str, Any]]:
        retina = SwarmPhysarumRetina(num_agents=max(len(foveal_positions), 1))
        return retina.extract_topological_digest(
            foveal_positions,
            grid_size=grid_size,
            image_shape=(self.height, self.width),
            top_n=top_n,
        )

    def observe(
        self,
        nutrient_landscape: np.ndarray,
        *,
        num_scouts: int = 50,
        peripheral_steps: int = 15,
        num_foveal: int = 300,
        foveal_steps: int = 25,
        digest_grid_size: int = 24,
        digest_top_n: int = 16,
    ) -> FoveatedSaccadeResult:
        target = self.glance_peripheral(
            nutrient_landscape,
            num_scouts=num_scouts,
            steps=peripheral_steps,
        )
        positions, memory = self.saccade_foveal(
            nutrient_landscape,
            target.y,
            target.x,
            num_foveal=num_foveal,
            steps=foveal_steps,
        )
        digest = self.foveal_digest(positions, grid_size=digest_grid_size, top_n=digest_top_n)
        return FoveatedSaccadeResult(
            target=target,
            foveal_positions=positions,
            foveal_memory=memory,
            foveal_digest=digest,
        )


def nutrient_from_image(image: Image.Image) -> np.ndarray:
    retina = SwarmPhysarumRetina(num_agents=1)
    return retina.compute_nutrient_landscape(image)


def build_digest_row(
    result: FoveatedSaccadeResult,
    *,
    image_ref: str,
    image_w: int,
    image_h: int,
    peripheral_scouts: int,
    peripheral_steps: int,
    foveal_agents: int,
    foveal_steps: int,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    positions = result.foveal_positions.astype(float)
    mean_y = float(np.mean(positions[:, 0])) if len(positions) else 0.0
    mean_x = float(np.mean(positions[:, 1])) if len(positions) else 0.0
    spread = float(np.mean(np.linalg.norm(positions - np.array([mean_y, mean_x]), axis=1))) if len(positions) else 0.0
    row = {
        "event": "foveated_saccade_digest",
        "schema": _SCHEMA,
        "module_version": _MODULE_VERSION,
        "image_ref": image_ref,
        "image_w": int(image_w),
        "image_h": int(image_h),
        "peripheral_scouts": int(peripheral_scouts),
        "peripheral_steps": int(peripheral_steps),
        "foveal_agents": int(foveal_agents),
        "foveal_steps": int(foveal_steps),
        "target_x": int(result.target.x),
        "target_y": int(result.target.y),
        "target_salience": round(float(result.target.salience), 6),
        "foveal_mean_x": round(mean_x, 6),
        "foveal_mean_y": round(mean_y, 6),
        "foveal_spread": round(spread, 6),
        "foveal_digest": result.foveal_digest,
        "digest_count": len(result.foveal_digest),
        "ts": time.time() if now is None else float(now),
    }
    assert_payload_keys("foveated_saccades.jsonl", row, strict=True)
    return row


def write_observation(
    image: Image.Image,
    *,
    image_ref: str,
    ledger_path: Optional[Path] = None,
    seed: Optional[int] = None,
    peripheral_scouts: int = 50,
    peripheral_steps: int = 15,
    foveal_agents: int = 300,
    foveal_steps: int = 25,
) -> Dict[str, Any]:
    nutrient = nutrient_from_image(image)
    height, width = nutrient.shape
    vision = SwarmSaccadicVision(width, height, seed=seed)
    result = vision.observe(
        nutrient,
        num_scouts=peripheral_scouts,
        peripheral_steps=peripheral_steps,
        num_foveal=foveal_agents,
        foveal_steps=foveal_steps,
    )
    row = build_digest_row(
        result,
        image_ref=image_ref,
        image_w=width,
        image_h=height,
        peripheral_scouts=peripheral_scouts,
        peripheral_steps=peripheral_steps,
        foveal_agents=foveal_agents,
        foveal_steps=foveal_steps,
    )
    target = Path(ledger_path) if ledger_path is not None else _LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(target, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def proof_of_property() -> bool:
    vision = SwarmSaccadicVision(
        screen_width=960,
        screen_height=400,
        seed=61,
        peripheral_window=30,
        peripheral_blur_sigma=8.0,
        foveal_sigma=6.0,
    )
    nutrient = np.zeros((400, 960), dtype=np.float32)
    nutrient[250:350, 740:880] = 1.0

    result = vision.observe(
        nutrient,
        num_scouts=40,
        peripheral_steps=10,
        num_foveal=180,
        foveal_steps=15,
    )
    assert 250 <= result.target.y <= 350, "[FAIL] peripheral glance missed target y"
    assert 740 <= result.target.x <= 880, "[FAIL] peripheral glance missed target x"
    mean_y = float(np.mean(result.foveal_positions[:, 0]))
    mean_x = float(np.mean(result.foveal_positions[:, 1]))
    assert 250 <= mean_y <= 350, "[FAIL] foveal swarm drifted off target y"
    assert 740 <= mean_x <= 880, "[FAIL] foveal swarm drifted off target x"
    assert result.foveal_digest, "[FAIL] foveal digest is empty"
    return True


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run foveated swarm saccades on an image.")
    parser.add_argument("image", nargs="?", help="image path; omitted runs proof_of_property")
    parser.add_argument("--source", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--peripheral-scouts", type=int, default=50)
    parser.add_argument("--peripheral-steps", type=int, default=15)
    parser.add_argument("--foveal-agents", type=int, default=300)
    parser.add_argument("--foveal-steps", type=int, default=25)
    args = parser.parse_args(argv)

    if not args.image:
        print(json.dumps({"event": "foveated_saccade_digest", "proof": proof_of_property()}))
        return 0

    image_path = Path(args.image)
    row = write_observation(
        _load_image(image_path),
        image_ref=args.source or str(image_path),
        seed=args.seed,
        peripheral_scouts=args.peripheral_scouts,
        peripheral_steps=args.peripheral_steps,
        foveal_agents=args.foveal_agents,
        foveal_steps=args.foveal_steps,
    )
    print(json.dumps(row, indent=2))
    return 0


__all__ = [
    "FoveatedSaccadeConfig",
    "FoveatedSaccadeResult",
    "FoveatedSwarmSaccades",
    "SaccadeTarget",
    "SwarmSaccadicVision",
    "build_digest_row",
    "nutrient_from_image",
    "proof_of_property",
    "write_observation",
]


if __name__ == "__main__":
    raise SystemExit(main())
