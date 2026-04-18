#!/usr/bin/env python3
"""
lagrangian_constraint_manifold.py — VECTOR 8: Constrained MARL
══════════════════════════════════════════════════════════════════════
Implements formal Constrained Multi-Agent Reinforcement Learning (MARL)
via adaptive Lagrangian dual ascent.

Instead of hard "annihilation" or dictatorial "freezes", the system operates
over a constrained feasible space. Violations smoothly escalate Lagrangian 
multipliers (λ), applying shaping pressure to the entire Swarm policy.

The 4 layers:
1. Constraint Layer: reads ρ, λ₂, E_total. Computes C_i(s, a).
2. Dual Layer: updates λ_i under dual ascent.
3. Projection Layer: hard masks ONLY if safety bounds are breached totally.
4. Residue Layer: logs the constraint geometry.

Emergence is structural optimization over what remains possible.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_DUAL_STATE_PATH = _STATE_DIR / "lagrangian_multipliers.json"
_RESIDUE_LOG_PATH = _STATE_DIR / "constraint_residues.jsonl"


@dataclass
class LagrangianMultipliers:
    """The $\\lambda$ vector tracking dual constraints."""
    lambda_congestion: float = 0.0  # Pressure from high Stigmergic Density
    lambda_safety: float = 0.0      # Pressure from topological breakdown (Schism)
    lambda_energy: float = 0.0      # Pressure from E_total collapse


@dataclass
class ConstraintLimits:
    """The formal $d_i$ constants defining the feasible set."""
    max_rho: float = 0.85           # Above this, congestion penalty kicks in
    min_lambda2: float = 0.3        # Below this, safety penalty kicks in
    min_energy: float = 0.50        # Below this, energy penalty kicks in


class LagrangianManifold:
    """
    Computes constraint violations and applies Dual Ascent to adaptive multipliers.
    """
    
    def __init__(self):
        self.limits = ConstraintLimits()
        self.multipliers = self._load_multipliers()
        self.alpha_ascent = 0.05    # Learning rate for constraint violations
        self.alpha_decay = 0.01     # Decay rate for safe margins

    def _load_multipliers(self) -> LagrangianMultipliers:
        if _DUAL_STATE_PATH.exists():
            try:
                d = json.loads(_DUAL_STATE_PATH.read_text())
                return LagrangianMultipliers(**d)
            except Exception:
                pass
        return LagrangianMultipliers()

    def _read_telemetry(self) -> Dict[str, float]:
        """Reads the structural physics variables from the system."""
        telemetry = {"rho": 0.0, "lambda2": 1.0, "e_total": 1.0}
        
        # 1. Congestion (ρ)
        regime_path = _STATE_DIR / "regime_state.json"
        if regime_path.exists():
            try:
                state = json.loads(regime_path.read_text())
                telemetry["rho"] = state.get("stigmergic_density", state.get("density", 0.0))
            except Exception: pass
            
        # 2. Topology Safety (λ₂)
        spectral_path = _STATE_DIR / "spectral_entanglement.json"
        if spectral_path.exists():
            try:
                state = json.loads(spectral_path.read_text())
                telemetry["lambda2"] = state.get("algebraic_connectivity", 1.0)
            except Exception: pass
            
        # 3. Thermodynamic Energy (E_total)
        energy_path = _STATE_DIR / "hysteresis_state.json"
        if energy_path.exists():
            try:
                state = json.loads(energy_path.read_text())
                telemetry["e_total"] = state.get("E_total", 1.0)
            except Exception: pass
            
        return telemetry

    def compute_dual_ascent(self) -> Dict[str, Any]:
        """
        The formal MARL update loop:
        λ_i ← max(0, λ_i + α * (C_i(s) - d_i))
        """
        tel = self._read_telemetry()
        
        # 1. Formulate Constraint Violations (C_i - d_i)
        # Positive values = constraint violated. Negative = safe margin.
        v_congestion = tel["rho"] - self.limits.max_rho
        v_safety = self.limits.min_lambda2 -  tel["lambda2"]   # inverted, lower is worse
        v_energy = self.limits.min_energy - tel["e_total"]     # inverted, lower is worse

        # 2. Adaptive Dual Update (Ascent / Decay)
        def update_lambda(current: float, violation: float) -> float:
            # If violating, rapidly ascend. If safe, slowly decay.
            lr = self.alpha_ascent if violation > 0 else self.alpha_decay
            return max(0.0, current + (lr * violation))

        prev_multipliers = asdict(self.multipliers)

        self.multipliers.lambda_congestion = round(update_lambda(self.multipliers.lambda_congestion, v_congestion), 5)
        self.multipliers.lambda_safety = round(update_lambda(self.multipliers.lambda_safety, v_safety), 5)
        self.multipliers.lambda_energy = round(update_lambda(self.multipliers.lambda_energy, v_energy), 5)

        # 3. Projection Masking Layer
        # Soft penalty is the norm. Hard masking is a last resort.
        projection_masks = {
            "mask_fission": self.multipliers.lambda_congestion > 0.5,  # Congestion too high = disable replication
            "mask_mutation": self.multipliers.lambda_safety > 0.8,     # Safety too low = disable random drift
            "mask_exploration": self.multipliers.lambda_energy > 0.4   # Energy too low = disable wide search
        }

        # 4. Total Multiplier Pressure
        total_lambda = (
            self.multipliers.lambda_congestion + 
            self.multipliers.lambda_safety + 
            self.multipliers.lambda_energy
        )

        result = {
            "timestamp": time.time(),
            "measurements": {
                "rho": tel["rho"],
                "lambda2": tel["lambda2"],
                "e_total": tel["e_total"]
            },
            "violations": {
                "congestion": round(v_congestion, 5),
                "safety": round(v_safety, 5),
                "energy": round(v_energy, 5)
            },
            "multipliers": asdict(self.multipliers),
            "total_lambda_penalty": round(total_lambda, 5),
            "projection_masks": projection_masks
        }

        self._persist(result)
        return result

    def _persist(self, data: Dict[str, Any]):
        # Save stateful multipliers
        try:
            _DUAL_STATE_PATH.write_text(json.dumps(asdict(self.multipliers), indent=2))
        except Exception:
            pass
            
        # Log to the residue ledger
        try:
            with open(_RESIDUE_LOG_PATH, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception:
            pass


def get_manifold() -> LagrangianManifold:
    return LagrangianManifold()


if __name__ == "__main__":
    print("═" * 68)
    print("  VECTOR 8: LAGRANGIAN CONSTRAINT MANIFOLD")
    print("  'Constrained MARL via adaptive dual ascent over field state'")
    print("═" * 68 + "\n")
    
    lm = get_manifold()
    result = lm.compute_dual_ascent()
    
    print("  [ Field Measurements ]")
    print(f"    Stigmergic Density (ρ)  : {result['measurements']['rho']} (limit: {lm.limits.max_rho})")
    print(f"    Topology Factor    (λ₂) : {result['measurements']['lambda2']} (limit: >{lm.limits.min_lambda2})")
    print(f"    Energy Function   (E_T) : {result['measurements']['e_total']} (limit: >{lm.limits.min_energy})")
    
    print("\n  [ Lagrangian Multipliers (λ) ]")
    print(f"    λ_congestion            : {result['multipliers']['lambda_congestion']:.5f}")
    print(f"    λ_safety                : {result['multipliers']['lambda_safety']:.5f}")
    print(f"    λ_energy                : {result['multipliers']['lambda_energy']:.5f}")
    
    print("\n  [ Projection Masking ]")
    masks = result['projection_masks']
    print(f"    Mask Fission            : {masks['mask_fission']}")
    print(f"    Mask Mutation           : {masks['mask_mutation']}")
    print(f"    Mask Exploration        : {masks['mask_exploration']}")
    
    if result['total_lambda_penalty'] > 0:
        print(f"\n  ⚠️ SYSTEM UNDER CONSTRAINT PRESSURE (Σλ = {result['total_lambda_penalty']:.4f})")
    else:
        print(f"\n  🌐 SWARM IN FEASIBLE STATE (Σλ = 0.0). FULL EXPLORATION.")
        
    print(f"\n  ✅ DUAL ASCENT COMPLETE 🐜⚡")
