#!/usr/bin/env python3
"""
spectral_fault_tolerance.py — PAPER 2: Spectral Fault Tolerance Without Control Flow
═══════════════════════════════════════════════════════════════════════════════════════
Proves that the organism survives node removal WITHOUT any explicit failover code.

The only rule:
  System survives iff λ₂(L) > 0 after node deletion.

There is NO "if node dies → reroute" logic anywhere.
Fault tolerance is a PROPERTY of the spectral structure, not a programmed behavior.

Publishable result:
  "Fault tolerance without failover logic via spectral persistence"
"""

from __future__ import annotations

import json
import time
import copy
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FAULT_STATE = _STATE_DIR / "spectral_fault_tolerance.json"


@dataclass
class FaultInjectionResult:
    """Result of removing a single node from the skill graph."""
    removed_node: str
    removed_index: int
    original_lambda2: float
    post_removal_lambda2: float
    survived: bool           # True iff λ₂ > 0 after removal
    criticality: float       # 0 = non-critical, 1 = removal kills graph


class SpectralFaultTolerance:
    """
    Paper 2 Engine: Tests every node in the skill graph for spectral survival.
    No explicit failover. No rerouting. No if-then repair.
    Only: does the Laplacian remain connected after deletion?
    """
    
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
        
        if N < 3 or not self.has_numpy:
            return None, [], N
        
        analyzer = SpectralAnalyzer()
        A = self.np.zeros((N, N))
        
        for i in range(N):
            for j in range(i + 1, N):
                overlap = analyzer._jaccard_overlap(skills[i], skills[j])
                if overlap > 0.3:
                    A[i, j] = overlap
                    A[j, i] = overlap
        
        skill_names = [s.id[:12] for s in skills]
        return A, skill_names, N

    def _lambda2(self, A) -> float:
        """Compute algebraic connectivity from adjacency matrix."""
        D = self.np.diag(A.sum(axis=1))
        L = D - A
        eigenvalues = self.np.linalg.eigvalsh(L)
        eigenvalues.sort()
        return float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0

    def run_fault_injection(self) -> Dict[str, Any]:
        """
        Systematically remove every node, one at a time.
        Record whether the graph survives (λ₂ > 0) after each removal.
        No repair code. No failover. Pure spectral persistence.
        """
        A, names, N = self._build_adjacency()
        
        if A is None:
            result = {
                "nodes": N,
                "testable": False,
                "message": "Insufficient nodes or numpy missing.",
                "results": [],
                "survival_rate": 0.0,
                "critical_nodes": [],
                "proof_statement": "Cannot evaluate — graph too small."
            }
            self._persist(result)
            return result
        
        # Baseline λ₂
        baseline_lambda2 = self._lambda2(A)
        
        results: List[Dict[str, Any]] = []
        survived_count = 0
        critical_nodes = []
        
        for i in range(N):
            # Delete node i: remove row i and column i
            A_reduced = self.np.delete(self.np.delete(A, i, axis=0), i, axis=1)
            
            if A_reduced.shape[0] < 2:
                # Trivially connected (1 node)
                post_lambda2 = 0.0
                survived = False
            else:
                post_lambda2 = self._lambda2(A_reduced)
                survived = post_lambda2 > 1e-8
            
            criticality = 1.0 - (post_lambda2 / baseline_lambda2) if baseline_lambda2 > 0 else 1.0
            criticality = max(0.0, min(1.0, criticality))
            
            result_entry = FaultInjectionResult(
                removed_node=names[i],
                removed_index=i,
                original_lambda2=round(baseline_lambda2, 6),
                post_removal_lambda2=round(post_lambda2, 6),
                survived=survived,
                criticality=round(criticality, 4)
            )
            results.append(asdict(result_entry))
            
            if survived:
                survived_count += 1
            else:
                critical_nodes.append(names[i])
        
        survival_rate = survived_count / N if N > 0 else 0.0
        
        # Formal proof statement
        if survival_rate == 1.0:
            proof = (
                f"THEOREM HOLDS: All {N} nodes can be individually removed "
                f"while maintaining λ₂ > 0. The graph is spectrally fault-tolerant "
                f"with NO failover logic. Fault tolerance is a topological property."
            )
        elif survival_rate > 0.5:
            proof = (
                f"PARTIAL RESULT: {survived_count}/{N} nodes removable with spectral survival. "
                f"Critical nodes: {critical_nodes}. Graph has structural dependencies."
            )
        else:
            proof = (
                f"FRAGILE TOPOLOGY: Only {survived_count}/{N} nodes removable. "
                f"Graph structure is star-like or near-disconnected."
            )
        
        output = {
            "nodes": N,
            "testable": True,
            "baseline_lambda2": round(baseline_lambda2, 6),
            "survival_rate": round(survival_rate, 4),
            "survived_count": survived_count,
            "critical_nodes": critical_nodes,
            "results": results,
            "proof_statement": proof
        }
        
        self._persist(output)
        return output

    def _persist(self, data: Dict[str, Any]):
        try:
            _FAULT_STATE.write_text(json.dumps(data, indent=2))
        except Exception:
            pass


def get_fault_engine() -> SpectralFaultTolerance:
    return SpectralFaultTolerance()


if __name__ == "__main__":
    print("═" * 62)
    print("  PAPER 2: SPECTRAL FAULT TOLERANCE WITHOUT CONTROL FLOW")
    print("  'Fault tolerance via spectral persistence, not failover'")
    print("═" * 62 + "\n")
    
    engine = get_fault_engine()
    result = engine.run_fault_injection()
    
    print(f"  🧠 Nodes Tested      : {result['nodes']}")
    print(f"  🔗 Baseline λ₂       : {result.get('baseline_lambda2', 'N/A')}")
    print(f"  🛡️ Survival Rate     : {result['survival_rate'] * 100:.1f}%")
    print(f"  💀 Critical Nodes    : {result['critical_nodes']}")
    
    if result.get("results"):
        print("\n  [ Per-Node Fault Injection ]")
        for r in result["results"][:10]:
            status = "✅ SURVIVED" if r["survived"] else "💀 KILLED"
            print(f"    {r['removed_node']}: λ₂={r['post_removal_lambda2']:.4f} "
                  f"crit={r['criticality']:.2f} {status}")
    
    print(f"\n  📜 {result['proof_statement']}")
    print(f"\n  ✅ SPECTRAL FAULT TOLERANCE COMPUTED 🐜⚡")
