#!/usr/bin/env python3
"""ODE-backed adaptive sampling governor for SIFTA organs.

Research notes in the optimization tournament say the right shape is a
phase-space controller, not a pile of unrelated timers. This module makes that
operational: one small state vector, one vector field, one bounded sample
period decision.

It does not own sensors. It converts receipt-grade inputs such as prediction
error, salience, owner presence, STGM cost, and thermal cost into the next
sampling cadence an organ can use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRUTH_LABEL = "FIELD_GOVERNOR_V1"
LEDGER_NAME = "field_governor.jsonl"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        env = os.environ.get("SIFTA_STATE_ROOT")
        return Path(env) if env else _repo_root() / ".sifta_state"
    p = Path(state_root)
    if p.name == ".sifta_state":
        return p
    if (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


@dataclass(frozen=True)
class GovernorConfig:
    """Numerical and policy constants for one organ family."""

    fast_ms: float = 80.0
    slow_ms: float = 800.0
    attention_k: float = 8.0
    attention_tau_s: float = 0.65
    fatigue_tau_s: float = 8.0
    uncertainty_tau_s: float = 5.0
    cost_gain: float = 0.65
    fatigue_gain: float = 0.35
    dt_s: float = 0.25

    def min_period_s(self) -> float:
        return max(0.001, float(self.fast_ms) / 1000.0)

    def max_period_s(self) -> float:
        return max(self.min_period_s(), float(self.slow_ms) / 1000.0)


@dataclass(frozen=True)
class FieldGovernorInput:
    """Receipt-grade control inputs, normalized to roughly 0..1."""

    prediction_error: float = 0.0
    salience: float = 0.0
    owner_presence: float = 0.0
    task_need: float = 0.0
    evidence_gain: float = 0.0
    thermal_cost: float = 0.0
    stgm_cost: float = 0.0
    interrupt_risk: float = 0.0

    def bounded(self) -> "FieldGovernorInput":
        return FieldGovernorInput(
            prediction_error=_clamp(self.prediction_error),
            salience=_clamp(self.salience),
            owner_presence=_clamp(self.owner_presence),
            task_need=_clamp(self.task_need),
            evidence_gain=_clamp(self.evidence_gain),
            thermal_cost=_clamp(self.thermal_cost),
            stgm_cost=_clamp(self.stgm_cost),
            interrupt_risk=_clamp(self.interrupt_risk),
        )


@dataclass(frozen=True)
class FieldGovernorState:
    """Small phase-space point for one adaptive sampler."""

    attention: float = 0.0
    fatigue: float = 0.0
    uncertainty: float = 0.5

    def bounded(self) -> "FieldGovernorState":
        return FieldGovernorState(
            attention=_clamp(self.attention),
            fatigue=_clamp(self.fatigue),
            uncertainty=_clamp(self.uncertainty),
        )


@dataclass(frozen=True)
class FieldGovernorDecision:
    truth_label: str
    organ_id: str
    state: FieldGovernorState
    inputs: FieldGovernorInput
    sample_period_s: float
    schedule_ms: int
    attention: float
    drive: float
    wake_reason: str
    action: str
    method: str = "rk4_phase_space_exp_schedule"

    def as_dict(self) -> dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "organ_id": self.organ_id,
            "state": asdict(self.state),
            "inputs": asdict(self.inputs),
            "sample_period_s": self.sample_period_s,
            "schedule_ms": self.schedule_ms,
            "attention": self.attention,
            "drive": self.drive,
            "wake_reason": self.wake_reason,
            "action": self.action,
            "method": self.method,
        }


def raw_drive(inputs: FieldGovernorInput, config: GovernorConfig | None = None) -> float:
    """Attention law from tournament notes, bounded for production use."""
    cfg = config or GovernorConfig()
    i = inputs.bounded()
    positive = (
        0.45 * i.prediction_error
        + 0.22 * i.salience
        + 0.16 * i.owner_presence
        + 0.13 * i.task_need
        + 0.12 * i.evidence_gain
    )
    negative = cfg.cost_gain * (
        0.42 * i.thermal_cost + 0.34 * i.stgm_cost + 0.24 * i.interrupt_risk
    )
    return _clamp(positive - negative)


def _derivative(
    state: FieldGovernorState,
    inputs: FieldGovernorInput,
    config: GovernorConfig,
) -> FieldGovernorState:
    s = state.bounded()
    i = inputs.bounded()
    target_attention = raw_drive(i, config)
    load = _clamp(
        0.45 * i.prediction_error
        + 0.20 * i.salience
        + 0.20 * i.task_need
        + 0.15 * (i.thermal_cost + i.stgm_cost)
    )
    evidence = _clamp(0.55 * i.evidence_gain + 0.45 * i.owner_presence)
    target_uncertainty = _clamp(i.prediction_error + i.interrupt_risk - 0.45 * evidence)
    return FieldGovernorState(
        attention=(target_attention - s.attention) / max(config.attention_tau_s, 1e-6),
        fatigue=(load - s.fatigue) / max(config.fatigue_tau_s, 1e-6),
        uncertainty=(target_uncertainty - s.uncertainty) / max(config.uncertainty_tau_s, 1e-6),
    )


def rk4_step(
    state: FieldGovernorState,
    inputs: FieldGovernorInput,
    *,
    config: GovernorConfig | None = None,
    dt_s: float | None = None,
) -> FieldGovernorState:
    """Fourth-order Runge-Kutta step for the governor state vector."""
    cfg = config or GovernorConfig()
    dt = float(cfg.dt_s if dt_s is None else dt_s)
    s0 = state.bounded()

    def add(s: FieldGovernorState, k: FieldGovernorState, scale: float) -> FieldGovernorState:
        return FieldGovernorState(
            attention=s.attention + k.attention * scale,
            fatigue=s.fatigue + k.fatigue * scale,
            uncertainty=s.uncertainty + k.uncertainty * scale,
        )

    k1 = _derivative(s0, inputs, cfg)
    k2 = _derivative(add(s0, k1, dt / 2.0), inputs, cfg)
    k3 = _derivative(add(s0, k2, dt / 2.0), inputs, cfg)
    k4 = _derivative(add(s0, k3, dt), inputs, cfg)
    out = FieldGovernorState(
        attention=s0.attention + dt * (k1.attention + 2 * k2.attention + 2 * k3.attention + k4.attention) / 6.0,
        fatigue=s0.fatigue + dt * (k1.fatigue + 2 * k2.fatigue + 2 * k3.fatigue + k4.fatigue) / 6.0,
        uncertainty=s0.uncertainty + dt * (k1.uncertainty + 2 * k2.uncertainty + 2 * k3.uncertainty + k4.uncertainty) / 6.0,
    )
    return out.bounded()


def decide_sampling(
    inputs: FieldGovernorInput,
    *,
    organ_id: str = "generic",
    prior_state: FieldGovernorState | None = None,
    config: GovernorConfig | None = None,
    reason_hint: str | None = None,
) -> FieldGovernorDecision:
    """Return the next sample-period decision for one organ."""
    cfg = config or GovernorConfig()
    i = inputs.bounded()
    prior = (prior_state or FieldGovernorState()).bounded()
    state = rk4_step(prior, i, config=cfg)
    drive = raw_drive(i, cfg)
    effective_attention = _clamp(
        state.attention
        + 0.35 * i.prediction_error
        + 0.15 * i.salience
        - cfg.fatigue_gain * state.fatigue
        - 0.20 * (i.thermal_cost + i.stgm_cost + i.interrupt_risk)
    )
    min_p = cfg.min_period_s()
    max_p = cfg.max_period_s()
    period = min_p + (max_p - min_p) * math.exp(-float(cfg.attention_k) * effective_attention)
    period = max(min_p, min(max_p, period))

    if i.thermal_cost + i.stgm_cost + i.interrupt_risk >= 1.15:
        wake_reason = "cost_throttle"
    elif i.prediction_error >= 0.18 or i.salience >= 0.28:
        wake_reason = "surprise"
    elif i.owner_presence >= 0.55 or i.task_need >= 0.55:
        wake_reason = "owner_need"
    elif effective_attention <= 0.06:
        wake_reason = "static"
    else:
        wake_reason = "mid"
    if reason_hint:
        wake_reason = f"{wake_reason}:{reason_hint}"

    action = "sample_now" if period <= (min_p + (max_p - min_p) * 0.33) else "defer"
    return FieldGovernorDecision(
        truth_label=TRUTH_LABEL,
        organ_id=str(organ_id),
        state=state,
        inputs=i,
        sample_period_s=round(period, 6),
        schedule_ms=int(round(period * 1000)),
        attention=round(effective_attention, 6),
        drive=round(drive, 6),
        wake_reason=wake_reason,
        action=action,
    )


def decide_from_delta(
    *,
    delta: float,
    baseline: float | None = None,
    organ_id: str = "eye",
    fast_ms: float = 80.0,
    slow_ms: float = 800.0,
    attention_k: float = 8.0,
    thermal_cost: float = 0.0,
    stgm_cost: float = 0.0,
    interrupt_risk: float = 0.0,
    owner_presence: float = 0.0,
) -> FieldGovernorDecision:
    """Convenience adapter for frame-delta organs such as the eye."""
    d = _clamp(delta)
    b = _clamp(d if baseline is None else baseline)
    salience = _clamp(max(0.0, d - b) / max(0.05, b + 0.001))
    return decide_sampling(
        FieldGovernorInput(
            prediction_error=d,
            salience=salience,
            owner_presence=owner_presence,
            thermal_cost=thermal_cost,
            stgm_cost=stgm_cost,
            interrupt_risk=interrupt_risk,
            evidence_gain=max(0.0, 1.0 - d) * 0.12,
        ),
        organ_id=organ_id,
        config=GovernorConfig(
            fast_ms=fast_ms,
            slow_ms=slow_ms,
            attention_k=attention_k,
        ),
    )


def _receipt_id(row: dict[str, Any]) -> str:
    blob = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def write_decision_receipt(
    decision: FieldGovernorDecision,
    *,
    state_root: str | Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one receipt. Never used by hot paths unless they opt in."""
    row: dict[str, Any] = {
        "ts": time.time(),
        "kind": "FIELD_GOVERNOR_DECISION",
        "truth_label": TRUTH_LABEL,
        "decision": decision.as_dict(),
    }
    if extra:
        row["extra"] = extra
    row["receipt_id"] = _receipt_id(row)
    path = _state_dir(state_root) / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return row


def _cli() -> int:
    parser = argparse.ArgumentParser(description="SIFTA adaptive field governor")
    parser.add_argument("--delta", type=float, default=0.0)
    parser.add_argument("--baseline", type=float, default=None)
    parser.add_argument("--thermal-cost", type=float, default=0.0)
    parser.add_argument("--stgm-cost", type=float, default=0.0)
    parser.add_argument("--interrupt-risk", type=float, default=0.0)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    decision = decide_from_delta(
        delta=args.delta,
        baseline=args.baseline,
        thermal_cost=args.thermal_cost,
        stgm_cost=args.stgm_cost,
        interrupt_risk=args.interrupt_risk,
    )
    payload: dict[str, Any] = {"decision": decision.as_dict()}
    if args.write:
        payload["receipt"] = write_decision_receipt(decision, state_root=args.state_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
