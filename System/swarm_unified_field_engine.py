#!/usr/bin/env python3
"""
Unified Field Engine: memory + prediction + attention + repair - danger.

Agents are minimal: they sense the local gradient of a shared environmental
tensor and move reactively. The environment carries the computation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

import numpy as np

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "unified_field_engine.jsonl"
_SCHEMA = "SIFTA_UNIFIED_FIELD_ENGINE_V1"
_MODULE_VERSION = "swarm_unified_field_engine.v1"

MEMORY = 0
PREDICTION = 1
REPAIR = 2
DANGER = 3
SALIENCE = 4
CROWDING = 5
ATTENTION = SALIENCE

FieldMode = Literal["total", "memory", "prediction", "attention", "salience", "danger", "crowding", "repair"]
DepositKind = Literal["memory", "prediction", "attention", "salience", "danger", "crowding", "repair"]

_KIND_TO_CHANNEL = {
    "memory": MEMORY,
    "prediction": PREDICTION,
    "attention": ATTENTION,
    "salience": SALIENCE,
    "danger": DANGER,
    "crowding": CROWDING,
    "repair": REPAIR,
}


@dataclass(frozen=True)
class UnifiedFieldConfig:
    grid_size: int = 96
    alpha_memory: float = 0.65
    beta_prediction: float = 0.55
    gamma_repair: float = 0.75
    delta_danger: float = 0.90
    decay: float = 0.965
    diffusion: float = 0.035
    memory_deposit: float = 0.45
    prediction_deposit: float = 0.55
    repair_deposit: float = 0.60
    danger_deposit: float = 1.4
    salience_weight: float = 0.75
    crowding_weight: float = 0.55
    crowding_deposit: float = 1.0
    crowding_decay: float = 0.96
    prediction_horizon: int = 8
    repair_threshold: float = 0.25
    step_size: float = 0.025
    entropy_pressure: float = 0.012
    eps: float = 1e-8


class UnifiedFieldEngine:
    """Single environmental tensor that externalizes swarm memory and prediction."""

    def __init__(self, cfg: Optional[UnifiedFieldConfig] = None) -> None:
        self.cfg = cfg or UnifiedFieldConfig()
        if self.cfg.grid_size <= 1:
            raise ValueError("grid_size must be > 1")
        if self.cfg.prediction_horizon <= 0:
            raise ValueError("prediction_horizon must be positive")
        if not 0.0 <= self.cfg.decay <= 1.0:
            raise ValueError("decay must be in [0, 1]")
        if not 0.0 <= self.cfg.diffusion <= 0.25:
            raise ValueError("diffusion must be in [0, 0.25]")

        g = self.cfg.grid_size
        self.fields = np.zeros((6, g, g), dtype=np.float32)
        self.prev_positions: Optional[np.ndarray] = None
        self.prev_velocities: Optional[np.ndarray] = None
        axis = np.linspace(0.0, 1.0, g, dtype=np.float32)
        self._grid_x, self._grid_y = np.meshgrid(axis, axis, indexing="ij")

    def reset(self) -> None:
        self.fields.fill(0.0)
        self.prev_positions = None
        self.prev_velocities = None

    @property
    def memory(self) -> np.ndarray:
        return self.fields[MEMORY]

    @property
    def prediction(self) -> np.ndarray:
        return self.fields[PREDICTION]

    @property
    def repair(self) -> np.ndarray:
        return self.fields[REPAIR]

    @property
    def danger(self) -> np.ndarray:
        return self.fields[DANGER]

    @property
    def salience(self) -> np.ndarray:
        return self.fields[SALIENCE]

    @property
    def attention(self) -> np.ndarray:
        return self.fields[ATTENTION]

    @property
    def crowding(self) -> np.ndarray:
        return self.fields[CROWDING]

    @property
    def total(self) -> np.ndarray:
        return self.total_field()

    def _validate_positions(self, positions: np.ndarray) -> np.ndarray:
        pos = np.asarray(positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] < 2:
            raise ValueError("positions must have shape (n_agents, >=2)")
        return np.clip(pos[:, :2], 0.0, 1.0)

    def _idx(self, xy: np.ndarray) -> Tuple[int, int]:
        clipped = np.clip(np.asarray(xy, dtype=np.float32)[:2], 0.0, 1.0)
        ij = np.floor(clipped * (self.cfg.grid_size - 1)).astype(int)
        return int(ij[0]), int(ij[1])

    def _deposit(self, channel: int, pos: np.ndarray, amount: float) -> None:
        self.fields[channel][self._idx(pos)] += float(amount)

    def deposit(self, pos: np.ndarray, kind: DepositKind, amount: float) -> None:
        """Public single-cell deposit API for the unified substrate."""
        try:
            channel = _KIND_TO_CHANNEL[str(kind)]
        except KeyError as exc:
            raise ValueError(
                "kind must be one of: memory, prediction, attention, "
                "salience, danger, crowding, repair"
            ) from exc
        self._deposit(channel, np.asarray(pos, dtype=np.float32), float(amount))

    def _sample(self, channel: int, pos: np.ndarray) -> float:
        return float(self.fields[channel][self._idx(pos)])

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
        for idx in range(self.fields.shape[0]):
            self.fields[idx] = self._diffuse(self.fields[idx] * self.cfg.decay)

    def _inject_disk(self, channel: int, centers: np.ndarray, radius: float, amount: float) -> None:
        centers = np.asarray(centers, dtype=np.float32)
        if centers.size == 0:
            return
        if centers.ndim == 1:
            centers = centers.reshape(1, -1)
        if centers.ndim != 2 or centers.shape[1] < 2:
            raise ValueError("centers must have shape (n_events, >=2)")
        if radius <= 0.0:
            raise ValueError("radius must be positive")

        mask = np.zeros_like(self.fields[channel], dtype=bool)
        for center in centers[:, :2]:
            clipped = np.clip(center, 0.0, 1.0)
            dx = self._grid_x - float(clipped[0])
            dy = self._grid_y - float(clipped[1])
            mask |= (dx * dx + dy * dy) <= radius * radius
            mask[self._idx(clipped)] = True
        self.fields[channel][mask] += float(amount)

    def inject_memory(self, centers: np.ndarray, radius: float = 0.05, amount: float = 1.0) -> None:
        self._inject_disk(MEMORY, centers, radius, amount)

    def inject_danger(self, centers: np.ndarray, radius: float = 0.05, amount: Optional[float] = None) -> None:
        self._inject_disk(DANGER, centers, radius, self.cfg.danger_deposit if amount is None else amount)

    def total_field(self) -> np.ndarray:
        cfg = self.cfg
        return (
            cfg.alpha_memory * self.fields[MEMORY]
            + cfg.beta_prediction * self.fields[PREDICTION]
            + cfg.gamma_repair * self.fields[REPAIR]
            + cfg.salience_weight * self.fields[SALIENCE]
            - cfg.delta_danger * self.fields[DANGER]
            - cfg.crowding_weight * self.fields[CROWDING]
        ).astype(np.float32)

    def weight_dict(self) -> Dict[str, float]:
        """Current tunable field weights, exposed for the Event 66 meta-cortex."""
        return {
            "alpha_memory": float(self.cfg.alpha_memory),
            "beta_prediction": float(self.cfg.beta_prediction),
            "gamma_repair": float(self.cfg.gamma_repair),
            "delta_danger": float(self.cfg.delta_danger),
            "salience_weight": float(self.cfg.salience_weight),
            "crowding_weight": float(self.cfg.crowding_weight),
        }

    def set_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Replace selected field weights while preserving all other config.

        `UnifiedFieldConfig` stays frozen so accidental mutation cannot drift
        across callers. The runtime engine swaps in a validated replacement cfg.
        """
        allowed = set(self.weight_dict())
        updates: Dict[str, float] = {}
        for key, value in weights.items():
            if key not in allowed:
                raise ValueError(f"unknown unified-field weight: {key}")
            val = float(value)
            if not np.isfinite(val) or val < 0.0:
                raise ValueError(f"{key} must be a finite non-negative number")
            updates[key] = val
        if updates:
            self.cfg = replace(self.cfg, **updates)
        return self.weight_dict()

    def combined(self) -> np.ndarray:
        """Compatibility alias: one collapsed field agents can follow."""
        return self.total_field()

    def _validate_field(self, field: Optional[np.ndarray], name: str) -> np.ndarray:
        if field is None:
            return np.zeros_like(self.fields[MEMORY], dtype=np.float32)
        arr = np.asarray(field, dtype=np.float32)
        if arr.shape != self.fields[MEMORY].shape:
            raise ValueError(f"{name} must have shape {self.fields[MEMORY].shape}")
        return np.clip(arr, 0.0, None).astype(np.float32)

    def _normalize_field(self, field: np.ndarray) -> np.ndarray:
        max_value = float(field.max()) if field.size else 0.0
        if max_value <= self.cfg.eps:
            return np.zeros_like(field, dtype=np.float32)
        return (field / max_value).astype(np.float32)

    def update(
        self,
        *,
        memory: Optional[np.ndarray] = None,
        prediction: Optional[np.ndarray] = None,
        salience: Optional[np.ndarray] = None,
        danger: Optional[np.ndarray] = None,
        repair: Optional[np.ndarray] = None,
        positions: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Load external local fields into the master equation."""
        self.fields[MEMORY] = self._normalize_field(self._validate_field(memory, "memory"))
        self.fields[PREDICTION] = self._normalize_field(self._validate_field(prediction, "prediction"))
        self.fields[SALIENCE] = self._normalize_field(self._validate_field(salience, "salience"))
        self.fields[DANGER] = self._normalize_field(self._validate_field(danger, "danger"))
        self.fields[REPAIR] = self._normalize_field(self._validate_field(repair, "repair"))

        self.fields[CROWDING] = self._diffuse(self.fields[CROWDING] * self.cfg.crowding_decay)
        if positions is not None:
            pos = self._validate_positions(positions)
            for current in pos:
                self._deposit(CROWDING, current, self.cfg.crowding_deposit)
            self.fields[CROWDING] = self._normalize_field(self.fields[CROWDING])

        return self.total_field()

    def gradient_at(self, pos: np.ndarray) -> np.ndarray:
        total = self.total_field()
        i, j = self._idx(pos)
        i0, i1 = max(0, i - 1), min(self.cfg.grid_size - 1, i + 1)
        j0, j1 = max(0, j - 1), min(self.cfg.grid_size - 1, j + 1)
        return np.array(
            [float(total[i1, j] - total[i0, j]), float(total[i, j1] - total[i, j0])],
            dtype=np.float32,
        )

    def gradient(self, pos: np.ndarray) -> np.ndarray:
        """Compatibility alias for single-agent substrate users."""
        return self.gradient_at(pos)

    def sense(self, positions: np.ndarray):
        arr = np.asarray(positions, dtype=np.float32)
        if arr.ndim == 1:
            if arr.shape[0] < 2:
                raise ValueError("position must have at least two coordinates")
            i, j = self._idx(arr)
            total = float(self.total_field()[i, j])
            channels = (
                float(self.fields[MEMORY, i, j]),
                float(self.fields[PREDICTION, i, j]),
                float(self.fields[ATTENTION, i, j]),
                float(self.fields[DANGER, i, j]),
            )
            return total, channels

        pos = self._validate_positions(positions)
        obs = np.zeros((len(pos), 7), dtype=np.float32)
        for idx, current in enumerate(pos):
            obs[idx, 0] = self._sample(MEMORY, current)
            obs[idx, 1] = self._sample(PREDICTION, current)
            obs[idx, 2] = self._sample(REPAIR, current)
            obs[idx, 3] = self._sample(DANGER, current)
            grad = self.gradient_at(current)
            obs[idx, 4:6] = grad
            obs[idx, 6] = float(np.linalg.norm(grad))
        return obs

    def policy_actions(self, positions: np.ndarray) -> np.ndarray:
        pos = self._validate_positions(positions)
        actions = np.zeros_like(pos)
        center = np.array([0.5, 0.5], dtype=np.float32)
        total = self.total_field()
        shifted = np.maximum(total, 0.0)
        attractor: Optional[np.ndarray] = None
        if float(shifted.sum()) > self.cfg.eps:
            mass = float(shifted.sum())
            attractor = np.array(
                [
                    float(np.sum(self._grid_x * shifted) / mass),
                    float(np.sum(self._grid_y * shifted) / mass),
                ],
                dtype=np.float32,
            )
        for idx, current in enumerate(pos):
            grad = self.gradient_at(current)
            norm = float(np.linalg.norm(grad))
            if norm > self.cfg.eps:
                actions[idx] = grad / norm
            elif attractor is not None:
                direction = attractor - current
                direction_norm = float(np.linalg.norm(direction))
                if direction_norm > self.cfg.eps:
                    actions[idx] = direction / direction_norm
            else:
                radial = current - center
                tangent = np.array([-radial[1], radial[0]], dtype=np.float32)
                tangent_norm = float(np.linalg.norm(tangent))
                if tangent_norm > self.cfg.eps:
                    actions[idx] = tangent / tangent_norm
        return actions

    def active_inference_actions(
        self,
        positions: np.ndarray,
        *,
        candidate_actions: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Friston-style action selection over the unified field.

        Each minimal agent evaluates a small discrete policy set and chooses the
        action with lowest expected free energy: low danger/crowding, high
        preferred field value, and low prediction error against its previous
        velocity. This upgrades raw gradient ascent into anticipatory action.
        """
        pos = self._validate_positions(positions)
        if candidate_actions is None:
            step = self.cfg.step_size
            candidate_actions = np.array(
                [
                    [step, 0.0],
                    [-step, 0.0],
                    [0.0, step],
                    [0.0, -step],
                    [step, step],
                    [step, -step],
                    [-step, step],
                    [-step, -step],
                    [0.0, 0.0],
                ],
                dtype=np.float32,
            )
        candidates = np.asarray(candidate_actions, dtype=np.float32)
        if candidates.ndim != 2 or candidates.shape[1] != 2:
            raise ValueError("candidate_actions must have shape (n_actions, 2)")

        total = self.total_field()
        chosen = np.zeros_like(pos)
        for idx, current in enumerate(pos):
            previous_velocity = (
                self.prev_velocities[idx]
                if self.prev_velocities is not None and idx < len(self.prev_velocities)
                else np.zeros(2, dtype=np.float32)
            )
            best_g = float("inf")
            best_action = candidates[-1]
            for action in candidates:
                preferences = []
                dangers = []
                crowds = []
                for horizon in range(1, self.cfg.prediction_horizon + 1):
                    future = np.clip(current + action * horizon, 0.0, 1.0)
                    i, j = self._idx(future)
                    preferences.append(float(total[i, j]))
                    dangers.append(float(self.fields[DANGER, i, j]))
                    crowds.append(float(self.fields[CROWDING, i, j]))
                preference = max(preferences)
                danger = max(dangers)
                crowding = max(crowds)
                prediction_error = float(np.linalg.norm(action - previous_velocity))
                ambiguity = 1.0 / (1.0 + abs(preference))
                expected_g = (
                    self.cfg.delta_danger * danger
                    + self.cfg.crowding_weight * crowding
                    + prediction_error
                    + 0.25 * ambiguity
                    - preference
                )
                if expected_g < best_g:
                    best_g = expected_g
                    best_action = action
            norm = float(np.linalg.norm(best_action))
            chosen[idx] = best_action / norm if norm > self.cfg.eps else best_action
        return chosen

    def step(self, positions: Optional[np.ndarray] = None):
        if positions is None:
            self._decay_and_diffuse()
            return None

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

        for current, velocity in zip(pos, velocities):
            movement = float(np.linalg.norm(velocity))
            self._deposit(MEMORY, current, self.cfg.memory_deposit * np.tanh(movement * self.cfg.grid_size))
            for horizon in range(1, self.cfg.prediction_horizon + 1):
                self._deposit(PREDICTION, current + velocity * horizon, self.cfg.prediction_deposit / horizon)

        total = self.total_field()
        for idx, current in enumerate(pos):
            i, j = self._idx(current)
            danger = self._sample(DANGER, current)
            repair = self._sample(REPAIR, current)
            if danger > self.cfg.repair_threshold:
                self._deposit(REPAIR, current, self.cfg.repair_deposit * np.tanh(danger))
                self.fields[DANGER, i, j] *= 0.90
            rewards[idx] = float(total[i, j] - self.cfg.delta_danger * danger + self.cfg.gamma_repair * repair)

        self.prev_positions = pos.copy()
        self.prev_velocities = velocities.copy()
        return rewards

    def peak(self) -> Tuple[float, float, float]:
        total = self.total_field()
        idx = np.unravel_index(int(np.argmax(total)), total.shape)
        denom = max(1, self.cfg.grid_size - 1)
        return float(idx[0] / denom), float(idx[1] / denom), float(total[idx])

    def glyph(self, mode: FieldMode = "total") -> str:
        if mode == "total":
            field = self.total_field()
        elif mode == "memory":
            field = self.fields[MEMORY]
        elif mode == "prediction":
            field = self.fields[PREDICTION]
        elif mode in {"attention", "salience"}:
            field = self.fields[SALIENCE]
        elif mode == "danger":
            field = self.fields[DANGER]
        elif mode == "crowding":
            field = self.fields[CROWDING]
        elif mode == "repair":
            field = self.fields[REPAIR]
        else:
            raise ValueError("unknown field mode")
        shifted = field - float(field.min())
        if shifted.size == 0 or float(shifted.max()) <= 0.0:
            return ""
        chars = np.array(list(" .:-=+*#%@"))
        norm = shifted / (float(shifted.max()) + self.cfg.eps)
        idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)
        return "\n".join("".join(chars[row]) for row in idx.T[::-1])


