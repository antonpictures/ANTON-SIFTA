#!/usr/bin/env python3
"""
skill_spectral_analyzer.py — Skill Graph Spectral Theory
═══════════════════════════════════════════════════════════════════
Calculates the Graph Laplacian of the organism's memory traces.
Computes Algebraic Connectivity (λ2), revealing if the Swarm's skills 
are fracturing into disjoint subsets (schizophrenia) or merging into unified
continual learning blocks.

Uses numpy if available; falls back to simulated/graceful degradation if not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from temporal_identity_compression import get_compression_engine, SkillPrimitive

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_SPECTRAL_LOG = _STATE_DIR / "spectral_entanglement.json"


class SpectralAnalyzer:
    def __init__(self):
        self.engine = get_compression_engine()
        self.has_numpy = False
        try:
            import numpy as np
            self.np = np
            self.has_numpy = True
        except ImportError:
            pass

    def _jaccard_overlap(self, s1: SkillPrimitive, s2: SkillPrimitive) -> float:
        """Calculate generalized overlap of signatures."""
        parts1 = set(s1.pattern_signature.split('|'))
        parts2 = set(s2.pattern_signature.split('|'))
        union = parts1.union(parts2)
        intersection = parts1.intersection(parts2)
        if not union:
            return 0.0
        return len(intersection) / len(union)

    def compute_laplacian(self) -> Dict[str, Any]:
        """
        Builds the unnormalized Graph Laplacian L = D - A.
        Calculates Algebraic Connectivity and Fiedler Gap.
        """
        skills = list(self.engine.skills.values())
        N = len(skills)
        
        if N < 2:
            return {
                "nodes": N,
                "algebraic_connectivity": 0.0,
                "fiedler_gap": 0.0,
                "schism_warning": False,
                "message": "Not enough nodes for spectral breakdown."
            }

        # If numpy is not installed, we cannot run an eigensolver gracefully. 
        # Fall back to a structural heuristic.
        if not self.has_numpy:
            return {
                "nodes": N,
                "algebraic_connectivity": 0.01,
                "fiedler_gap": 0.0,
                "schism_warning": False,
                "message": "Numpy missing — Eigen decomposition disabled."
            }

        # Build Adjacency Matrix A
        A = self.np.zeros((N, N))
        for i in range(N):
            for j in range(i + 1, N):
                overlap = self._jaccard_overlap(skills[i], skills[j])
                # Filter out weak couplings
                if overlap > 0.3:
                    A[i, j] = overlap
                    A[j, i] = overlap

        # Build Degree Matrix D
        D = self.np.diag(A.sum(axis=1))

        # Graph Laplacian L = D - A
        L = D - A

        # Compute Eigenvalues and Eigenvectors
        eigenvalues, eigenvectors = self.np.linalg.eigh(L)
        
        # Sort eigenvalues (they should be roughly sorted, but good practice)
        idx = eigenvalues.argsort()
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # λ1 is always ~ 0 for a valid Laplacian.
        # λ2 is algebraic connectivity (Fiedler value).
        lambda_2 = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0
        lambda_3 = float(eigenvalues[2]) if len(eigenvalues) > 2 else lambda_2
        
        # Determine if the graph is disconnecting
        schism = lambda_2 < 1e-4

        result = {
            "nodes": N,
            "algebraic_connectivity": round(lambda_2, 5),
            "fiedler_gap": round(lambda_3 - lambda_2, 5),
            "schism_warning": schism,
            "message": "Graph fractured!" if schism else "Graph connected."
        }
        
        self._persist(result)
        return result

    def _persist(self, data: Dict[str, Any]):
        try:
            _SPECTRAL_LOG.write_text(json.dumps(data, indent=2))
        except Exception:
            pass


def get_analyzer() -> SpectralAnalyzer:
    return SpectralAnalyzer()

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — GRAPH SPECTRAL ANALYZER")
    print("═" * 58 + "\n")
    
    analyzer = get_analyzer()
    stats = analyzer.compute_laplacian()
    
    print(f"  🧠 Skill Nodes Analyzed : {stats['nodes']}")
    print(f"  🔗 Algebraic Conn (λ2)  : {stats['algebraic_connectivity']}")
    print(f"  📉 Fiedler Gap          : {stats['fiedler_gap']}")
    print(f"  ⚠  Schism Warning       : {stats['schism_warning']}")
    print(f"  -> {stats['message']}")
    
    print(f"\n  ✅ SPECTRAL THEORY RUNNING 🐜⚡")
