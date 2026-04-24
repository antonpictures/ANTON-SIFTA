# swarmrl/tasks/stigmergic_boot_glyph.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass
class GlyphTraceConfig:
    grid_size: int = 96
    decay: float = 0.985
    diffusion: float = 0.08
    deposit: float = 1.0
    novelty_weight: float = 0.35
    trail_weight: float = 0.55
    curvature_weight: float = 0.10
    saturation: float = 8.0
    epsilon: float = 1e-8


class StigmergicBootGlyph:
    """
    Stigmergic reward field with boot-persistent glyph traces.

    Agents write motion traces into a decaying/diffusing field.
    Reward comes from:
      1. following useful traces,
      2. creating novel structure,
      3. maintaining curved/non-degenerate trajectories.
    """

    def __init__(self, config: GlyphTraceConfig | None = None):
        self.config = config or GlyphTraceConfig()
        g = self.config.grid_size
        self.field = np.zeros((g, g), dtype=np.float32)
        self.prev_positions: np.ndarray | None = None
        self.prev_velocities: np.ndarray | None = None

    def reset(self) -> None:
        self.field.fill(0.0)
        self.prev_positions = None
        self.prev_velocities = None

    def _grid_index(self, xy: np.ndarray) -> tuple[int, int]:
        g = self.config.grid_size
        clipped = np.clip(xy, 0.0, 1.0)
        ij = np.floor(clipped * (g - 1)).astype(int)
        return int(ij[0]), int(ij[1])

    def _diffuse(self) -> None:
        c = self.config.diffusion
        if c <= 0.0:
            return

        f = self.field
        lap = (
            np.roll(f, 1, axis=0)
            + np.roll(f, -1, axis=0)
            + np.roll(f, 1, axis=1)
            + np.roll(f, -1, axis=1)
            - 4.0 * f
        )
        self.field = np.maximum(f + c * lap, 0.0)

    def _sample(self, xy: np.ndarray) -> float:
        i, j = self._grid_index(xy)
        return float(self.field[i, j])

    def _deposit_segment(self, a: np.ndarray, b: np.ndarray, amount: float) -> None:
        dist = np.linalg.norm(b - a)
        steps = max(2, int(dist * self.config.grid_size * 2))

        for t in np.linspace(0.0, 1.0, steps):
            p = a * (1.0 - t) + b * t
            i, j = self._grid_index(p)
            self.field[i, j] += amount / steps

    def step(self, positions: Sequence[Sequence[float]]) -> np.ndarray:
        pos = np.asarray(positions, dtype=np.float32)

        if pos.ndim != 2 or pos.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")

        pos = pos[:, :2]

        if self.prev_positions is None:
            self.prev_positions = pos.copy()
            self.prev_velocities = np.zeros_like(pos)
            return np.zeros(len(pos), dtype=np.float32)

        cfg = self.config

        self.field *= cfg.decay
        self._diffuse()

        vel = pos - self.prev_positions
        rewards = np.zeros(len(pos), dtype=np.float32)

        for k, (old, new, v) in enumerate(zip(self.prev_positions, pos, vel)):
            before = self._sample(new)

            speed = np.linalg.norm(v) + cfg.epsilon
            amount = cfg.deposit * np.tanh(speed * cfg.grid_size)

            self._deposit_segment(old, new, amount)

            after = self._sample(new)
            novelty = 1.0 / (1.0 + before)
            trail = np.tanh(after / cfg.saturation)

            pv = self.prev_velocities[k]
            pv_norm = np.linalg.norm(pv) + cfg.epsilon
            curvature = 1.0 - float(np.dot(v, pv) / (speed * pv_norm))
            curvature = np.clip(curvature, 0.0, 2.0) * 0.5

            rewards[k] = (
                cfg.novelty_weight * novelty
                + cfg.trail_weight * trail
                + cfg.curvature_weight * curvature
            )

        self.prev_positions = pos.copy()
        self.prev_velocities = vel.copy()

        return rewards

    def snapshot(self) -> np.ndarray:
        return self.field.copy()

    def boot_glyph(self, threshold: float = 0.25) -> str:
        f = self.field
        if f.max() <= 0:
            return ""

        norm = f / (f.max() + self.config.epsilon)
        chars = np.array(list(" .:-=+*#%@"))
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)

        mask = norm >= threshold
        idx = np.where(mask, idx, 0)

        return "\n".join("".join(chars[row]) for row in idx.T[::-1])
