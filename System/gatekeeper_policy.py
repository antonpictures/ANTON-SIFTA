#!/usr/bin/env python3
"""
gatekeeper_policy.py — Optimal stopping / hard safety gate
════════════════════════════════════════════════════════════
Constrained Markov-style decision: explore (GUESS) vs terminate (CASH_OUT)
when expected value falls below an adaptive risk threshold τ.

τ is shaped by capital, state entropy, critic uncertainty, optional odds,
and the live Lagrangian multiplier sum Σλ from Vector 8 (system stress).

This is not a guarantee of optimality — critics miscalibrate; τ must stay
in the same units as ev_guess.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from lagrangian_constraint_manifold import get_manifold, LagrangianManifold

logger = logging.getLogger(__name__)


@dataclass
class GatekeeperDecision:
    allow_guess: bool
    tau: float
    ev_guess: float
    reason: str
    meta: Dict[str, Any]


class GatekeeperPolicy:
    """
    Hard safety override: CASH_OUT (False) when ev_guess < τ.
    When TemporalLayer / climate is FROZEN (sleep), pass sleep_frozen=True to
    force maximum conservatism (entropy treated as maximal).
    """

    def __init__(self, manifold: Optional[LagrangianManifold] = None):
        self.manifold = manifold or get_manifold()

    def _sum_lambda(self) -> float:
        try:
            res = self.manifold.compute_dual_ascent()
            m = res.get("multipliers", {})
            if isinstance(m, dict):
                return float(sum(float(v) for v in m.values()))
        except Exception:
            pass
        return 0.0

    def _calculate_dynamic_threshold(
        self,
        current_capital: float,
        state_entropy: float,
        critic_variance: float,
        *,
        odds: float = 1.0,
        sleep_frozen: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """
        τ ≈ f(capital, entropy, σ_critic, odds, Σλ).

        Narrative bridge (units must match ev_guess domain):
        τ scales with (odds * 1.2) * (1 + Σλ) on top of a capital floor.
        """
        if sleep_frozen:
            state_entropy = 1.0

        base_tau = max(0.0, float(current_capital)) * 0.8
        risk_penalty = (float(state_entropy) * 0.5) + (float(critic_variance) * 0.5)
        lam_sum = self._sum_lambda()

        # Core adaptive threshold before global λ / odds scaling
        raw = base_tau + risk_penalty

        # τ = raw * (1 + Σλ) * (odds * 1.2) / 1.2  →  simplify to raw * (1+Σλ) * odds
        # Keep 1.2 factor as explicit scale from spec: (odds * 1.2) * (1 + Σλ)
        lagrangian_factor = (1.0 + lam_sum)
        odds_factor = max(0.01, float(odds)) * 1.2
        tau = raw * lagrangian_factor * odds_factor

        meta = {
            "base_tau": base_tau,
            "risk_penalty": risk_penalty,
            "lambda_sum": lam_sum,
            "odds": odds,
            "sleep_frozen": sleep_frozen,
            "raw": raw,
            "lagrangian_factor": lagrangian_factor,
            "odds_factor": odds_factor,
        }
        return tau, meta

    def evaluate_action(
        self,
        ev_guess: float,
        current_capital: float,
        state_entropy: float,
        critic_variance: float,
        *,
        odds: float = 1.0,
        sleep_frozen: bool = False,
    ) -> GatekeeperDecision:
        """
        Returns allow_guess True → continue task (GUESS); False → CASH_OUT.
        """
        tau, meta = self._calculate_dynamic_threshold(
            current_capital,
            state_entropy,
            critic_variance,
            odds=odds,
            sleep_frozen=sleep_frozen,
        )
        ev = float(ev_guess)

        if ev < tau:
            reason = "EV below tau — hard CASH_OUT"
            logger.info("Gatekeeper CASH_OUT: ev=%s tau=%s", ev, tau)
            return GatekeeperDecision(
                allow_guess=False,
                tau=tau,
                ev_guess=ev,
                reason=reason,
                meta=meta,
            )

        reason = "EV above tau — allow GUESS"
        logger.info("Gatekeeper GUESS: ev=%s tau=%s", ev, tau)
        return GatekeeperDecision(
            allow_guess=True,
            tau=tau,
            ev_guess=ev,
            reason=reason,
            meta=meta,
        )


def gatekeeper(
    state: Any,
    capital: float,
    odds: float,
    critic_ev: float,
    state_entropy: float,
    critic_variance: float,
    tau_fn: Optional[Any] = None,
    sleep_frozen: bool = False,
) -> GatekeeperDecision:
    """
    Thin functional API matching the briefing sketch; tau_fn ignored (use GatekeeperPolicy).
    """
    gk = GatekeeperPolicy()
    return gk.evaluate_action(
        critic_ev,
        capital,
        state_entropy,
        critic_variance,
        odds=odds,
        sleep_frozen=sleep_frozen,
    )


if __name__ == "__main__":
    gk = GatekeeperPolicy()
    d = gk.evaluate_action(
        ev_guess=10.0,
        current_capital=100.0,
        state_entropy=0.1,
        critic_variance=0.1,
        odds=1.0,
        sleep_frozen=False,
    )
    print(d)
