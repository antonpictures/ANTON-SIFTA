#!/usr/bin/env python3
"""Self-tuning four-channel weights for the unified stigmergic field."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Sequence

import numpy as np

FIELD_NAMES = ("memory", "prediction", "attention", "danger")
UNIFIED_FIELD_WEIGHT_KEYS = (
    "alpha_memory",
    "beta_prediction",
    "salience_weight",
    "delta_danger",
)


@dataclass(frozen=True)
class AdaptiveWeightsConfig:
    n_fields: int = 4
    lr: float = 0.03
    momentum: float = 0.90
    entropy_bonus: float = 0.02
    min_weight: float = 0.05
    max_weight: float = 3.0
    eps: float = 1e-8

    def __post_init__(self) -> None:
        if self.n_fields <= 0:
            raise ValueError("n_fields must be positive")
        if self.lr < 0.0:
            raise ValueError("lr must be non-negative")
        if not 0.0 <= self.momentum < 1.0:
            raise ValueError("momentum must be in [0, 1)")
        if self.entropy_bonus < 0.0:
            raise ValueError("entropy_bonus must be non-negative")
        if self.min_weight <= 0.0:
            raise ValueError("min_weight must be positive")
        if self.max_weight < self.min_weight:
            raise ValueError("max_weight must be >= min_weight")
        if self.eps <= 0.0:
            raise ValueError("eps must be positive")


class AdaptiveMemoryWeights:
    """
    Learns how much each sensed field should matter.

    Default field order:
      0 = memory
      1 = prediction
      2 = attention
      3 = danger

    The update rule rewards field weights whose centered feature values predict
    future reward, with a small entropy pressure to keep one channel from
    permanently swallowing the organism.
    """

    def __init__(
        self,
        cfg: AdaptiveWeightsConfig | None = None,
        **overrides: float | int,
    ) -> None:
        if cfg is not None and overrides:
            raise ValueError("pass either cfg or keyword overrides, not both")
        self.cfg = cfg or AdaptiveWeightsConfig()
        if overrides:
            self.cfg = replace(self.cfg, **overrides)
            self.cfg.__post_init__()

        self.weights = np.ones(self.cfg.n_fields, dtype=np.float32)
        self.velocity = np.zeros_like(self.weights)

        self.prev_features: np.ndarray | None = None
        self.prev_reward: float = 0.0

    def reset(self) -> None:
        self.weights.fill(1.0)
        self.velocity.fill(0.0)
        self.prev_features = None
        self.prev_reward = 0.0

    def _validate_features(self, features: np.ndarray) -> np.ndarray:
        arr = np.asarray(features, dtype=np.float32)
        if arr.ndim != 2:
            raise ValueError("features must have shape (n_agents, n_fields)")
        if arr.shape[1] != self.cfg.n_fields:
            raise ValueError("wrong number of fields")
        if not np.all(np.isfinite(arr)):
            raise ValueError("features must be finite")
        return arr

    def score(self, features: np.ndarray) -> np.ndarray:
        """Return one scalar field-metabolism score per agent."""
        arr = self._validate_features(features)
        return arr @ self.weights

    def update(self, features: np.ndarray, rewards: np.ndarray) -> np.ndarray:
        arr = self._validate_features(features)
        reward_arr = np.asarray(rewards, dtype=np.float32)

        if reward_arr.ndim != 1:
            raise ValueError("rewards must have shape (n_agents,)")
        if len(reward_arr) != len(arr):
            raise ValueError("rewards must match agent count")
        if not np.all(np.isfinite(reward_arr)):
            raise ValueError("rewards must be finite")

        reward_mean = float(np.mean(reward_arr))
        centered_features = arr - arr.mean(axis=0, keepdims=True)
        advantage = reward_arr - reward_mean

        grad = np.mean(centered_features * advantage[:, None], axis=0)

        # Encourage non-collapse: do not let one field dominate forever.
        p = self.weights / (self.weights.sum() + self.cfg.eps)
        entropy_grad = -np.log(p + self.cfg.eps) - 1.0
        grad += self.cfg.entropy_bonus * entropy_grad

        self.velocity = self.cfg.momentum * self.velocity + self.cfg.lr * grad
        self.weights += self.velocity
        self.weights = np.clip(
            self.weights,
            self.cfg.min_weight,
            self.cfg.max_weight,
        ).astype(np.float32)

        self.prev_features = arr.copy()
        self.prev_reward = reward_mean
        return self.weights.copy()

    def normalized(self) -> np.ndarray:
        return self.weights / (self.weights.sum() + self.cfg.eps)

    def apply_to_unified_field(self, field: Any, weights: Sequence[float] | None = None) -> Dict[str, float]:
        """
        Apply learned weights to `UnifiedFieldEngine` or `UnifiedStigmergicField`.

        The field configs are frozen, so this goes through the engine's validated
        `set_weights()` API instead of mutating `field.cfg` attributes directly.
        """
        if self.cfg.n_fields < 4:
            raise ValueError("at least four fields are required for unified-field application")
        values = np.asarray(self.weights if weights is None else weights, dtype=np.float32)
        if values.ndim != 1 or len(values) < 4:
            raise ValueError("weights must contain at least four values")
        if not np.all(np.isfinite(values)):
            raise ValueError("weights must be finite")
        if not hasattr(field, "set_weights"):
            raise TypeError("field must expose set_weights()")

        return field.set_weights(
            {
                key: float(value)
                for key, value in zip(UNIFIED_FIELD_WEIGHT_KEYS, values[:4])
            }
        )


def features_from_unified_field(field: Any, positions: np.ndarray) -> np.ndarray:
    """Sample memory, prediction, attention, danger features for each position."""
    pos = np.asarray(positions, dtype=np.float32)
    if pos.ndim != 2 or pos.shape[1] < 2:
        raise ValueError("positions must have shape (n_agents, >=2)")

    rows = [field.sense(current)[1] for current in pos]
    return np.asarray(rows, dtype=np.float32)


__all__ = [
    "AdaptiveMemoryWeights",
    "AdaptiveWeightsConfig",
    "FIELD_NAMES",
    "UNIFIED_FIELD_WEIGHT_KEYS",
    "features_from_unified_field",
]
