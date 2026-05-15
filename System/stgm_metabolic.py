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


# ═══════════════════════════════════════════════════════════════════════════════
# KLEIBER ¾-POWER ACTION ACCOUNTING
# ═══════════════════════════════════════════════════════════════════════════════
#
# Biological grounding:
#   Kleiber (1932): Metabolic rate B ∝ M^(3/4) — every metabolic function,
#   including surveillance, has a sub-linear cost as the organism scales.
#
#   Ballesteros et al. (2018), Scientific Reports — Thermodynamic origin of
#   metabolic scaling. Shows the ¾ exponent emerges from universal cellular
#   energy constraints, not just body mass. Directly supports pricing any
#   compute/sense action as: cost ∝ action_count^0.75.
#
#   Thommen et al. (2019), eLife — Body-size-dependent energy storage causes
#   Kleiber's law scaling even in simple organisms (planarians). Confirms the
#   law holds at small scales relevant to software agents.
#
# SIFTA translation:
#   - `node_power` ≈ organism mass proxy: M5 = 1.0 (full watt), M1 = 0.6, RPi = 0.1
#   - `writes` ≈ metabolic actions taken per epoch
#   - cost = writes^0.75 × node_power × base_cost_per_action
#   - Larger nodes pay more per epoch but less per action (sub-linear economy of scale)
#
# References (DOIs):
#   Kleiber 1932 → Hilgardia 6:315-353
#   Ballesteros et al. 2018 → 10.1038/s41598-018-19853-6
#   Thommen et al. 2019 → 10.7554/eLife.38187
# ═══════════════════════════════════════════════════════════════════════════════

KLEIBER_EXPONENT = 0.75          # the universal ¾ metabolic scaling exponent
BASE_COST_PER_ACTION = 0.001     # base STGM per atomic ledger / immune write
NODE_POWER_M5    = 1.00          # M5 Apple Silicon — full power tier
NODE_POWER_M1    = 0.60          # M1 Apple Silicon — medium power tier
NODE_POWER_RPI   = 0.10          # Raspberry Pi / edge node — low power tier

# Hard budget guard per epoch (prevents runaway during immune storm / debug floods)
MAX_KLEIBER_COST_PER_EPOCH = 5.0  # STGM


def kleiber_action_cost(
    writes: int,
    *,
    node_power: float = NODE_POWER_M5,
    base_cost: float = BASE_COST_PER_ACTION,
    exponent: float = KLEIBER_EXPONENT,
) -> float:
    """
    Kleiber ¾-power cost for a batch of ledger writes / immune actions.

    Formula:
        cost = min(MAX, writes^exponent × node_power × base_cost)

    Biology:
        Metabolic rate B ∝ M^(3/4) (Kleiber 1932).
        Here writes ≈ metabolic work; cost is sub-linear at scale (economy of
        biology: a whale does more with each calorie than a shrew, per unit mass).

    Args:
        writes:     Number of ledger rows / immune interventions in this epoch.
        node_power: Hardware power tier (use NODE_POWER_* constants).
                    M5=1.0, M1=0.6, RPi=0.1. Scales absolute cost to hardware.
        base_cost:  Cost per single write at node_power=1.0, writes=1.
        exponent:   ¾ by default (Kleiber). Tunable for research (must be 0<e<1
                    to preserve sub-linearity).

    Returns:
        STGM cost (float). Pure math, no I/O — pass to STGM spend ledger.
    """
    if writes <= 0:
        return 0.0
    exponent = max(0.01, min(1.0, float(exponent)))  # safety clamp
    node_power = max(0.0, float(node_power))
    raw = (float(writes) ** exponent) * node_power * float(base_cost)
    return round(min(raw, MAX_KLEIBER_COST_PER_EPOCH), 6)


