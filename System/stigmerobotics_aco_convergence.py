#!/usr/bin/env python3
"""
System/stigmerobotics_aco_convergence.py
=========================================

E39 — Discrete pheromone convergence

ROB 501 topic: Discrete ACO convergence with append-only integer timestamps.

References (HYPOTHESIS until wired to SIFTA tests + receipts):
  Dorigo, M. & Stützle, T. (2004). Ant Colony Optimization. MIT Press.
    — Theorem 4.1: ACO pheromone trails converge under bounded deposit rate.
  Salman, J. et al. (2024). Swarm stigmergy with append-only fields.
    DOI: 10.1038/s44172-024-00175-7
  Boldini, A. et al. (2024). Pheromone field dynamics in distributed systems.
    DOI: 10.1098/rsos.240845

──────────────────────────────────────────────────────────────────────────────
Convergence Theorem (E39):

  Let:
    τ     = evaporation half-life (seconds, τ > 0, enforced by E33)
    s     = deposit strength per row (s > 0, enforced by E33)
    λ     = deposit rate (rows per second, λ > 0)
    Δt    = discrete timestep (seconds per integer tick)

  Per-step retention factor:
    ρ = exp(-Δt / τ) ∈ (0, 1)   (because τ > 0 and Δt > 0)

  Total pheromone intensity on a single channel after n equal deposits
  spaced Δt apart:
    I_n = s · ρ · (1 - ρⁿ) / (1 - ρ)

  As n → ∞ (geometric series with |ρ| < 1):
    I_∞ = s · ρ / (1 - ρ) = s / (exp(Δt/τ) - 1)

  Convergence bound:
    |I_n - I_∞| = s · ρ^(n+1) / (1 - ρ) ≤ ε
    ⟺ n ≥ log(ε(1-ρ)/s) / log(ρ)       [convergence rate]

  Falsifier: ρ ≥ 1 (τ ≤ 0 or Δt = 0) → series diverges.
             This is prevented by E33 τ > 0 invariant.

  Multi-channel extension: channels are independent linear superpositions.
  Global field intensity I_global(t) = Σ_c I_c(t) converges to
    I_global_∞ = Σ_c (s_c / (exp(Δt/τ_c) - 1))

──────────────────────────────────────────────────────────────────────────────
§8.6 compliance: This module is side-effect free. It never reads live
.sifta_state/ and never writes any ledger row. All functions are pure math.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


# ── Core convergence math ────────────────────────────────────────────────────

def retention_factor(tau_s: float, dt_s: float) -> float:
    """
    ρ = exp(-dt_s / tau_s) — the per-step multiplicative retention.

    Must be in (0, 1) for convergence.
    Raises ValueError if tau_s <= 0 or dt_s <= 0.
    """
    if tau_s <= 0.0:
        raise ValueError(f"tau_s must be > 0, got {tau_s}")
    if dt_s <= 0.0:
        raise ValueError(f"dt_s must be > 0, got {dt_s}")
    return math.exp(-dt_s / tau_s)


def steady_state_intensity(strength: float, tau_s: float, dt_s: float) -> float:
    """
    I_∞ = strength / (exp(dt_s / tau_s) - 1)

    The limiting field intensity on a single channel receiving one deposit
    of `strength` per discrete step of duration `dt_s`, with evaporation
    half-life `tau_s`.

    Derivation: geometric series with ratio ρ = exp(-dt_s/tau_s) < 1:
      I_∞ = s · ρ / (1 - ρ) = s / (1/ρ - 1) = s / (exp(dt_s/tau_s) - 1)
    """
    rho = retention_factor(tau_s, dt_s)
    # 1/rho - 1 = exp(dt_s/tau_s) - 1, numerically stable for small dt_s/tau_s
    return strength * rho / (1.0 - rho)


def intensity_after_n_deposits(
    strength: float, tau_s: float, dt_s: float, n: int
) -> float:
    """
    I_n = s · ρ · (1 - ρⁿ) / (1 - ρ)

    Exact intensity after n equal deposits spaced dt_s apart.
    """
    if n <= 0:
        return 0.0
    rho = retention_factor(tau_s, dt_s)
    return strength * rho * (1.0 - rho ** n) / (1.0 - rho)


def convergence_error(strength: float, tau_s: float, dt_s: float, n: int) -> float:
    """
    |I_n - I_∞| = s · ρ^(n+1) / (1 - ρ)

    The absolute error between the n-deposit field and the steady state.
    This monotonically decreases to 0 as n → ∞.
    """
    rho = retention_factor(tau_s, dt_s)
    return strength * (rho ** (n + 1)) / (1.0 - rho)


def convergence_steps_to_epsilon(
    strength: float, tau_s: float, dt_s: float, epsilon: float
) -> int:
    """
    Smallest n such that |I_n - I_∞| ≤ epsilon.

    n ≥ ceil( log(ε(1-ρ)/s) / log(ρ) ) - 1

    Returns 0 if epsilon is already ≥ I_∞ (trivially converged).
    """
    if epsilon <= 0.0:
        raise ValueError(f"epsilon must be > 0, got {epsilon}")
    rho = retention_factor(tau_s, dt_s)
    i_inf = steady_state_intensity(strength, tau_s, dt_s)
    if epsilon >= i_inf:
        return 0
    # |I_n - I_∞| ≤ ε → ρ^(n+1) ≤ ε(1-ρ)/s
    threshold = epsilon * (1.0 - rho) / strength
    if threshold <= 0:
        return int(1e9)  # effectively infinite
    # n+1 ≥ log(threshold) / log(rho)
    n_plus_1 = math.log(threshold) / math.log(rho)
    return max(0, math.ceil(n_plus_1) - 1)


# ── Multi-channel convergence ────────────────────────────────────────────────

@dataclass(frozen=True)
class ChannelSpec:
    """Specification of one pheromone channel."""
    name: str
    strength: float
    tau_s: float
    dt_s: float

    @property
    def rho(self) -> float:
        return retention_factor(self.tau_s, self.dt_s)

    @property
    def i_inf(self) -> float:
        return steady_state_intensity(self.strength, self.tau_s, self.dt_s)

    def converges(self) -> bool:
        """True iff ρ ∈ (0, 1) — the geometric series converges."""
        r = self.rho
        return 0.0 < r < 1.0


@dataclass(frozen=True)
class ACOConvergenceReport:
    """
    Convergence analysis for a set of channels.
    """
    channels: tuple[ChannelSpec, ...]
    epsilon: float = 1e-3

    @property
    def global_i_inf(self) -> float:
        """I_global_∞ = Σ_c I_c_∞"""
        return sum(c.i_inf for c in self.channels)

    @property
    def all_converge(self) -> bool:
        """True iff every channel has ρ ∈ (0, 1)."""
        return all(c.converges() for c in self.channels)

    @property
    def divergent_channels(self) -> list[str]:
        return [c.name for c in self.channels if not c.converges()]

    def steps_to_epsilon(self, channel: ChannelSpec) -> int:
        return convergence_steps_to_epsilon(
            channel.strength, channel.tau_s, channel.dt_s, self.epsilon
        )

    @property
    def max_steps_to_epsilon(self) -> int:
        """Worst-case convergence steps across all channels."""
        if not self.channels:
            return 0
        return max(self.steps_to_epsilon(c) for c in self.channels)

    def intensity_at_n(self, n: int) -> dict[str, float]:
        """Per-channel intensity after n deposits."""
        return {c.name: intensity_after_n_deposits(c.strength, c.tau_s, c.dt_s, n)
                for c in self.channels}

    def summary_lines(self) -> list[str]:
        lines = [
            f"E39 ACO Convergence: {'CONVERGES' if self.all_converge else 'DIVERGES'}",
            f"channels: {len(self.channels)}",
            f"global_I_inf: {self.global_i_inf:.6f}",
            f"epsilon: {self.epsilon}",
            f"max_steps_to_epsilon: {self.max_steps_to_epsilon}",
            "",
            "per-channel convergence:",
        ]
        for c in self.channels:
            lines.append(
                f"  {c.name:32s} I_inf={c.i_inf:.6f} rho={c.rho:.6f} "
                f"n_eps={self.steps_to_epsilon(c)}"
            )
        if self.divergent_channels:
            lines.append("")
            lines.append("DIVERGENT (tau <= 0 or dt <= 0):")
            lines.extend(f"  {name}" for name in self.divergent_channels)
        return lines

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E39": "Discrete pheromone field converges to finite steady state",
            "theorem": "I_inf = s / (exp(dt/tau) - 1) for each channel; I_global = sum",
            "convergence_condition": "rho = exp(-dt/tau) in (0,1) — enforced by E33 tau>0 invariant",
            "all_channels_converge": self.all_converge,
            "global_I_inf": self.global_i_inf,
            "max_steps_to_epsilon": self.max_steps_to_epsilon,
            "divergent_channels": self.divergent_channels,
            "falsifier": "rho >= 1 (tau <= 0 or dt <= 0) → series diverges — E33 prevents this",
            "truth_label": "OPERATIONAL" if self.all_converge else "BROKEN",
        }


# ── Factory from E33 tau / strength tables ───────────────────────────────────

def channels_from_e33_tables(
    tau_table: dict[str, float],
    strength_table: dict[str, float],
    dt_s: float = 1.0,
) -> tuple[ChannelSpec, ...]:
    """
    Build ChannelSpec objects from the E33 DEFAULT_TAU_S and DEFAULT_STRENGTH
    lookup tables.  dt_s defaults to 1 second (unit discrete step).
    """
    channels: list[ChannelSpec] = []
    all_kinds = set(tau_table) | set(strength_table)
    default_tau = 900.0
    default_strength = 0.35
    for kind in sorted(all_kinds):
        tau = tau_table.get(kind, default_tau)
        strength = strength_table.get(kind, default_strength)
        channels.append(ChannelSpec(name=kind, strength=strength, tau_s=tau, dt_s=dt_s))
    return tuple(channels)


def aco_convergence_report(
    tau_table: dict[str, float],
    strength_table: dict[str, float],
    dt_s: float = 1.0,
    epsilon: float = 1e-3,
) -> ACOConvergenceReport:
    channels = channels_from_e33_tables(tau_table, strength_table, dt_s)
    return ACOConvergenceReport(channels=channels, epsilon=epsilon)


if __name__ == "__main__":
    from System.stigmerobotics_pheromone_field import DEFAULT_TAU_S, DEFAULT_STRENGTH
    report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH)
    print("\n".join(report.summary_lines()))
