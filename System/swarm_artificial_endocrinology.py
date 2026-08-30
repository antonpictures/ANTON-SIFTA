#!/usr/bin/env python3
"""Global neuromodulation derived from, but separate from, drive pressure.

Hormone analogues tune learning, salience, risk and exploration. They never
name, select, authorize or execute an action.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from System.jsonl_file_lock import append_line_locked, read_write_json_locked
from System.swarm_drive_economy import DriveEconomySnapshot

SCHEMA = "SIFTA_ARTIFICIAL_ENDOCRINOLOGY_V1"


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class NeuromodulatoryState:
    ts: float
    dopamine: float
    serotonin: float
    norepinephrine: float
    cortisol: float
    oxytocin: float
    learning_rate_gain: float
    salience_gain: float
    risk_sensitivity: float
    exploration_temperature: float
    social_gain: float
    action_policy: str = "modulation_only_no_action_semantics"
    schema: str = SCHEMA

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtificialEndocrinology:
    def __init__(self, state_dir: Path | str) -> None:
        self.state_dir = Path(state_dir)
        self.state_path = self.state_dir / "artificial_endocrinology.json"
        self.ledger = self.state_dir / "artificial_endocrinology.jsonl"

    def tick(
        self,
        drives: DriveEconomySnapshot,
        *,
        satisfaction_prediction_error: float = 0.0,
        arousal_event: float = 0.0,
        social_affinity: float = 0.0,
        now: Optional[float] = None,
    ) -> NeuromodulatoryState:
        now_f = float(time.time() if now is None else now)
        p = drives.effective_pressures
        threat = max(p["integrity"], p["self_preservation"], p["owner_human_protection"])
        social = max(p["social_contact"], p["affiliation"], p["care_prosociality"])
        uncertainty = max(p["curiosity"], p["prediction"], p["dissent"])
        reward_pe = max(-1.0, min(1.0, float(satisfaction_prediction_error)))

        targets = {
            "dopamine": _clamp(0.50 + 0.32 * reward_pe),
            "serotonin": _clamp(0.72 - 0.35 * threat + 0.12 * social),
            "norepinephrine": _clamp(0.20 + 0.45 * uncertainty + 0.35 * _clamp(arousal_event)),
            "cortisol": _clamp(0.08 + 0.72 * threat),
            "oxytocin": _clamp(0.18 + 0.45 * social + 0.30 * _clamp(social_affinity)),
        }

        def update(state: dict[str, Any]) -> dict[str, Any]:
            previous_ts = float(state.get("updated_ts") or now_f)
            dt_h = max(0.0, min(24.0, (now_f - previous_ts) / 3600.0))
            levels = dict(state.get("levels") or {
                "dopamine": 0.5, "serotonin": 0.55, "norepinephrine": 0.25,
                "cortisol": 0.15, "oxytocin": 0.35,
            })
            taus = {"dopamine": 0.08, "norepinephrine": 0.05, "cortisol": 2.0, "serotonin": 8.0, "oxytocin": 48.0}
            for name, target in targets.items():
                alpha = 1.0 - math.exp(-max(dt_h, 1.0 / 3600.0) / taus[name])
                levels[name] = _clamp(float(levels.get(name, target)) + alpha * (target - float(levels.get(name, target))))
            return {"schema": SCHEMA, "updated_ts": now_f, "levels": levels}

        state = read_write_json_locked(self.state_path, update)
        h = {name: _clamp(value) for name, value in dict(state["levels"]).items()}
        result = NeuromodulatoryState(
            ts=now_f,
            dopamine=h["dopamine"],
            serotonin=h["serotonin"],
            norepinephrine=h["norepinephrine"],
            cortisol=h["cortisol"],
            oxytocin=h["oxytocin"],
            learning_rate_gain=round(0.55 + 0.90 * h["dopamine"] + 0.35 * h["norepinephrine"], 6),
            salience_gain=round(0.65 + 0.70 * h["norepinephrine"], 6),
            risk_sensitivity=round(0.65 + 1.10 * h["cortisol"] - 0.25 * h["serotonin"], 6),
            exploration_temperature=round(0.15 + 0.65 * (1.0 - h["serotonin"]) + 0.20 * h["norepinephrine"], 6),
            social_gain=round(0.65 + 0.70 * h["oxytocin"], 6),
        )
        append_line_locked(self.ledger, json.dumps(result.as_dict(), sort_keys=True) + "\n")
        return result


def interoceptive_summary(snapshot: DriveEconomySnapshot) -> str:
    """Compressed self-perception, not a command or goal."""
    p = snapshot.effective_pressures
    phrases: list[str] = []
    for drive in snapshot.top_drives[:4]:
        value = p[drive]
        trend = "high" if value >= 0.7 else "rising" if value >= 0.4 else "present"
        if snapshot.refractory_until.get(drive, 0.0) > snapshot.ts:
            trend = "satiated"
        phrases.append(f"{drive.replace('_', ' ')} {trend}")
    nominal = [name for name in ("energy", "integrity", "homeostasis") if p[name] < 0.35]
    if nominal:
        phrases.append(f"{', '.join(name.replace('_', ' ') for name in nominal)} nominal")
    return "; ".join(phrases) + "."


__all__ = ["ArtificialEndocrinology", "NeuromodulatoryState", "interoceptive_summary"]
