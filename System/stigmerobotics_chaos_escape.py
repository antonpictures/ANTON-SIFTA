#!/usr/bin/env python3
"""
System/stigmerobotics_chaos_escape.py
=====================================

E45 - Variable chaos / bounded wiggle escape.

The field can get stuck when same-channel collision risk or total pheromone
intensity climbs too high.  This module converts that pressure into a
deterministic, bounded wiggle vector.  It never actuates and never writes a
ledger row; callers may use the decision to yield, reroute, or keep gradient
descent calm.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.stigmerobotics_pheromone_field import (
    PheromoneFieldReport,
    field_report,
    load_jsonl,
    live_pheromone_field,
)
from System.stigmerobotics_physical_space import (
    PhysicalSpaceReport,
    build_physical_space_report,
)

_REPO = Path(__file__).resolve().parent.parent
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e45_chaos_high_collision.jsonl"

DEFAULT_COLLISION_THRESHOLD = 0.45
DEFAULT_INTENSITY_THRESHOLD = 3.0
DEFAULT_MAX_AMPLITUDE = 0.25
DEFAULT_MIN_AMPLITUDE = 0.02


@dataclass(frozen=True)
class WiggleChannel:
    channel: str
    intensity: float
    wiggle: float


@dataclass(frozen=True)
class ChaosEscapeDecision:
    mode: str
    action: str
    collision_risk: float
    total_intensity: float
    pressure: float
    physical_pressure: float
    amplitude: float
    max_amplitude: float
    seed: str
    wiggles: tuple[WiggleChannel, ...]
    violations: tuple[str, ...] = field(default_factory=tuple)
    physical_observation_count: int = 0
    physical_sensor_kinds: tuple[str, ...] = field(default_factory=tuple)
    nearest_body_distance_m: float | None = None

    @property
    def ok(self) -> bool:
        return not self.violations and self.amplitude <= self.max_amplitude + 1e-12

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E45": "Variable chaos / bounded wiggle escape",
            "trigger": "collision_risk >= threshold OR total_intensity >= threshold",
            "mode": self.mode,
            "action": self.action,
            "collision_risk": self.collision_risk,
            "total_intensity": self.total_intensity,
            "pressure": self.pressure,
            "physical_pressure": self.physical_pressure,
            "physical_observation_count": self.physical_observation_count,
            "physical_sensor_kinds": list(self.physical_sensor_kinds),
            "nearest_body_distance_m": self.nearest_body_distance_m,
            "amplitude": self.amplitude,
            "max_amplitude": self.max_amplitude,
            "bounded": all(abs(w.wiggle) <= self.amplitude + 1e-12 for w in self.wiggles),
            "deterministic_seed": self.seed,
            "violations": list(self.violations),
            "truth_label": "OPERATIONAL" if self.ok else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"E45 Chaos Escape: {self.mode}",
            f"action: {self.action}",
            f"collision_risk: {self.collision_risk:.6f}",
            f"total_intensity: {self.total_intensity:.6f}",
            f"pressure: {self.pressure:.6f}",
            f"physical_pressure: {self.physical_pressure:.6f}",
            f"physical_observations: {self.physical_observation_count}",
            f"physical_sensors: {', '.join(self.physical_sensor_kinds) or 'none'}",
            f"nearest_body_distance_m: {self.nearest_body_distance_m if self.nearest_body_distance_m is not None else 'none'}",
            f"amplitude: {self.amplitude:.6f}",
            f"seed: {self.seed}",
            "",
            "wiggles:",
        ]
        for item in self.wiggles[:12]:
            lines.append(f"  {item.channel:52s} intensity={item.intensity:.6f} wiggle={item.wiggle:+.6f}")
        if self.violations:
            lines.append("")
            lines.append("violations:")
            lines.extend(f"  {v}" for v in self.violations)
        return lines


def _bounded_ratio(value: float, threshold: float) -> float:
    if threshold <= 0.0:
        return float("inf")
    return max(0.0, value / threshold)


def _amplitude_from_pressure(
    pressure: float,
    *,
    min_amplitude: float = DEFAULT_MIN_AMPLITUDE,
    max_amplitude: float = DEFAULT_MAX_AMPLITUDE,
) -> float:
    if pressure < 1.0:
        return 0.0
    if max_amplitude <= 0.0:
        return 0.0
    min_amp = max(0.0, min(min_amplitude, max_amplitude))
    scale = min(1.0, max(0.0, pressure - 1.0))
    return min(max_amplitude, min_amp + (max_amplitude - min_amp) * scale)


def deterministic_wiggle(channel: str, seed: str, amplitude: float) -> float:
    if amplitude <= 0.0:
        return 0.0
    digest = hashlib.blake2b(f"{seed}:{channel}".encode("utf-8"), digest_size=8).digest()
    unit = int.from_bytes(digest, "big") / float(2**64 - 1)
    return ((unit * 2.0) - 1.0) * amplitude


def chaos_escape_decision(
    report: PheromoneFieldReport,
    *,
    physical_space: PhysicalSpaceReport | None = None,
    collision_threshold: float = DEFAULT_COLLISION_THRESHOLD,
    intensity_threshold: float = DEFAULT_INTENSITY_THRESHOLD,
    max_amplitude: float = DEFAULT_MAX_AMPLITUDE,
    min_amplitude: float = DEFAULT_MIN_AMPLITUDE,
    seed: str | None = None,
) -> ChaosEscapeDecision:
    if physical_space is None:
        physical_space = build_physical_space_report(())
    violations: list[str] = []
    if report.violations:
        violations.extend(report.violations)
    if collision_threshold <= 0.0:
        violations.append("collision_threshold_must_be_positive")
    if intensity_threshold <= 0.0:
        violations.append("intensity_threshold_must_be_positive")
    if max_amplitude < 0.0:
        violations.append("max_amplitude_must_be_nonnegative")

    physical_observation_count = len(physical_space.observations)
    physical_sensor_kinds = physical_space.sensor_kinds
    nearest_body_distance_m = physical_space.nearest_body_distance_m

    if violations:
        return ChaosEscapeDecision(
            mode="FROZEN",
            action="FREEZE_AND_REPAIR_FIELD",
            collision_risk=report.collision_risk,
            total_intensity=report.total_intensity,
            pressure=0.0,
            physical_pressure=0.0,
            amplitude=0.0,
            max_amplitude=max(0.0, max_amplitude),
            seed=seed or f"{report.now_ts:.6f}",
            wiggles=(),
            violations=tuple(violations),
            physical_observation_count=physical_observation_count,
            physical_sensor_kinds=physical_sensor_kinds,
            nearest_body_distance_m=nearest_body_distance_m,
        )

    collision_pressure = _bounded_ratio(report.collision_risk, collision_threshold)
    intensity_pressure = _bounded_ratio(report.total_intensity, intensity_threshold)
    physical_pressure = physical_space.pressure
    pressure = max(collision_pressure, intensity_pressure, physical_pressure)
    amplitude = _amplitude_from_pressure(
        pressure,
        min_amplitude=min_amplitude,
        max_amplitude=max_amplitude,
    )

    if amplitude <= 0.0:
        mode = "CALM"
        action = "KEEP_GRADIENT"
    elif physical_pressure >= collision_pressure and physical_pressure >= intensity_pressure:
        mode = "PHYSICAL_SPACE_ESCAPE"
        action = "YIELD_OR_REROUTE_AROUND_MOVING_BODY"
    elif collision_pressure >= intensity_pressure:
        mode = "CHAOS_ESCAPE"
        action = "YIELD_OR_REROUTE_COLLIDING_WRITERS"
    else:
        mode = "WIGGLE"
        action = "INJECT_BOUNDED_WIGGLE"

    wiggle_seed = seed or f"{report.now_ts:.6f}:{len(report.deposits)}:{len(report.collision_signals)}"
    ranked = sorted(report.field.items(), key=lambda item: item[1], reverse=True)
    wiggles = tuple(
        WiggleChannel(
            channel=channel,
            intensity=intensity,
            wiggle=deterministic_wiggle(channel, wiggle_seed, amplitude),
        )
        for channel, intensity in ranked
    )

    return ChaosEscapeDecision(
        mode=mode,
        action=action,
        collision_risk=report.collision_risk,
        total_intensity=report.total_intensity,
        pressure=pressure,
        physical_pressure=physical_pressure,
        amplitude=amplitude,
        max_amplitude=max_amplitude,
        seed=wiggle_seed,
        wiggles=wiggles,
        physical_observation_count=physical_observation_count,
        physical_sensor_kinds=physical_sensor_kinds,
        nearest_body_distance_m=nearest_body_distance_m,
    )


def chaos_escape_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    now_ts: float | None = None,
    collision_threshold: float = DEFAULT_COLLISION_THRESHOLD,
    intensity_threshold: float = DEFAULT_INTENSITY_THRESHOLD,
    max_amplitude: float = DEFAULT_MAX_AMPLITUDE,
    seed: str | None = None,
) -> ChaosEscapeDecision:
    row_tuple = tuple(rows)
    # Primary substrate: physical desk-space sensor observations.
    physical_space = build_physical_space_report(row_tuple, now_ts=now_ts)

    # Virtual substrate: the ledger and stigmergic pheromones.
    report = field_report(row_tuple, now_ts=now_ts)

    return chaos_escape_decision(
        report,
        physical_space=physical_space,
        collision_threshold=collision_threshold,
        intensity_threshold=intensity_threshold,
        max_amplitude=max_amplitude,
        seed=seed,
    )


def fixture_chaos_escape(path: Path = _FIXTURE, *, now_ts: float | None = None) -> ChaosEscapeDecision:
    return chaos_escape_from_rows(load_jsonl(path), now_ts=now_ts)


def live_chaos_escape(*, limit: int = 300) -> ChaosEscapeDecision:
    if _TRACE.exists():
        return chaos_escape_from_rows(load_jsonl(_TRACE)[-limit:])
    report = live_pheromone_field(limit=limit)
    return chaos_escape_decision(report)


if __name__ == "__main__":
    print("\n".join(live_chaos_escape().summary_lines()))
    print("\nproof_of_property:")
    print(json.dumps(live_chaos_escape().proof_of_property, indent=2, ensure_ascii=False))
