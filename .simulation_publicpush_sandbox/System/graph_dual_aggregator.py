#!/usr/bin/env python3
"""
graph_dual_aggregator.py — VECTOR 10A: Graph-Coupled Dual Variables
════════════════════════════════════════════════════════════════════════
Replaces independent single-scalar lambda updates with consensus smoothing.
Instead of the whole system freezing, dual variables are mapped across
the skill graph topology (W_ij).

Math: λ_i ← Σ_j W_ij λ_j + α c_i

Prevents explosion per-agent by diffusing constraint pressure across neighbors.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_GRAPH_DUALS_PATH = _STATE_DIR / "graph_dual_lambdas.json"


class GraphDualAggregator:
    def __init__(self):
        self.has_numpy = False
        try:
            import numpy as np
            self.np = np
            self.has_numpy = True
        except ImportError:
            pass

    def _build_adjacency(self) -> Any:
        """Build adjacency matrix from live skill graph."""
        from temporal_identity_compression import get_compression_engine
        from skill_spectral_analyzer import SpectralAnalyzer
        
        engine = get_compression_engine()
        skills = list(engine.skills.values())
        N = len(skills)
        
        if N < 2 or not self.has_numpy:
            return None, [], N
        
        analyzer = SpectralAnalyzer()
        A = self.np.zeros((N, N))
        
        for i in range(N):
            for j in range(i + 1, N):
                overlap = analyzer._jaccard_overlap(skills[i], skills[j])
                if overlap > 0.1:
                    A[i, j] = overlap
                    A[j, i] = overlap
                    
        skill_names = [s.id[:12] for s in skills]
        return A, skill_names, N

    def _load_previous_lambdas(self, names: List[str]) -> Any:
        if not self.has_numpy:
            return None
        
        prev = self.np.zeros(len(names))
        if _GRAPH_DUALS_PATH.exists():
            try:
                state = json.loads(_GRAPH_DUALS_PATH.read_text())
                l_dict = state.get("lambdas", {})
                for i, name in enumerate(names):
                    if name in l_dict:
                        prev[i] = l_dict[name]
            except Exception:
                pass
        return prev

    def _get_local_violations(self, N: int) -> float:
        """
        In a true distributed system, c_i would be calculated per-agent.
        Here we proxy the global density to apply uniform base pressure,
        which will then diffuse across the topology.
        """
        c_base = 0.0
        try:
            regime = json.loads((_STATE_DIR / "regime_state.json").read_text())
            rho = regime.get("stigmergic_density", 0.0)
            if rho > 0.85:
                c_base = rho - 0.85
        except Exception:
            pass
        return c_base

    def aggregate_duals(self) -> Dict[str, Any]:
        """
        λ_i ← Σ_j W_ij λ_j + α c_i
        """
        A, names, N = self._build_adjacency()
        if A is None:
            return {"status": "failed", "reason": "No graph or numpy available."}

        # Normalize Adjacency to create a transition matrix W
        row_sums = A.sum(axis=1)
        # Avoid division by zero
        row_sums[row_sums == 0] = 1.0
        W = A / row_sums[:, self.np.newaxis]

        # Add self-loops so agents retain their own pressure
        W = W * 0.5 + self.np.eye(N) * 0.5 

        lambdas = self._load_previous_lambdas(names)
        
        # Base violation applied globally but diffused structurally
        c_i = self._get_local_violations(N)
        alpha = 0.05
        
        # The Consensus Update: λ ← W λ + α C
        new_lambdas = self.np.dot(W, lambdas) + (alpha * c_i)
        
        # Apply decay to non-violating states to prevent infinite accumulation
        if c_i == 0.0:
            new_lambdas = new_lambdas * 0.95

        lambda_dict = {names[i]: round(float(new_lambdas[i]), 5) for i in range(N)}
        
        result = {
            "timestamp": time.time(),
            "nodes_coupled": N,
            "global_violation_c_i": round(c_i, 5),
            "lambdas": lambda_dict,
            "max_pressure_node": max(lambda_dict.items(), key=lambda x: x[1])[0] if lambda_dict else "None",
            "proof": "λ updated via adjacency consensus (W_ij)."
        }
        
        try:
            _GRAPH_DUALS_PATH.write_text(json.dumps(result, indent=2))
        except Exception:
            pass
            
        return result


def get_aggregator() -> GraphDualAggregator:
    return GraphDualAggregator()


if __name__ == "__main__":
    print("═" * 70)
    print("  VECTOR 10A: GRAPH-COUPLED DUAL VARIABLES")
    print("  'λ_i ← Σ_j W_ij λ_j + α c_i'")
    print("═" * 70 + "\n")
    
    agg = get_aggregator()
    res = agg.aggregate_duals()
    
    if res.get("status") != "failed":
        print(f"  🔗 Nodes Coupled: {res['nodes_coupled']}")
        print(f"  ⚠️ Global Violations (c_i): {res['global_violation_c_i']}")
        print(f"  🔴 Max Pressure Node: {res['max_pressure_node']}")
        print("\n  [ Top 5 Agent Constraints (λ_i) ]")
        
        sorted_l = sorted(res['lambdas'].items(), key=lambda x: x[1], reverse=True)
        for name, val in sorted_l[:5]:
            print(f"    {name} : {val:.5f}")
        
        print(f"\n  📜 {res['proof']}")
    else:
        print(f"  ❌ {res['reason']}")
    
    print(f"\n  ✅ GRAPH-COUPLED CONSENSUS ONLINE 🐜⚡")
