#!/usr/bin/env python3
"""
hierarchical_meta_controller.py — VECTOR 9: Hierarchical Dual-Constraint Swarm Layer
══════════════════════════════════════════════════════════════════════════════════════
Maps SwarmGPT's generic MARL architecture natively into SIFTA's constraint physics.

Implements the structural 3-Layer Hierarchy:
- Level 1: Hard Constraints (Projection Layer / Masking)
- Level 2: Soft Constraints (Lagrangian Multiplier penalties - Vector 8)
- Level 3: Meta-Controller (Adapts λ update rates dynamically to prevent shock)

The Meta-Controller reads total penalty magnitude (Σλ). 
- State Highly Unstable  → Lowers LR (prevents cascading shock limits)
- State Highly Stable    → Raises LR (faster micro-corrections)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

from lagrangian_constraint_manifold import get_manifold, LagrangianManifold

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_META_CONTROLLER_STATE = _STATE_DIR / "meta_controller_state.json"


@dataclass
class MetaOptimizationState:
    """The learning rate bounds for the Lagrangian limits."""
    base_alpha: float = 0.05
    current_alpha: float = 0.05       # Ascent rate
    current_decay: float = 0.01       # Descent rate
    total_penalty_magnitude: float = 0.0


class HierarchicalMetaController:
    """
    Level 3: Governs the adaptation speeds of the Level 2 Lagrangian physics.
    """
    
    def __init__(self):
        self.manifold = get_manifold()  # The Vector 8 engine (Level 1 + 2)
        self.state = self._load_state()

    def _load_state(self) -> MetaOptimizationState:
        if _META_CONTROLLER_STATE.exists():
            try:
                data = json.loads(_META_CONTROLLER_STATE.read_text())
                return MetaOptimizationState(**data)
            except Exception:
                pass
        return MetaOptimizationState()

    def step(self) -> Dict[str, Any]:
        """
        Executes a holistic step across all 3 layers.
        """
        # --- Level 1 & 2 Execution ---
        # Run the Dual Ascent over the manifold, generating penalties and masks.
        manifold_res = self.manifold.compute_dual_ascent()
        
        # --- Level 3 Execution (Meta Control) ---
        # Evaluate how strained the system is based on its constraint violations
        mag = manifold_res["total_lambda_penalty"]
        self.state.total_penalty_magnitude = mag
        
        # SwarmGPT Logic translation:
        # "If system is unstable → slow down λ updates (prevent explosion)"
        # "If stable → allow faster adaptation (tighter tracking)"
        if mag > 1.0:
            # Significant pressure. Back off learning rate to avoid oscillating collapse.
            self.state.current_alpha = self.state.base_alpha * 0.5
            adaptation_status = "DAMPENED"
        elif mag < 0.2:
            # Healthy bounds. React quickly to new micro-breaches.
            self.state.current_alpha = self.state.base_alpha * 1.5
            adaptation_status = "ACCELERATED"
        else:
            # Nominal pressure.
            self.state.current_alpha = self.state.base_alpha
            adaptation_status = "NOMINAL"
            
        # Write back the new tailored learning rates to the Level 2 Lagrangian layer
        # Future ticks of the manifold will respond to this new rate.
        self.manifold.alpha_ascent = self.state.current_alpha
        
        # Prepare the Hierarchical Summary
        result = {
            "timestamp": time.time(),
            "level_3_meta": {
                "adaptation_status": adaptation_status,
                "dynamic_learning_rate": round(self.state.current_alpha, 5),
                "penalty_magnitude": round(mag, 5)
            },
            "level_2_soft": manifold_res["multipliers"],
            "level_1_hard": manifold_res["projection_masks"]
        }
        
        self._persist(result)
        return result

    def _persist(self, data: Dict[str, Any]):
        try:
            _META_CONTROLLER_STATE.write_text(json.dumps(data, indent=2))
        except Exception:
            pass


def get_hierarchical_controller() -> HierarchicalMetaController:
    return HierarchicalMetaController()


if __name__ == "__main__":
    print("═" * 70)
    print("  VECTOR 9: HIERARCHICAL META-CONTROLLER")
    print("  'Structured policy shaping across 3 time-scales of constraints'")
    print("═" * 70 + "\n")
    
    hmc = get_hierarchical_controller()
    result = hmc.step()
    
    print("  [ LEVEL 3: META CONTROLLER ]")
    print(f"    System Pressure (Σλ) : {result['level_3_meta']['penalty_magnitude']}")
    print(f"    Adaptation Profile   : {result['level_3_meta']['adaptation_status']}")
    print(f"    Dynamic LR (α)       : {result['level_3_meta']['dynamic_learning_rate']}")
    
    print("\n  [ LEVEL 2: SOFT CONSTRAINTS (Lagrangian λ) ]")
    l2 = result['level_2_soft']
    print(f"    λ_congestion         : {l2['lambda_congestion']:.5f}")
    print(f"    λ_safety             : {l2['lambda_safety']:.5f}")
    print(f"    λ_energy             : {l2['lambda_energy']:.5f}")
    
    print("\n  [ LEVEL 1: HARD CONSTRAINTS (Projection) ]")
    l1 = result['level_1_hard']
    print(f"    Mask Fission         : {l1['mask_fission']}")
    print(f"    Mask Mutation        : {l1['mask_mutation']}")
    print(f"    Mask Exploration     : {l1['mask_exploration']}")
    
    print(f"\n  ✅ HIERARCHICAL STEP COMPLETE 🐜⚡")
