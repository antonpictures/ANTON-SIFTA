#!/usr/bin/env python3
"""
System/swarm_evolutionary_rl.py

Event 66: bounded evolutionary tuning for the unified stigmergic field.

The tuner mutates only real `UnifiedFieldEngine` weights, evaluates each
candidate through `run_unified_field_experiment()`, and emits one canonical
row describing the selected physics. No neural-network dependency is needed.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, Optional

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys  # noqa: E402
from System.jsonl_file_lock import append_line_locked  # noqa: E402
from System.swarm_unified_field_engine import (  # noqa: E402
    UnifiedFieldConfig,
    UnifiedFieldEngine,
    run_unified_field_experiment,
)

_LEDGER = _REPO / ".sifta_state" / "evolutionary_rl_meta_cortex.jsonl"
_SCHEMA = "SIFTA_EVOLUTIONARY_RL_META_CORTEX_V1"
_MODULE_VERSION = "swarm_evolutionary_rl.v1"


class EvolutionaryFieldTuner:
    """Mutation-selection over UnifiedFieldEngine weight coefficients."""

    def __init__(
        self,
        cfg: Optional[UnifiedFieldConfig] = None,
        *,
        seed: int = 66,
        mutation_scale: float = 0.10,
    ) -> None:
        self.cfg = cfg or UnifiedFieldConfig()
        if mutation_scale < 0.0:
            raise ValueError("mutation_scale must be non-negative")
        self.mutation_scale = float(mutation_scale)
        self.rng = np.random.default_rng(seed)
        self.seed = int(seed)
        self._baseline_weights = UnifiedFieldEngine(self.cfg).weight_dict()

    @staticmethod
    def _score(metrics: Dict[str, object]) -> float:
        """Turn substrate metrics into a scalar reward for local selection."""
        path_efficiency = float(metrics.get("path_efficiency", 0.0))
        repair_total = float(metrics.get("repair_total", 0.0))
        prediction_total = float(metrics.get("prediction_total", 0.0))
        danger_remaining = float(metrics.get("danger_remaining", 0.0))
        field_entropy = float(metrics.get("field_entropy", 0.0))
        compute_to_behavior = float(metrics.get("compute_to_behavior", 0.0))
        return (
            path_efficiency
            + 0.020 * repair_total
            + 0.005 * prediction_total
            + 0.050 * field_entropy
            + 1000.0 * compute_to_behavior
            - 0.010 * danger_remaining
        )

    @staticmethod
    def _metrics_subset(row: Dict[str, object]) -> Dict[str, float]:
        keys = (
            "path_efficiency",
            "field_entropy",
            "danger_remaining",
            "repair_total",
            "prediction_total",
            "compute_to_behavior",
        )
        return {key: float(row[key]) for key in keys}

    def _mutate(self, weights: Dict[str, float]) -> Dict[str, float]:
        mutated: Dict[str, float] = {}
        for key, value in weights.items():
            noise = float(self.rng.normal(0.0, self.mutation_scale))
            candidate = float(value) * (1.0 + noise)
            mutated[key] = float(np.clip(candidate, 0.05, 5.0))
        return mutated

    def _evaluate(
        self,
        weights: Dict[str, float],
        *,
        n_agents: int,
        steps: int,
        eval_seed: int,
    ) -> tuple[float, Dict[str, object]]:
        cfg = replace(self.cfg, **weights)
        row = run_unified_field_experiment(
            n_agents=int(n_agents),
            steps=int(steps),
            seed=int(eval_seed),
            cfg=cfg,
        )
        return self._score(row), row

    def tune(
        self,
        *,
        generations: int = 4,
        population: int = 6,
        n_agents: int = 40,
        steps: int = 30,
    ) -> Dict[str, object]:
        if generations <= 0:
            raise ValueError("generations must be positive")
        if population <= 0:
            raise ValueError("population must be positive")

        baseline_score, baseline_row = self._evaluate(
            self._baseline_weights,
            n_agents=n_agents,
            steps=steps,
            eval_seed=self.seed,
        )
        best_weights = dict(self._baseline_weights)
        best_score = float(baseline_score)
        best_row = dict(baseline_row)

        parent = dict(self._baseline_weights)
        for generation in range(int(generations)):
            candidates = [dict(parent)]
            candidates.extend(self._mutate(parent) for _ in range(max(0, int(population) - 1)))
            for candidate_idx, candidate in enumerate(candidates):
                score, row = self._evaluate(
                    candidate,
                    n_agents=n_agents,
                    steps=steps,
                    eval_seed=self.seed + generation * 1009 + candidate_idx,
                )
                if score > best_score:
                    best_score = float(score)
                    best_weights = dict(candidate)
                    best_row = dict(row)
            parent = dict(best_weights)

        out = {
            "event": "evolutionary_rl_meta_cortex_tune",
            "schema": _SCHEMA,
            "module_version": _MODULE_VERSION,
            "generations": int(generations),
            "population": int(population),
            "baseline_weights": dict(self._baseline_weights),
            "best_weights": best_weights,
            "baseline_score": round(float(baseline_score), 10),
            "best_score": round(float(max(best_score, baseline_score)), 10),
            "reward_delta": round(float(max(0.0, best_score - baseline_score)), 10),
            "best_metrics": self._metrics_subset(best_row),
            "ts": time.time(),
        }
        assert_payload_keys("evolutionary_rl_meta_cortex.jsonl", out, strict=True)
        return out


def apply_tuned_weights(engine: UnifiedFieldEngine, row: Dict[str, object]) -> Dict[str, float]:
    weights = row.get("best_weights")
    if not isinstance(weights, dict):
        raise ValueError("row must contain best_weights")
    return engine.set_weights({str(k): float(v) for k, v in weights.items()})


def append_tuning_row(
    row: Dict[str, object],
    *,
    ledger_path: Optional[Path] = None,
) -> Dict[str, object]:
    assert_payload_keys("evolutionary_rl_meta_cortex.jsonl", row, strict=True)
    target = Path(ledger_path) if ledger_path is not None else _LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(target, json.dumps(row, ensure_ascii=False) + "\n")
    return row


class SwarmEvolutionaryMetaCortex:
    """Compatibility facade for earlier Event 66 callers."""

    def __init__(self, engine: UnifiedFieldEngine, learning_rate: float = 0.01):
        self.engine = engine
        self.lr = float(learning_rate)
        self.weights = self.engine.weight_dict()
        self.prev_reward = 0.0

    def get_current_physics(self) -> Dict[str, float]:
        return dict(self.weights)

    def observe_and_learn(self, current_reward: float, environment_volatility: float) -> None:
        advantage = float(current_reward) - float(self.prev_reward)
        updates: Dict[str, float] = {}
        for key, value in self.weights.items():
            gradient = 0.05 * advantage
            if environment_volatility > 0.7:
                if key == "salience_weight":
                    gradient += 0.5
                elif key == "alpha_memory":
                    gradient -= 0.5
                elif key == "delta_danger":
                    gradient += 0.2
            updates[key] = float(np.clip(value + self.lr * gradient, 0.05, 5.0))
        self.weights = self.engine.set_weights(updates)
        self.prev_reward = float(current_reward)


def proof_of_property() -> bool:
    print("\n=== SIFTA EVOLUTIONARY RL META-CORTEX (Event 66) : JUDGE VERIFICATION ===")
    tuner = EvolutionaryFieldTuner(
        UnifiedFieldConfig(grid_size=28, diffusion=0.0),
        seed=66,
        mutation_scale=0.12,
    )
    row = tuner.tune(generations=2, population=4, n_agents=18, steps=12)
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=28, diffusion=0.0))
    applied = apply_tuned_weights(engine, row)

    assert row["best_score"] >= row["baseline_score"]
    assert row["reward_delta"] >= 0.0
    assert set(applied) == set(engine.weight_dict())
    assert np.isfinite(list(applied.values())).all()
    print(
        f"[+] Event 66 selected weights: reward_delta={row['reward_delta']:.6f} "
        f"best_score={row['best_score']:.6f}"
    )
    return True


if __name__ == "__main__":
    proof_of_property()
