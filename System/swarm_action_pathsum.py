#!/usr/bin/env python3
"""Event 94.5: action quanta, path sums, and threshold gates.

This module turns the Veritasium / action / path-integral dirt in tournament
section 17.5 into executable scaffolding. It is deliberately SIM_ONLY:

- enumerate tiny discrete 1D paths and compute classical action;
- sum phase factors exp(i S / hbar) as a path-sum toy;
- expose a photoelectric-style threshold gate;
- expose a mass-energy invariant helper for demos.

Truth guard
-----------
This does not implement physical QED, prove a new interpretation of quantum
mechanics, or replace textbook path integrals. It gives SIFTA a tested local
organ for the analogies in Event 94.5: path histories, action quanta, and
constraint-first gates.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np


TRUTH_LABEL = "SIFTA_EVENT94_ACTION_PATHSUM_V1"
TRUTH_GUARD = (
    "SIM_ONLY action/path-sum harness. Discrete path histories, phase sums, "
    "photoelectric-style thresholds, and mass-energy invariants are local demo "
    "tools; they do not replace QED, the Standard Model, or textbook relativity."
)

PotentialFn = Callable[[float, int], float]


@dataclass(frozen=True)
class ActionPathConfig:
    """Bounded 1D path enumeration settings."""

    start: int = 0
    end: int = 0
    steps: int = 4
    max_step: int = 1
    mass: float = 1.0
    dt: float = 1.0
    hbar: float = 1.0
    max_paths: int = 50_000

    def __post_init__(self) -> None:
        if self.steps <= 0:
            raise ValueError("steps must be positive")
        if self.max_step <= 0:
            raise ValueError("max_step must be positive")
        if self.mass <= 0 or self.dt <= 0 or self.hbar <= 0:
            raise ValueError("mass, dt, and hbar must be positive")
        if self.max_paths <= 0:
            raise ValueError("max_paths must be positive")


def enumerate_discrete_paths(config: ActionPathConfig) -> list[list[int]]:
    """Enumerate all bounded paths from start to end over `steps`.

    This is intentionally tiny and deterministic. It is for demo/referee
    harnesses, not large-scale path integration.
    """
    moves = tuple(range(-config.max_step, config.max_step + 1))
    paths: list[list[int]] = []

    def walk(prefix: list[int], remaining: int) -> None:
        if len(paths) >= config.max_paths:
            raise RuntimeError("path count exceeded max_paths")
        current = prefix[-1]
        if remaining == 0:
            if current == config.end:
                paths.append(prefix.copy())
            return
        span_left = remaining * config.max_step
        if abs(config.end - current) > span_left:
            return
        for move in moves:
            prefix.append(current + move)
            walk(prefix, remaining - 1)
            prefix.pop()

    walk([config.start], config.steps)
    return paths


def path_action(
    path: Iterable[float],
    *,
    mass: float = 1.0,
    dt: float = 1.0,
    potential: PotentialFn | None = None,
) -> float:
    """Discrete action sum int (T - V) dt for a single path."""
    if mass <= 0 or dt <= 0:
        raise ValueError("mass and dt must be positive")
    points = [float(p) for p in path]
    if len(points) < 2:
        raise ValueError("path needs at least two points")
    action = 0.0
    for i, (a, b) in enumerate(zip(points, points[1:])):
        velocity = (b - a) / dt
        midpoint = 0.5 * (a + b)
        kinetic = 0.5 * mass * velocity * velocity
        potential_energy = 0.0 if potential is None else float(potential(midpoint, i))
        action += (kinetic - potential_energy) * dt
    return float(action)


def phase_sum(actions: Iterable[float], *, hbar: float = 1.0) -> dict[str, Any]:
    """Average exp(iS/hbar) over actions and return amplitude/probability."""
    if hbar <= 0:
        raise ValueError("hbar must be positive")
    arr = np.asarray(list(actions), dtype=np.float64)
    if arr.ndim != 1 or len(arr) == 0:
        raise ValueError("actions must be a non-empty 1D sequence")
    phases = np.exp(1j * arr / float(hbar))
    amplitude = complex(np.mean(phases))
    return {
        "truth_label": TRUTH_LABEL,
        "count": int(len(arr)),
        "amplitude_real": float(amplitude.real),
        "amplitude_imag": float(amplitude.imag),
        "probability_proxy": float(abs(amplitude) ** 2),
        "mean_action": float(np.mean(arr)),
        "action_std": float(np.std(arr)),
    }


def path_sum_report(
    config: ActionPathConfig,
    *,
    potential: PotentialFn | None = None,
) -> dict[str, Any]:
    """Enumerate paths, compute actions, and report least-action + phase sum."""
    paths = enumerate_discrete_paths(config)
    actions = [
        path_action(path, mass=config.mass, dt=config.dt, potential=potential)
        for path in paths
    ]
    if not paths:
        return {
            "truth_label": TRUTH_LABEL,
            "truth_guard": TRUTH_GUARD,
            "path_count": 0,
            "least_action": None,
            "least_action_path": None,
            "phase_sum": None,
        }
    idx = int(np.argmin(np.asarray(actions, dtype=np.float64)))
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": TRUTH_GUARD,
        "config": asdict(config),
        "path_count": len(paths),
        "least_action": float(actions[idx]),
        "least_action_path": paths[idx],
        "phase_sum": phase_sum(actions, hbar=config.hbar),
    }


def photoelectric_gate(
    photon_energy_ev: float,
    work_function_ev: float,
    *,
    intensity: float = 1.0,
) -> dict[str, Any]:
    """Threshold gate: frequency/energy clears; intensity does not lower threshold."""
    if photon_energy_ev < 0 or work_function_ev < 0 or intensity < 0:
        raise ValueError("energies and intensity must be non-negative")
    emitted = float(photon_energy_ev) >= float(work_function_ev)
    return {
        "truth_label": TRUTH_LABEL,
        "emitted": bool(emitted),
        "photon_energy_ev": float(photon_energy_ev),
        "work_function_ev": float(work_function_ev),
        "intensity": float(intensity),
        "electron_kinetic_energy_ev": (
            float(photon_energy_ev) - float(work_function_ev) if emitted else 0.0
        ),
        "policy_analogy": (
            "threshold_cleared" if emitted else "threshold_blocked_regardless_of_intensity"
        ),
    }


def mass_energy_invariant(
    energy: float,
    momentum: float,
    *,
    c: float = 1.0,
) -> dict[str, Any]:
    """Return E^2 - p^2 c^2 and invariant mass when timelike."""
    if c <= 0:
        raise ValueError("c must be positive")
    invariant_energy_squared = float(energy) ** 2 - (float(momentum) * c) ** 2
    mass_squared = invariant_energy_squared / (c ** 4)
    timelike = mass_squared >= 0.0
    return {
        "truth_label": TRUTH_LABEL,
        "energy": float(energy),
        "momentum": float(momentum),
        "c": float(c),
        "invariant_energy_squared": float(invariant_energy_squared),
        "mass_squared": float(mass_squared),
        "invariant_mass": math.sqrt(mass_squared) if timelike else None,
        "timelike": bool(timelike),
    }


def constructor_constraint_report(
    possible: Iterable[str],
    impossible: Iterable[str],
) -> dict[str, Any]:
    """Small constructor-theory-style impossibility/possibility summary."""
    possible_list = [str(x) for x in possible]
    impossible_list = [str(x) for x in impossible]
    return {
        "truth_label": TRUTH_LABEL,
        "possible_transformations": possible_list,
        "impossible_transformations": impossible_list,
        "constraint_first": True,
    }


def event94_action_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": TRUTH_GUARD,
        "surfaces": [
            "discrete_action_paths",
            "phase_sum_proxy",
            "photoelectric_threshold_gate",
            "mass_energy_invariant",
            "constructor_constraint_report",
        ],
        "primary_anchors": [
            "planck_1901_quantum_action",
            "einstein_1905_light_quantum",
            "feynman_1948_path_integral",
            "einstein_1905_mass_energy",
            "everett_1957_relative_state",
            "deutsch_marletto_2012_constructor_theory",
        ],
    }


def write_action_pathsum_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_root or Path(__file__).resolve().parent.parent / ".sifta_state"
    out = receipt_path or root / "event94_action_pathsum_receipts.jsonl"
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "EVENT94_ACTION_PATHSUM_RECEIPT",
        **event94_action_payload(),
    }
    if extra:
        row["extra"] = dict(extra)
    row["sha256"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "ActionPathConfig",
    "TRUTH_GUARD",
    "TRUTH_LABEL",
    "constructor_constraint_report",
    "enumerate_discrete_paths",
    "event94_action_payload",
    "mass_energy_invariant",
    "path_action",
    "path_sum_report",
    "phase_sum",
    "photoelectric_gate",
    "write_action_pathsum_receipt",
]
