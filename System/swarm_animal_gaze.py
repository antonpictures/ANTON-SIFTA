#!/usr/bin/env python3
"""Animal gaze: motion, novelty, and inhibition for active screen vision."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from scipy.ndimage import gaussian_filter, sobel
except Exception:  # pragma: no cover - exercised only on minimal installs
    def gaussian_filter(x: np.ndarray, sigma: float) -> np.ndarray:
        return x

    def sobel(x: np.ndarray, axis: int) -> np.ndarray:
        return np.gradient(x, axis=axis)


@dataclass
class AnimalGazeConfig:
    scouts: int = 80
    foveal_agents: int = 350
    peripheral_steps: int = 12
    foveal_steps: int = 30
    peripheral_sigma: float = 18.0
    inhibition_decay: float = 0.88
    inhibition_strength: float = 0.78
    motion_weight: float = 1.25
    edge_weight: float = 0.75
    intensity_weight: float = 0.35
    novelty_weight: float = 1.10
    memory_penalty: float = 0.48
    scout_jump: int = 28
    foveal_window: int = 4
    seed: int | None = None
    eps: float = 1e-8


class SwarmAnimalGaze:
    """Animal-inspired active vision with curiosity bounded by real evidence."""

    def __init__(self, width: int, height: int, cfg: AnimalGazeConfig | None = None):
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        self.width = int(width)
        self.height = int(height)
        self.cfg = cfg or AnimalGazeConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self.prev_frame: np.ndarray | None = None
        self.saliency = np.zeros((self.height, self.width), dtype=np.float32)
        self.inhibition = np.zeros((self.height, self.width), dtype=np.float32)
        self.foveal_memory = np.zeros((self.height, self.width), dtype=np.float32)

    def reset(self) -> None:
        self.prev_frame = None
        self.saliency.fill(0)
        self.inhibition.fill(0)
        self.foveal_memory.fill(0)

    def _validate_frame(self, frame: np.ndarray) -> np.ndarray:
        arr = np.asarray(frame, dtype=np.float32)
        if arr.shape != (self.height, self.width):
            raise ValueError(f"frame must have shape {(self.height, self.width)}")
        return arr

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=np.float32)
        span = float(arr.max() - arr.min()) if arr.size else 0.0
        if span <= self.cfg.eps:
            return np.zeros_like(arr, dtype=np.float32)
        return ((arr - float(arr.min())) / (span + self.cfg.eps)).astype(np.float32)

    @staticmethod
    def _nearest_peak(patch: np.ndarray, local_y: int, local_x: int) -> tuple[int, int]:
        if patch.size == 0:
            return 0, 0
        peak = float(np.max(patch))
        candidates = np.argwhere(np.isclose(patch, peak))
        if len(candidates) == 0:
            return tuple(int(v) for v in np.unravel_index(int(np.argmax(patch)), patch.shape))
        anchor = np.array([local_y, local_x], dtype=np.float32)
        distances = np.sum((candidates.astype(np.float32) - anchor) ** 2, axis=1)
        return tuple(int(v) for v in candidates[int(np.argmin(distances))])

    def _build_nutrient_landscape(self, frame: np.ndarray) -> np.ndarray:
        frame = self._normalize(self._validate_frame(frame))
        gx = sobel(frame, axis=1)
        gy = sobel(frame, axis=0)
        edges = self._normalize(np.sqrt(gx * gx + gy * gy))
        motion = (
            np.zeros_like(frame)
            if self.prev_frame is None
            else self._normalize(np.abs(frame - self.prev_frame))
        )
        visual_evidence = self._normalize(
            self.cfg.motion_weight * motion
            + self.cfg.edge_weight * edges
            + self.cfg.intensity_weight * frame
        )
        novelty = (1.0 / (1.0 + self.foveal_memory)).astype(np.float32)
        curiosity = self.cfg.novelty_weight * novelty * visual_evidence
        nutrient = visual_evidence + curiosity - self.cfg.inhibition_strength * self.inhibition
        self.prev_frame = frame.copy()
        return self._normalize(np.maximum(nutrient, 0.0))

    def glance(self, frame: np.ndarray) -> tuple[int, int]:
        nutrient = self._build_nutrient_landscape(frame)
        ys = self.rng.integers(0, self.height, self.cfg.scouts).astype(np.float32)
        xs = self.rng.integers(0, self.width, self.cfg.scouts).astype(np.float32)
        self.saliency.fill(0)

        for _ in range(self.cfg.peripheral_steps):
            for k in range(self.cfg.scouts):
                y, x = int(ys[k]), int(xs[k])
                r = self.cfg.scout_jump
                y0, y1 = max(0, y - r), min(self.height, y + r + 1)
                x0, x1 = max(0, x - r), min(self.width, x + r + 1)
                patch = nutrient[y0:y1, x0:x1]
                if patch.size == 0:
                    continue
                py, px = self._nearest_peak(patch, y - y0, x - x0)
                ys[k] = y0 + py
                xs[k] = x0 + px
                self.saliency[int(ys[k]), int(xs[k])] += 1.0

        self.saliency = gaussian_filter(self.saliency, sigma=self.cfg.peripheral_sigma)
        target_y, target_x = self._nearest_peak(
            self.saliency,
            self.height // 2,
            self.width // 2,
        )
        return int(target_y), int(target_x)

    def saccade(self, frame: np.ndarray, target_y: int, target_x: int) -> np.ndarray:
        nutrient = self._build_nutrient_landscape(frame)
        ys = np.clip(self.rng.normal(target_y, 10, self.cfg.foveal_agents), 0, self.height - 1)
        xs = np.clip(self.rng.normal(target_x, 10, self.cfg.foveal_agents), 0, self.width - 1)

        for _ in range(self.cfg.foveal_steps):
            for k in range(self.cfg.foveal_agents):
                y, x = int(ys[k]), int(xs[k])
                r = self.cfg.foveal_window
                y0, y1 = max(0, y - r), min(self.height, y + r + 1)
                x0, x1 = max(0, x - r), min(self.width, x + r + 1)
                food = nutrient[y0:y1, x0:x1]
                memory = self.foveal_memory[y0:y1, x0:x1]
                fitness = food - self.cfg.memory_penalty * memory
                py, px = self._nearest_peak(fitness, y - y0, x - x0)
                ys[k] = y0 + py
                xs[k] = x0 + px
                self.foveal_memory[int(ys[k]), int(xs[k])] += 1.0

        self._mark_inhibition(target_y, target_x)
        return np.column_stack((ys.astype(int), xs.astype(int)))

    def _mark_inhibition(self, y: int, x: int, radius: int = 80) -> None:
        self.inhibition *= self.cfg.inhibition_decay
        y0, y1 = max(0, y - radius), min(self.height, y + radius + 1)
        x0, x1 = max(0, x - radius), min(self.width, x + radius + 1)
        self.inhibition[y0:y1, x0:x1] += 1.0
        self.inhibition = self._normalize(gaussian_filter(self.inhibition, sigma=20))

    def observe(self, frame: np.ndarray) -> dict:
        y, x = self.glance(frame)
        points = self.saccade(frame, y, x)
        return {
            "target_y": y,
            "target_x": x,
            "foveal_points": points,
            "saliency": self.saliency.copy(),
            "memory": self.foveal_memory.copy(),
            "inhibition": self.inhibition.copy(),
        }


def proof_of_property() -> bool:
    frame = np.zeros((120, 200), dtype=np.float32)
    frame[70:105, 145:185] = 1.0
    gaze = SwarmAnimalGaze(
        200,
        120,
        AnimalGazeConfig(
            scouts=48,
            foveal_agents=120,
            peripheral_steps=8,
            foveal_steps=10,
            peripheral_sigma=5.0,
            seed=555,
        ),
    )
    result = gaze.observe(frame)
    points = result["foveal_points"]
    assert 70 <= result["target_y"] <= 105
    assert 145 <= result["target_x"] <= 185
    assert 70 <= float(np.mean(points[:, 0])) <= 105
    assert 145 <= float(np.mean(points[:, 1])) <= 185
    return True
