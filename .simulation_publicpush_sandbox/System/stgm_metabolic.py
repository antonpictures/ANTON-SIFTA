#!/usr/bin/env python3
"""
stgm_metabolic.py — Vector 14: metabolic throttle (pure math, no I/O)
══════════════════════════════════════════════════════════════════════

Pressure-dependent **effective** STGM rates for mint-side payouts and
store-side economics. Bounded power law on storage stress; linear throttle
on mint — no exponentials (deadlock-safe).

Defaults mirror `StigmergicMemoryBus` store payout (`STGM_STORE_REWARD = 0.05`).
Callers that mean “casino mint” or another base can pass `base_mint=`.

**Integration:** Any change to real ledger lines must still go through
`System/crypto_keychain.py` signing — this module only returns floats.

DYOR (retrieved **2026-04-17**, stigmergic clock = wall date in user session):
  - Lagrangian / dual view of resource prices in online allocation:
    https://proceedings.mlr.press/v119/balseiro20a.html  
    https://arxiv.org/abs/2411.01899  
  - Primal–dual policies without re-solving (shadow prices ≈ λ pressure):
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5133857  
"""

from __future__ import annotations

# Align with System/stigmergic_memory_bus.py — do not silently drift.
DEFAULT_BASE_STORE_PAYOUT = 0.05   # STGM_STORE_REWARD (swimmer reward on store)
DEFAULT_BASE_MINT = 0.05          # same scale unless caller overrides (e.g. casino)

# Curve (tunable; Vector 9 meta-controller could own these later)
STRESS_EXPONENT_P = 2.0
PENALTY_MULTIPLIER_K = 2.0
MAX_STORE_MULTIPLIER = 3.0

MINT_THROTTLE_SLOPE = 0.9   # at λ=1 → factor (1 - slope) = 0.1 of linear headroom
MINT_FLOOR_FRACTION = 0.10  # never pay less than 10% of base mint (starvation guard)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def calculate_metabolic_mint_rate(
    lambda_norm: float,
    *,
    base_mint: float | None = None,
) -> float:
    """
    Linear throttle: effective = base * (1 - λ * 0.9), floored at 10% of base.

    `lambda_norm` in [0, 1] — same sense as CWMS / manifold pressure.
    """
    base = DEFAULT_BASE_MINT if base_mint is None else float(base_mint)
    lam = _clamp01(lambda_norm)
    raw = base * (1.0 - lam * MINT_THROTTLE_SLOPE)
    floor = base * MINT_FLOOR_FRACTION
    return max(floor, raw)


def calculate_dynamic_store_fee(
    lambda_norm: float,
    *,
    base_store: float | None = None,
    p: float | None = None,
    k: float | None = None,
) -> float:
    """
    Capped power-law stress on storage *cost* (relative STGM units):

        fee = min(base * max_mult, base * (1 + k * λ^p))

    No runaway: hard cap at `MAX_STORE_MULTIPLIER` × base.
    """
    base = DEFAULT_BASE_STORE_PAYOUT if base_store is None else float(base_store)
    pp = STRESS_EXPONENT_P if p is None else float(p)
    kk = PENALTY_MULTIPLIER_K if k is None else float(k)
    lam = _clamp01(lambda_norm)

    scaled = base * (1.0 + kk * (lam**pp))
    cap = base * MAX_STORE_MULTIPLIER
    return min(scaled, cap)


def metabolic_regime_label(lambda_norm: float) -> str:
    """UI / logging helper — not used in economics."""
    lam = _clamp01(lambda_norm)
    if lam > 0.7:
        return "METABOLIC_BUNKER"
    if lam < 0.3:
        return "CALM_EXPLORATION"
    return "TRANSITION"


if __name__ == "__main__":
    for lam in (0.0, 0.2, 0.7, 0.95, 1.0):
        print(
            f"λ={lam:.2f}  regime={metabolic_regime_label(lam):20}"
            f"  mint={calculate_metabolic_mint_rate(lam):.4f}"
            f"  store_fee={calculate_dynamic_store_fee(lam):.4f}"
        )
