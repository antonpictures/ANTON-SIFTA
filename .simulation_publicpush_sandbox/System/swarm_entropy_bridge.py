#!/usr/bin/env python3
"""
swarm_entropy_bridge.py — Thin SIFTA-facing wrapper for dual-track entropy fusion
══════════════════════════════════════════════════════════════════════════════════

**Grounded:** uses only real modules:
  - `lagrangian_entropy_controller.entropy_coefficient_exponential` (Track A)
  - `stigmergic_entropy_trace.StigmergicEntropyController` (Track B)
  - `stigmergic_composition.compose_entropy_coeff` (mixer)

**Rejected (browser-tab hallucination):** there is no `get_memory_bus()`,
no `LagrangianEntropyController.get_coefficient`, no `_spawn_forager()` on a bus.
If Track B should incorporate **ACMF / memory_fitness.json**, add an explicit
adapter that reads locked overlay state — do not invent APIs.

Trainer integration: call `SiftaEntropyBridge.apply_to_agents(agents, buffer)`
from `Trainer.update_rl` (same choke point as `swarmrl_entropy_hooks`).
"""
from __future__ import annotations

from typing import Any, MutableMapping, Optional

from System.lagrangian_entropy_controller import entropy_coefficient_exponential
from System.stigmergic_composition import CompositionConfig, compose_entropy_coeff
from System.stigmergic_entropy_trace import StigmergicBuffer, StigmergicEntropyController


def lambda_norm_from_manifold() -> float:
    """Same λ_norm as `telemetry_snapshot` / `refresh_from_manifold`."""
    try:
        from System.lagrangian_constraint_manifold import get_manifold

        dual = get_manifold().compute_dual_ascent()
        total = float(dual.get("total_lambda_penalty", 0.0))
        return min(1.0, total / 1.5)
    except Exception:
        return 0.0


class SiftaEntropyBridge:
    """Fuse manifold-based c_λ with trace-based c_trace; optional composition modes."""

    def __init__(
        self,
        composition: Optional[CompositionConfig] = None,
        trace_controller: Optional[StigmergicEntropyController] = None,
        *,
        c2_max: float = 0.01,
    ):
        self.composition = composition or CompositionConfig()
        self.trace_controller = trace_controller or StigmergicEntropyController()
        self.c2_max = float(c2_max)

    def compute_fused(
        self,
        lambda_norm: float,
        buffer: StigmergicBuffer,
    ) -> tuple[float, float, float]:
        """Returns (c_fused, c_lambda, c_trace)."""
        lam = max(0.0, min(1.0, float(lambda_norm)))
        c_l = entropy_coefficient_exponential(lam, c2_max=self.c2_max)
        c_t = self.trace_controller.compute_entropy_coef(buffer)
        fused = compose_entropy_coeff(c_l, c_t, self.composition)
        return float(fused), float(c_l), float(c_t)

    def apply_to_agents(
        self,
        agents: MutableMapping[str, Any],
        buffer: StigmergicBuffer,
        *,
        lambda_norm: Optional[float] = None,
    ) -> dict[str, Any]:
        """Set every agent's `loss.entropy_coefficient` to fused c₂."""
        lam = float(lambda_norm) if lambda_norm is not None else lambda_norm_from_manifold()
        fused, c_l, c_t = self.compute_fused(lam, buffer)
        for agent in agents.values():
            loss = getattr(agent, "loss", None)
            if loss is not None and hasattr(loss, "entropy_coefficient"):
                setattr(loss, "entropy_coefficient", fused)
        return {
            "entropy_coefficient_c2": fused,
            "c_lambda": c_l,
            "c_trace": c_t,
            "lambda_norm": lam,
            "composition_mode": self.composition.mode,
            "policy_collapse": bool(fused < 1e-4 and c_l < 1e-3 and c_t < 1e-3),
        }


__all__ = ["SiftaEntropyBridge", "lambda_norm_from_manifold"]
