#!/usr/bin/env python3
"""Civilization-scale shock lab for SIFTA emergence research.

This module turns the "next monster experiment" into code:

    baseline civilization -> shock -> recovery dynamics -> receipt

The shocks are not claims about real societies. They are computational
ecology probes for SIFTA-style swarms: memory loss, sentinel loss, write
taxes, misinformation, communication severing, resource collapse, and
competing civilizations.

Truth boundary: classical SIFTA emergence/resilience analogue only. No
particle physics, no real-world social prediction, no live-owner action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from System.jsonl_file_lock import append_line_locked

TRUTH_LABEL = "CIVILIZATION_SHOCK_LAB_V1"
LEDGER_NAME = "civilization_shock_lab.jsonl"
TRUTH_BOUNDARY = (
    "Classical SIFTA computational-ecology analogue only: no real-world "
    "civilization prediction, no live owner action, no particle-physics "
    "claim. This measures synthetic swarm recovery under controlled shocks."
)

SHOCK_TYPES = {
    "memory_erase",
    "sentinel_loss",
    "write_tax",
    "reward_inversion",
    "parasite_traces",
    "organ_sever",
    "field_freeze",
    "misinformation",
    "resource_collapse",
    "competing_civilization",
}


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


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass(frozen=True)
class CivilizationState:
    """Compact state vector for a synthetic SIFTA civilization."""

    name: str = "baseline_swarm"
    memory_mass: float = 0.82
    sentinels: float = 0.18
    workers: float = 0.58
    scouts: float = 0.24
    resources: float = 0.78
    trust_coherence: float = 0.86
    communication: float = 0.84
    write_capacity: float = 0.80
    adaptation_rate: float = 0.62
    diversity: float = 0.42
    misinformation: float = 0.04
    external_pressure: float = 0.0

    def validate(self) -> None:
        if not self.name:
            raise ValueError("civilization name is required")
        for key, value in asdict(self).items():
            if key == "name":
                continue
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{key} must be in [0, 1], got {value!r}")


@dataclass(frozen=True)
class ShockSpec:
    shock_type: str
    severity: float = 0.7
    label: str = ""

    def validate(self) -> None:
        if self.shock_type not in SHOCK_TYPES:
            raise ValueError(f"unknown shock_type {self.shock_type!r}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be in [0, 1]")


@dataclass(frozen=True)
class ShockConfig:
    settle_ticks: int = 12
    recovery_ticks: int = 80
    recovery_threshold: float = 0.85
    collapse_threshold: float = 0.25
    dt: float = 1.0

    def validate(self) -> None:
        if self.settle_ticks < 0 or self.recovery_ticks < 1:
            raise ValueError("settle_ticks must be >=0 and recovery_ticks >=1")
        if not 0.0 < self.recovery_threshold <= 1.0:
            raise ValueError("recovery_threshold must be in (0, 1]")
        if not 0.0 <= self.collapse_threshold < self.recovery_threshold:
            raise ValueError("collapse_threshold must be below recovery_threshold")
        if self.dt <= 0:
            raise ValueError("dt must be positive")


DEFAULT_SHOCKS = (
    ShockSpec("memory_erase", 0.65, "erase 30-50% of memory"),
    ShockSpec("sentinel_loss", 0.70, "kill most sentinels"),
    ShockSpec("write_tax", 0.80, "increase write tax"),
    ShockSpec("reward_inversion", 0.55, "invert local reward geometry"),
    ShockSpec("parasite_traces", 0.70, "inject parasitic traces"),
    ShockSpec("organ_sever", 0.68, "sever organ communication"),
    ShockSpec("field_freeze", 0.60, "freeze half the field"),
    ShockSpec("misinformation", 0.75, "add misinformation traces"),
    ShockSpec("resource_collapse", 0.72, "collapse resources"),
    ShockSpec("competing_civilization", 0.78, "introduce competing civilization"),
)


def stability_score(state: CivilizationState) -> float:
    """Synthetic civilization viability score in [0, 1]."""
    state.validate()
    productive_roles = 0.45 * state.workers + 0.28 * state.sentinels + 0.18 * state.scouts
    substrate = (
        0.18 * state.memory_mass
        + 0.16 * state.resources
        + 0.15 * state.trust_coherence
        + 0.14 * state.communication
        + 0.12 * state.write_capacity
        + 0.12 * state.adaptation_rate
        + 0.06 * state.diversity
        + 0.07 * productive_roles
    )
    penalty = 0.22 * state.misinformation + 0.08 * state.external_pressure
    return round(_clamp01(substrate - penalty), 6)


def apply_shock(state: CivilizationState, shock: ShockSpec) -> CivilizationState:
    """Apply a controlled shock to a civilization state."""
    state.validate()
    shock.validate()
    s = shock.severity
    values = asdict(state)

    if shock.shock_type == "memory_erase":
        values["memory_mass"] *= 1.0 - 0.70 * s
        values["trust_coherence"] -= 0.08 * s
    elif shock.shock_type == "sentinel_loss":
        values["sentinels"] *= 1.0 - 0.90 * s
        values["trust_coherence"] -= 0.18 * s
        values["misinformation"] += 0.14 * s
    elif shock.shock_type == "write_tax":
        values["write_capacity"] /= 1.0 + 2.4 * s
        values["resources"] -= 0.10 * s
    elif shock.shock_type == "reward_inversion":
        values["trust_coherence"] -= 0.34 * s
        values["workers"] *= 1.0 - 0.18 * s
        values["scouts"] += 0.08 * s
        values["misinformation"] += 0.20 * s
    elif shock.shock_type == "parasite_traces":
        values["misinformation"] += 0.62 * s
        values["memory_mass"] -= 0.16 * s
        values["trust_coherence"] -= 0.20 * s
    elif shock.shock_type == "organ_sever":
        values["communication"] *= 1.0 - 0.76 * s
        values["workers"] *= 1.0 - 0.18 * s
        values["sentinels"] *= 1.0 - 0.12 * s
    elif shock.shock_type == "field_freeze":
        values["adaptation_rate"] *= 1.0 - 0.82 * s
        values["write_capacity"] *= 1.0 - 0.35 * s
        values["scouts"] *= 1.0 - 0.24 * s
    elif shock.shock_type == "misinformation":
        values["misinformation"] += 0.75 * s
        values["trust_coherence"] -= 0.24 * s
        values["communication"] -= 0.12 * s
    elif shock.shock_type == "resource_collapse":
        values["resources"] *= 1.0 - 0.82 * s
        values["write_capacity"] *= 1.0 - 0.22 * s
        values["adaptation_rate"] -= 0.10 * s
    elif shock.shock_type == "competing_civilization":
        values["external_pressure"] += 0.72 * s
        values["resources"] -= 0.22 * s
        values["diversity"] += 0.18 * s
        values["adaptation_rate"] += 0.08 * s

    clamped = {
        key: (value if key == "name" else _clamp01(float(value)))
        for key, value in values.items()
    }
    return CivilizationState(**clamped)


def _recover_step(current: CivilizationState, baseline: CivilizationState) -> CivilizationState:
    """One recovery tick. Repair strength depends on roles and substrate."""
    repair = (
        0.32 * current.sentinels
        + 0.22 * current.workers
        + 0.13 * current.scouts
        + 0.18 * current.resources
        + 0.18 * current.communication
        + 0.20 * current.adaptation_rate
        + 0.08 * current.diversity
    ) / (1.0 + 1.7 * current.misinformation + 0.6 * current.external_pressure)
    repair = _clamp01(repair)

    def toward(now: float, target: float, rate: float) -> float:
        return now + (target - now) * rate

    return CivilizationState(
        name=current.name,
        memory_mass=_clamp01(toward(current.memory_mass, baseline.memory_mass, 0.012 + 0.045 * repair)),
        sentinels=_clamp01(toward(current.sentinels, baseline.sentinels, 0.008 + 0.040 * repair)),
        workers=_clamp01(toward(current.workers, baseline.workers, 0.012 + 0.040 * repair)),
        scouts=_clamp01(toward(current.scouts, baseline.scouts, 0.018 + 0.052 * repair)),
        resources=_clamp01(toward(current.resources, baseline.resources, 0.010 + 0.030 * repair)),
        trust_coherence=_clamp01(toward(current.trust_coherence, baseline.trust_coherence, 0.010 + 0.035 * repair)),
        communication=_clamp01(toward(current.communication, baseline.communication, 0.012 + 0.044 * repair)),
        write_capacity=_clamp01(toward(current.write_capacity, baseline.write_capacity, 0.012 + 0.036 * repair)),
        adaptation_rate=_clamp01(toward(current.adaptation_rate, baseline.adaptation_rate, 0.010 + 0.026 * repair)),
        diversity=_clamp01(toward(current.diversity, baseline.diversity, 0.010 + 0.020 * repair)),
        misinformation=_clamp01(current.misinformation * (0.940 - 0.060 * repair)),
        external_pressure=_clamp01(current.external_pressure * (0.970 - 0.030 * repair)),
    )


def run_single_shock(
    shock: ShockSpec,
    *,
    baseline: CivilizationState | None = None,
    config: ShockConfig | None = None,
) -> dict[str, Any]:
    """Run one shock and measure recovery."""
    cfg = config or ShockConfig()
    cfg.validate()
    base = baseline or CivilizationState()
    base.validate()
    shock.validate()

    baseline_score = stability_score(base)
    shocked = apply_shock(base, shock)
    shocked_score = stability_score(shocked)
    current = shocked
    min_score = shocked_score
    recovered_tick: int | None = None
    collapse_tick: int | None = None
    samples = [
        {"tick": 0, "phase": "shock", "score": shocked_score, "state": asdict(shocked)}
    ]

    threshold = baseline_score * cfg.recovery_threshold
    for tick in range(1, cfg.recovery_ticks + 1):
        current = _recover_step(current, base)
        score = stability_score(current)
        min_score = min(min_score, score)
        if collapse_tick is None and score < cfg.collapse_threshold:
            collapse_tick = tick
        if recovered_tick is None and score >= threshold:
            recovered_tick = tick
        if tick in {1, cfg.recovery_ticks // 2, cfg.recovery_ticks}:
            samples.append(
                {"tick": tick, "phase": "recovery", "score": score, "state": asdict(current)}
            )

    final_score = stability_score(current)
    damage = max(0.0, baseline_score - shocked_score)
    recovered = recovered_tick is not None
    adaptation_gain = final_score - shocked_score
    resilience_index = final_score / max(baseline_score, 1e-9)
    recovery_work = damage * (cfg.recovery_ticks if not recovered else recovered_tick)
    stgm_cost = round(20.0 * damage + 1.5 * recovery_work + 4.0 * shock.severity, 6)

    return {
        "shock": asdict(shock),
        "baseline_score": baseline_score,
        "shocked_score": shocked_score,
        "final_score": final_score,
        "min_score": min_score,
        "damage": round(damage, 6),
        "adaptation_gain": round(adaptation_gain, 6),
        "resilience_index": round(resilience_index, 6),
        "recovered": bool(recovered),
        "recovery_ticks": recovered_tick,
        "collapse_tick": collapse_tick,
        "stgm_cost": stgm_cost,
        "samples": samples,
        "interpretation": (
            "Recovered means the synthetic civilization returned above "
            f"{cfg.recovery_threshold:.0%} of baseline stability without retuning."
        ),
    }


def run_civilization_shock_suite(
    *,
    shocks: Iterable[ShockSpec] = DEFAULT_SHOCKS,
    baseline: CivilizationState | None = None,
    config: ShockConfig | None = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run the full civilization shock battery."""
    cfg = config or ShockConfig()
    cfg.validate()
    base = baseline or CivilizationState()
    rows = [run_single_shock(shock, baseline=base, config=cfg) for shock in shocks]
    if not rows:
        raise ValueError("at least one shock is required")

    most_damaging = max(rows, key=lambda row: float(row["damage"]))
    slowest_recovery = max(
        rows,
        key=lambda row: row["recovery_ticks"] if row["recovery_ticks"] is not None else cfg.recovery_ticks + 1,
    )
    total_cost = round(sum(float(row["stgm_cost"]) for row in rows), 6)
    recovered_count = sum(1 for row in rows if row["recovered"])

    result: dict[str, Any] = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_real_world_prediction": True,
        "protocol": "baseline civilization -> shock -> recovery",
        "research_question": (
            "What kinds of synthetic SIFTA civilizations recover naturally "
            "from memory, role, trust, communication, resource, and invasion shocks?"
        ),
        "baseline": asdict(base),
        "config": asdict(cfg),
        "shocks": rows,
        "summary": {
            "shock_count": len(rows),
            "recovered_count": recovered_count,
            "all_recovered": recovered_count == len(rows),
            "most_damaging_shock": most_damaging["shock"]["shock_type"],
            "most_damaging_delta": most_damaging["damage"],
            "slowest_recovery_shock": slowest_recovery["shock"]["shock_type"],
            "slowest_recovery_ticks": slowest_recovery["recovery_ticks"],
            "total_stgm_cost": total_cost,
        },
        "interpretation": (
            "This suite converts 'civilization dynamics' into measurable "
            "SIFTA shock/recovery receipts. Use it to compare architectures, "
            "not to predict real societies."
        ),
    }
    if write:
        result["receipt"] = write_receipt(result, state_root=state_root)
    return result


