#!/usr/bin/env python3
"""
Anticipatory stigmergy for local swarm simulations.

Agents write traces for where they are likely to be, then read those traces as
collision risk, opportunity, and prediction-error signals. This is predictive
local-field coordination only: no hardware spreading, sockets, or process control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np


@dataclass(frozen=True)
class PremonitionConfig:
    grid_size: int = 128
    horizon: int = 12
    decay: float = 0.96
    diffusion: float = 0.04
    future_deposit: float = 1.0
    collision_penalty: float = 0.9
    opportunity_reward: float = 0.6
    surprise_weight: float = 0.4
    eps: float = 1e-8


GlyphMode = Literal["composite", "future", "surprise"]


class StigmergicPremonitionField:
    """
    Agents mark expected future occupancy, then score current positions against it.

    Biology translation:
      predictive coding  -> expected future sensory state
      animal path memory -> likely movement corridors
      alarm pheromone    -> predicted collision/danger zones
      curiosity          -> reward prediction error reduction
    """

    def __init__(self, cfg: Optional[PremonitionConfig] = None) -> None:
        self.cfg = cfg or PremonitionConfig()
        if self.cfg.grid_size <= 1:
            raise ValueError("grid_size must be > 1")
        if self.cfg.horizon <= 0:
            raise ValueError("horizon must be positive")
        if not 0.0 <= self.cfg.decay <= 1.0:
            raise ValueError("decay must be in [0, 1]")
        if not 0.0 <= self.cfg.diffusion <= 0.25:
            raise ValueError("diffusion must be in [0, 0.25]")

        g = self.cfg.grid_size
        self.future = np.zeros((g, g), dtype=np.float32)
        self.surprise = np.zeros((g, g), dtype=np.float32)
        self.prev_positions: Optional[np.ndarray] = None
        self.prev_velocities: Optional[np.ndarray] = None

    def reset(self) -> None:
        self.future.fill(0.0)
        self.surprise.fill(0.0)
        self.prev_positions = None
        self.prev_velocities = None

    def _validate_positions(self, positions: np.ndarray) -> np.ndarray:
        pos = np.asarray(positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")
        return np.clip(pos[:, :2], 0.0, 1.0)

    def _idx(self, xy: np.ndarray) -> tuple[int, int]:
        g = self.cfg.grid_size
        clipped = np.clip(np.asarray(xy, dtype=np.float32)[:2], 0.0, 1.0)
        ij = np.floor(clipped * (g - 1)).astype(int)
        return int(ij[0]), int(ij[1])

    def _diffuse(self, field: np.ndarray) -> np.ndarray:
        if self.cfg.diffusion == 0.0:
            return field
        lap = (
            np.roll(field, 1, axis=0)
            + np.roll(field, -1, axis=0)
            + np.roll(field, 1, axis=1)
            + np.roll(field, -1, axis=1)
            - 4.0 * field
        )
        return np.maximum(field + self.cfg.diffusion * lap, 0.0).astype(np.float32)

    def _decay_and_diffuse(self) -> None:
        self.future = self._diffuse(self.future * self.cfg.decay)
        self.surprise = self._diffuse(self.surprise * self.cfg.decay)

    def _deposit(self, field: np.ndarray, pos: np.ndarray, amount: float) -> None:
        field[self._idx(pos)] += float(amount)

    def _sample(self, field: np.ndarray, pos: np.ndarray) -> float:
        return float(field[self._idx(pos)])

    def step(self, positions: np.ndarray) -> np.ndarray:
        pos = self._validate_positions(positions)

        if (
            self.prev_positions is None
            or self.prev_velocities is None
            or self.prev_positions.shape[0] != pos.shape[0]
        ):
            self.prev_positions = pos.copy()
            self.prev_velocities = np.zeros_like(pos)
            return np.zeros(len(pos), dtype=np.float32)

        velocities = pos - self.prev_positions
        self._decay_and_diffuse()
        rewards = np.zeros(len(pos), dtype=np.float32)

        # First write future occupancy traces so agents see one another's likely corridors.
        for current, velocity in zip(pos, velocities):
            for horizon in range(1, self.cfg.horizon + 1):
                predicted = current + velocity * horizon
                self._deposit(self.future, predicted, self.cfg.future_deposit / horizon)

        # Then score present states against predicted future density and own error.
        for idx, current in enumerate(pos):
            future_density = self._sample(self.future, current)
            predicted_here = self.prev_positions[idx] + self.prev_velocities[idx]
            prediction_error = float(np.linalg.norm(current - predicted_here))
            self._deposit(self.surprise, current, prediction_error)

            collision_risk = float(np.tanh(future_density))
            opportunity = 1.0 / (1.0 + future_density)
            surprise_cost = float(np.tanh(prediction_error * self.cfg.grid_size))
            rewards[idx] = (
                self.cfg.opportunity_reward * opportunity
                - self.cfg.collision_penalty * collision_risk
                - self.cfg.surprise_weight * surprise_cost
            )

        self.prev_positions = pos.copy()
        self.prev_velocities = velocities.copy()
        return rewards

    def sense(self, positions: np.ndarray) -> np.ndarray:
        pos = self._validate_positions(positions)
        obs = np.zeros((len(pos), 2), dtype=np.float32)
        for idx, current in enumerate(pos):
            obs[idx, 0] = self._sample(self.future, current)
            obs[idx, 1] = self._sample(self.surprise, current)
        return obs

    def glyph(self, mode: GlyphMode = "composite") -> str:
        if mode == "future":
            field = self.future
        elif mode == "surprise":
            field = self.surprise
        elif mode == "composite":
            field = self.future - self.surprise
        else:
            raise ValueError("mode must be one of: composite, future, surprise")

        shifted = field - float(field.min())
        if shifted.size == 0 or float(shifted.max()) <= 0.0:
            return ""

        chars = np.array(list(" .:-=+*#%@"))
        norm = shifted / (float(shifted.max()) + self.cfg.eps)
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)
        return "\n".join("".join(chars[row]) for row in idx.T[::-1])


def proof_of_property() -> bool:
    field = StigmergicPremonitionField(
        PremonitionConfig(grid_size=48, horizon=8, diffusion=0.02, future_deposit=1.0)
    )
    first = np.array([[0.20, 0.50], [0.80, 0.50]], dtype=np.float32)
    second = np.array([[0.28, 0.50], [0.72, 0.50]], dtype=np.float32)
    third = np.array([[0.36, 0.50], [0.64, 0.50]], dtype=np.float32)

    assert np.all(field.step(first) == 0.0)
    rewards_a = field.step(second)
    rewards_b = field.step(third)
    obs = field.sense(third)

    assert float(field.future.max()) > 0.0
    assert float(field.surprise.max()) > 0.0
    assert obs.shape == (2, 2)
    assert np.all(rewards_a < 0.6)
    assert np.all(rewards_b < 0.6)
    assert field.glyph("future")
    return True


if __name__ == "__main__":
    print("STIGMERGIC PREMONITION:", "PASS" if proof_of_property() else "FAIL")
