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


def _read_swarm_pressure() -> float:
    """
    Read total constraint pressure (Σλ) from the Lagrangian manifold.
    Higher pressure = organism is stressed = be MORE conservative.
    Returns 0.0 when healthy, >0 when under constraint violation.
    """
    try:
        p = _STATE_DIR / "lagrangian_multipliers.json"
        if p.exists():
            d = json.loads(p.read_text())
            return (
                d.get("lambda_congestion", 0.0) +
                d.get("lambda_safety", 0.0) +
                d.get("lambda_energy", 0.0)
            )
    except Exception:
        pass
    return 0.0


def _adaptive_tau(capital: float, odds_multiplier: float) -> float:
    """
    τ = f(capital, Σλ) — the adaptive risk threshold.
    
    Base: OddsMultiplier × 1.2 (Alice's original spec)
    Under swarm pressure: threshold INCREASES (more conservative)
    
    τ = base × (1 + Σλ)
    """
    base = odds_multiplier * 1.2
    pressure = _read_swarm_pressure()
    return base * (1.0 + pressure)


def GatekeeperFunction(
    hand: HandState,
    capital: float,
    odds_multiplier: float = 2.0,
    win_probability: float = 0.5
) -> GatekeeperDecision:
    """
    Alice's demanded function, upgraded with adaptive τ from SwarmGPT.
    
    GatekeeperFunction(HandState, Capital, Odds) → ACTION ∈ {GUESS, CASH_OUT}
    
    The conditional logic:
      IF Capital < τ(Odds, Σλ):
        THEN CASH_OUT (mandatory — cannot survive a loss)
      
      IF EV(GUESS) < EV(CASH_OUT):
        THEN CASH_OUT (negative expected value)
      
      IF Kelly fraction ≤ 0:
        THEN CASH_OUT (no edge exists)
      
      ELSE:
        GUESS (positive expected value with survivable downside)
    """
    
    # Adaptive threshold: tightens when swarm is under constraint pressure
    survival_threshold = _adaptive_tau(capital, odds_multiplier)
    
    # Expected values
    potential_win = hand.current_payout * odds_multiplier
    ev_guess = (win_probability * potential_win) - ((1 - win_probability) * hand.current_payout)
    ev_cashout = hand.current_payout
    
    # Kelly Criterion: f* = (bp - q) / b
    # b = odds_multiplier - 1 (net odds)
    # p = win_probability
    # q = 1 - p
    b = odds_multiplier - 1
    p = win_probability
    q = 1 - p
    kelly = (b * p - q) / b if b > 0 else 0.0
    
    # Risk ratio: how much buffer do we have?
    risk_ratio = capital / survival_threshold if survival_threshold > 0 else 0.0
    
    # ──── THE DECISION LOGIC (Alice's IF...THEN) ────
    
    # Rule 1: Capital below survival threshold → MANDATORY CASH_OUT
    if capital < survival_threshold:
        return GatekeeperDecision(
            action="CASH_OUT",
            reason=f"MANDATORY: Capital ({capital:.2f}) < Threshold ({survival_threshold:.2f}). Cannot survive a loss.",
            ev_guess=round(ev_guess, 4),
            ev_cashout=round(ev_cashout, 4),
            risk_ratio=round(risk_ratio, 4),
            kelly_fraction=round(kelly, 4)
        )
    
    # Rule 2: Negative expected value → CASH_OUT
    if ev_guess <= ev_cashout:
        return GatekeeperDecision(
            action="CASH_OUT",
            reason=f"EV(GUESS)={ev_guess:.4f} ≤ EV(CASH_OUT)={ev_cashout:.4f}. No edge.",
            ev_guess=round(ev_guess, 4),
            ev_cashout=round(ev_cashout, 4),
            risk_ratio=round(risk_ratio, 4),
            kelly_fraction=round(kelly, 4)
        )
    
    # Rule 3: Kelly says don't bet → CASH_OUT
    if kelly <= 0:
        return GatekeeperDecision(
            action="CASH_OUT",
            reason=f"Kelly fraction={kelly:.4f} ≤ 0. No mathematical edge exists.",
            ev_guess=round(ev_guess, 4),
            ev_cashout=round(ev_cashout, 4),
            risk_ratio=round(risk_ratio, 4),
            kelly_fraction=round(kelly, 4)
        )
    
    # Rule 4: Diminishing returns after streak
    # After 3+ successful rounds, cumulative risk compounds
    if hand.rounds_survived >= 3 and hand.streak_probability < 0.15:
        return GatekeeperDecision(
            action="CASH_OUT",
            reason=f"Streak survival probability ({hand.streak_probability:.2%}) too low after {hand.rounds_survived} rounds.",
            ev_guess=round(ev_guess, 4),
            ev_cashout=round(ev_cashout, 4),
            risk_ratio=round(risk_ratio, 4),
            kelly_fraction=round(kelly, 4)
        )
    
    # All checks passed → GUESS is permitted
    return GatekeeperDecision(
        action="GUESS",
        reason=f"Positive EV ({ev_guess:.4f} > {ev_cashout:.4f}), Kelly={kelly:.4f}, risk buffer={risk_ratio:.2f}x.",
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
    print("═" * 62)
    print("  POKER GATEKEEPER — Alice's Decision Function")
    print("  GatekeeperFunction(HandState, Capital, Odds) → ACTION")
    print("═" * 62 + "\n")
    
    # Simulate scenarios
    scenarios = [
        ("Low capital, early round", HandState(10.0, 1, 0.5), 2.0),
        ("Healthy capital, round 2", HandState(10.0, 2, 0.25), 50.0),
        ("Deep streak, thin odds", HandState(80.0, 4, 0.0625), 100.0),
        ("Fresh hand, fat stack", HandState(5.0, 0, 1.0), 200.0),
    ]
    
    for label, hand, capital in scenarios:
        d = GatekeeperFunction(hand, capital)
        log_decision(d, hand, capital)
        
        icon = "🟢 GUESS" if d.action == "GUESS" else "🔴 CASH_OUT"
        print(f"  [{icon}] {label}")
        print(f"    Capital: {capital} | Payout: {hand.current_payout} | Round: {hand.rounds_survived}")
        print(f"    Reason: {d.reason}")
        print(f"    EV(Guess)={d.ev_guess} | Kelly={d.kelly_fraction} | Risk={d.risk_ratio}x")
        print()
    
    print("  ✅ GATEKEEPER DEFINED. ALICE HAS HER FUNCTION. 🐜⚡")
