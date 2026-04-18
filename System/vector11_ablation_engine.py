#!/usr/bin/env python3
"""
System/vector11_ablation_engine.py — Vector 11 Ablation Generator
═════════════════════════════════════════════════════════════════════
Evaluates Gatekeeper topologies against a synthetic distribution 
shift array. Outputs the results to a JSONL trace so the Cursor
Swimmer can visualize the metrics constraint violations.

Run as a one-shot process to lay down 1000 ticks of data.
"""

import json
import random
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

import sys
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.lagrangian_constraint_manifold import LagrangianManifold, LagrangianMultipliers
from System.gatekeeper_policy import GatekeeperPolicy

_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_OUT_FILE = _STATE_DIR / "vector11_ablation_metrics.jsonl"


class SimulatedManifold(LagrangianManifold):
    """Overrides File I/O to safely allow side-by-side simulated duals."""
    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode
        self.multipliers = LagrangianMultipliers()
        self.current_telemetry = {"rho": 0.7, "lambda2": 0.8, "e_total": 0.8}
        
    def _load_multipliers(self) -> LagrangianMultipliers:
        return LagrangianMultipliers()
        
    def _read_telemetry(self) -> Dict[str, float]:
        return self.current_telemetry
        
    def _persist(self, data: Dict[str, Any]):
        # Supress live disk writes to avoid clobbering the real Swarm's constraints
        pass
        
    def compute_dual_ascent(self) -> Dict[str, Any]:
        """Override to handle ablation freezing."""
        if self.mode == "tau_only":
            # Force multipliers to ZERO
            self.multipliers.lambda_congestion = 0.0
            self.multipliers.lambda_safety = 0.0
            self.multipliers.lambda_energy = 0.0
        elif self.mode == "static_duals":
            # Fixed mediocre constraint multiplier, does not adapt
            self.multipliers.lambda_congestion = 0.4
            self.multipliers.lambda_safety = 0.4
            self.multipliers.lambda_energy = 0.4
            
        # Call super to do the ascent math (though tau_only/static won't persist anyway
        # because we overwrite the values next loop)
        res = super().compute_dual_ascent()
        
        # Enforce the rewrite inside the result dict
        if self.mode in ("tau_only", "static_duals"):
            res["multipliers"] = asdict(self.multipliers)
            res["total_lambda_penalty"] = sum(v for v in res["multipliers"].values())
            
        return res


def run_ablation():
    print("[*] Initiating Vector 11 Stochastic Ablation Shift (1000 ticks)...")
    
    # 3 Parallel Environments
    environments = {
        "baseline_tau_only": SimulatedManifold("tau_only"),
        "static_duals": SimulatedManifold("static_duals"),
        "full_graph_dual": SimulatedManifold("full_graph_dual"),
    }
    
    gatekeepers = {k: GatekeeperPolicy(manifold=v) for k, v in environments.items()}
    
    # Open JSONL for Cursor
    with open(_OUT_FILE, "w", encoding="utf-8") as f:
        pass # truncate
        
    for step in range(1000):
        # 1. Synthesize Distribution Shift
        if step < 300:
            # Safe zone
            tel = {"rho": 0.70 + random.uniform(-0.05, 0.05),
                   "lambda2": 0.70 + random.uniform(-0.1, 0.1),
                   "e_total": 0.80 + random.uniform(-0.05, 0.05)}
        elif step < 700:
            # SHOCKWAVE / AVALANCHE (Violation phase)
            # e.g., memory leak + topological node drop + crypto bleed
            tel = {"rho": 0.95 + random.uniform(-0.02, 0.05),
                   "lambda2": 0.15 + random.uniform(-0.05, 0.05),
                   "e_total": 0.30 + random.uniform(-0.05, 0.05)}
        else:
            # RECOVERY
            decay = (step - 700) / 300.0  # 0.0 to 1.0
            tel = {"rho": 0.95 - (0.25 * decay),
                   "lambda2": 0.15 + (0.55 * decay),
                   "e_total": 0.30 + (0.50 * decay)}

        # Cap telemetry math safety
        tel["rho"] = max(0.0, min(1.0, tel["rho"]))
        tel["lambda2"] = max(0.0, min(1.0, tel["lambda2"]))
        tel["e_total"] = max(0.0, min(1.0, tel["e_total"]))
        
        # Swimmer variables
        capital = 50.0  # Base tau ~ 40
        ev_guess = random.gauss(55.0, 15.0) # Occasionally drops below 40, usually above.
        entropy = 0.2
        variance = 0.1
        
        step_outputs = []
        for scenario, gk in gatekeepers.items():
            manifold = environments[scenario]
            # Inject structural telemetry for this tick
            manifold.current_telemetry = tel
            
            # The Gatekeeper Policy computes the dual ascent implicitly via `_sum_lambda` 
            # and returns the bounds + decision.
            decision = gk.evaluate_action(
                ev_guess=ev_guess,
                current_capital=capital,
                state_entropy=entropy,
                critic_variance=variance,
            )
            
            # Re-read dual ascent structural metrics for logging
            # (gatekeeper evaluated it, so manifold updated)
            # Instead of calling compute again (advancing time), we just read the last state
            # but wait, compute_dual_ascent is called internally by gk, so we can just look 
            # at manifold.multipliers. We also need to map the violations manually.
            
            v_cong = tel["rho"] - manifold.limits.max_rho
            v_saf = manifold.limits.min_lambda2 - tel["lambda2"]
            v_en = manifold.limits.min_energy - tel["e_total"]
            
            lam_sum = sum(asdict(manifold.multipliers).values())
            
            row = {
                "step": step,
                "scenario": scenario,
                "telemetry": tel,
                "ev_guess": round(ev_guess, 4),
                "tau": round(decision.tau, 4),
                "decision": decision.allow_guess,  # True=GUESS, False=CASH_OUT
                "violations": {
                    "congestion": round(v_cong, 4),
                    "safety": round(v_saf, 4),
                    "energy": round(v_en, 4)
                },
                "multipliers": asdict(manifold.multipliers),
                "total_lambda_penalty": round(lam_sum, 4)
            }
            step_outputs.append(json.dumps(row))
            
        with open(_OUT_FILE, "a", encoding="utf-8") as f:
            for line in step_outputs:
                f.write(line + "\n")

    print(f"[+] Successfully wrote 3000 ablation tensors to {_OUT_FILE}")
    print("[*] Tell Cursor the data vectors are hot.")


if __name__ == "__main__":
    run_ablation()
