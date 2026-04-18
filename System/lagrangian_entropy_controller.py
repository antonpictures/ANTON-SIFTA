#!/usr/bin/env python3
"""
lagrangian_entropy_controller.py — λ_norm → PPO entropy coefficient (c₂)
══════════════════════════════════════════════════════════════════════════

**Ordinary RL:** PPO adds an entropy bonus scaled by coefficient c₂ (often written
next to S[π] in the clipped objective). Higher c₂ → more exploration pressure
in the loss; lower c₂ → narrower policy updates (more exploitation).

**SIFTA hook:** Treat manifold pressure `lambda_norm ∈ [0,1]` as a *schedule input*
that **reduces** c₂ under stress. This module is **pure math** — it does not touch
JAX tensors. A future `swarmrl` bridge passes the returned float into
`ProximalPolicyLoss(..., entropy_coefficient=c2)` when constructing the trainer.

DYOR:
  - Spinning Up — PPO: https://spinningup.openai.com/en/latest/algorithms/ppo.html
  - SwarmRL default c₂ = 0.01 — `Archive/swarmrl_upstream/swarmrl/losses/proximal_policy_loss.py`

**Not** evidence of cross-tab coupling or model “awareness” — only a control map.

Trainer hook + call-site map: `System/swarmrl_entropy_hooks.py`.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Literal

ScheduleName = Literal["exponential_lambda", "linear_lambda"]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def entropy_coefficient_exponential(
    lambda_norm: float,
    *,
    c2_max: float = 0.01,
    c2_floor: float = 0.0,
    decay_rate: float = 2.0,
) -> float:
    """
    c₂(λ) = c_floor + (c_max - c_floor) * exp(-k λ).

    At λ=0 → c_max (matches SwarmRL default when unstressed).
    As λ→1 → approaches c_floor (default 0: exploration term effectively off).
    """
    lam = _clamp01(lambda_norm)
    span = max(0.0, float(c2_max) - float(c2_floor))
    return float(c2_floor) + span * math.exp(-float(decay_rate) * lam)


def entropy_coefficient_linear(
    lambda_norm: float,
    *,
    c2_max: float = 0.01,
    c2_min: float = 0.0,
    throttle_slope: float = 0.95,
) -> float:
    """Linear headroom shrink (same spirit as mint throttle in stgm_metabolic)."""
    lam = _clamp01(lambda_norm)
    raw = float(c2_max) * (1.0 - lam * float(throttle_slope))
    return max(float(c2_min), raw)


def exploration_headroom(c2: float, *, c2_max: float = 0.01) -> float:
    """Unitless [0,1] gauge: how much of the nominal exploration budget remains."""
    if c2_max <= 0:
        return 0.0
    return _clamp01(float(c2) / float(c2_max))


def recommended_entropy_schedule(
    lambda_norm: float,
    *,
    schedule: ScheduleName = "exponential_lambda",
    c2_max: float = 0.01,
) -> Dict[str, Any]:
    """
    Single dict for telemetry / Flutter — keeps JSON self-describing.

    `schedule` selects the law; defaults match Gemini-style exponential decay
    at decay_rate=2, c2_max=0.01 (visual parity with browser lab, not mysticism).
    """
    lam = _clamp01(lambda_norm)
    if schedule == "linear_lambda":
        c2 = entropy_coefficient_linear(lam, c2_max=c2_max)
        law = "c2_max * (1 - 0.95*λ), floored at c2_min=0"
    else:
        c2 = entropy_coefficient_exponential(lam, c2_max=c2_max)
        law = "c_floor + (c_max-c_floor)*exp(-2*λ)"
    return {
        "schedule": schedule,
        "lambda_norm": round(lam, 6),
        "entropy_coefficient_c2": round(c2, 8),
        "c2_max": float(c2_max),
        "exploration_headroom": round(exploration_headroom(c2, c2_max=c2_max), 6),
        "law_summary": law,
        "swarmrl_param": "ProximalPolicyLoss.entropy_coefficient",
    }


if __name__ == "__main__":
    print("λ_norm   c2(exp)   headroom")
    for lam in (0.0, 0.25, 0.5, 0.75, 1.0):
        d = recommended_entropy_schedule(lam)
        print(f"{lam:4.2f}    {d['entropy_coefficient_c2']:.6f}   {d['exploration_headroom']:.4f}")


# ═══════════════════════════════════════════════════════════════════
# PIECE 2: Trainer Hook (Perplexity spec)
# ═══════════════════════════════════════════════════════════════════

def refresh_entropy_coefficient(loss_fn: Any, lambda_norm: float) -> float:
    """
    Mutate the loss function's entropy_coefficient before each episode.

    Called by the trainer BEFORE compute_loss(). The loss_fn is an
    instance of ProximalPolicyLoss (or any object with an
    `entropy_coefficient` attribute).

    Returns the new coefficient for logging.
    """
    new_ce = entropy_coefficient_exponential(lambda_norm)
    loss_fn.entropy_coefficient = new_ce
    return new_ce


# ═══════════════════════════════════════════════════════════════════
# PIECE 3: Telemetry Record (Perplexity spec)
# ═══════════════════════════════════════════════════════════════════

def record_entropy_state(
    lambda_norm: float,
    entropy_coefficient: float,
    episode: int | None = None,
) -> Dict[str, Any]:
    """
    Append a log entry so the mapping can be replayed and audited.
    Written to .sifta_state/entropy_schedule.jsonl (flock-safe).
    """
    import json, time, sys
    from pathlib import Path as _P

    _repo = _P(__file__).resolve().parent.parent
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from System.jsonl_file_lock import append_line_locked

    state_dir = _repo / ".sifta_state"
    log_file = state_dir / "entropy_schedule.jsonl"

    entry: Dict[str, Any] = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lambda_norm": round(lambda_norm, 6),
        "entropy_coefficient": round(entropy_coefficient, 8),
        "exploration_headroom": round(
            exploration_headroom(entropy_coefficient), 6
        ),
        "regime": (
            "FULL" if lambda_norm < 0.3
            else "NARROWING" if lambda_norm < 0.7
            else "EXPLOITATION"
        ),
    }
    if episode is not None:
        entry["episode"] = episode

    state_dir.mkdir(parents=True, exist_ok=True)
    append_line_locked(log_file, json.dumps(entry) + "\n")
    return entry

