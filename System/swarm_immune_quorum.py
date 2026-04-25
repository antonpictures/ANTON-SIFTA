# System/swarm_immune_quorum.py

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class ImmuneQuorumConfig:
    grid_size: int = 128
    decay: float = 0.985
    diffusion: float = 0.05

    signal_deposit: float = 1.0
    danger_deposit: float = 1.5
    repair_deposit: float = 0.8

    quorum_threshold: float = 0.35
    inflammation_limit: float = 2.5

    follow_weight: float = 0.55
    repair_weight: float = 0.75
    danger_penalty: float = 0.65
    diversity_weight: float = 0.25

    eps: float = 1e-8


class SwarmImmuneQuorum:
    """
    Biology translation:
      pheromone field  -> cytokine-like signal
      danger field     -> damage / pathogen marker
      repair field     -> wound-healing trace
      quorum gate      -> collective immune activation

    Agents coordinate by writing and reading local biochemical-like fields.
    """

    def __init__(self, cfg: ImmuneQuorumConfig | None = None):
        self.cfg = cfg or ImmuneQuorumConfig()
        g = self.cfg.grid_size

        self.signal = np.zeros((g, g), dtype=np.float32)
        self.danger = np.zeros((g, g), dtype=np.float32)
        self.repair = np.zeros((g, g), dtype=np.float32)
        self.prev_positions: np.ndarray | None = None

    def reset(self):
        self.signal.fill(0)
        self.danger.fill(0)
        self.repair.fill(0)
        self.prev_positions = None

    def _idx(self, xy):
        g = self.cfg.grid_size
        xy = np.clip(xy[:2], 0.0, 1.0)
        ij = np.floor(xy * (g - 1)).astype(int)
        return int(ij[0]), int(ij[1])

    def _diffuse(self, field):
        lap = (
            np.roll(field, 1, 0)
            + np.roll(field, -1, 0)
            + np.roll(field, 1, 1)
            + np.roll(field, -1, 1)
            - 4 * field
        )
        return np.maximum(field + self.cfg.diffusion * lap, 0.0)

    def _decay_and_diffuse(self):
        self.signal = self._diffuse(self.signal * self.cfg.decay)
        self.danger = self._diffuse(self.danger * self.cfg.decay)
        self.repair = self._diffuse(self.repair * self.cfg.decay)

    def _sample(self, field, pos):
        i, j = self._idx(pos)
        return float(field[i, j])

    def _deposit(self, field, pos, amount):
        i, j = self._idx(pos)
        field[i, j] += amount

    def inject_damage(self, centers: np.ndarray, radius: float = 0.04):
        """
        External wound/pathogen event.
        centers shape: (n_events, 2)
        """
        centers = np.asarray(centers, dtype=np.float32)
        if centers.ndim != 2 or centers.shape[1] < 2:
            raise ValueError("centers must have shape (n_events, >=2)")
        if radius <= 0.0:
            raise ValueError("radius must be positive")

        for x in np.linspace(0, 1, self.cfg.grid_size):
            for y in np.linspace(0, 1, self.cfg.grid_size):
                p = np.array([x, y], dtype=np.float32)
                if np.any(np.linalg.norm(centers - p, axis=1) < radius):
                    i, j = self._idx(p)
                    self.danger[i, j] += self.cfg.danger_deposit
        for center in centers[:, :2]:
            i, j = self._idx(center)
            if self.danger[i, j] <= 0.0:
                self.danger[i, j] += self.cfg.danger_deposit

    def sense(self, positions: np.ndarray) -> np.ndarray:
        positions = np.asarray(positions, dtype=np.float32)
        if positions.ndim != 2 or positions.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")
        positions = positions[:, :2]
        obs = np.zeros((len(positions), 3), dtype=np.float32)

        for k, p in enumerate(positions):
            obs[k, 0] = self._sample(self.signal, p)
            obs[k, 1] = self._sample(self.danger, p)
            obs[k, 2] = self._sample(self.repair, p)

        return obs

    def step(self, positions: np.ndarray) -> np.ndarray:
        positions = np.asarray(positions, dtype=np.float32)
        if positions.ndim != 2 or positions.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")
        positions = positions[:, :2]

        if self.prev_positions is None or self.prev_positions.shape[0] != positions.shape[0]:
            self.prev_positions = positions.copy()
            return np.zeros(len(positions), dtype=np.float32)

        self._decay_and_diffuse()

        rewards = np.zeros(len(positions), dtype=np.float32)

        for k, p in enumerate(positions):
            movement = np.linalg.norm(p - self.prev_positions[k])
            motile = np.tanh(movement * self.cfg.grid_size)

            sig = self._sample(self.signal, p)
            dmg = self._sample(self.danger, p)
            rep = self._sample(self.repair, p)

            quorum = sig / (sig + self.cfg.quorum_threshold + self.cfg.eps)
            inflammation = np.tanh(dmg / self.cfg.inflammation_limit)

            # Immune-like behavior:
            # low signal: explore and mark
            # high danger + quorum: repair
            # excessive danger: penalty unless repair rises
            self._deposit(self.signal, p, self.cfg.signal_deposit * motile)

            if dmg > self.cfg.quorum_threshold and quorum > 0.5:
                self._deposit(self.repair, p, self.cfg.repair_deposit * quorum)
                self.danger[self._idx(p)] *= 0.92

            diversity = 1.0 / (1.0 + sig)

            rewards[k] = (
                self.cfg.follow_weight * quorum
                + self.cfg.repair_weight * rep
                + self.cfg.diversity_weight * diversity
                - self.cfg.danger_penalty * inflammation * (1.0 - rep / (1.0 + rep))
            )

        self.prev_positions = positions.copy()
        return rewards

    def glyph(self, mode: str = "composite") -> str:
        if mode == "danger":
            field = self.danger
        elif mode == "repair":
            field = self.repair
        elif mode == "signal":
            field = self.signal
        else:
            field = self.signal + 2.0 * self.repair - self.danger

        chars = np.array(list(" .:-=+*#%@"))
        f = field - field.min()
        if f.max() <= 0:
            return ""

        norm = f / (f.max() + self.cfg.eps)
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)
        return "\n".join("".join(chars[row]) for row in idx.T[::-1])
