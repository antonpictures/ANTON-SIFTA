#!/usr/bin/env python3
"""General SIFTA perturbation / naturalness loop.

The Higgs-inspired labs ask whether participation creates inertia. This
module generalizes that pattern to any SIFTA organ:

    baseline -> nudge -> recovery -> receipt

It is a classical operating-system stability instrument, not a particle
physics claim. An organ is "natural" in this local engineering sense when
high-level perturbations do not require hand retuning to preserve low-level
behavior.
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

TRUTH_LABEL = "NATURALNESS_FIELD_AUDIT_V1"
LEDGER_NAME = "naturalness_field_audit.jsonl"
TRUTH_BOUNDARY = (
    "Classical SIFTA UV-IR stability analogue only: no Higgs boson, "
    "no collider result, no Standard Model claim. This measures whether "
    "an organ preserves low-level behavior under controlled perturbation."
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
class OrganProbe:
    """Synthetic or live-derived organ profile for perturbation testing.

    The fields are intentionally generic so any organ can project its own
    telemetry into this shape: latency, STGM burn, error/residue, and
    coherence. Higher resilience means faster recovery; higher coupling
    means the perturbation reaches deeper into the organ.
    """

    name: str
    baseline_latency_ms: float
    baseline_stgm_burn: float
    baseline_error_rate: float
    baseline_coherence: float
    resilience: float = 0.6
    coupling: float = 1.0
    retune_budget: float = 0.0

    def validate(self) -> None:
        if not self.name:
            raise ValueError("organ name is required")
        if self.baseline_latency_ms < 0 or self.baseline_stgm_burn < 0:
            raise ValueError("baseline latency and burn must be non-negative")
        if not 0.0 <= self.baseline_error_rate <= 1.0:
            raise ValueError("baseline_error_rate must be in [0, 1]")
        if not 0.0 <= self.baseline_coherence <= 1.0:
            raise ValueError("baseline_coherence must be in [0, 1]")
        if self.resilience < 0 or self.coupling < 0 or self.retune_budget < 0:
            raise ValueError("resilience, coupling, and retune_budget must be non-negative")


@dataclass(frozen=True)
class PerturbationSpec:
    """Baseline/nudge/recovery schedule and perturbation amplitude."""

    baseline_ticks: int = 12
    nudge_ticks: int = 24
    recovery_ticks: int = 48
    amplitude: float = 1.0
    dt: float = 1.0
    max_allowed_latency_multiplier: float = 2.0
    max_allowed_error_delta: float = 0.12
    min_recovered_coherence: float = 0.78

    def total_ticks(self) -> int:
        return self.baseline_ticks + self.nudge_ticks + self.recovery_ticks

    def validate(self) -> None:
        if self.baseline_ticks < 1 or self.nudge_ticks < 1 or self.recovery_ticks < 1:
            raise ValueError("all phases need at least one tick")
        if self.amplitude < 0 or self.dt <= 0:
            raise ValueError("amplitude must be non-negative and dt must be positive")
        if self.max_allowed_latency_multiplier < 1:
            raise ValueError("latency multiplier threshold must be >= 1")
        if self.max_allowed_error_delta < 0:
            raise ValueError("error delta threshold must be non-negative")
        if not 0 <= self.min_recovered_coherence <= 1:
            raise ValueError("min_recovered_coherence must be in [0, 1]")


DEFAULT_ORGAN_PROBES = (
    OrganProbe(
        "eye_surprise_sampler",
        baseline_latency_ms=42.0,
        baseline_stgm_burn=0.20,
        baseline_error_rate=0.02,
        baseline_coherence=0.94,
        resilience=0.85,
        coupling=0.70,
    ),
    OrganProbe(
        "talk_cortex_router",
        baseline_latency_ms=820.0,
        baseline_stgm_burn=1.80,
        baseline_error_rate=0.05,
        baseline_coherence=0.88,
        resilience=0.55,
        coupling=1.15,
    ),
    OrganProbe(
        "residue_bowel",
        baseline_latency_ms=65.0,
        baseline_stgm_burn=0.35,
        baseline_error_rate=0.03,
        baseline_coherence=0.91,
        resilience=0.95,
        coupling=0.90,
    ),
    OrganProbe(
        "swarm_higgs_lab",
        baseline_latency_ms=310.0,
        baseline_stgm_burn=1.15,
        baseline_error_rate=0.01,
        baseline_coherence=0.93,
        resilience=0.62,
        coupling=1.30,
    ),
)


def _phase_for_tick(tick: int, spec: PerturbationSpec) -> str:
    if tick < spec.baseline_ticks:
        return "baseline"
    if tick < spec.baseline_ticks + spec.nudge_ticks:
        return "nudge"
    return "recovery"


def simulate_organ_probe(
    probe: OrganProbe,
    spec: PerturbationSpec | None = None,
) -> dict[str, Any]:
    """Run one organ through baseline -> nudge -> recovery.

    This is deterministic and intentionally cheap. It can be used as a
    synthetic loop now, then swapped to live telemetry later by creating
    OrganProbe rows from real ledgers.
    """
    cfg = spec or PerturbationSpec()
    probe.validate()
    cfg.validate()

    latency = float(probe.baseline_latency_ms)
    burn = float(probe.baseline_stgm_burn)
    error = float(probe.baseline_error_rate)
    coherence = float(probe.baseline_coherence)

    pressure = 0.0
    peak_latency = latency
    peak_error = error
    min_coherence = coherence
    recovery_tick: int | None = None
    samples: list[dict[str, Any]] = []

    for tick in range(cfg.total_ticks()):
        phase = _phase_for_tick(tick, cfg)
        if phase == "baseline":
            target_pressure = 0.0
        elif phase == "nudge":
            target_pressure = cfg.amplitude * probe.coupling
        else:
            target_pressure = 0.0

        # First-order allostatic response. Resilient organs discharge
        # pressure faster; high coupling admits a stronger hit.
        charge = 0.30 + 0.12 * probe.coupling
        discharge = 0.10 + 0.22 * probe.resilience
        pressure += (target_pressure - pressure) * (charge if target_pressure else discharge)

        latency = probe.baseline_latency_ms * (1.0 + 0.55 * pressure)
        burn = probe.baseline_stgm_burn * (1.0 + 0.80 * pressure)
        error = min(1.0, probe.baseline_error_rate + 0.075 * pressure)
        coherence = max(0.0, probe.baseline_coherence - 0.18 * pressure)

        peak_latency = max(peak_latency, latency)
        peak_error = max(peak_error, error)
        min_coherence = min(min_coherence, coherence)

        recovered = (
            phase == "recovery"
            and recovery_tick is None
            and latency <= probe.baseline_latency_ms * 1.08
            and error <= probe.baseline_error_rate + 0.02
            and coherence >= min(1.0, probe.baseline_coherence - 0.03)
        )
        if recovered:
            recovery_tick = tick - (cfg.baseline_ticks + cfg.nudge_ticks)

        if tick in {
            0,
            cfg.baseline_ticks - 1,
            cfg.baseline_ticks,
            cfg.baseline_ticks + cfg.nudge_ticks - 1,
            cfg.total_ticks() - 1,
        }:
            samples.append(
                {
                    "tick": tick,
                    "phase": phase,
                    "pressure": round(pressure, 6),
                    "latency_ms": round(latency, 6),
                    "stgm_burn": round(burn, 6),
                    "error_rate": round(error, 6),
                    "coherence": round(coherence, 6),
                }
            )

    latency_multiplier = peak_latency / max(probe.baseline_latency_ms, 1e-9)
    error_delta = peak_error - probe.baseline_error_rate
    recovered_coherence = coherence
    retune_needed = (
        latency_multiplier > cfg.max_allowed_latency_multiplier
        or error_delta > cfg.max_allowed_error_delta
        or recovered_coherence < cfg.min_recovered_coherence
    )
    if probe.retune_budget > 0:
        retune_needed = bool(retune_needed and probe.retune_budget < cfg.amplitude * probe.coupling)

    revert_work = (
        latency_multiplier
        + 10.0 * error_delta
        + max(0.0, probe.baseline_coherence - recovered_coherence) * 4.0
    )
    stgm_cost = cfg.nudge_ticks * probe.baseline_stgm_burn * (1.0 + cfg.amplitude * probe.coupling)
    naturalness_score = 1.0 / (1.0 + revert_work + (3.0 if retune_needed else 0.0))

    return {
        "organ": asdict(probe),
        "peak_latency_ms": round(peak_latency, 6),
        "latency_multiplier": round(latency_multiplier, 6),
        "peak_error_rate": round(peak_error, 6),
        "error_delta": round(error_delta, 6),
        "min_coherence": round(min_coherence, 6),
        "recovered_coherence": round(recovered_coherence, 6),
        "recovery_ticks": recovery_tick,
        "retune_needed": bool(retune_needed),
        "revert_work": round(revert_work, 6),
        "stgm_cost": round(stgm_cost, 6),
        "naturalness_score": round(naturalness_score, 6),
        "samples": samples,
    }


def run_naturalness_audit(
    *,
    probes: Iterable[OrganProbe] = DEFAULT_ORGAN_PROBES,
    spec: PerturbationSpec | None = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run a general UV-IR stability audit across organs."""
    cfg = spec or PerturbationSpec()
    cfg.validate()
    rows = [simulate_organ_probe(probe, cfg) for probe in probes]
    if not rows:
        raise ValueError("at least one organ probe is required")

    retune_count = sum(1 for row in rows if row["retune_needed"])
    mean_score = sum(float(row["naturalness_score"]) for row in rows) / len(rows)
    worst = min(rows, key=lambda row: float(row["naturalness_score"]))

    result: dict[str, Any] = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "protocol": "baseline -> nudge -> recovery",
        "research_question": (
            "Can SIFTA preserve low-level behavior when high-dimensional "
            "organ state is perturbed, without manual retuning?"
        ),
        "config": asdict(cfg),
        "organs": rows,
        "summary": {
            "organ_count": len(rows),
            "retune_needed_count": retune_count,
            "all_recovered_without_retune": retune_count == 0,
            "mean_naturalness_score": round(mean_score, 6),
            "worst_organ": worst["organ"]["name"],
            "worst_naturalness_score": worst["naturalness_score"],
            "total_stgm_cost": round(sum(float(row["stgm_cost"]) for row in rows), 6),
        },
        "interpretation": (
            "A high naturalness score means the organ absorbs the nudge and "
            "returns near baseline without parameter changes. A low score "
            "flags fine-tuning risk."
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
        "kind": "NATURALNESS_FIELD_AUDIT",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    append_line_locked(state / LEDGER_NAME, json.dumps(row, sort_keys=True) + "\n")
    return {
        "trace_id": row["trace_id"],
        "ledger": str(state / LEDGER_NAME),
        "sha256": row["sha256"],
    }


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "Naturalness Field Audit (UV-IR stability)",
        f"truth_label: {result['truth_label']}",
        f"boundary: {result['truth_boundary']}",
        "",
        "organ                 latency x  error d  recovery  retune  score",
        "--------------------  ---------  -------  --------  ------  ------",
    ]
    for row in result["organs"]:
        name = row["organ"]["name"][:20]
        recovery = row["recovery_ticks"]
        recovery_s = "none" if recovery is None else str(recovery)
        lines.append(
            f"{name:<20}  {row['latency_multiplier']:>9.3f}  "
            f"{row['error_delta']:>7.3f}  {recovery_s:>8}  "
            f"{str(row['retune_needed']):>6}  {row['naturalness_score']:>6.3f}"
        )
    s = result["summary"]
    lines.extend(
        [
            "",
            f"all recovered without retune: {s['all_recovered_without_retune']}",
            f"mean naturalness score: {s['mean_naturalness_score']}",
            f"worst organ: {s['worst_organ']} ({s['worst_naturalness_score']})",
            f"total STGM cost: {s['total_stgm_cost']}",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amplitude", type=float, default=1.0)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_naturalness_audit(
        spec=PerturbationSpec(amplitude=args.amplitude),
        write=not args.no_write,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

