#!/usr/bin/env python3
"""SIFTA steering subsystem.

The steering spine says the missing layer is not another raw language model;
it is a value, salience, interrupt, and homeostasis layer around the cortex.
This module is that layer in deterministic, testable form.

It does not claim biological cortex equivalence. It combines existing SIFTA
signals into an operational steering vector:

* journal importance: what deserves memory and attention
* reward delta: what the owner reinforced or suppressed
* metabolic pressure: whether Alice should spend or conserve
* owner pressure: care/body-time priority
* sensor salience: whether the body should probe the world
* novelty/risk/tool truth: whether the cortex may act or must verify
* memory mass: whether recall should be pulled before answering

Truth label: STEERING_SUBSYSTEM_V1.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "steering_subsystem.jsonl"
TRUTH_LABEL = "STEERING_SUBSYSTEM_V1"
TRUTH_BOUNDARY = (
    "Deterministic SIFTA steering combiner. It routes attention and budget "
    "from receipt-backed or caller-supplied signals. It is not a biological "
    "brain claim and not a proof of omnidirectional inference."
)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(default)
    return max(0.0, min(1.0, number))


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _ledger_path(state_dir: str | Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _safe_reward_delta(text: str) -> tuple[float, str]:
    try:
        from System.dopamine_reward_loop import detect_reward

        delta, marker = detect_reward(text)
        return float(delta), str(marker or "")
    except Exception:
        return 0.0, ""


def _importance_for(text: str, source: str) -> tuple[float, str, str | None]:
    try:
        from System.swarm_journal_importance import score_importance

        score = score_importance(text, source=source)
        return float(score.score), str(score.label), score.matched_pattern
    except Exception:
        return 0.40 if str(text or "").strip() else 0.0, "SUBSTANTIVE", None


def read_live_metabolic_pressure() -> float:
    """Best-effort live metabolic pressure; returns 0.0 if unavailable."""
    try:
        from System.stgm_economy import scan_economy
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState

        economy = scan_economy().as_dict()
        balance = float(economy.get("canonical_wallet_sum") or 0.0)
        homeostat = MetabolicHomeostat()
        sampled = homeostat.sample_live()
        state = MetabolicState(
            usd_burn_24h=float(getattr(sampled, "usd_burn_24h", 0.0)),
            local_units_24h=float(getattr(sampled, "local_units_24h", 0.0)),
            stgm_balance=balance,
        )
        return _clamp01(homeostat.pressure(state))
    except Exception:
        return 0.0


@dataclass(frozen=True)
class SteeringPrediction:
    source: str
    target: str
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "confidence": round(_clamp01(self.confidence), 4),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SteeringDecision:
    route: str
    priority: float
    budget_multiplier: float
    temperature_hint: float
    should_write_memory: bool
    should_probe_sensors: bool
    should_pull_memory: bool
    should_verify_tools: bool
    salience: float
    interrupt: float
    curiosity: float
    care: float
    conserve: float
    tool_truth: float
    importance_label: str
    matched_pattern: str | None
    reward_delta: float
    reward_marker: str
    signals: dict[str, float] = field(default_factory=dict)
    predictions: tuple[SteeringPrediction, ...] = field(default_factory=tuple)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "route": self.route,
            "priority": round(_clamp01(self.priority), 4),
            "budget_multiplier": round(_clamp01(self.budget_multiplier), 4),
            "temperature_hint": round(max(0.05, min(1.0, float(self.temperature_hint))), 4),
            "should_write_memory": self.should_write_memory,
            "should_probe_sensors": self.should_probe_sensors,
            "should_pull_memory": self.should_pull_memory,
            "should_verify_tools": self.should_verify_tools,
            "salience": round(_clamp01(self.salience), 4),
            "interrupt": round(_clamp01(self.interrupt), 4),
            "curiosity": round(_clamp01(self.curiosity), 4),
            "care": round(_clamp01(self.care), 4),
            "conserve": round(_clamp01(self.conserve), 4),
            "tool_truth": round(_clamp01(self.tool_truth), 4),
            "importance_label": self.importance_label,
            "matched_pattern": self.matched_pattern,
            "reward_delta": round(float(self.reward_delta), 4),
            "reward_marker": self.reward_marker,
            "signals": {k: round(_clamp01(v), 4) for k, v in sorted(self.signals.items())},
            "predictions": [p.to_dict() for p in self.predictions],
        }


def _prediction_edges(
    *,
    salience: float,
    metabolic_pressure: float,
    owner_pressure: float,
    sensor_salience: float,
    memory_mass: float,
    reward_delta: float,
    novelty: float,
    risk: float,
    tool_truth_risk: float,
) -> tuple[SteeringPrediction, ...]:
    """Return explicit any-signal-to-target edges for inspectable steering."""
    reward_mag = _clamp01(abs(reward_delta))
    return (
        SteeringPrediction(
            "journal_importance",
            "attention_budget",
            salience,
            "important text receives more cortex budget",
        ),
        SteeringPrediction(
            "metabolic_pressure",
            "conserve_or_spend",
            metabolic_pressure,
            "high pressure throttles non-urgent work",
        ),
        SteeringPrediction(
            "owner_pressure",
            "care_priority",
            owner_pressure,
            "owner body/time pressure raises care priority",
        ),
        SteeringPrediction(
            "sensor_salience",
            "probe_world",
            sensor_salience,
            "high sensory salience asks the body to sample/probe",
        ),
        SteeringPrediction(
            "memory_mass",
            "pull_recall",
            memory_mass,
            "heavy memory should be recalled before answering",
        ),
        SteeringPrediction(
            "reward_delta",
            "temperature_hint",
            reward_mag,
            "reward/punishment sharpens or softens policy",
        ),
        SteeringPrediction(
            "novelty_risk",
            "deep_cortex",
            max(novelty, risk),
            "novel or risky turns deserve deeper reasoning",
        ),
        SteeringPrediction(
            "tool_truth_risk",
            "verify_before_action",
            tool_truth_risk,
            "possible external action requires receipt-backed verification",
        ),
    )


def steer_event(
    text: str,
    *,
    source: str = "typed",
    signals: Mapping[str, Any] | None = None,
    state_dir: str | Path | None = None,
    write: bool = False,
    now: float | None = None,
) -> SteeringDecision:
    """Build a deterministic steering decision for a turn or organ event.

    ``signals`` can contain any subset of:
    ``metabolic_pressure``, ``owner_pressure``, ``sensor_salience``,
    ``vision_salience``, ``audio_salience``, ``memory_mass``, ``novelty``,
    ``risk``, ``tool_truth_risk``, and ``social_salience``.
    Missing signals default to zero except importance/reward, which are derived
    from text.
    """
    text = str(text or "")
    sig_in = dict(signals or {})
    importance, importance_label, matched_pattern = _importance_for(text, source)
    reward_delta, reward_marker = _safe_reward_delta(text)

    metabolic_pressure = _clamp01(
        sig_in.get("metabolic_pressure"),
        default=read_live_metabolic_pressure() if "metabolic_pressure" not in sig_in else 0.0,
    )
    owner_pressure = _clamp01(sig_in.get("owner_pressure"))
    sensor_salience = max(
        _clamp01(sig_in.get("sensor_salience")),
        _clamp01(sig_in.get("vision_salience")),
        _clamp01(sig_in.get("audio_salience")),
    )
    memory_mass = _clamp01(sig_in.get("memory_mass"))
    novelty = _clamp01(sig_in.get("novelty"))
    risk = _clamp01(sig_in.get("risk"))
    tool_truth_risk = _clamp01(sig_in.get("tool_truth_risk"))
    social_salience = _clamp01(sig_in.get("social_salience"))
    reward_mag = _clamp01(abs(reward_delta))

    salience = _clamp01(max(importance, 0.55 * novelty + 0.45 * sensor_salience))
    interrupt = _clamp01(max(
        1.0 if importance_label == "EMERGENCY" else 0.0,
        0.85 if importance_label == "BOUNDARY" else 0.0,
        risk,
        tool_truth_risk,
    ))
    curiosity = _clamp01(0.55 * novelty + 0.25 * salience + 0.20 * max(0.0, reward_delta))
    care = _clamp01(max(owner_pressure, social_salience, 0.65 if "owner" in text.lower() else 0.0))
    conserve = _clamp01(max(metabolic_pressure, max(0.0, -reward_delta)))
    tool_truth = _clamp01(max(tool_truth_risk, 0.80 if any(w in text.lower() for w in ("send", "delete", "run", "open", "change")) and importance_label == "BOUNDARY" else 0.0))

    priority = _clamp01(
        0.35 * salience
        + 0.25 * interrupt
        + 0.15 * curiosity
        + 0.15 * care
        + 0.10 * memory_mass
    )

    should_verify_tools = bool(tool_truth >= 0.60 or importance_label == "BOUNDARY")
    should_probe_sensors = bool(sensor_salience >= 0.50 and interrupt < 0.85)
    should_pull_memory = bool(memory_mass >= 0.45 or importance_label in {"DOCTRINE", "BOUNDARY", "EMERGENCY"})
    should_write_memory = bool(importance >= 0.40 or interrupt >= 0.65 or abs(reward_delta) >= 0.50)

    if importance_label == "EMERGENCY" or interrupt >= 0.92:
        route = "EMERGENCY_INTERRUPT"
        budget_multiplier = max(0.50, 1.0 - 0.35 * metabolic_pressure)
    elif should_verify_tools:
        route = "VERIFY_BEFORE_ACTION"
        budget_multiplier = max(0.25, 1.0 - 0.55 * metabolic_pressure)
    elif metabolic_pressure >= 0.75 and importance < 0.65:
        route = "CONSERVE_OR_DEFER"
        budget_multiplier = max(0.05, 1.0 - metabolic_pressure)
    elif importance_label in {"UTILITY", "BACKCHANNEL"} and interrupt < 0.40 and novelty < 0.35:
        route = "FAST_REFLEX"
        budget_multiplier = max(0.10, 1.0 - metabolic_pressure)
    elif priority >= 0.48 or novelty >= 0.70 or risk >= 0.60 or importance_label == "DOCTRINE":
        route = "DEEP_CORTEX"
        budget_multiplier = max(0.20, 1.0 - 0.45 * metabolic_pressure)
    else:
        route = "NORMAL_CORTEX"
        budget_multiplier = max(0.15, 1.0 - 0.60 * metabolic_pressure)

    # Positive reward sharpens; punishment softens/explores.
    temperature_hint = 0.30 - 0.10 * max(0.0, reward_delta) + 0.15 * max(0.0, -reward_delta)
    temperature_hint += 0.08 * novelty + 0.05 * risk
    temperature_hint = max(0.10, min(0.70, temperature_hint))

    normalized_signals = {
        "importance": importance,
        "metabolic_pressure": metabolic_pressure,
        "owner_pressure": owner_pressure,
        "sensor_salience": sensor_salience,
        "memory_mass": memory_mass,
        "novelty": novelty,
        "risk": risk,
        "tool_truth_risk": tool_truth_risk,
        "social_salience": social_salience,
        "reward_magnitude": reward_mag,
    }
    decision = SteeringDecision(
        route=route,
        priority=priority,
        budget_multiplier=budget_multiplier,
        temperature_hint=temperature_hint,
        should_write_memory=should_write_memory,
        should_probe_sensors=should_probe_sensors,
        should_pull_memory=should_pull_memory,
        should_verify_tools=should_verify_tools,
        salience=salience,
        interrupt=interrupt,
        curiosity=curiosity,
        care=care,
        conserve=conserve,
        tool_truth=tool_truth,
        importance_label=importance_label,
        matched_pattern=matched_pattern,
        reward_delta=reward_delta,
        reward_marker=reward_marker,
        signals=normalized_signals,
        predictions=_prediction_edges(
            salience=salience,
            metabolic_pressure=metabolic_pressure,
            owner_pressure=owner_pressure,
            sensor_salience=sensor_salience,
            memory_mass=memory_mass,
            reward_delta=reward_delta,
            novelty=novelty,
            risk=risk,
            tool_truth_risk=tool_truth_risk,
        ),
    )
    if write:
        write_steering_receipt(decision, text=text, source=source, state_dir=state_dir, now=now)
    return decision


def write_steering_receipt(
    decision: SteeringDecision,
    *,
    text: str,
    source: str = "typed",
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a steering receipt without storing the full user text."""
    ts = float(now if now is not None else time.time())
    row = decision.to_dict()
    row.update({
        "schema": "SIFTA_STEERING_SUBSYSTEM_RECEIPT_V1",
        "ts": ts,
        "source": str(source or "unknown"),
        "input_sha12": _sha12(str(text or "")),
        "input_preview": " ".join(str(text or "").split())[:120],
        "truth_boundary": TRUTH_BOUNDARY,
    })
    path = _ledger_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def steering_prompt_block(decision: SteeringDecision) -> str:
    """Compact block that a caller can inject into a cortex prompt."""
    flags: list[str] = []
    if decision.should_verify_tools:
        flags.append("verify_tools")
    if decision.should_probe_sensors:
        flags.append("probe_sensors")
    if decision.should_pull_memory:
        flags.append("pull_memory")
    if decision.should_write_memory:
        flags.append("write_memory")
    flag_text = ", ".join(flags) if flags else "none"
    return (
        "STEERING SUBSYSTEM (receipt-backed deterministic gate)\n"
        f"  route: {decision.route}\n"
        f"  priority: {decision.priority:.3f}\n"
        f"  budget_multiplier: {decision.budget_multiplier:.3f}\n"
        f"  temperature_hint: {decision.temperature_hint:.3f}\n"
        f"  importance: {decision.importance_label}\n"
        f"  flags: {flag_text}\n"
        f"  truth: {decision.truth_label}"
    )


def demo_steering_snapshot() -> dict[str, Any]:
    """Small deterministic demo for scripts and smoke tests."""
    samples = [
        ("What time is it?", {"metabolic_pressure": 0.10}),
        ("From now on, steering goes before cortex.", {"novelty": 0.60}),
        ("Do not send that message without a receipt.", {"tool_truth_risk": 0.90}),
        ("Help me now, I can't breathe.", {"metabolic_pressure": 0.95}),
    ]
    return {
        "truth_label": TRUTH_LABEL,
        "decisions": [
            steer_event(text, signals=signals, write=False).to_dict()
            for text, signals in samples
        ],
    }


__all__ = [
    "LEDGER_NAME",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "SteeringDecision",
    "SteeringPrediction",
    "demo_steering_snapshot",
    "read_live_metabolic_pressure",
    "steer_event",
    "steering_prompt_block",
    "write_steering_receipt",
]


if __name__ == "__main__":
    print(json.dumps(demo_steering_snapshot(), indent=2, sort_keys=True))
