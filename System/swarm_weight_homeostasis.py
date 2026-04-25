#!/usr/bin/env python3
"""Homeostatic memory for unified-field weight regulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence

import numpy as np

UNIFIED_FIELD_WEIGHT_KEYS = (
    "alpha_memory",
    "beta_prediction",
    "salience_weight",
    "delta_danger",
)


@dataclass(frozen=True)
class HomeostasisConfig:
    target_entropy: float = 0.85
    correction_rate: float = 0.04
    drift_decay: float = 0.97
    min_weight: float = 0.05
    max_weight: float = 5.0
    eps: float = 1e-8

    def __post_init__(self) -> None:
        if not 0.0 <= self.target_entropy <= 1.0:
            raise ValueError("target_entropy must be in [0, 1]")
        if self.correction_rate < 0.0:
            raise ValueError("correction_rate must be non-negative")
        if not 0.0 <= self.drift_decay <= 1.0:
            raise ValueError("drift_decay must be in [0, 1]")
        if self.min_weight <= 0.0:
            raise ValueError("min_weight must be positive")
        if self.max_weight < self.min_weight:
            raise ValueError("max_weight must be >= min_weight")
        if self.eps <= 0.0:
            raise ValueError("eps must be positive")


class WeightHomeostasis:
    """
    Keeps field weights alive but stable.

    Evolutionary tuner = explores better weights.
    Homeostasis = prevents one channel from becoming a tyrant.
    """

    def __init__(self, n_fields: int = 4, cfg: HomeostasisConfig | None = None) -> None:
        if n_fields <= 1:
            raise ValueError("n_fields must be > 1")
        self.cfg = cfg or HomeostasisConfig()
        self.drift = np.zeros(int(n_fields), dtype=np.float32)
        self.last_entropy = 1.0

    def reset(self) -> None:
        self.drift.fill(0.0)
        self.last_entropy = 1.0

    def _validate_weights(self, weights: Sequence[float] | np.ndarray) -> np.ndarray:
        w = np.asarray(weights, dtype=np.float32)
        if w.ndim != 1:
            raise ValueError("weights must have shape (n_fields,)")
        if len(w) != len(self.drift):
            raise ValueError("weights must match n_fields")
        if not np.all(np.isfinite(w)):
            raise ValueError("weights must be finite")
        if np.any(w < 0.0):
            raise ValueError("weights must be non-negative")
        return w

    def entropy(self, weights: Sequence[float] | np.ndarray) -> float:
        w = self._validate_weights(weights)
        total = float(w.sum()) + self.cfg.eps
        p = w / total
        return float(-np.sum(p * np.log(p + self.cfg.eps)) / np.log(len(w)))

    def regulate(self, weights: Sequence[float] | np.ndarray) -> np.ndarray:
        w = self._validate_weights(weights)
        total = float(w.sum()) + self.cfg.eps
        p = w / total

        entropy = float(-np.sum(p * np.log(p + self.cfg.eps)) / np.log(len(w)))
        dominance = p - (1.0 / len(w))

        if entropy < self.cfg.target_entropy:
            self.drift = (
                self.cfg.drift_decay * self.drift
                - self.cfg.correction_rate * dominance
            ).astype(np.float32)
        else:
            self.drift = (self.drift * self.cfg.drift_decay).astype(np.float32)

        self.last_entropy = entropy
        regulated = w + self.drift
        return np.clip(regulated, self.cfg.min_weight, self.cfg.max_weight).astype(np.float32)

    def regulate_dict(
        self,
        weights: Mapping[str, float],
        *,
        keys: Sequence[str] = UNIFIED_FIELD_WEIGHT_KEYS,
    ) -> Dict[str, float]:
        ordered = np.asarray([float(weights[key]) for key in keys], dtype=np.float32)
        regulated = self.regulate(ordered)
        return {str(key): float(value) for key, value in zip(keys, regulated)}

    def apply_to_unified_field(
        self,
        engine: Any,
        weights: Mapping[str, float] | Sequence[float] | np.ndarray,
        *,
        keys: Sequence[str] = UNIFIED_FIELD_WEIGHT_KEYS,
    ) -> Dict[str, float]:
        """Regulate candidate weights and apply them through `engine.set_weights()`."""
        if not hasattr(engine, "set_weights"):
            raise TypeError("engine must expose set_weights()")
        if isinstance(weights, Mapping):
            updates = self.regulate_dict(weights, keys=keys)
        else:
            regulated = self.regulate(weights)
            updates = {str(key): float(value) for key, value in zip(keys, regulated)}
        return engine.set_weights(updates)


def regulate_tuning_row(
    row: Mapping[str, Any],
    homeostasis: WeightHomeostasis | None = None,
    *,
    keys: Sequence[str] = UNIFIED_FIELD_WEIGHT_KEYS,
) -> Dict[str, float]:
    """Regulate an `EvolutionaryFieldTuner.tune()` row's `best_weights` payload."""
    weights = row.get("best_weights")
    if not isinstance(weights, Mapping):
        raise ValueError("row must contain best_weights")
    homeo = homeostasis or WeightHomeostasis(n_fields=len(keys))
    return homeo.regulate_dict(weights, keys=keys)


__all__ = [
    "HomeostasisConfig",
    "UNIFIED_FIELD_WEIGHT_KEYS",
    "WeightHomeostasis",
    "regulate_tuning_row",
]
