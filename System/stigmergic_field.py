"""General-purpose stigmergic field — the reusable principle.

This module extracts the core mechanism from the Bell theorem app into
a general-purpose component that can be applied to any domain where
agents interact through a shared, history-dependent environment.

The governing equation (same at every scale):

    ∂φ/∂t = D∇²φ − λφ + f(agents)         (field evolution)
    agent_response ∝ g(φ, ∇φ)              (agent coupling)

    | Scale    | Field φ               | Agents         | Coupling g        |
    |----------|-----------------------|----------------|-------------------|
    | Quantum  | pilot wave ψ          | particles      | quantum pot Q     |
    | Biology  | pheromone conc        | ants/termites  | chemotaxis ∇φ     |
    | SIFTA    | StigmergicField       | swimmers       | nonlinear feedback|

Two-timescale memory:
    fast_layer: volatile traces — recent context, rapid decay
    slow_layer: persistent pattern — accumulated structure, slow decay

Gradient coupling:
    ∂φ/∂x provides directional information (chemotaxis / quantum potential)

Research spine:
    Bio: Grassé 1959; Bonabeau/Dorigo/Theraulaz 1999; Bertozzi 2014
    Physics: de Broglie 1927; Bohm 1952; Hall 2018; Vervoort 2024
    Source guard: System.swarm_bell_research_spine separates verified
        support, theoretical bridges, and quarantined unverified citations.
    SIFTA: Bell app demonstration — SIM_ONLY classical contextual analogue
        via field coupling; not a claimed physical cause of quantum Bell
        violations.

SIFTA Non-Proliferation Public License v1.0 applies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class FieldConfig:
    """Configuration for a StigmergicField instance."""
    n_bins: int = 72
    n_channels: int = 2
    fast_decay: float = 0.95
    slow_decay: float = 0.999
    fast_weight: float = 0.3
    slow_weight: float = 0.7
    threshold: float = 4.0


class StigmergicField:
    """Two-timescale stigmergic field with gradient coupling.

    This is the general principle extracted from the Bell theorem app.
    Any system where agents deposit traces and read the accumulated
    pattern can use this field to create contextual, history-dependent
    behavior — the same mechanism that produces Bell violation in our
    classical analogue.
    """

    def __init__(self, config: FieldConfig | None = None) -> None:
        cfg = config or FieldConfig()
        self.n_bins = cfg.n_bins
        self.n_channels = cfg.n_channels
        self._fast_decay = cfg.fast_decay
        self._slow_decay = cfg.slow_decay
        self._fast_weight = cfg.fast_weight
        self._slow_weight = cfg.slow_weight
        self.threshold = cfg.threshold

        shape = (self.n_bins, self.n_channels)
        self.fast_layer = np.zeros(shape, dtype=np.float64)
        self.slow_layer = np.zeros(shape, dtype=np.float64)

        self._deposit_count = 0
        self._read_count = 0

    # ── deposit ───────────────────────────────────────────────────

    def deposit(self, bin_idx: int, channel: int, amount: float = 1.0) -> None:
        """Agent deposits a trace into both field layers."""
        bi = int(bin_idx) % self.n_bins
        ch = int(channel) % self.n_channels
        self.fast_layer[bi, ch] += amount
        self.slow_layer[bi, ch] += amount
        self._deposit_count += 1

    # ── read ──────────────────────────────────────────────────────

    def read_correlation(self, bin_idx: int) -> float | None:
        """Read the blended two-timescale correlation at a bin.

        Returns the weighted blend of fast and slow field correlations,
        or None if insufficient data at this bin.

        For a 2-channel field, correlation = (ch0 - ch1) / total.
        """
        bi = int(bin_idx) % self.n_bins
        self._read_count += 1

        fast_total = float(np.sum(self.fast_layer[bi]))
        slow_total = float(np.sum(self.slow_layer[bi]))
        total = fast_total + slow_total

        if total < self.threshold:
            return None

        fast_corr = 0.0
        slow_corr = 0.0
        if self.n_channels >= 2:
            if fast_total > 1.0:
                fast_corr = (self.fast_layer[bi, 0] - self.fast_layer[bi, 1]) / fast_total
            if slow_total > 1.0:
                slow_corr = (self.slow_layer[bi, 0] - self.slow_layer[bi, 1]) / slow_total

        w_slow = self._slow_weight if slow_total > 2.0 else 0.0
        w_fast = self._fast_weight if fast_total > 2.0 else 0.0
        w_sum = w_slow + w_fast
        if w_sum <= 0:
            return 0.0
        return (w_fast * fast_corr + w_slow * slow_corr) / w_sum

    # ── gradient ──────────────────────────────────────────────────

    def read_gradient(self, bin_idx: int) -> float:
        """Read the slow-field correlation gradient ∂φ/∂x at a bin.

        Bio analog: chemotactic gradient ∇φ
        Physics analog: quantum potential ∇Q
        """
        bi = int(bin_idx) % self.n_bins
        if bi <= 0 or bi >= self.n_bins - 1:
            return 0.0

        left_t = float(np.sum(self.slow_layer[bi - 1]))
        right_t = float(np.sum(self.slow_layer[bi + 1]))
        if left_t < 1.0 or right_t < 1.0:
            return 0.0

        if self.n_channels >= 2:
            left_c = (self.slow_layer[bi - 1, 0] - self.slow_layer[bi - 1, 1]) / left_t
            right_c = (self.slow_layer[bi + 1, 0] - self.slow_layer[bi + 1, 1]) / right_t
            return (right_c - left_c) / 2.0
        return 0.0

    # ── decay ─────────────────────────────────────────────────────

    def decay(self) -> None:
        """Apply timescale-specific decay to both layers."""
        self.fast_layer *= self._fast_decay
        self.slow_layer *= self._slow_decay

    # ── field energy ──────────────────────────────────────────────

    @property
    def energy(self) -> float:
        """Total field energy: ∫|φ|² (combined both layers)."""
        combined = self.fast_layer + self.slow_layer
        return float(np.sum(combined ** 2))

    @property
    def fast_energy(self) -> float:
        return float(np.sum(self.fast_layer ** 2))

    @property
    def slow_energy(self) -> float:
        return float(np.sum(self.slow_layer ** 2))

    # ── combined view ─────────────────────────────────────────────

    @property
    def combined(self) -> np.ndarray:
        """Combined field view for visualization."""
        return self.fast_layer + self.slow_layer

    # ── snapshot ──────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot of field state."""
        return {
            "n_bins": self.n_bins,
            "n_channels": self.n_channels,
            "deposits": self._deposit_count,
            "reads": self._read_count,
            "energy": round(self.energy, 4),
            "fast_energy": round(self.fast_energy, 4),
            "slow_energy": round(self.slow_energy, 4),
            "fast_decay": self._fast_decay,
            "slow_decay": self._slow_decay,
        }


def nonlinear_flip_probability(
    disagreement: float,
    gradient: float,
    kappa: float,
    max_prob: float = 0.50,
    gradient_scale: float = 0.03,
) -> float:
    """The general nonlinear coupling function.

    This is the function that creates Bell violation. It maps the
    disagreement between an agent's local prediction and the field's
    accumulated pattern into a probability of flipping the agent's
    decision.

    Bio: probability of path switching ∝ |pheromone_gradient|²
    Physics: pilot-wave velocity ∝ |∇S|; quantum potential ∝ |∇²R/R|
    SIFTA: flip_prob = κ × (|disagreement|/3)² + κ × |gradient| × scale
    """
    base = kappa * (abs(disagreement) / 3.0) ** 2
    grad = kappa * abs(gradient) * gradient_scale
    return min(base + grad, max_prob)