def _field_entropy(field: np.ndarray, eps: float) -> float:
    shifted = np.maximum(field - float(field.min()), 0.0)
    total = float(shifted.sum())
    if total <= eps:
        return 0.0
    p = (shifted / total).ravel()
    p = p[p > eps]
    return float(-np.sum(p * np.log(p)) / (np.log(len(shifted.ravel())) + eps))


def run_unified_field_experiment(
    *,
    n_agents: int = 100,
    steps: int = 80,
    seed: int = 65,
    cfg: Optional[UnifiedFieldConfig] = None,
) -> Dict[str, object]:
    engine = UnifiedFieldEngine(cfg)
    rng = np.random.default_rng(seed)
    positions = rng.uniform(0.05, 0.25, size=(n_agents, 2)).astype(np.float32)
    start_centroid = positions.mean(axis=0)
    goal = np.array([0.82, 0.78], dtype=np.float32)

    engine.inject_memory(np.array([goal], dtype=np.float32), radius=0.10, amount=3.0)
    engine.inject_danger(np.array([[0.18, 0.18], [0.50, 0.50]], dtype=np.float32), radius=0.08)
    initial_goal_distance = float(np.linalg.norm(start_centroid - goal))

    for _ in range(steps):
        engine.step(positions)
        actions = engine.policy_actions(positions)
        jitter = rng.normal(0.0, engine.cfg.entropy_pressure, size=positions.shape).astype(np.float32)
        positions = np.clip(positions + engine.cfg.step_size * actions + jitter, 0.0, 1.0)

    engine.step(positions)
    centroid = positions.mean(axis=0)
    final_goal_distance = float(np.linalg.norm(centroid - goal))
    total = engine.total_field()
    progress = max(0.0, initial_goal_distance - final_goal_distance)
    path_efficiency = progress / max(initial_goal_distance, engine.cfg.eps)
    cohesion = float(np.mean(np.linalg.norm(positions - centroid, axis=1)))
    minimal_policy_ops = max(1, n_agents * steps * 2)
    compute_to_behavior = float((path_efficiency + max(0.0, 1.0 - cohesion)) / minimal_policy_ops)

    row = {
        "event": "unified_field_engine_run",
        "schema": _SCHEMA,
        "module_version": _MODULE_VERSION,
        "n_agents": int(n_agents),
        "steps": int(steps),
        "grid_size": int(engine.cfg.grid_size),
        "weights": {
            "alpha": engine.cfg.alpha_memory,
            "beta": engine.cfg.beta_prediction,
            "gamma": engine.cfg.gamma_repair,
            "delta": engine.cfg.delta_danger,
        },
        "field_energy": round(float(np.mean(np.abs(total))), 8),
        "field_entropy": round(_field_entropy(total, engine.cfg.eps), 8),
        "cohesion": round(cohesion, 8),
        "danger_remaining": round(float(engine.fields[DANGER].sum()), 8),
        "repair_total": round(float(engine.fields[REPAIR].sum()), 8),
        "prediction_total": round(float(engine.fields[PREDICTION].sum()), 8),
        "path_efficiency": round(float(path_efficiency), 8),
        "compute_to_behavior": round(compute_to_behavior, 12),
        "glyph": engine.glyph(),
        "ts": time.time(),
    }
    assert_payload_keys("unified_field_engine.jsonl", row, strict=True)
    return row


