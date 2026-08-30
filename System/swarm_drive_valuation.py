#!/usr/bin/env python3
"""Valuation and goal proposals between neuromodulation and action competition."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from System.swarm_artificial_endocrinology import NeuromodulatoryState
from System.swarm_drive_economy import DriveEconomy, DriveEconomySnapshot


@dataclass(frozen=True)
class GoalProposal:
    drive: str
    desired_change: str
    urgency: float
    policy: str = "proposal_only_requires_basal_ganglia_and_authority_gates"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValuationResult:
    values: dict[str, float]
    expected_satisfaction: dict[str, dict[str, float]]
    policy: str = "values_existing_candidates_only"


def form_goal(snapshot: DriveEconomySnapshot) -> GoalProposal:
    return GoalProposal(
        drive=snapshot.dominant,
        desired_change=f"reduce {snapshot.dominant.replace('_', ' ')} pressure",
        urgency=snapshot.effective_pressures[snapshot.dominant],
    )


def value_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    snapshot: DriveEconomySnapshot,
    neuromodulation: NeuromodulatoryState,
    economy: DriveEconomy,
) -> ValuationResult:
    """Value existing candidates from learned effects; never select or execute."""
    learned = economy.learned_action_effects()
    values: dict[str, float] = {}
    expected: dict[str, dict[str, float]] = {}
    for candidate in candidates:
        name = str(candidate.get("name") or candidate.get("action") or "")
        if not name:
            continue
        base = float(candidate.get("base_value", candidate.get("salience", 0.0)) or 0.0)
        cost = max(0.0, float(candidate.get("cost", 0.0) or 0.0))
        effects = dict(learned.get(name) or {})
        satisfaction_value = sum(
            snapshot.effective_pressures.get(drive, 0.0) * float(effect)
            for drive, effect in effects.items()
        )
        social_effect = sum(float(effects.get(d, 0.0)) for d in ("social_contact", "affiliation", "care_prosociality"))
        risk = cost * neuromodulation.risk_sensitivity
        value = base + satisfaction_value * neuromodulation.salience_gain
        value += social_effect * 0.1 * neuromodulation.social_gain
        value -= risk
        values[name] = round(value, 6)
        expected[name] = {drive: round(float(effect), 6) for drive, effect in effects.items()}
    return ValuationResult(values=values, expected_satisfaction=expected)


__all__ = ["GoalProposal", "ValuationResult", "form_goal", "value_candidates"]
