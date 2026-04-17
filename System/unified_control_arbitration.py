#!/usr/bin/env python3
"""
unified_control_arbitration.py — "The Unification Layer"
═══════════════════════════════════════════════════════════════════
The absolute final boss of the architecture. Solves the 4-governor problem.
If ICF, Skill Spectral Graph, Node Coherence, and Failure Metrics disagree,
this system dictates the final override based on calculated Free Energy:

  E_total = α*ICF + β*λ2(skills) + γ*Φ - δ*λ_max(failures)
"""

import json
from pathlib import Path
from typing import Dict, Any
import time

from identity_coherence_field import get_icf
from skill_spectral_analyzer import get_analyzer as get_spectral
from eigen_failure_analyzer import get_analyzer as get_failure
from cross_node_coherence import get_node_analyzer
from phase_transition_control import get_ptc

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_ARBITER_STATE = _STATE_DIR / "unified_control_state.json"

class UnifiedControlArbiter:
    def __init__(self):
        self.E_total: float = 1.0
        self.last_E_total: float = 1.0
        
        # Free Energy Weights
        self.alpha = 0.4  # ICF Weight
        self.beta = 0.2   # Skill Graph Topology
        self.gamma = 0.2  # Distributed Machine Coherence
        self.delta = 0.2  # Penalty for Eigen Failures

    def arbitrate(self) -> Dict[str, Any]:
        """
        Pull state from all four thermodynamic vectors.
        Output single truth dictate for the rest of SIFTA.
        """
        
        # 1. Gather all thermodynamic readings
        icf = get_icf()
        icf.evaluate_system()
        val_icf = icf.quantized_icf
        
        spectral = get_spectral().compute_laplacian()
        val_skill = spectral.get("algebraic_connectivity", 0.0)
        
        coherence = get_node_analyzer().evaluate_coherence()
        val_node = coherence.get("phi", 0.0)
        
        failure = get_failure().compute_failure_spectrum()
        # Scale lambda max to a 0-1 risk factor
        val_fail = min(1.0, failure.get("lambda_max", 0.0) / 10.0)
        
        # 2. Calculate E_total
        e_current = (
            (self.alpha * val_icf) + 
            (self.beta * val_skill) + 
            (self.gamma * val_node) - 
            (self.delta * val_fail)
        )
        
        self.last_E_total = self.E_total
        # Smooth momentum update
        self.E_total = max(0.0, min(1.0, (self.E_total * 0.5) + (e_current * 0.5)))
        
        e_delta = self.E_total - self.last_E_total
        
        # 3. Determine Dictates (Visual Only)
        
        ptc = get_ptc()
        regime = ptc.evaluate_regime()
        
        if self.E_total < 0.3 or regime == "CRITICAL_COLLAPSE":
            status = "ENERGY_CRITICAL"
        elif e_delta < -0.15:
            # Dropping rapidly
            status = "ENERGY_DROPPING_THROTTLED"
        elif self.E_total > 0.7:
            # Healthy
            status = "EXPLORATION_PERMITTED"
        else:
            status = "STABLE"

        res = {
            "ts": time.time(),
            "E_total": round(self.E_total, 4),
            "E_delta": round(e_delta, 4),
            "status": status,
            "metrics": {
                "ICF": round(val_icf, 3),
                "Skill_L2": round(val_skill, 3),
                "Node_Phi": round(val_node, 3),
                "Fail_Risk": round(val_fail, 3)
            }
        }
        
        self._persist(res)
        return res

    def _persist(self, data: Dict[str, Any]):
        try:
            _ARBITER_STATE.write_text(json.dumps(data, indent=2))
        except: pass

def get_arbiter() -> UnifiedControlArbiter:
    return UnifiedControlArbiter()

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — UNIFIED CONTROL ARBITRATION")
    print("═" * 58 + "\n")
    arb = get_arbiter()
    stat = arb.arbitrate()
    
    print(f"  ⚡ TOTAL FREE ENERGY (E_total) : {stat['E_total']}")
    print(f"  📉 Energy Gradient (ΔE)        : {stat['E_delta']}")
    print(f"  🛡️ Arbiter Status             : {stat['status']}")
    print("\n  [ Inputs ]")
    print(f"    ICF       : {stat['metrics']['ICF']}")
    print(f"    Skill λ2  : {stat['metrics']['Skill_L2']}")
    print(f"    Node Φ    : {stat['metrics']['Node_Phi']}")
    print(f"    Fail Risk : {stat['metrics']['Fail_Risk']}")
    
    print(f"\n  ✅ TOTAL FREE ENERGY CALCULATED 🐜⚡")