def append_experiment_row(row: Dict[str, object], *, ledger_path: Optional[Path] = None) -> Dict[str, object]:
    assert_payload_keys("unified_field_engine.jsonl", row, strict=True)
    target = Path(ledger_path) if ledger_path is not None else _LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(target, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def proof_of_property() -> bool:
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=40, prediction_horizon=4, diffusion=0.02))
    positions = np.array([[0.20, 0.20], [0.22, 0.20]], dtype=np.float32)
    engine.inject_memory(np.array([[0.75, 0.75]], dtype=np.float32), radius=0.08, amount=2.0)
    engine.inject_danger(np.array([[0.35, 0.35]], dtype=np.float32), radius=0.05)
    engine.step(positions)
    rewards = engine.step(positions + np.array([0.04, 0.03], dtype=np.float32))
    obs = engine.sense(positions)
    row = run_unified_field_experiment(n_agents=20, steps=20, cfg=UnifiedFieldConfig(grid_size=40))

    assert engine.total_field().shape == (40, 40)
    assert float(engine.fields[MEMORY].max()) > 0.0
    assert float(engine.fields[PREDICTION].max()) > 0.0
    assert obs.shape == (2, 7)
    assert rewards.shape == (2,)
    assert row["path_efficiency"] > 0.0
    assert row["glyph"]
    return True


if __name__ == "__main__":
    result = run_unified_field_experiment()
    print(json.dumps({k: v for k, v in result.items() if k != "glyph"}, indent=2))
