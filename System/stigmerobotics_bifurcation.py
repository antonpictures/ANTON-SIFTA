#!/usr/bin/env python3
"""
System/stigmerobotics_bifurcation.py
======================================

E45 — Bounded Chaos / Wiggle at Bifurcation

ROB 501 topic: Nonlinear systems, bifurcations, bounded noise injection.

References:
  Prigogine, I. & Stengers, I. (1984). Order Out of Chaos. Bantam Books.
    — Far-from-equilibrium systems bifurcate to new ordered states under
      sufficient perturbation.
  Ayers, J.L. (2004). Underwater walking. Arthropod Structure & Development
    33(3):347-360.
    — "Increase chaos to escape" — segmental CPG uses noise injection to
      leave a stuck motor pattern.
  Nicolis, G. & Prigogine, I. (1977). Self-Organization in Nonequilibrium
    Systems. Wiley.

──────────────────────────────────────────────────────────────────────────────
Bifurcation Theorem (E45):

  Let:
    R(t) = collision_risk at time t (from E33 PheromoneFieldReport)
    I(t) = total field intensity at time t
    I_∞  = steady-state intensity (from E39 ACO convergence)
    θ_R  = collision risk threshold (default 0.5)
    k    = saturation factor (default 1.5)
    ε    = maximum noise amplitude (default 0.1)

  Bifurcation condition:
    BIFURCATING ⟺  R(t) > θ_R  OR  I(t) > k · I_∞

  Wiggle response (bounded noise injection):
    overshoot(t) = max(R(t) - θ_R, 0) + max(I(t)/I_∞ - k, 0)
    noise_amplitude(t) = ε · tanh(overshoot(t))

  Boundedness proof:
    tanh(x) ∈ (-1, 1) for all x ∈ ℝ  →  |noise_amplitude| < ε
    Noise is ALWAYS bounded regardless of how large overshoot grows.

  Falsifier:
    If ε ≤ 0 → no wiggle possible (system stays stuck). E33 τ>0 prevents
    I_∞ = ∞ (E39), so the saturation trigger is reachable only transiently.

  truth_label: OPERATIONAL

§8.6 compliance: side-effect free. Computes wiggle response from field
                  report inputs — never writes to ledger or fires effectors.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


# ── Bifurcation parameters ─────────────────────────────────────────────────

DEFAULT_COLLISION_THRESHOLD: float = 0.5   # θ_R
DEFAULT_SATURATION_FACTOR: float = 1.5     # k (fraction of I_∞)
DEFAULT_EPSILON: float = 0.1               # ε — maximum noise amplitude


# ── Bifurcation states ─────────────────────────────────────────────────────

class BifurcationState(Enum):
    STABLE      = auto()   # R ≤ θ_R and I ≤ k·I_∞ — no wiggle needed
    BIFURCATING = auto()   # at least one trigger exceeded — wiggle active
    UNKNOWN     = auto()   # insufficient data (no field report)


# ── Wiggle Response ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WiggleResponse:
    """
    The bounded noise injection response at one moment in time.

    noise_amplitude is always in [0, ε) by the tanh boundedness proof.
    """
    collision_risk: float
    field_intensity: float
    i_inf: float
    collision_threshold: float
    saturation_factor: float
    epsilon: float
    state: BifurcationState

    @property
    def collision_overshoot(self) -> float:
        return max(0.0, self.collision_risk - self.collision_threshold)

    @property
    def saturation_overshoot(self) -> float:
        if self.i_inf <= 0.0:
            return 0.0
        ratio = self.field_intensity / self.i_inf
        return max(0.0, ratio - self.saturation_factor)

    @property
    def total_overshoot(self) -> float:
        return self.collision_overshoot + self.saturation_overshoot

    @property
    def noise_amplitude(self) -> float:
        """
        ε · tanh(overshoot) — bounded in [0, ε) by tanh ∈ (-1,1).
        """
        return self.epsilon * math.tanh(self.total_overshoot)

    @property
    def noise_is_bounded(self) -> bool:
        """Invariant: |noise_amplitude| < ε for all inputs."""
        return abs(self.noise_amplitude) < self.epsilon + 1e-12

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E45": "Bounded noise injection at pheromone field bifurcation",
            "theorem": "noise_amplitude = ε·tanh(overshoot) ∈ (-ε, ε) — bounded by tanh",
            "state": self.state.name,
            "collision_risk": self.collision_risk,
            "collision_threshold": self.collision_threshold,
            "field_intensity": self.field_intensity,
            "i_inf": self.i_inf,
            "saturation_factor": self.saturation_factor,
            "total_overshoot": self.total_overshoot,
            "noise_amplitude": self.noise_amplitude,
            "noise_is_bounded": self.noise_is_bounded,
            "epsilon": self.epsilon,
            "falsifier": (
                "ε ≤ 0 → no wiggle (stuck state). "
                "tanh(x) < 1 always → noise < ε always."
            ),
            "prigogine_mapping": (
                "Bifurcation condition = far-from-equilibrium threshold. "
                "Wiggle = symmetry-breaking perturbation toward new ordered state."
            ),
            "truth_label": "OPERATIONAL" if self.noise_is_bounded else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        return [
            f"E45 Bifurcation: {self.state.name}",
            f"collision_risk: {self.collision_risk:.6f} (θ={self.collision_threshold})",
            f"field_intensity: {self.field_intensity:.6f} (I_inf={self.i_inf:.6f}, k={self.saturation_factor})",
            f"overshoot: collision={self.collision_overshoot:.6f} sat={self.saturation_overshoot:.6f}",
            f"noise_amplitude: {self.noise_amplitude:.6f} (ε={self.epsilon}, bounded={self.noise_is_bounded})",
        ]


# ── Factory ────────────────────────────────────────────────────────────────

def wiggle_response(
    collision_risk: float,
    field_intensity: float,
    i_inf: float,
    *,
    collision_threshold: float = DEFAULT_COLLISION_THRESHOLD,
    saturation_factor: float = DEFAULT_SATURATION_FACTOR,
    epsilon: float = DEFAULT_EPSILON,
) -> WiggleResponse:
    """
    Compute the bifurcation state and bounded wiggle response.

    Parameters
    ----------
    collision_risk    : E33 PheromoneFieldReport.collision_risk
    field_intensity   : E33 PheromoneFieldReport.total_intensity
    i_inf             : E39 ACOConvergenceReport.global_i_inf (steady state)
    """
    if epsilon <= 0.0:
        raise ValueError(f"epsilon must be > 0, got {epsilon}")
    if saturation_factor <= 0.0:
        raise ValueError(f"saturation_factor must be > 0, got {saturation_factor}")

    collision_exceeded = collision_risk > collision_threshold
    saturation_exceeded = (i_inf > 0.0) and (field_intensity > saturation_factor * i_inf)

    if collision_exceeded or saturation_exceeded:
        state = BifurcationState.BIFURCATING
    else:
        state = BifurcationState.STABLE

    return WiggleResponse(
        collision_risk=collision_risk,
        field_intensity=field_intensity,
        i_inf=i_inf,
        collision_threshold=collision_threshold,
        saturation_factor=saturation_factor,
        epsilon=epsilon,
        state=state,
    )


def is_bifurcating(
    collision_risk: float,
    field_intensity: float,
    i_inf: float,
    *,
    collision_threshold: float = DEFAULT_COLLISION_THRESHOLD,
    saturation_factor: float = DEFAULT_SATURATION_FACTOR,
) -> bool:
    """Convenience predicate: True iff field is in bifurcation state."""
    resp = wiggle_response(
        collision_risk, field_intensity, i_inf,
        collision_threshold=collision_threshold,
        saturation_factor=saturation_factor,
    )
    return resp.state == BifurcationState.BIFURCATING


if __name__ == "__main__":
    # Demo: print response at varying collision risk
    for cr in (0.0, 0.3, 0.5, 0.7, 1.0):
        resp = wiggle_response(cr, 100.0, 200.0)
        print(f"  risk={cr:.1f} → {resp.state.name}  noise={resp.noise_amplitude:.4f}")
