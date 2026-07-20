#!/usr/bin/env python3
"""swarm_need_driven_cadence.py — body-law intervals, not kitchen timers.

George (2026-07-10): "my body does something if it needs it not — look my body
does anything every 3 seconds no matter what?"

The disease was `_ATTENTION_DIRECTOR_INTERVAL_MS = 3000`: a hardcoded wall
tick that woke Alice whether or not anything asked for attention. Bodies do
not thrash on a fixed second count. They wake when need rises and rest when
need falls.

Hardware still has a clock (absolute time exists). What we refuse is
**dimensioned life schedules** ("do X every 3s forever"). Intervals here are
derived from dimensionless need ∈ [0, 1]:

    interval = t_min + (t_rest − t_min) · (1 − need)²

- need → 0  → rest near t_rest (idle breath)
- need → 1  → wake near t_min (refractory floor so Qt does not thrash)
- pending work / high salience / engage policy raise need

Companion doctrine:
- System/owner_heartbeat.py — owner presence gates heavy work
- tools/find_static_time_constants.py — kitchen-timer census
- System/event_density_clock.py — perceived time = f(event_rate)
"""

from __future__ import annotations

from typing import Any

# Refractory floor / rest ceiling are *bounds for the event loop*, not life law.
# They exist so Qt timers cannot spin at 0ms or sleep forever without a safety peek.
# The *shape* of the schedule is the formula above, not "3 seconds".
_DEFAULT_T_MIN_MS = 200
_DEFAULT_T_REST_MS = 30_000
_DEFAULT_ATTENTION_T_MIN_S = 0.35
_DEFAULT_ATTENTION_T_REST_S = 12.0

_POLICY_NEED = {
    "engage": 1.0,
    "sample": 0.55,
    "idle": 0.0,
}


def clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def compute_need(
    *,
    policy: str = "idle",
    salience: float = 0.0,
    pending_count: int = 0,
    need_signal: bool = False,
    pending_full_at: int = 4,
) -> float:
    """Dimensionless organism need in [0, 1].

    need = max(policy_need, salience, pending_need[, floor if need_signal])

    Body law on pending work: *any* real pending task is a full wake signal.
    A body does not "half-wake" for a wound because there is only one wound.
    pending_full_at remains for soft scaling of *extra* load beyond the first
    task (unused when pend==0); first task saturates.
    """
    pol = str(policy or "idle").strip().lower()
    policy_need = float(_POLICY_NEED.get(pol, 0.0))
    sal = clamp01(salience)
    pend = max(0, int(pending_count))
    full = max(1, int(pending_full_at))
    if pend <= 0:
        pending_need = 0.0
    else:
        # First pending task → full need; extra tasks stay saturated.
        pending_need = min(1.0, max(1.0, float(pend) / float(full)))
    need = max(policy_need, sal, pending_need)
    if need_signal and pend > 0:
        need = 1.0
    elif need_signal:
        need = max(need, 0.7)
    return clamp01(need)


def need_to_interval_ms(
    need: float,
    *,
    t_min_ms: int = _DEFAULT_T_MIN_MS,
    t_rest_ms: int = _DEFAULT_T_REST_MS,
) -> int:
    """Map need → milliseconds. Body law: interval ∝ (1 − need)².

    Quadratic rest bias: low need stays near rest; high need collapses to t_min.
    """
    n = clamp01(need)
    t_min = max(50, int(t_min_ms))
    t_rest = max(t_min, int(t_rest_ms))
    span = float(t_rest - t_min)
    interval = t_min + span * ((1.0 - n) ** 2)
    return max(t_min, min(t_rest, int(round(interval))))


def need_to_interval_s(
    need: float,
    *,
    t_min_s: float = _DEFAULT_ATTENTION_T_MIN_S,
    t_rest_s: float = _DEFAULT_ATTENTION_T_REST_S,
) -> float:
    """Same body law in seconds (attention sub-organs)."""
    n = clamp01(need)
    t_min = max(0.05, float(t_min_s))
    t_rest = max(t_min, float(t_rest_s))
    span = t_rest - t_min
    interval = t_min + span * ((1.0 - n) ** 2)
    return max(t_min, min(t_rest, float(interval)))


def scheduler_interval_ms(
    *,
    policy: str = "idle",
    salience: float = 0.0,
    pending_count: int = 0,
    need_signal: bool | None = None,
    t_min_ms: int = _DEFAULT_T_MIN_MS,
    t_rest_ms: int = _DEFAULT_T_REST_MS,
    floor_ms: int | None = None,
) -> int:
    """Desktop kernel QTimer interval from live need (not a fixed 3000ms).

    floor_ms: optional absolute floor (tests pass a small engage floor).
    When need is high, the result is max(formula, floor) only if floor is set
    and need is high enough that we'd otherwise thrash — normally floor_ms is
    used as t_min when provided for test harnesses.
    """
    if need_signal is None:
        need_signal = bool(pending_count) or str(policy or "").strip().lower() == "engage" or float(salience or 0) >= 0.55
    need = compute_need(
        policy=policy,
        salience=salience,
        pending_count=pending_count,
        need_signal=bool(need_signal),
    )
    use_min = int(t_min_ms)
    if floor_ms is not None and need >= 0.55:
        # Tests / callers may pin a minimum wake when work is present.
        use_min = max(use_min, int(floor_ms))
    return need_to_interval_ms(need, t_min_ms=use_min, t_rest_ms=t_rest_ms)


def attention_interval_s(
    *,
    policy: str = "idle",
    salience: float = 0.0,
    pending_count: int = 0,
) -> float:
    """How often the attention director itself should fire.

    Replaces hardcoded 1.5 / 3.0 / 6.0 s kitchen tiers.
    """
    need = compute_need(
        policy=policy,
        salience=salience,
        pending_count=pending_count,
        need_signal=False,
    )
    return need_to_interval_s(need)


def explain_cadence(
    *,
    policy: str = "idle",
    salience: float = 0.0,
    pending_count: int = 0,
    need_signal: bool | None = None,
) -> dict[str, Any]:
    """Receipt-friendly explanation for diaries / debug HUD."""
    if need_signal is None:
        need_signal = bool(pending_count) or str(policy or "").strip().lower() == "engage" or float(salience or 0) >= 0.55
    need = compute_need(
        policy=policy,
        salience=salience,
        pending_count=pending_count,
        need_signal=bool(need_signal),
    )
    return {
        "truth_label": "NEED_DRIVEN_CADENCE_V1",
        "formula": "interval = t_min + (t_rest - t_min) * (1 - need)^2",
        "policy": str(policy or "idle"),
        "salience": clamp01(salience),
        "pending_count": int(pending_count),
        "need": need,
        "scheduler_interval_ms": scheduler_interval_ms(
            policy=policy,
            salience=salience,
            pending_count=pending_count,
            need_signal=bool(need_signal),
        ),
        "attention_interval_s": attention_interval_s(
            policy=policy,
            salience=salience,
            pending_count=pending_count,
        ),
        "note": "Not a 3-second kitchen timer. Wake when need rises; rest when need falls.",
    }