def immune_budget_check(
    writes: int,
    budget_stgm: float,
    *,
    node_power: float = NODE_POWER_M5,
) -> dict:
    """
    Check if an immune intervention batch fits within the current STGM budget.

    Returns a dict with:
        cost:      computed Kleiber cost for `writes` actions
        budget:    the passed budget_stgm
        allowed:   True if cost ≤ budget
        surplus:   budget - cost (positive = headroom, negative = deficit)
        regime:    human-readable metabolic regime string

    Artificial Immune System grounding:
        Hofmeyr & Forrest (2000), Evolutionary Computation — self/non-self
        discrimination via negative selection. The immune system should fire
        only when budget permits; this function is the gate before quarantine
        actions are committed to the ledger (analogous to clonal selection
        threshold).

        de Castro & Von Zuben (2002) — AIS for anomaly detection. Efficiency
        requires cost-gated activation, not unlimited immune response.
    """
    cost = kleiber_action_cost(writes, node_power=node_power)
    surplus = round(float(budget_stgm) - cost, 6)
    # Derive a pressure proxy from budget consumption
    lambda_proxy = _clamp01(cost / max(float(budget_stgm), 1e-9))
    return {
        "cost_stgm":    cost,
        "budget_stgm":  round(float(budget_stgm), 6),
        "allowed":      surplus >= 0.0,
        "surplus_stgm": surplus,
        "writes":       writes,
        "node_power":   node_power,
        "regime":       metabolic_regime_label(lambda_proxy),
        "exponent":     KLEIBER_EXPONENT,
        "citation":     "Kleiber 1932 / Ballesteros 2018 / Thommen 2019",
    }


def describe_kleiber_accounting() -> str:
    """Return a one-paragraph human-readable explanation for docs / dashboard."""
    return (
        "STGM Kleiber ¾-Power Accounting — Every ledger write and immune "
        "quarantine action is priced as: cost = writes^0.75 × node_power × "
        f"{BASE_COST_PER_ACTION} STGM. The sub-linear ¾ exponent comes from "
        "Kleiber's Law (1932): metabolic rate scales as body_mass^0.75 in all "
        "known organisms. Ballesteros et al. (2018) show this exponent emerges "
        "from universal cellular energy constraints — not just body size — making "
        "it a principled cost function for any metabolic action, including "
        "surveillance and computation. Larger nodes (higher node_power) pay more "
        "per epoch but less per action (economy of scale). The budget gate in "
        "immune_budget_check() mirrors the clonal selection threshold in "
        "Hofmeyr & Forrest's Artificial Immune System (2000): the immune system "
        "fires only when the STGM reserve allows it."
    )


if __name__ == "__main__":
    # ── Original pressure-curve demo ──────────────────────────────────
    for lam in (0.0, 0.2, 0.7, 0.95, 1.0):
        print(
            f"λ={lam:.2f}  regime={metabolic_regime_label(lam):20}"
            f"  mint={calculate_metabolic_mint_rate(lam):.4f}"
            f"  store_fee={calculate_dynamic_store_fee(lam):.4f}"
        )

    # ── Kleiber ¾-power demo ──────────────────────────────────────────
    print("\n── Kleiber ¾-Power Action Accounting ──")
    print(f"Exponent: {KLEIBER_EXPONENT}  (Kleiber 1932 / Ballesteros 2018)")
    print(f"Base cost per write: {BASE_COST_PER_ACTION} STGM")
    print(f"\n{'writes':>8}  {'cost (M5)':>12}  {'cost (M1)':>12}  {'cost (RPi)':>12}")
    for n in (1, 5, 10, 50, 100, 500, 1000):
        c_m5  = kleiber_action_cost(n, node_power=NODE_POWER_M5)
        c_m1  = kleiber_action_cost(n, node_power=NODE_POWER_M1)
        c_rpi = kleiber_action_cost(n, node_power=NODE_POWER_RPI)
        print(f"{n:>8}  {c_m5:>12.6f}  {c_m1:>12.6f}  {c_rpi:>12.6f}")

    print("\n── Immune Budget Check (budget=0.05 STGM, M5) ──")
    for n in (1, 10, 50, 200):
        result = immune_budget_check(n, budget_stgm=0.05)
        status = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(f"  writes={n:>4}  cost={result['cost_stgm']:.6f}  {status}  surplus={result['surplus_stgm']:+.6f}")

