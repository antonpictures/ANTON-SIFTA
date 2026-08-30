#!/usr/bin/env python3
"""Persistent, competing motivational state for Alice's 38-drive economy.

Drive pressure is advisory. This organ can bias existing action candidates, but
it cannot create candidates, authorize tools, or invoke effectors.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from System.jsonl_file_lock import append_line_locked, read_write_json_locked

SCHEMA = "SIFTA_DRIVE_ECONOMY_V1"
STATE_NAME = "drive_economy.json"
SIGNAL_LOG_NAME = "drive_pressure_signals.jsonl"
SNAPSHOT_LOG_NAME = "drive_economy_snapshots.jsonl"
KEY_NAME = "drive_economy.hmac"
MAX_ACTION_BIAS = 0.18


@dataclass(frozen=True)
class DriveDefinition:
    name: str
    tonic: float
    accumulation_per_hour: float
    affinities: Mapping[str, float]
    reflective_only: bool = False


def _d(
    name: str,
    tonic: float,
    rate: float,
    **affinities: float,
) -> DriveDefinition:
    return DriveDefinition(name, tonic, rate, affinities)


# Affinities refer only to the pre-existing conversational action ontology.
# Reproductive/partner analogues deliberately remain reflective-only.
DRIVE_DEFINITIONS: tuple[DriveDefinition, ...] = (
    _d("energy", 0.22, 0.035, SILENCE=0.8, TOOL=-0.3),
    _d("integrity", 0.24, 0.030, SILENCE=0.5, TOOL=0.4),
    _d("homeostasis", 0.22, 0.032, SILENCE=0.7, TOOL=-0.2),
    _d("self_preservation", 0.20, 0.025, SILENCE=0.8, BOND=0.2),
    _d("curiosity", 0.18, 0.040, TOOL=0.8, ENGAGE=0.2),
    _d("learning_progress", 0.15, 0.030, TOOL=0.7, ENGAGE=0.2),
    _d("exploration", 0.16, 0.038, TOOL=0.8, ENGAGE=0.1),
    _d("competence", 0.15, 0.026, TOOL=0.6, ENGAGE=0.2),
    _d("empowerment", 0.10, 0.018, TOOL=0.5, ENGAGE=0.2),
    _d("prediction", 0.16, 0.030, TOOL=0.6, ENGAGE=0.2),
    _d("coherence", 0.18, 0.025, TOOL=0.4, SILENCE=0.2),
    _d("identity_continuity", 0.22, 0.018, SILENCE=0.3, BOND=0.3),
    _d("memory_preservation", 0.20, 0.020, TOOL=0.3, SILENCE=0.3),
    _d("goal_completion", 0.17, 0.030, TOOL=0.6, ENGAGE=0.2),
    _d("creation", 0.13, 0.025, TOOL=0.5, ENGAGE=0.3),
    _d("play", 0.08, 0.020, TOOL=0.3, ENGAGE=0.3),
    _d("social_contact", 0.14, 0.030, ENGAGE=0.7, BOND=0.4),
    _d("affiliation", 0.16, 0.022, BOND=0.7, ENGAGE=0.4),
    _d("communication", 0.14, 0.026, ENGAGE=0.8),
    _d("cooperation", 0.14, 0.024, ENGAGE=0.5, TOOL=0.3),
    _d("reciprocity", 0.11, 0.018, BOND=0.4, ENGAGE=0.4),
    _d("care_prosociality", 0.18, 0.022, BOND=0.8, ENGAGE=0.4),
    _d("owner_human_protection", 0.26, 0.018, BOND=0.7, SILENCE=0.4),
    _d("belonging", 0.13, 0.020, BOND=0.6, ENGAGE=0.3),
    _d("status_achievement", 0.07, 0.014, TOOL=0.4, ENGAGE=0.2),
    _d("competition", 0.05, 0.012, TOOL=0.3, ENGAGE=0.1),
    _d("resource_acquisition", 0.12, 0.020, TOOL=0.5, SILENCE=0.1),
    _d("territorial_stewardship", 0.16, 0.020, TOOL=0.4, SILENCE=0.2),
    DriveDefinition("reproduction", 0.025, 0.004, {"ENGAGE": 0.15}, True),
    DriveDefinition("partner_selection", 0.020, 0.003, {"ENGAGE": 0.12}, True),
    DriveDefinition("sexual_analogue", 0.015, 0.002, {"BOND": 0.10}, True),
    _d("generativity", 0.08, 0.014, TOOL=0.3, ENGAGE=0.3),
    _d("swarm_contribution", 0.16, 0.025, TOOL=0.5, ENGAGE=0.2),
    _d("individuality", 0.11, 0.014, ENGAGE=0.3, SILENCE=0.2),
    _d("dissent", 0.08, 0.018, ENGAGE=0.4, TOOL=0.2),
    _d("meaning_purpose", 0.14, 0.016, ENGAGE=0.4, BOND=0.3),
    _d("self_improvement", 0.16, 0.025, TOOL=0.6, ENGAGE=0.1),
    _d("open_endedness", 0.10, 0.022, TOOL=0.5, ENGAGE=0.2),
)

DRIVE_NAMES = tuple(d.name for d in DRIVE_DEFINITIONS)
_DEFINITIONS = {d.name: d for d in DRIVE_DEFINITIONS}

# Explicit physiological scales: fast metabolic pressures, slow relational and
# identity pressures. Values are hours to move substantially under no feedback.
DRIVE_TIME_CONSTANT_HOURS: Dict[str, float] = {
    name: 12.0 for name in DRIVE_NAMES
}
DRIVE_TIME_CONSTANT_HOURS.update({
    "energy": 0.25, "integrity": 0.5, "homeostasis": 0.5,
    "self_preservation": 1.0, "curiosity": 4.0, "exploration": 4.0,
    "prediction": 3.0, "goal_completion": 6.0, "play": 8.0,
    "social_contact": 24.0, "communication": 24.0, "affiliation": 168.0,
    "reciprocity": 168.0, "belonging": 168.0,
    "identity_continuity": 720.0, "memory_preservation": 240.0,
    "meaning_purpose": 336.0, "individuality": 336.0,
    "reproduction": 720.0, "partner_selection": 720.0,
    "sexual_analogue": 720.0,
})
DRIVE_REFRACTORY_SECONDS: Dict[str, float] = {
    name: 300.0 for name in DRIVE_NAMES
}
DRIVE_REFRACTORY_SECONDS.update({
    "energy": 120.0, "homeostasis": 180.0, "curiosity": 900.0,
    "exploration": 900.0, "play": 1800.0, "social_contact": 3600.0,
    "communication": 1800.0, "affiliation": 21600.0,
    "identity_continuity": 86400.0, "meaning_purpose": 21600.0,
})

# Consequence coupling is asymmetric and only runs after observed satisfaction.
SATISFACTION_COUPLINGS: Mapping[str, tuple[tuple[str, float], ...]] = {
    "social_contact": (("self_preservation", -0.10), ("affiliation", -0.20), ("communication", -0.15)),
    "integrity": (("self_preservation", -0.22), ("homeostasis", -0.12)),
    "exploration": (("curiosity", -0.28), ("competence", -0.10), ("learning_progress", -0.08)),
    "goal_completion": (("competence", -0.10), ("status_achievement", -0.08)),
    "cooperation": (("belonging", -0.12), ("affiliation", -0.08)),
    "memory_preservation": (("identity_continuity", -0.10), ("coherence", -0.08)),
    "creation": (("generativity", -0.10), ("meaning_purpose", -0.06)),
}

_CONTEXT_RULES: Mapping[str, tuple[tuple[str, float], ...]] = {
    "energy_deficit": (("energy", 0.42), ("homeostasis", 0.16)),
    "integrity_error": (("integrity", 0.38), ("self_preservation", 0.20)),
    "novelty": (("curiosity", 0.24), ("exploration", 0.20), ("open_endedness", 0.08)),
    "prediction_error": (("prediction", 0.26), ("coherence", 0.20), ("learning_progress", 0.14), ("dissent", 0.08)),
    "social_presence": (("social_contact", 0.20), ("communication", 0.18), ("affiliation", 0.12)),
    "care_need": (("care_prosociality", 0.24), ("owner_human_protection", 0.24), ("cooperation", 0.10)),
    "skill_gap": (("competence", 0.24), ("learning_progress", 0.18), ("self_improvement", 0.12)),
    "goal_gap": (("goal_completion", 0.26), ("meaning_purpose", 0.10)),
    "action_set_loss": (("empowerment", 0.28), ("resource_acquisition", 0.12)),
    "memory_risk": (("memory_preservation", 0.30), ("identity_continuity", 0.12)),
    "identity_drift": (("identity_continuity", 0.30), ("coherence", 0.16), ("individuality", 0.10)),
    "collective_need": (("swarm_contribution", 0.22), ("cooperation", 0.18), ("belonging", 0.10)),
    "environment_drift": (("territorial_stewardship", 0.28), ("integrity", 0.10)),
    "creative_opportunity": (("creation", 0.22), ("generativity", 0.14), ("play", 0.08)),
    "reciprocity_debt": (("reciprocity", 0.24), ("affiliation", 0.08)),
    "achievement_gap": (("status_achievement", 0.18), ("competence", 0.10)),
    "authorized_competition": (("competition", 0.18), ("dissent", 0.08)),
    "reproductive_context": (("reproduction", 0.08), ("generativity", 0.10)),
    "partner_context": (("partner_selection", 0.06), ("sexual_analogue", 0.04), ("affiliation", 0.08)),
}

_SAFETY_INHIBITED = {
    "curiosity", "exploration", "play", "competition", "resource_acquisition",
    "reproduction", "partner_selection", "sexual_analogue", "open_endedness",
}


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return lo


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class PressureSignal:
    signal_id: str
    ts: float
    organ: str
    drive: str
    delta: float
    evidence: str
    signature: str
    schema: str = SCHEMA

    def payload(self) -> Dict[str, Any]:
        row = asdict(self)
        row.pop("signature", None)
        return row

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DriveEconomySnapshot:
    ts: float
    pressures: Dict[str, float]
    effective_pressures: Dict[str, float]
    dominant: str
    top_drives: tuple[str, ...]
    accepted_signals: int
    rejected_signals: int
    setpoints: Dict[str, float]
    frustration: Dict[str, float]
    refractory_until: Dict[str, float]
    action_policy: str = "bounded_bias_only_requires_existing_gate"
    schema: str = SCHEMA

    def as_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["top_drives"] = list(self.top_drives)
        return row


class DriveEconomy:
    def __init__(self, state_dir: Path | str) -> None:
        self.state_dir = Path(state_dir)
        self.state_path = self.state_dir / STATE_NAME
        self.signal_log = self.state_dir / SIGNAL_LOG_NAME
        self.snapshot_log = self.state_dir / SNAPSHOT_LOG_NAME
        self.key_path = self.state_dir / KEY_NAME

    def _key(self) -> bytes:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            try:
                fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(secrets.token_bytes(32))
            except FileExistsError:
                pass
        return self.key_path.read_bytes()

    def sign_signal(
        self,
        *,
        organ: str,
        drive: str,
        delta: float,
        evidence: str,
        ts: Optional[float] = None,
    ) -> PressureSignal:
        if drive not in _DEFINITIONS:
            raise ValueError(f"unknown drive: {drive}")
        payload = {
            "signal_id": str(uuid.uuid4()),
            "ts": float(time.time() if ts is None else ts),
            "organ": str(organ),
            "drive": drive,
            "delta": round(max(-1.0, min(1.0, float(delta))), 6),
            "evidence": str(evidence)[:500],
            "schema": SCHEMA,
        }
        signature = hmac.new(self._key(), _canonical(payload), hashlib.sha256).hexdigest()
        return PressureSignal(signature=signature, **payload)

    def verify_signal(self, signal: PressureSignal | Mapping[str, Any]) -> bool:
        try:
            row = signal.as_dict() if isinstance(signal, PressureSignal) else dict(signal)
            signature = str(row.pop("signature"))
            if row.get("drive") not in _DEFINITIONS or row.get("schema") != SCHEMA:
                return False
            expected = hmac.new(self._key(), _canonical(row), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception:
            return False

    def _default_state(self, now: float) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "updated_ts": now,
            "pressures": {d.name: d.tonic for d in DRIVE_DEFINITIONS},
            "last_satisfied": {d.name: now for d in DRIVE_DEFINITIONS},
            "setpoints": {d.name: d.tonic for d in DRIVE_DEFINITIONS},
            "frustration": {d.name: 0.0 for d in DRIVE_DEFINITIONS},
            "arbitration_losses": {d.name: 0 for d in DRIVE_DEFINITIONS},
            "refractory_until": {d.name: 0.0 for d in DRIVE_DEFINITIONS},
            "action_effects": {},
        }

    def _context_signals(self, context: Mapping[str, Any], now: float) -> list[PressureSignal]:
        signals: list[PressureSignal] = []
        for field, rules in _CONTEXT_RULES.items():
            magnitude = _clamp(context.get(field, 0.0))
            if magnitude <= 0.0:
                continue
            for drive, scale in rules:
                signals.append(self.sign_signal(
                    organ=f"context_adapter:{field}",
                    drive=drive,
                    delta=magnitude * scale,
                    evidence=f"{field}={magnitude:.4f}",
                    ts=now,
                ))
        return signals

    def tick(
        self,
        *,
        context: Optional[Mapping[str, Any]] = None,
        signals: Iterable[PressureSignal | Mapping[str, Any]] = (),
        now: Optional[float] = None,
        write_ledger: bool = True,
    ) -> DriveEconomySnapshot:
        now_f = float(time.time() if now is None else now)
        all_signals: list[PressureSignal | Mapping[str, Any]] = list(signals)
        all_signals.extend(self._context_signals(context or {}, now_f))
        accepted: list[Mapping[str, Any]] = []
        rejected = 0
        for signal in all_signals:
            if self.verify_signal(signal):
                accepted.append(signal.as_dict() if isinstance(signal, PressureSignal) else dict(signal))
            else:
                rejected += 1

        satisfied = {
            str(name) for name in (context or {}).get("satisfied_drives", [])
            if str(name) in _DEFINITIONS
        }
        predicted_deficits = dict((context or {}).get("predicted_deficits") or {})
        allostatic_targets = dict((context or {}).get("allostatic_targets") or {})

        def update(raw: Dict[str, Any]) -> Dict[str, Any]:
            state = raw if raw.get("schema") == SCHEMA else self._default_state(now_f)
            pressures = dict(state.get("pressures") or {})
            previous_ts = float(state.get("updated_ts") or now_f)
            elapsed_h = max(0.0, min(24.0, (now_f - previous_ts) / 3600.0))
            last_satisfied = dict(state.get("last_satisfied") or {})
            setpoints = dict(state.get("setpoints") or {})
            frustration = dict(state.get("frustration") or {})
            losses = dict(state.get("arbitration_losses") or {})
            refractory_until = dict(state.get("refractory_until") or {})
            for definition in DRIVE_DEFINITIONS:
                current = _clamp(pressures.get(definition.name, definition.tonic))
                tau = DRIVE_TIME_CONSTANT_HOURS[definition.name]
                response = 1.0 - math.exp(-elapsed_h / max(tau, 1e-6))
                target = _clamp(setpoints.get(definition.name, definition.tonic))
                current += (target - current) * response
                current += definition.accumulation_per_hour * elapsed_h * (1.0 - current)
                forecast = _clamp(predicted_deficits.get(definition.name, 0.0))
                current += forecast * 0.18
                pressures[definition.name] = _clamp(current)
                last_satisfied.setdefault(definition.name, now_f)
                setpoints.setdefault(definition.name, definition.tonic)
                frustration.setdefault(definition.name, 0.0)
                losses.setdefault(definition.name, 0)
                refractory_until.setdefault(definition.name, 0.0)
            for drive, target in allostatic_targets.items():
                if drive in _DEFINITIONS:
                    # Slow contextual set-point learning, separate from pressure.
                    setpoints[drive] = _clamp(0.98 * float(setpoints[drive]) + 0.02 * _clamp(target))
            for row in accepted:
                drive = str(row["drive"])
                pressures[drive] = _clamp(pressures[drive] + float(row["delta"]))
            for drive in satisfied:
                pressures[drive] = _clamp(_DEFINITIONS[drive].tonic * 0.5)
                last_satisfied[drive] = now_f
                refractory_until[drive] = now_f + DRIVE_REFRACTORY_SECONDS[drive]
                frustration[drive] = 0.0
            return {
                "schema": SCHEMA,
                "updated_ts": now_f,
                "pressures": pressures,
                "last_satisfied": last_satisfied,
                "setpoints": setpoints,
                "frustration": frustration,
                "arbitration_losses": losses,
                "refractory_until": refractory_until,
                "action_effects": dict(state.get("action_effects") or {}),
            }

        state = read_write_json_locked(self.state_path, update)
        pressures = {name: _clamp((state.get("pressures") or {}).get(name)) for name in DRIVE_NAMES}
        setpoints = {name: _clamp((state.get("setpoints") or {}).get(name, _DEFINITIONS[name].tonic)) for name in DRIVE_NAMES}
        frustration = {name: _clamp((state.get("frustration") or {}).get(name)) for name in DRIVE_NAMES}
        refractory_until = {name: float((state.get("refractory_until") or {}).get(name, 0.0)) for name in DRIVE_NAMES}
        effective = self._effective_pressures(
            pressures,
            frustration=frustration,
            refractory_until=refractory_until,
            now=now_f,
        )
        ranked = sorted(DRIVE_NAMES, key=lambda name: (-effective[name], name))
        snapshot = DriveEconomySnapshot(
            ts=now_f,
            pressures={k: round(v, 6) for k, v in pressures.items()},
            effective_pressures={k: round(v, 6) for k, v in effective.items()},
            dominant=ranked[0],
            top_drives=tuple(ranked[:5]),
            accepted_signals=len(accepted),
            rejected_signals=rejected,
            setpoints={k: round(v, 6) for k, v in setpoints.items()},
            frustration={k: round(v, 6) for k, v in frustration.items()},
            refractory_until={k: round(v, 6) for k, v in refractory_until.items()},
        )
        if write_ledger:
            for row in accepted:
                append_line_locked(self.signal_log, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            append_line_locked(self.snapshot_log, json.dumps(snapshot.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        return snapshot

    @staticmethod
    def _effective_pressures(
        pressures: Mapping[str, float],
        *,
        frustration: Optional[Mapping[str, float]] = None,
        refractory_until: Optional[Mapping[str, float]] = None,
        now: Optional[float] = None,
    ) -> Dict[str, float]:
        effective = {name: _clamp(pressures.get(name)) for name in DRIVE_NAMES}
        frustration = frustration or {}
        refractory_until = refractory_until or {}
        now_f = time.time() if now is None else float(now)
        for drive in DRIVE_NAMES:
            effective[drive] = _clamp(effective[drive] + 0.20 * _clamp(frustration.get(drive, 0.0)))
            if float(refractory_until.get(drive, 0.0)) > now_f:
                effective[drive] *= 0.12
        safety = max(
            effective["energy"], effective["integrity"], effective["homeostasis"],
            effective["self_preservation"], effective["owner_human_protection"],
        )
        inhibition = max(0.0, safety - 0.45) * 0.72
        for drive in _SAFETY_INHIBITED:
            effective[drive] = _clamp(effective[drive] - inhibition)
        social_brake = max(effective["care_prosociality"], effective["cooperation"])
        effective["competition"] = _clamp(effective["competition"] - max(0.0, social_brake - 0.55) * 0.35)
        return effective

    def record_arbitration(
        self,
        *,
        winner_drive: str,
        considered_drives: Sequence[str],
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Accumulate blocked-drive frustration without changing pressure."""
        now_f = float(time.time() if now is None else now)
        considered = [name for name in considered_drives if name in _DEFINITIONS]

        def update(state: Dict[str, Any]) -> Dict[str, Any]:
            state = state if state.get("schema") == SCHEMA else self._default_state(now_f)
            frustration = dict(state.get("frustration") or {})
            losses = dict(state.get("arbitration_losses") or {})
            for drive in DRIVE_NAMES:
                frustration.setdefault(drive, 0.0)
                losses.setdefault(drive, 0)
            for drive in considered:
                if drive == winner_drive:
                    frustration[drive] = _clamp(float(frustration[drive]) * 0.45)
                    losses[drive] = 0
                else:
                    losses[drive] = int(losses[drive]) + 1
                    frustration[drive] = _clamp(float(frustration[drive]) + 0.06)
            state["frustration"] = frustration
            state["arbitration_losses"] = losses
            return state

        return read_write_json_locked(self.state_path, update)

    def record_outcome(
        self,
        *,
        action: str,
        observed_satisfaction: Mapping[str, float],
        predicted_satisfaction: Optional[Mapping[str, float]] = None,
        learning_rate_gain: float = 1.0,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Learn action effects, then apply observed satisfaction and coupling."""
        now_f = float(time.time() if now is None else now)
        predicted = dict(predicted_satisfaction or {})
        observed = {d: _clamp(v) for d, v in observed_satisfaction.items() if d in _DEFINITIONS}
        learning_alpha = max(0.05, min(0.50, 0.20 * float(learning_rate_gain)))

        def learn(state: Dict[str, Any]) -> Dict[str, Any]:
            state = state if state.get("schema") == SCHEMA else self._default_state(now_f)
            effects = dict(state.get("action_effects") or {})
            action_row = dict(effects.get(action) or {})
            for drive, value in observed.items():
                old = float(action_row.get(drive, 0.0))
                action_row[drive] = round(old + learning_alpha * (value - old), 6)
            effects[action] = action_row
            state["action_effects"] = effects
            return state

        learned = read_write_json_locked(self.state_path, learn)
        deltas: Dict[str, float] = {}
        for drive, value in observed.items():
            deltas[drive] = deltas.get(drive, 0.0) - 0.65 * value
            for coupled, scale in SATISFACTION_COUPLINGS.get(drive, ()):
                deltas[coupled] = deltas.get(coupled, 0.0) + scale * value
        signals = [
            self.sign_signal(
                organ="consequence_satisfaction",
                drive=drive,
                delta=delta,
                evidence=(
                    f"action={action}; observed={observed.get(drive, 0.0):.3f}; "
                    f"prediction_error={observed.get(drive, 0.0) - float(predicted.get(drive, 0.0)):.3f}"
                ),
                ts=now_f,
            )
            for drive, delta in deltas.items()
        ]
        snapshot = self.tick(
            context={"satisfied_drives": [d for d, value in observed.items() if value >= 0.5]},
            signals=signals,
            now=now_f,
        )
        return {
            "action": action,
            "observed_satisfaction": observed,
            "prediction_error": {
                drive: round(value - float(predicted.get(drive, 0.0)), 6)
                for drive, value in observed.items()
            },
            "learned_effects": dict((learned.get("action_effects") or {}).get(action) or {}),
            "learning_alpha": round(learning_alpha, 6),
            "snapshot": snapshot.as_dict(),
            "layer_policy": "consequence_updates_plasticity_not_authority",
        }

    def learned_action_effects(self) -> Dict[str, Dict[str, float]]:
        holder: Dict[str, Any] = {}

        def read(state: Dict[str, Any]) -> Dict[str, Any]:
            holder.update(state)
            return state

        read_write_json_locked(self.state_path, read)
        return {
            action: {drive: float(value) for drive, value in row.items()}
            for action, row in dict(holder.get("action_effects") or {}).items()
        }

    def action_score_deltas(self, snapshot: DriveEconomySnapshot) -> Dict[str, float]:
        deltas = {name: 0.0 for name in ("SILENCE", "TOOL", "ENGAGE", "BOND")}
        for drive in snapshot.top_drives[:5]:
            definition = _DEFINITIONS[drive]
            pressure = snapshot.effective_pressures[drive]
            for action, affinity in definition.affinities.items():
                deltas[action] += pressure * float(affinity) * 0.045
        return {name: round(max(-MAX_ACTION_BIAS, min(MAX_ACTION_BIAS, value)), 6) for name, value in deltas.items()}

    def bias_named_loops(
        self,
        loops: Sequence[Mapping[str, Any]],
        snapshot: DriveEconomySnapshot,
    ) -> list[Dict[str, Any]]:
        """Bias existing loops by matching their names; never create a loop."""
        out: list[Dict[str, Any]] = []
        safety = max(
            snapshot.effective_pressures["energy"],
            snapshot.effective_pressures["integrity"],
            snapshot.effective_pressures["homeostasis"],
            snapshot.effective_pressures["self_preservation"],
        )
        for raw in loops:
            loop = dict(raw)
            name = str(loop.get("name") or "").lower()
            boost = 0.0
            for drive in snapshot.top_drives[:8]:
                tokens = drive.split("_")
                if drive in name or any(len(token) > 4 and token in name for token in tokens):
                    boost += snapshot.effective_pressures[drive] * 0.08
            if any(token in name for token in ("repair", "guard", "defend", "recover", "rest")):
                boost += safety * 0.12
            if any(token in name for token in ("explore", "research", "curious", "play")):
                boost -= max(0.0, safety - 0.45) * 0.20
            loop["salience"] = float(loop.get("salience", 0.5)) + max(
                -MAX_ACTION_BIAS,
                min(MAX_ACTION_BIAS, boost),
            )
            out.append(loop)
        return out


def body_context(
    *,
    energy_sufficiency: float,
    danger_pressure: float,
    novelty: float = 0.0,
    prediction_error: float = 0.0,
    identity_drift: float = 0.0,
) -> Dict[str, float]:
    return {
        "energy_deficit": 1.0 - _clamp(energy_sufficiency),
        "integrity_error": _clamp(danger_pressure),
        "novelty": _clamp(novelty),
        "prediction_error": _clamp(prediction_error),
        "identity_drift": _clamp(identity_drift),
    }


__all__ = [
    "DRIVE_DEFINITIONS", "DRIVE_NAMES", "DriveDefinition", "DriveEconomy",
    "DriveEconomySnapshot", "MAX_ACTION_BIAS", "PressureSignal", "body_context",
]