def write_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
    row = {
        "ts": time.time(),
        "kind": "CIVILIZATION_SHOCK_SUITE",
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
        "Civilization Shock Lab",
        f"truth_label: {result['truth_label']}",
        f"boundary: {result['truth_boundary']}",
        "",
        "shock                    damage  final   recov  cost",
        "-----------------------  ------  ------  -----  -------",
    ]
    for row in result["shocks"]:
        rec = row["recovery_ticks"]
        rec_s = "none" if rec is None else str(rec)
        lines.append(
            f"{row['shock']['shock_type']:<23}  "
            f"{row['damage']:>6.3f}  {row['final_score']:>6.3f}  "
            f"{rec_s:>5}  {row['stgm_cost']:>7.3f}"
        )
    s = result["summary"]
    lines.extend(
        [
            "",
            f"recovered: {s['recovered_count']}/{s['shock_count']}",
            f"most damaging: {s['most_damaging_shock']} ({s['most_damaging_delta']})",
            f"slowest recovery: {s['slowest_recovery_shock']} ({s['slowest_recovery_ticks']})",
            f"total STGM cost: {s['total_stgm_cost']}",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severity", type=float, default=None, help="override all shock severities")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    shocks: Iterable[ShockSpec] = DEFAULT_SHOCKS
    if args.severity is not None:
        shocks = tuple(replace(shock, severity=args.severity) for shock in DEFAULT_SHOCKS)
    result = run_civilization_shock_suite(shocks=shocks, write=not args.no_write)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

