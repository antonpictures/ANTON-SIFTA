#!/usr/bin/env python3
"""
cross_node_coherence.py — Vector 4: Cross-Node Coherence Law
═══════════════════════════════════════════════════════════════════
Evaluates the spatial synchronization of the distributed Swarm across
independent physical machines (e.g. M5, M1, CRUCIBLE, EDGE).

Constructs the Coherence Matrix C from local machine states:
  C_ij = similarity(state_i, state_j)
Then computes the Global Coherence Scalar (Φ) using Algebraic Connectivity:
  Φ = λ2(C)
"""

import json
from pathlib import Path
from typing import Dict, Any, List
import time

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_NODE_STATE = _STATE_DIR / "cross_node_coherence.json"

class CrossNodeCoherenceAnalyzer:
    def __init__(self):
        self.has_numpy = False
        try:
            import numpy as np
            self.np = np
            self.has_numpy = True
        except ImportError:
            pass

    def _extract_machine_states(self) -> Dict[str, Dict[str, float]]:
        """
        Derives the local machine state from execution traces inside a recent window.
        Machine State Vector = [TaskVolume, AverageOutcome, TemporalRecency]
        """
        now = time.time()
        window = 86400 * 2  # 48 hours
        logs_path = _STATE_DIR / "execution_traces.jsonl"
        
        machines: Dict[str, Dict[str, Any]] = {}
        
        if not logs_path.exists():
            return machines
            
        try:
            with open(logs_path, "r") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    ts = data.get("ts", 0)
                    if now - ts > window: continue
                    
                    hw = data.get("hardware_target", "UNKNOWN")
                    if hw not in machines:
                        machines[hw] = {"count": 0, "successes": 0, "last_ts": 0.0}
                        
                    machines[hw]["count"] += 1
                    machines[hw]["last_ts"] = max(machines[hw]["last_ts"], ts)
                    if str(data.get("outcome", False)).lower() in ("true", "1"):
                        machines[hw]["successes"] += 1
        except Exception:
            pass
            
        # Normalize states into vectors
        mac_vectors = {}
        for hw, m in machines.items():
            vol_norm = min(1.0, m["count"] / 100.0) 
            succ_rate = m["successes"] / m["count"] if m["count"] > 0 else 0.0
            recency = min(1.0, 1.0 - ((now - m["last_ts"]) / window))
            mac_vectors[hw] = {
                "vector": [vol_norm, succ_rate, recency],
                "count": m["count"]
            }
            
        return mac_vectors

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not self.has_numpy:
            # Fallback naive euclidean sim
            dist = sum((a-b)**2 for a, b in zip(v1, v2))
            return max(0.0, 1.0 - dist)
        v1 = self.np.array(v1)
        v2 = self.np.array(v2)
        n1 = self.np.linalg.norm(v1)
        n2 = self.np.linalg.norm(v2)
        if n1 == 0 or n2 == 0: return 0.0
        return self.np.dot(v1, v2) / (n1 * n2)

    def evaluate_coherence(self) -> Dict[str, Any]:
        mac_states = self._extract_machine_states()
        hw_ids = list(mac_states.keys())
        N = len(hw_ids)
        
        if N < 2:
            return self._emit({
                "nodes": N,
                "phi": 1.0, # Complete unity (only 1 node exists)
                "status": "UNIFIED_SINGLETON",
                "matrix": []
            })
            
        if not self.has_numpy:
            return self._emit({
                "nodes": N,
                "phi": 0.5,
                "status": "NUMPY_MISSING",
                "matrix": []
            })

        # Build Coherence Similarity Matrix C
        C = self.np.zeros((N, N))
        for i in range(N):
            for j in range(i, N):
                hw1, hw2 = hw_ids[i], hw_ids[j]
                sim = self._cosine_similarity(mac_states[hw1]["vector"], mac_states[hw2]["vector"])
                C[i, j] = sim
                C[j, i] = sim
                
        # Laplacian L = D - C
        D = self.np.diag(C.sum(axis=1) - self.np.diag(C))
        L = D - C
        
        eigenvalues, _ = self.np.linalg.eigh(L)
        eigenvalues = self.np.sort(eigenvalues)
        
        phi = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0 # Algebraic Connectivity of Nodes
        phi_norm = max(0.0, min(1.0, phi)) # bounded clamp
        
        state = "FRAGMENTING"
        if phi_norm > 0.8:
            state = "SYNCHRONIZED"
        elif phi_norm > 0.4:
            state = "SPECIALIZED"
            
        res = {
            "nodes": N,
            "machine_ids": hw_ids,
            "phi": round(phi_norm, 4),
            "status": state,
            "matrix": C.tolist()
        }
        return self._emit(res)

    def _emit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _NODE_STATE.write_text(json.dumps(data, indent=2))
        except: pass
        return data

def get_node_analyzer() -> CrossNodeCoherenceAnalyzer:
    return CrossNodeCoherenceAnalyzer()

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — CROSS-NODE COHERENCE MATRIX (Φ)")
    print("═" * 58 + "\n")
    a = get_node_analyzer()
    r = a.evaluate_coherence()
    print(f"  🌐 Active Nodes: {r['nodes']} {r.get('machine_ids', [])}")
    print(f"  🔗 Global Coherence (Φ): {r['phi']:.4f}")
    print(f"  🛡️ Status             : {r['status']}")
    print(f"\n  ✅ Distributed Field Executed 🐜⚡")
