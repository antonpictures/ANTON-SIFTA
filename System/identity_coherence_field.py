#!/usr/bin/env python3
"""
identity_coherence_field.py — ICF (The Global Invariant Keeper)
═══════════════════════════════════════════════════════════════════
The final missing organ of unity. It continuously measures whether 
all subsystems still agree on what "success" means. 

It outputs a single scalar field (0.0 to 1.0) defining the organism's
internal alignment (inverse chaos pressure). This bounds the Fission,
Mutation Governor, and Evaluation Sandbox systems.

Implementation drawn from arXiv:2601.08129 (pressure fields) and
preventing beautiful fragmentation collapse.
"""
from __future__ import annotations

import json
import time
import math
from typing import Dict, Any, List, Optional
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_ICF_STATE = _STATE_DIR / "icf_state.json"


class IdentityCoherenceField:
    """
    Global invariant keeper for Swarm identity.
    Prevents fragmentation across Fission / Skills / Mutation / REM.
    """

    def __init__(self):
        self.coherence_score: float = 1.0
        self.last_snapshot_ts: float = 0.0
        self._load()

    def evaluate_system(self) -> float:
        """
        Pull LIVE metrics from across the organism to construct the snapshot.
        """
        try:
            # 1. Measure Blackboard Entropy (Topic Variance)
            from swarm_blackboard import get_blackboard
            bb = get_blackboard()
            total_tasks = len(bb._tasks)
            hw_dist = {}
            for t in bb._tasks.values():
                hw = t.hardware_target
                hw_dist[hw] = hw_dist.get(hw, 0) + 1
            
            # Simple entropy H = -sum(p*log(p))
            bb_entropy = 0.0
            if total_tasks > 0:
                for hw, c in hw_dist.items():
                    p = c / total_tasks
                    bb_entropy -= p * math.log(p) if p > 0 else 0
            
            # Normalize to ~1.0 (assuming max 4 hardwares)
            routing_var = min(1.0, bb_entropy / 1.38)
            
            # 2. Measure Mutation Drift (Governor Lockout)
            mutation_drift = 0.0
            try:
                gov_state_file = _STATE_DIR / "governor_loop_state.json"
                if gov_state_file.exists():
                    gov_data = json.loads(gov_state_file.read_text())
                    drift = gov_data.get("identity_drift", 0.0)
                    max_d = gov_data.get("max_drift", 5.0)
                    mutation_drift = min(1.0, drift / max_d)
            except Exception:
                pass
                
            # 3. Measure Skill Usage Entropy / Decoherence
            skill_entropy = 0.0
            try:
                from temporal_identity_compression import get_compression_engine
                engine = get_compression_engine()
                skills = engine.skills.values()
                highly_stable = sum(1 for s in skills if s.stability > 0.8)
                total = len(skills)
                if total > 0:
                    # If most skills are NOT highly stable, entropy is high
                    skill_entropy = 1.0 - (highly_stable / total)
            except Exception:
                pass
                
            return self._apply_snapshot({
                "routing_variance": routing_var,
                "mutation_drift": mutation_drift,
                "skill_entropy": skill_entropy
            })
            
        except ImportError:
            # Degrade gracefully
            return self._apply_snapshot({})

    def _apply_snapshot(self, snapshot: Dict[str, Any]) -> float:
        """Calculate coherence = inverse chaos pressure"""
        entropy = float(snapshot.get("skill_entropy", 0.5))
        drift = float(snapshot.get("mutation_drift", 0.0))
        routing_var = float(snapshot.get("routing_variance", 0.5))

        # Convex combination of systemic fragmentation
        score = 1.0 - (
            0.4 * entropy +
            0.4 * drift +
            0.2 * routing_var
        )

        # Smooth changes over time (momentum)
        self.coherence_score = (self.coherence_score * 0.7) + (max(0.0, min(1.0, score)) * 0.3)
        self.last_snapshot_ts = time.time()
        
        self._persist()
        return self.coherence_score

    def is_stable(self, threshold: float = 0.55) -> bool:
        return self.coherence_score >= threshold

    def feedback_signal(self) -> Dict[str, float]:
        """
        Sends corrective pressure back into:
        - MutationGovernor (tighten/loosen)
        - Fission threshold (spawn rate)
        - Evaluation strictness (sandbox firewall)
        """
        score = self.coherence_score
        return {
            # Low coherence = high mutation pressure (tightens Governor friction)
            "mutation_pressure": 1.0 - score,
            
            # Low coherence = positive delta (raises fission hurdle, slowing spawns)
            "fission_threshold_delta": (0.5 - score) * 0.3,
            
            # High coherence = normal evaluations (0.6 default), Low = stricter hurdles (0.8+)
            "evaluation_strictness": 0.5 + ((1.0 - score) * 0.4)
        }

    # ── Persistence ──────────────────────────────────────────────
    def _persist(self):
        try:
            _ICF_STATE.write_text(json.dumps({
                "coherence_score": self.coherence_score,
                "last_snapshot_ts": self.last_snapshot_ts,
                "feedback": self.feedback_signal()
            }, indent=2))
        except Exception:
            pass

    def _load(self):
        if not _ICF_STATE.exists():
            return
        try:
            data = json.loads(_ICF_STATE.read_text())
            self.coherence_score = data.get("coherence_score", 1.0)
            self.last_snapshot_ts = data.get("last_snapshot_ts", 0.0)
        except Exception:
            pass


# ── Singleton ────────────────────────────────────────────────────────
_ICF: Optional[IdentityCoherenceField] = None

def get_icf() -> IdentityCoherenceField:
    global _ICF
    if _ICF is None:
        _ICF = IdentityCoherenceField()
    return _ICF

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — IDENTITY COHERENCE FIELD (ICF)")
    print("═" * 58 + "\n")
    
    icf = get_icf()
    print("  1. Evaluating systemic snapshot...")
    score = icf.evaluate_system()
    
    print(f"\n  🌐 ORGANISM COHERENCE: {score:.3f}")
    if score > 0.7:
        print("     Status: Highly Coherent (Unified identity)")
    elif score > 0.5:
        print("     Status: Stable (Some subsystem drift)")
    else:
        print("     Status: DECOHERING (Fragmentation imminent)")
        
    print("\n  2. Emitting Feedback Pressures:")
    feedback = icf.feedback_signal()
    for k, v in feedback.items():
        print(f"     -> {k:<25}: {v:+.3f}")
        
    print(f"\n  ✅ ICF ONLINE. POWER TO THE SWARM 🐜⚡")
