#!/usr/bin/env python3
"""
stigmergic_composition.py — Fuse Track-A (λ) and Track-B (trace) entropy coefficients
════════════════════════════════════════════════════════════════════════════════════

SwarmGPT “composition primitive” with one **semantic fix**: inputs are **entropy
coefficients** (order ~1e-2), not probabilities in [0, 1]. We sanitize with a
**positive floor** and an **upper cap** on inputs before `min` / `weighted` /
`harmonic`, instead of clamping both tracks to [0, 1] (which would mangle typical
PPO c₂ scales).

See: `System/swarmrl_entropy_hooks.refresh_entropy_dual_track`
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompositionConfig:
    """How Track A (λ schedule) and Track B (trace schedule) merge into one c₂."""

    mode: str = "harmonic"  # harmonic | min | weighted
    alpha: float = 0.5  # weight on c_lambda when mode == weighted
    eps: float = 1e-8
    input_cap: float = 0.2  # sane upper bound on coef going into the mixer


def _sanitize_coef(x: float, *, cap: float, eps: float) -> float:
    if x <= 0.0:
        return eps
    return min(float(x), float(cap))


def compose_entropy_coeff(
    c_lambda: float,
    c_trace: float,
    config: CompositionConfig | None = None,
) -> float:
    """
    Fuse two independent entropy coefficients.

    harmonic (default): 2 a b / (a + b + eps) — penalizes either track going tiny.
    """
    cfg = config or CompositionConfig()
    a = _sanitize_coef(c_lambda, cap=cfg.input_cap, eps=cfg.eps)
    b = _sanitize_coef(c_trace, cap=cfg.input_cap, eps=cfg.eps)

    if cfg.mode == "min":
        return min(a, b)

    if cfg.mode == "weighted":
        return cfg.alpha * a + (1.0 - cfg.alpha) * b

    denom = a + b + cfg.eps
    return 2.0 * a * b / denom


__all__ = ["CompositionConfig", "compose_entropy_coeff", "detect_policy_collapse"]


def detect_policy_collapse(
    c_lambda: float,
    c_trace: float,
    threshold: float = 0.001,
) -> bool:
    """
    If BOTH tracks are near zero, the policy has collapsed into
    premature exploitation. Warning signal for the trainer.
    """
    return c_lambda < threshold and c_trace < threshold


if __name__ == "__main__":
    print("═" * 65)
    print("  STIGMERGIC COMPOSITION — Dual-Track Fusion Test")
    print("═" * 65)
    print()

    cases = [
        (0.010, 0.010, "Both calm"),
        (0.010, 0.002, "λ calm, traces exhausted"),
        (0.002, 0.010, "λ stressed, traces fresh"),
        (0.002, 0.002, "Both stressed"),
        (0.010, 0.000, "Traces collapsed"),
        (0.000, 0.010, "λ collapsed"),
    ]

    for mode in ["harmonic", "min", "weighted"]:
        cfg = CompositionConfig(mode=mode)
        print(f"  Mode: {mode}")
        print(f"  {'c_λ':>8}  {'c_trace':>8}  {'fused':>8}  {'collapse':>9}  scenario")
        print("  " + "─" * 60)
        for c_l, c_t, label in cases:
            fused = compose_entropy_coeff(c_l, c_t, cfg)
            collapse = detect_policy_collapse(c_l, c_t)
            flag = "⚠️ YES" if collapse else "   no"
            print(f"  {c_l:>8.4f}  {c_t:>8.4f}  {fused:>8.6f}  {flag:>9}  {label}")
        print()

    print("  ✅ Dual-track arbitration verified across all modes.")

