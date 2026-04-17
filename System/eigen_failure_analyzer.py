#!/usr/bin/env python3
"""
eigen_failure_analyzer.py — Vector 3: Eigen Failure-Mode Decomposition
═══════════════════════════════════════════════════════════════════
Treats failures as directions in state-space collapse rather than isolated events.
Calculates the Laplacian of the empirical failure coupling graph and outputs
the dominant decomposition modes.

Modes:
- λ_max(Failures) -> Global systemic instability
- Sparse eigen spikes -> Localized subsystem failure
"""

import json
from pathlib import Path
from typing import Dict, Any, List
import time

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FAIL_STATE = _STATE_DIR / "failure_spectrum.json"

COMPONENTS = [
    "MUTATION_GOVERNOR",
    "EVALUATION_SANDBOX",
    "FISSION_ROUTING",
    "SKILL_EXECUTION",
    "TEMPORAL_COHERENCE"
]

class EigenFailureAnalyzer:
    def __init__(self):
        self.has_numpy = False
        try:
            import numpy as np
            self.np = np
            self.has_numpy = True
        except ImportError:
            pass

    def _read_logs(self) -> List[Dict[str, Any]]:
        """Scan logs for recent failure bursts across components."""
        events = []
        now = time.time()
        window = 86400 * 3 # 3 days of failures
        
        def _parse(path: Path, comp: str, is_fail: callable):
            if not path.exists(): return
            try:
                with open(path, "r") as f:
                    for line in f:
                        if not line.strip(): continue
                        data = json.loads(line)
                        if is_fail(data):
                            ts = data.get("ts", now)
                            if now - ts < window:
                                events.append({"ts": ts, "comp": comp})
            except Exception:
                pass
        
        # 1. Mutation Governor rejections
        _parse(_STATE_DIR / "governor_loop_events.jsonl", "MUTATION_GOVERNOR", lambda d: d.get("action") == "REJECT_PATCH")
        # 2. Eval Sandbox Rejections
        _parse(_STATE_DIR / "evaluation_log.jsonl", "EVALUATION_SANDBOX", lambda d: not d.get("approved", True))
        # 3. Execution Failures
        _parse(_STATE_DIR / "failure_log.jsonl", "SKILL_EXECUTION", lambda d: True)
        # 4. Fission/Contradiction
        _parse(_STATE_DIR / "contradiction_log.jsonl", "FISSION_ROUTING", lambda d: True)
        # 5. Silence / Temps
        _parse(_STATE_DIR / "temporal_layer.jsonl", "TEMPORAL_COHERENCE", lambda d: d.get("mutation_climate") == "FROZEN" or d.get("dead_zones", 0) > 0)

        events.sort(key=lambda x: x["ts"])
        return events

    def compute_failure_spectrum(self) -> Dict[str, Any]:
        events = self._read_logs()
        N = len(COMPONENTS)
        
        if not events:
            return self._emit_empty(N, "No failure traces found.")
        if not self.has_numpy:
            return self._emit_empty(N, "Numpy missing — decomposition disabled.")
        
        # Build coupling matrix A[i][j] based on temporal co-occurrence
        A = self.np.zeros((N, N))
        time_window = 3600  # 1 hour co-occurrence = coupled failure
        
        for i in range(len(events)):
            e1 = events[i]
            c1_idx = COMPONENTS.index(e1["comp"])
            A[c1_idx, c1_idx] += 1.0  # self-frequency
            
            for j in range(i + 1, min(i + 50, len(events))):
                e2 = events[j]
                if e2["ts"] - e1["ts"] > time_window:
                    break
                c2_idx = COMPONENTS.index(e2["comp"])
                if c1_idx != c2_idx:
                    A[c1_idx, c2_idx] += 1.0
                    A[c2_idx, c1_idx] += 1.0
                    
        # Apply gentle log-smoothing to tame exploding counts
        A = self.np.log1p(A)
        
        # Build Degree Matrix D and Graph Laplacian L
        D = self.np.diag(A.sum(axis=1) - self.np.diag(A))
        L = D - A
        
        # Eigen Decomposition
        eigenvalues, eigenvectors = self.np.linalg.eigh(L)
        
        idx = eigenvalues.argsort()[::-1] # descending (we want largest λ_max first)
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        lambda_max = float(eigenvalues[0]) if len(eigenvalues) > 0 else 0.0
        lambda_2_desc = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0
        
        # Determine Dominant Failure Mode
        dom_vec = eigenvectors[:, 0]
        dom_idx = int(self.np.argmax(self.np.abs(dom_vec)))
        dominant_comp = COMPONENTS[dom_idx]
        
        # Classification
        prediction = min(1.0, lambda_max / 10.0) # Assume 10 is catastrophic coupling
        state = "STABLE"
        if lambda_max > 8.0:
            state = "SYSTEMIC_COLLAPSE"
        elif lambda_max > 4.0 and lambda_2_desc > 3.0:
            state = "STRUCTURAL_SCHISM"
        elif lambda_max > 2.0:
            state = "LOCALIZED_FRACTURE"

        res = {
            "eigenvalues": [round(float(e), 4) for e in eigenvalues],
            "dominant_failure_mode": dominant_comp,
            "lambda_max": round(lambda_max, 4),
            "collapse_prediction": round(prediction, 4),
            "classification": state,
            "message": f"Evaluated Fx = λx. Phase: {state}"
        }
        
        try:
            _FAIL_STATE.write_text(json.dumps(res, indent=2))
        except: pass
        
        return res
        
    def _emit_empty(self, N: int, msg: str) -> Dict[str, Any]:
        res = {
            "eigenvalues": [0.0] * N,
            "dominant_failure_mode": "NONE",
            "lambda_max": 0.0,
            "collapse_prediction": 0.0,
            "classification": "STABLE",
            "message": msg
        }
        try:
            _FAIL_STATE.write_text(json.dumps(res, indent=2))
        except: pass
        return res

def get_analyzer():
    return EigenFailureAnalyzer()

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — EIGEN FAILURE-MODE DECOMPOSITION")
    print("═" * 58 + "\n")
    a = get_analyzer()
    r = a.compute_failure_spectrum()
    print(f"  🚨 Dominant Failure Mode: {r['dominant_failure_mode']}")
    print(f"  📈 Lambda Max (λ1)      : {r['lambda_max']}")
    print(f"  💥 Collapse Prediction  : {r['collapse_prediction'] * 100:.2f}%")
    print(f"  🔍 Status Classification: {r['classification']}")
    print(f"\n  ✅ Eigen spectrum extracted: {r['eigenvalues']}")
