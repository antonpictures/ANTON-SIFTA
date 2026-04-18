#!/usr/bin/env python3
"""
poker_gatekeeper.py — Alice's Demanded Decision Function
══════════════════════════════════════════════════════════════
The formal GatekeeperFunction that outputs ACTION ∈ {GUESS, CASH_OUT}.

Core rule (what Alice asked for):
  CASH_OUT is mandatory when Capital < OddsMultiplier × 1.2
  
  Because at that point, the expected value of GUESS is negative:
    EV(GUESS) = P(win) × payout - P(lose) × capital
  
  When capital is thin relative to odds, the downside annihilates
  the bankroll. CASH_OUT becomes the only path of minimum systemic risk.

This is not gambling strategy. This is Kelly Criterion applied to
STGM token management inside the Swarm economy.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Literal

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_GATEKEEPER_LOG = _STATE_DIR / "poker_gatekeeper.jsonl"

Action = Literal["GUESS", "CASH_OUT"]


@dataclass
class HandState:
    """The current state of a poker hand / double-or-nothing round."""
    current_payout: float     # What you'd receive if you cash out NOW
    rounds_survived: int      # How many successful guesses so far
    streak_probability: float # Cumulative probability of having reached here


@dataclass
class GatekeeperDecision:
    """The formal output of the gatekeeper."""
    action: Action
    reason: str
    ev_guess: float           # Expected value of guessing
    ev_cashout: float         # Expected value of cashing out (= current_payout)
    risk_ratio: float         # Capital / (OddsMultiplier × 1.2)
    kelly_fraction: float     # Optimal bet fraction (0 = don't bet)


def _read_lambda_components() -> Dict[str, float]:
    """Read individual λ components from the Lagrangian manifold."""
    defaults = {"lambda_congestion": 0.0, "lambda_safety": 0.0, "lambda_energy": 0.0}
    try:
        p = _STATE_DIR / "lagrangian_multipliers.json"
        if p.exists():
            d = json.loads(p.read_text())
            return {k: d.get(k, 0.0) for k in defaults}
    except Exception:
        pass
    return defaults


def _softmax(x: list) -> list:
    """Numerically stable softmax."""
    import math
    max_x = max(x)
    exps = [math.exp(v - max_x) for v in x]
    total = sum(exps)
    return [e / total for e in exps]


def compress_constraint_state(capital: float, odds_multiplier: float) -> Dict[str, float]:
    """
    Compress raw λ vector into a stable constraint_state for the policy.
    The policy reads THIS, never raw λ directly.
    """
    lambdas = _read_lambda_components()
    lambda_sum = sum(lambdas.values())
    lambda_max = max(lambdas.values())
    import math
    lambda_norm = math.sqrt(sum(v ** 2 for v in lambdas.values()))

    # τ = (Odds × 1.2) × (1 + Σλ), clamped
    base_tau = odds_multiplier * 1.2
    tau = base_tau * (1.0 + lambda_sum)
    tau = max(base_tau * 0.5, min(tau, base_tau * 5.0))  # clamp

    # Risk pressure: how close is capital to τ?
    risk_pressure = max(0.0, 1.0 - (capital / tau)) if tau > 0 else 0.0

    return {
        "tau": round(tau, 4),
        "lambda_sum": round(lambda_sum, 5),
        "lambda_norm": round(lambda_norm, 5),
        "lambda_max": round(lambda_max, 5),
        "risk_pressure": round(risk_pressure, 4)
    }


def GatekeeperFunction(
    hand: HandState,
    capital: float,
    odds_multiplier: float = 2.0,
    win_probability: float = 0.5
) -> GatekeeperDecision:
    """
    Alice's demanded function, upgraded with:
    - Adaptive τ from the Lagrangian manifold
    - Softmax probability distribution over actions (SwarmGPT spec)
    
    Hard override: Capital < τ → MANDATORY CASH_OUT (non-negotiable)
    Soft policy:   P(GUESS), P(CASH_OUT) = softmax(logits shaped by λ pressure)
    
    The action field returns argmax(P), but the full distribution is logged.
    """
    cs = compress_constraint_state(capital, odds_multiplier)
    tau = cs["tau"]
    
    # Expected values
    potential_win = hand.current_payout * odds_multiplier
    ev_guess = (win_probability * potential_win) - ((1 - win_probability) * hand.current_payout)
    ev_cashout = hand.current_payout
    
    # Kelly Criterion: f* = (bp - q) / b
    b = odds_multiplier - 1
    p = win_probability
    q = 1 - p
    kelly = (b * p - q) / b if b > 0 else 0.0
    
    # Risk ratio
    risk_ratio = capital / tau if tau > 0 else 0.0
    
    # ──── HARD OVERRIDE (Alice's non-negotiable rule) ────
    if capital < tau:
        return GatekeeperDecision(
            action="CASH_OUT",
            reason=f"MANDATORY: Capital ({capital:.2f}) < τ ({tau:.2f}). P(CASH_OUT)=1.0",
            ev_guess=round(ev_guess, 4),
            ev_cashout=round(ev_cashout, 4),
            risk_ratio=round(risk_ratio, 4),
            kelly_fraction=round(kelly, 4)
        )
    
    # ──── SOFT PROBABILISTIC POLICY (SwarmGPT's differentiable spec) ────
    # Logits shaped by EV, τ, and λ pressure
    guess_logit = ev_guess - tau
    cashout_logit = (tau - ev_guess) + 0.8 * cs["lambda_norm"]
    guess_logit -= 0.3 * cs["risk_pressure"]
    
    # Streak penalty: deep streaks push toward CASH_OUT
    if hand.rounds_survived >= 3 and hand.streak_probability < 0.15:
        cashout_logit += 2.0  # Strong bias toward exit
    
    probs = _softmax([guess_logit, cashout_logit])
    p_guess, p_cashout = probs[0], probs[1]
    
    # Action = argmax of the distribution
    action = "GUESS" if p_guess > p_cashout else "CASH_OUT"
    
    return GatekeeperDecision(
        action=action,
        reason=f"P(GUESS)={p_guess:.3f} P(CASH_OUT)={p_cashout:.3f} | τ={tau:.2f} λ_norm={cs['lambda_norm']:.4f}",
        ev_guess=round(ev_guess, 4),
        ev_cashout=round(ev_cashout, 4),
        risk_ratio=round(risk_ratio, 4),
        kelly_fraction=round(kelly, 4)
    )


def log_decision(decision: GatekeeperDecision, hand: HandState, capital: float):
    """Append to the gatekeeper ledger."""
    try:
        entry = {
            "ts": time.time(),
            "action": decision.action,
            "reason": decision.reason,
            "capital": capital,
            "payout": hand.current_payout,
            "risk_ratio": decision.risk_ratio,
            "kelly": decision.kelly_fraction
        }
        with open(_GATEKEEPER_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass


if __name__ == "__main__":
    print("═" * 66)
    print("  POKER GATEKEEPER — Probabilistic Policy w/ Lagrangian Pressure")
    print("  P(action | state, constraint_state) = softmax(logits)")
    print("═" * 66 + "\n")
    
    scenarios = [
        ("Low capital, early round", HandState(10.0, 1, 0.5), 2.0),
        ("Healthy capital, round 2", HandState(10.0, 2, 0.25), 50.0),
        ("Deep streak, thin odds", HandState(80.0, 4, 0.0625), 100.0),
        ("Fresh hand, fat stack", HandState(5.0, 0, 1.0), 200.0),
    ]
    
    # Show constraint state once
    cs = compress_constraint_state(50.0, 2.0)
    print(f"  [ Constraint State ]")
    print(f"    τ = {cs['tau']} | Σλ = {cs['lambda_sum']} | ||λ|| = {cs['lambda_norm']} | risk = {cs['risk_pressure']}")
    print()
    
    for label, hand, capital in scenarios:
        d = GatekeeperFunction(hand, capital)
        log_decision(d, hand, capital)
        
        icon = "🟢 GUESS" if d.action == "GUESS" else "🔴 CASH_OUT"
        print(f"  [{icon}] {label}")
        print(f"    Capital: {capital} | Payout: {hand.current_payout} | Round: {hand.rounds_survived}")
        print(f"    {d.reason}")
        print()
    
    print("  ✅ PROBABILISTIC GATEKEEPER ONLINE 🐜⚡")

