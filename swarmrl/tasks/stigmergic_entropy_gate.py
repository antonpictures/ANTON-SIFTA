# swarmrl/tasks/stigmergic_entropy_gate.py

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class EntropyGateConfig:
    grid_size: int = 96
    decay: float = 0.98
    diffusion: float = 0.06
    deposit_strength: float = 1.0

    trail_weight: float = 0.65
    novelty_weight: float = 0.45
    entropy_weight: float = 0.35
    crowding_penalty: float = 0.50

    local_window: int = 5
    eps: float = 1e-8


class StigmergicEntropyGate:
    """
    Agents write to a shared field.

    Reward:
      + follow existing useful traces
      + explore under-written space
      + increase local field entropy
      - over-crowd saturated trail cells
    """

    def __init__(self, config: EntropyGateConfig | None = None):
        self.cfg = config or EntropyGateConfig()
        g = self.cfg.grid_size

        self.field = np.zeros((g, g), dtype=np.float32)
        self.visit_count = np.zeros((g, g), dtype=np.float32)
        self.prev_positions: np.ndarray | None = None

    def reset(self) -> None:
        self.field.fill(0.0)
        self.visit_count.fill(0.0)
        self.prev_positions = None

    def _idx(self, xy: np.ndarray) -> tuple[int, int]:
        g = self.cfg.grid_size
        xy = np.clip(xy[:2], 0.0, 1.0)
        ij = np.floor(xy * (g - 1)).astype(int)
        return int(ij[0]), int(ij[1])

    def _diffuse(self) -> None:
        f = self.field
        lap = (
            np.roll(f, 1, axis=0)
            + np.roll(f, -1, axis=0)
            + np.roll(f, 1, axis=1)
            + np.roll(f, -1, axis=1)
            - 4.0 * f
        )
        self.field = np.maximum(f + self.cfg.diffusion * lap, 0.0)

    def _local_patch(self, i: int, j: int) -> np.ndarray:
        r = self.cfg.local_window // 2
        return self.field[
            max(0, i - r): i + r + 1,
            max(0, j - r): j + r + 1,
        ]

    def _entropy(self, patch: np.ndarray) -> float:
        total = float(patch.sum()) + self.cfg.eps
        p = patch.ravel() / total
        p = p[p > self.cfg.eps]

        if len(p) == 0:
            return 0.0

        h = -float(np.sum(p * np.log(p)))
        h_max = np.log(len(p) + self.cfg.eps)
        return h / (h_max + self.cfg.eps)

    def _deposit_line(self, a: np.ndarray, b: np.ndarray, amount: float) -> None:
        dist = np.linalg.norm(b[:2] - a[:2])
        steps = max(2, int(dist * self.cfg.grid_size * 2))

        for t in np.linspace(0.0, 1.0, steps):
            p = a * (1.0 - t) + b * t
            i, j = self._idx(p)
            self.field[i, j] += amount / steps
            self.visit_count[i, j] += 1.0 / steps

    def step(self, positions: np.ndarray) -> np.ndarray:
        positions = np.asarray(positions, dtype=np.float32)

        if positions.ndim != 2 or positions.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")

        positions = positions[:, :2]

        if self.prev_positions is None:
            self.prev_positions = positions.copy()
            return np.zeros(len(positions), dtype=np.float32)

        self.field *= self.cfg.decay
        self._diffuse()

        rewards = np.zeros(len(positions), dtype=np.float32)

        for k, pos in enumerate(positions):
            i, j = self._idx(pos)

            before_field = float(self.field[i, j])
            before_visits = float(self.visit_count[i, j])
            entropy_before = self._entropy(self._local_patch(i, j))

            movement = np.linalg.norm(pos - self.prev_positions[k])
            deposit = self.cfg.deposit_strength * np.tanh(movement * self.cfg.grid_size)

            self._deposit_line(self.prev_positions[k], pos, deposit)

            entropy_after = self._entropy(self._local_patch(i, j))

            trail_reward = np.tanh(before_field)
            novelty_reward = 1.0 / (1.0 + before_visits)
            entropy_gain = entropy_after - entropy_before
            crowding = np.tanh(before_visits / 10.0)

            rewards[k] = (
                self.cfg.trail_weight * trail_reward
                + self.cfg.novelty_weight * novelty_reward
                + self.cfg.entropy_weight * entropy_gain
                - self.cfg.crowding_penalty * crowding
            )

        self.prev_positions = positions.copy()
        return rewards

    def glyph(self) -> str:
        if self.field.max() <= 0:
            return ""

        norm = self.field / (self.field.max() + self.cfg.eps)
        chars = np.array(list(" .:-=+*#%@"))
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)

        return "\n".join("".join(chars[row]) for row in idx.T[::-1])
