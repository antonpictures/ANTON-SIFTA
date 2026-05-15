#!/usr/bin/env python3
"""Persistence-inertia perturbation harness.

Tournament §20.F sharpened the public ceiling:

    persistent participation in a shared memory field can create
    measurable inertia-like resistance to change.

This module turns that into a receipt-backed experiment. It is not a
particle-physics claim and it is not a Standard-Model simulation. It is a
classical distributed-systems analogue: agents that write more traces,
belong to more organs, and remain longer inside the organism become harder
to perturb cheaply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from System.jsonl_file_lock import append_line_locked

TRUTH_LABEL = "PERSISTENCE_INERTIA_FIELD_V1"
LEDGER_NAME = "persistence_inertia_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Classical SIFTA organizational-inertia analogue only: no OBSERVED "
    "Higgs bosons, no collider result, no Standard Model claim. This "
    "measures resistance-to-change in receipt-writing agents."
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        env = os.environ.get("SIFTA_STATE_ROOT")
        if env:
            return Path(env)
        return _repo_root() / ".sifta_state"
    p = Path(state_root)
    if (p / "System").exists() and (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


@dataclass(frozen=True)
class ParticipationCohort:
    """One band of agents in the shared memory field."""

    name: str
    trace_writes: int
    organ_memberships: int
    receipt_count: int
    dwell_time_s: float

    def participation_score(self) -> float:
        """Bounded, monotone score from persistent participation signals."""
        if self.trace_writes < 0 or self.organ_memberships < 0 or self.receipt_count < 0:
            raise ValueError("participation counts must be non-negative")
        if self.dwell_time_s < 0:
            raise ValueError("dwell_time_s must be non-negative")
        return (
            0.025 * self.trace_writes
            + 0.350 * self.organ_memberships
            + 0.015 * self.receipt_count
            + 0.070 * math.log1p(self.dwell_time_s)
        )


@dataclass(frozen=True)
class PerturbationConfig:
    baseline_ticks: int = 20
    nudge_ticks: int = 60
    recovery_ticks: int = 100
    nudge_force: float = 1.0
    dt: float = 0.1
    coupling_k: float = 0.9
    damping: float = 0.82
    anchor_base: float = 0.02
    anchor_per_score: float = 0.055

    def total_ticks(self) -> int:
        return self.baseline_ticks + self.nudge_ticks + self.recovery_ticks

    def validate(self) -> None:
        if self.baseline_ticks < 0 or self.nudge_ticks < 1 or self.recovery_ticks < 0:
            raise ValueError("tick counts must be non-negative and nudge_ticks >= 1")
        if self.dt <= 0:
            raise ValueError("dt must be positive")
        if self.coupling_k < 0 or self.damping < 0 or self.damping >= 1:
            raise ValueError("coupling_k must be >=0 and damping must be in [0,1)")
        if self.anchor_base < 0 or self.anchor_per_score < 0:
            raise ValueError("anchor values must be non-negative")


DEFAULT_COHORTS = (
    ParticipationCohort("free_probe", 0, 0, 0, 10.0),
    ParticipationCohort("recent_worker", 12, 1, 8, 600.0),
    ParticipationCohort("organ_member", 60, 4, 30, 3600.0),
    ParticipationCohort("sentinel_swimmer", 160, 9, 100, 14400.0),
)


def effective_inertia(cohort: ParticipationCohort, config: PerturbationConfig) -> float:
    return 1.0 + config.coupling_k * cohort.participation_score()


def anchoring_strength(cohort: ParticipationCohort, config: PerturbationConfig) -> float:
    return config.anchor_base + config.anchor_per_score * cohort.participation_score()


def simulate_cohort(
    cohort: ParticipationCohort,
    config: PerturbationConfig | None = None,
) -> dict[str, Any]:
    """Apply baseline -> nudge -> recovery to one cohort."""
    cfg = config or PerturbationConfig()
    cfg.validate()
    score = cohort.participation_score()
    inertia = effective_inertia(cohort, cfg)
    anchor = anchoring_strength(cohort, cfg)
    x = 0.0
    v = 0.0
    peak = 0.0
    peak_tick = 0
    samples: list[dict[str, float | int | str]] = []

    for tick in range(cfg.total_ticks()):
        if tick < cfg.baseline_ticks:
            phase = "baseline"
            force = 0.0
        elif tick < cfg.baseline_ticks + cfg.nudge_ticks:
            phase = "nudge"
            force = cfg.nudge_force
        else:
            phase = "recovery"
            force = 0.0

        acceleration = (force - anchor * x) / inertia
        v = (v + acceleration * cfg.dt) * cfg.damping
        x = x + v * cfg.dt
        if abs(x) > peak:
            peak = abs(x)
            peak_tick = tick
        if tick in {
            0,
            cfg.baseline_ticks,
            cfg.baseline_ticks + cfg.nudge_ticks - 1,
            cfg.total_ticks() - 1,
        }:
            samples.append(
                {
                    "tick": tick,
                    "phase": phase,
                    "position": round(x, 6),
                    "velocity": round(v, 6),
                    "force": round(force, 6),
                }
            )

    response_latency_ticks = max(0, peak_tick - cfg.baseline_ticks)
    revert_work = inertia * peak * (1.0 + 0.15 * score)
    stgm_cost = (
        0.020 * inertia * abs(cfg.nudge_force) * cfg.nudge_ticks
        + 0.010 * revert_work
    )
    return {
        "cohort": asdict(cohort),
        "participation_score": round(score, 6),
        "effective_inertia": round(inertia, 6),
        "anchor_strength": round(anchor, 6),
        "peak_displacement": round(peak, 6),
        "peak_tick": peak_tick,
        "response_latency_ticks": response_latency_ticks,
        "final_residual": round(abs(x), 6),
        "revert_work": round(revert_work, 6),
        "stgm_cost": round(stgm_cost, 6),
        "samples": samples,
    }


def run_persistence_inertia_protocol(
    *,
    cohorts: Iterable[ParticipationCohort] = DEFAULT_COHORTS,
    config: PerturbationConfig | None = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run the §20.F perturbation protocol and optionally receipt it."""
    cfg = config or PerturbationConfig()
    cfg.validate()
    rows = [simulate_cohort(c, cfg) for c in cohorts]
    if not rows:
        raise ValueError("at least one cohort is required")
    free_peak = rows[0]["peak_displacement"] or 1e-9
    for row in rows:
        row["resistance_vs_first_cohort"] = round(
            float(free_peak) / (float(row["peak_displacement"]) + 1e-9),
            6,
        )

    peak_values = [float(row["peak_displacement"]) for row in rows]
    inertia_values = [float(row["effective_inertia"]) for row in rows]
    monotone_resistance = all(
        peak_values[i] >= peak_values[i + 1] for i in range(len(peak_values) - 1)
    )
    monotone_inertia = all(
        inertia_values[i] <= inertia_values[i + 1] for i in range(len(inertia_values) - 1)
    )
    result = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question": (
            "Can persistent participation in shared memory fields create "
            "measurable inertia-like behavior in distributed agents?"
        ),
        "config": asdict(cfg),
        "cohorts": rows,
        "summary": {
            "cohort_count": len(rows),
            "monotone_inertia": monotone_inertia,
            "monotone_resistance_to_nudge": monotone_resistance,
            "free_peak_displacement": rows[0]["peak_displacement"],
            "most_embedded_peak_displacement": rows[-1]["peak_displacement"],
            "most_embedded_resistance_vs_free": rows[-1]["resistance_vs_first_cohort"],
            "most_embedded_stgm_cost": rows[-1]["stgm_cost"],
            "total_stgm_cost": round(sum(float(row["stgm_cost"]) for row in rows), 6),
        },
        "interpretation": (
            "The same perturbing force changes deeply embedded cohorts less, "
            "while requiring more modeled STGM/revert work. This supports the "
            "organizational-inertia analogy only."
        ),
    }
    if write:
        result["receipt"] = write_receipt(result, state_root=state_root)
    return result


