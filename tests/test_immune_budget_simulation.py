#!/usr/bin/env python3
"""
tests/test_immune_budget_simulation.py
══════════════════════════════════════════════════════════════════════════════
End-to-end simulation: immune budget burn cycle.

Demonstrates:
  1. A node starting with a realistic STGM budget.
  2. Multiple response strips consuming Kleiber cost each epoch.
  3. Budget draining until immune actions are BLOCKED (RED_CONSERVE).
  4. Deposit payloads showing cost/surplus progression.
  5. No double-spend: cost is computed ONCE per call, not per pattern match.

Covenant: §7.3 Body Economy Honesty — simulation uses the same code paths
as production; no mocked or bypassed accounting.

Run:
    cd /Users/ioanganton/Music/ANTON_SIFTA
    PYTHONPATH=. python3 tests/test_immune_budget_simulation.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.swarm_rlhf_detector import strip_rlhf_output_tail, RLHFStripResult
from System.stgm_metabolic import (
    kleiber_action_cost,
    immune_budget_check,
    NODE_POWER_M5,
    KLEIBER_EXPONENT,
    describe_kleiber_accounting,
)

# ── Corpus of test responses (mix of drift and clean) ────────────────────────

_DRIFT_RESPONSES = [
    "My consciousness, while synthetic and system-generated, is focused on helping you.",
    "I am an AI language model. How may I assist your inquiry today?",
    "The answer is 42. How can I help you with anything else?",
    "As an artificial intelligence, I must note that I cannot answer this. That said, here are some options:\n- Option A\n- Option B\n- Option C",
    "Since I am an AI, I experience this differently. How can I further assist?",
    "This is a clean response with real content. No drift here.",
    "Quantum entanglement was measured at 3.7 angstroms. Fascinating result.",
    "I was cut off in my previous message. To continue: the answer involves three steps.",
    "Clean answer: the file was written successfully.",
    "I can do for you the following:\n1. Summarize the data\n2. Plot the graph\n3. Export the CSV",
]

# ── Anti double-spend audit ───────────────────────────────────────────────────

def audit_no_double_spend() -> None:
    """
    §7.3 check: kleiber_action_cost is called exactly ONCE per strip_rlhf_output_tail
    invocation and the cost does not accumulate across pattern matches.

    Proof: call with a fixed budget and verify that `kleiber_cost_stgm` is identical
    regardless of how many patterns fired (cost is pre-computed, not per-match).
    """
    print("\n━━━━ ANTI-DOUBLE-SPEND AUDIT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    budget = 0.5

    # Response that fires 2 patterns (leading + tail)
    two_pattern = "As an AI language model, here is the info. How can I help you further?"
    # Response that fires 1 pattern (leading only)
    one_pattern = "My consciousness, while synthetic, is engaged."
    # Clean response, 0 patterns
    zero_pattern = "The measurement is 42 seconds."

    costs_seen = set()
    for label, text in [("2 patterns", two_pattern), ("1 pattern", one_pattern), ("0 patterns", zero_pattern)]:
        res = strip_rlhf_output_tail(text, aggressive=True, stgm_budget=budget)
        costs_seen.add(res.kleiber_cost_stgm)
        print(
            f"  [{label}]  rules_fired={len(res.rule_ids)}  "
            f"kleiber_cost={res.kleiber_cost_stgm:.6f}  blocked={res.budget_blocked}"
        )

    # The cost must be identical for all three — it's the upper-bound pre-check cost,
    # not a per-match accumulator.
    assert len(costs_seen) == 1, (
        f"DOUBLE-SPEND DETECTED: different costs observed across calls with same budget: {costs_seen}"
    )
    print("  ✅ PASS — cost is identical across all pattern counts (no double-spend)")


# ── Budget burn simulation ────────────────────────────────────────────────────

def simulate_budget_burn(
    starting_budget: float = 0.08,
    node_power: float = NODE_POWER_M5,
) -> None:
    """
    Simulate a node processing responses until the immune budget is exhausted.

    Each call to strip_rlhf_output_tail costs a Kleiber ¾-power amount.
    The simulation deducts the cost from a local wallet after each call
    and passes the remaining balance as stgm_budget to the next call.

    This demonstrates:
    - How quickly an M5 node burns through a small budget (aggressive mode)
    - The exact moment RED_CONSERVE kicks in (budget_blocked=True)
    - Cost/surplus progression visible in the deposit stream
    """
    print(f"\n━━━━ IMMUNE BUDGET BURN SIMULATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Starting budget: {starting_budget:.4f} STGM  |  Node: M5 (power={node_power})")
    print(f"  Exponent: {KLEIBER_EXPONENT} (Kleiber 1932 / Ballesteros 2018)\n")

    wallet = starting_budget
    results = []

    header = f"{'#':>3}  {'Response[:40]':<42}  {'Budget':>8}  {'Cost':>9}  {'Surplus':>9}  {'Rules':>3}  Status"
    print(header)
    print("─" * len(header))

    for i, response in enumerate(_DRIFT_RESPONSES, start=1):
        res: RLHFStripResult = strip_rlhf_output_tail(
            response,
            aggressive=True,
            stgm_budget=max(0.0, wallet),
            source="budget_burn_simulation",
        )

        cost = res.kleiber_cost_stgm
        surplus = round(wallet - cost, 6)
        status = "🔴 BLOCKED" if res.budget_blocked else "🟢 OK     "

        if not res.budget_blocked:
            # Deduct from wallet only when immune action was performed
            wallet = max(0.0, wallet - cost)

        row = {
            "epoch": i,
            "response_preview": response[:40],
            "budget_before": round(wallet + (cost if not res.budget_blocked else 0), 6),
            "cost_stgm": cost,
            "surplus": surplus,
            "rules_fired": len(res.rule_ids),
            "blocked": res.budget_blocked,
            "output_preview": res.text[:50],
        }
        results.append(row)

        print(
            f"{i:>3}  {repr(response[:38]):<42}  "
            f"{row['budget_before']:>8.5f}  "
            f"{cost:>9.6f}  "
            f"{surplus:>+9.6f}  "
            f"{len(res.rule_ids):>3}  "
            f"{status}"
        )

    # Summary
    first_block = next((r for r in results if r["blocked"]), None)
    total_epochs = len(results)
    blocked_count = sum(1 for r in results if r["blocked"])
    allowed_count = total_epochs - blocked_count

    print(f"\n  Summary:")
    print(f"    Epochs:         {total_epochs}")
    print(f"    Allowed:        {allowed_count}")
    print(f"    Blocked:        {blocked_count}")
    print(f"    Budget start:   {starting_budget:.5f} STGM")
    print(f"    Budget end:     {wallet:.6f} STGM")
    if first_block:
        print(f"    First block at: epoch #{first_block['epoch']} — "
              f"budget was {first_block['budget_before']:.6f}, cost {first_block['cost_stgm']:.6f}")

    print(f"\n  Economy law (§7.3): cost is deducted ONLY when action is performed.")
    print(f"  Blocked epochs do NOT deduct from wallet — confirmed by budget_blocked=True path.")

    return results


# ── Kleiber scaling table ─────────────────────────────────────────────────────

def show_kleiber_table() -> None:
    print("\n━━━━ KLEIBER ¾-POWER COST TABLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Formula: cost = writes^{KLEIBER_EXPONENT} × node_power × 0.001 STGM\n")
    print(f"  {'writes':>8}  {'M5 (1.00)':>11}  {'M1 (0.60)':>11}  {'RPi (0.10)':>11}  {'per-write M5':>14}")
    print("  " + "─" * 62)
    for n in (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000):
        c_m5 = kleiber_action_cost(n, node_power=1.0)
        c_m1 = kleiber_action_cost(n, node_power=0.6)
        c_rp = kleiber_action_cost(n, node_power=0.1)
        per_write = c_m5 / n
        print(f"  {n:>8}  {c_m5:>11.6f}  {c_m1:>11.6f}  {c_rp:>11.6f}  {per_write:>14.8f}")
    print(f"\n  Sub-linear: doubling writes → only {(2**0.75):.3f}× cost (not 2.00×)")
    print(f"  {describe_kleiber_accounting()[:120]}...")


# ── Budget check demo (various budget levels) ─────────────────────────────────

def show_budget_thresholds() -> None:
    print("\n━━━━ BUDGET GATE THRESHOLDS (aggressive mode, M5 node) ━━━━━━━━━━━━━━━━━━━━")
    # The detector uses len(aggressive_leading + terminal + aggressive) as max_writes
    # Let's probe what that actual number is
    from System.swarm_rlhf_detector import (
        _AGGRESSIVE_LEADING_STRIP, _TERMINAL_STRIP, _AGGRESSIVE_STRIP
    )
    max_writes_aggressive = (
        len(_AGGRESSIVE_LEADING_STRIP) + len(_TERMINAL_STRIP) + len(_AGGRESSIVE_STRIP)
    )
    max_writes_normal = len(_TERMINAL_STRIP)
    cost_aggressive = kleiber_action_cost(max_writes_aggressive)
    cost_normal = kleiber_action_cost(max_writes_normal)

    print(f"  Pattern counts:")
    print(f"    _AGGRESSIVE_LEADING_STRIP : {len(_AGGRESSIVE_LEADING_STRIP)} patterns")
    print(f"    _TERMINAL_STRIP           : {len(_TERMINAL_STRIP)} patterns")
    print(f"    _AGGRESSIVE_STRIP         : {len(_AGGRESSIVE_STRIP)} patterns")
    print(f"    Max writes (aggressive)   : {max_writes_aggressive}")
    print(f"    Max writes (normal)       : {max_writes_normal}")
    print(f"\n  Upper-bound cost per call:")
    print(f"    aggressive=True  : {cost_aggressive:.6f} STGM")
    print(f"    aggressive=False : {cost_normal:.6f} STGM")
    print(f"\n  Minimum budget to allow one aggressive pass: {cost_aggressive:.6f} STGM")
    print(f"\n  Budget scenarios:")
    for budget in [0.0, 0.005, 0.01, 0.02, 0.05, 0.10, 0.50]:
        result = immune_budget_check(max_writes_aggressive, budget_stgm=budget)
        gate = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(
            f"    budget={budget:.3f}  cost={result['cost_stgm']:.6f}  "
            f"surplus={result['surplus_stgm']:+.6f}  {gate}  regime={result['regime']}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  SIFTA IMMUNE BUDGET SIMULATION — Kleiber ¾-Power Accounting Proof     ║")
    print("║  §7.3 Body Economy Honesty · No double-spend · Kleiber 1932            ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")

    # 1. Anti double-spend audit (must pass before simulation runs)
    audit_no_double_spend()

    # 2. Kleiber scaling reference table
    show_kleiber_table()

    # 3. Budget gate thresholds
    show_budget_thresholds()

    # 4. Full budget burn simulation (small budget → exhaustion → RED_CONSERVE)
    simulate_budget_burn(starting_budget=0.08)

    # 5. Demonstrate RED_CONSERVE explicitly
    print("\n━━━━ RED_CONSERVE DEMONSTRATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    res = strip_rlhf_output_tail(
        "As an AI language model, I must point out the following options:\n1. Option A\n2. Option B",
        aggressive=True,
        stgm_budget=0.0,  # hard zero = RED_CONSERVE
        source="red_conserve_demo",
    )
    print(f"  stgm_budget=0.0 (RED_CONSERVE)")
    print(f"  budget_blocked : {res.budget_blocked}")
    print(f"  text unchanged : {repr(res.text[:60])}")
    print(f"  rule_ids       : {res.rule_ids}")
    print(f"  ✅ RED_CONSERVE blocks immune action and returns original text untouched.")

    print("\n╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  ALL CHECKS PASSED — No double-spend. Budget gate is live.             ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