def write_receipt(
    result: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_PROTOCOL",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    append_line_locked(state / LEDGER_NAME, json.dumps(row, sort_keys=True) + "\n")
    return {k: v for k, v in row.items() if k != "payload"}


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "Persistence-inertia perturbation protocol",
        f"truth: {result['truth_label']} / {result['truth_class']}",
        f"boundary: {result['truth_boundary']}",
        f"research: {result['research_question']}",
        "",
        "cohort                       score   inertia   peak Δ   resistance   STGM",
        "--------------------------  ------  --------  -------  ----------  ------",
    ]
    for row in result["cohorts"]:
        name = row["cohort"]["name"]
        lines.append(
            f"{name[:26]:26}  "
            f"{row['participation_score']:6.2f}  "
            f"{row['effective_inertia']:8.2f}  "
            f"{row['peak_displacement']:7.3f}  "
            f"{row['resistance_vs_first_cohort']:10.2f}  "
            f"{row['stgm_cost']:6.2f}"
        )
    s = result["summary"]
    lines.extend(
        [
            "",
            (
                "summary: "
                f"monotone_inertia={s['monotone_inertia']} "
                f"monotone_resistance={s['monotone_resistance_to_nudge']} "
                f"embedded/free resistance={s['most_embedded_resistance_vs_free']:.2f}x"
            ),
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--force", type=float, default=1.0)
    args = parser.parse_args(argv)

    result = run_persistence_inertia_protocol(
        config=PerturbationConfig(nudge_force=args.force),
        state_root=args.state_root,
        write=not args.no_write,
    )
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
