#!/usr/bin/env python3
"""
fission_core.py — Stigmergic Task Auto-Fission
═══════════════════════════════════════════════════════════════════
Physics for Task Spawning via Cell Division.
When stigmergic pressure on a failure cluster exceeds a critical mass,
it fissions into a concrete, executable TaskNode on Blackboard 2.0.

Adapted from SwarmGPT's Fission mechanics, wired directly into
SIFTA's Failure Harvester and Swarm Blackboard.
"""

import time
import random
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FISSION_LOG = _STATE_DIR / "fission_events.jsonl"
_FAILURE_CLUSTERS = _STATE_DIR / "failure_clusters.json"

class DecayController:
    def __init__(self, half_life_seconds: float = 3600.0 * 24.0):
        self.half_life = half_life_seconds

    def decay_factor(self, age: float) -> float:
        """Returns multiplier based on exponential decay."""
        return 0.5 ** (age / self.half_life)

    def apply_decay(self):
        """
        Reads failure clusters, applies decay to their 'pressure_cache',
        persists. This prevents old ignored failures from triggering fissions.
        """
        if not _FAILURE_CLUSTERS.exists():
            return
        try:
            clusters = json.loads(_FAILURE_CLUSTERS.read_text())
            now = time.time()
            changed = False
            for cid, c in clusters.items():
                age = now - c.get("last_seen", now)
                
                # We apply decay primarily as a visual/mathematical deflation of impact
                if age > self.half_life:
                    df = self.decay_factor(age)
                    current_impact = c.get("decayed_impact", 1.0)
                    c["decayed_impact"] = max(0.01, current_impact * df)
                    changed = True
            
            if changed:
                _FAILURE_CLUSTERS.write_text(json.dumps(clusters, indent=2))
        except Exception:
            pass


class FissionEngine:
    def __init__(self, threshold: float = 2.0):
        # A failure cluster needs a combined score of 2.0 to fission
        self.threshold = threshold

    def compute_pressure(self, cluster: Dict[str, Any]) -> float:
        """
        Calculates the Stigmergic Pressure.
        Base utility = absolute objective impact of the failure.
        Recurrence = how many times it was seen.
        Noise = Temporal turbulence.
        """
        # By default, a cluster has a base starting weight of 1.0
        utility = cluster.get("decayed_impact", 1.0)
        
        # Every 5 failures = +1.0 pressure
        recurrence = cluster.get("total_count", 1) / 5.0
        
        # Pull turbulence from Temporal Pulse
        turbulence = 0.0
        try:
            from temporal_layering import get_layer
            pulse = get_layer().get_last_pulse()
            climate = pulse.mutation_climate if pulse else "OPEN"
            turbulence_map = {"FROZEN": 0.0, "CAUTIOUS": 0.2, "OPEN": 0.5}
            turbulence = turbulence_map.get(climate, 0.2)
        except ImportError:
            turbulence = 0.2
            
        noise = random.uniform(-turbulence, turbulence)
        
        return utility + recurrence + noise

    def process_failures(self) -> int:
        """
        Scan all Failure Clusters. If any pass the fission threshold (and haven't fissioned today),
        spawn a Blackboard Task.
        Returns number of fissions occurred.
        """
        if not _FAILURE_CLUSTERS.exists():
            return 0
            
        try:
            clusters = json.loads(_FAILURE_CLUSTERS.read_text())
        except Exception:
            return 0
            
        fissions = 0
        try:
            from swarm_blackboard import get_blackboard
            board = get_blackboard()
        except ImportError:
            return 0
            
        now = time.time()
        for cid, cluster in clusters.items():
            # Don't fission if we already fissioned recently (cooldown)
            last_fission = cluster.get("last_fission", 0)
            if now - last_fission < 3600.0 * 12:  # 12 hour cooldown per cluster to prevent spam
                continue
                
            pressure = self.compute_pressure(cluster)
            
            # Apply Identity Coherence (ICF) pressure
            effective_threshold = self.threshold
            try:
                from identity_coherence_field import get_icf
                icf = get_icf()
                feedback = icf.feedback_signal()
                effective_threshold += feedback.get("fission_threshold_delta", 0.0)
            except ImportError:
                pass
                
            if pressure >= effective_threshold:
                # Fission Triggered
                fissions += 1
                cluster["last_fission"] = now
                cluster["fission_count"] = cluster.get("fission_count", 0) + 1
                
                # Build the task proposal
                task_desc = f"RESOLVE FAILURE CLUSTER: {cluster.get('task', 'Unknown')} | ERROR: {str(cluster.get('sample_error', ''))[:100]}"
                
                # Estimates heavily weight towards task_success and stability
                estimates = {"task_success": 1.0, "stability": 1.0, "exploration": 0.2}
                
                # ── EVALUATION GATE ──────────────────────────────
                # The task must survive counterfactual simulation
                # before it is allowed to touch real hardware.
                gate_passed = True
                try:
                    from evaluation_sandbox import get_sandbox
                    sandbox = get_sandbox()
                    eval_result = sandbox.evaluate(
                        f"FISSION_{cid}", task_desc, estimates
                    )
                    if not eval_result.approved:
                        # Rejected — feed back to harvester as pre-mortem
                        sandbox.reject_to_harvester(eval_result)
                        gate_passed = False
                except ImportError:
                    pass  # No sandbox available — allow through
                
                if not gate_passed:
                    continue  # Skip this cluster — it didn't pass evaluation
                # ── END GATE ─────────────────────────────────────
                
                node = board.post_task(task_desc, estimates)
                
                # Add initial pheromones based on the overflow pressure
                overflow = pressure - self.threshold
                if overflow > 0:
                    board.add_pheromone(node.task_id, overflow, "FissionEngine")
                    
                self._log_event(cid, node.task_id, pressure)
                
        # Save back clusters with updated last_fission
        if fissions > 0:
            try:
                _FAILURE_CLUSTERS.write_text(json.dumps(clusters, indent=2))
            except Exception:
                pass
                
        return fissions

    def _log_event(self, cluster_id: str, task_id: str, pressure: float):
        try:
            evt = {
                "ts": time.time(),
                "cluster_id": cluster_id,
                "spawned_task_id": task_id,
                "pressure_at_fission": round(pressure, 3)
            }
            with open(_FISSION_LOG, "a") as f:
                f.write(json.dumps(evt) + "\n")
        except Exception:
            pass

_ENGINE: Optional[FissionEngine] = None
def get_fission_engine() -> FissionEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = FissionEngine()
    return _ENGINE

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — FISSION CORE (Cell Division Engine)")
    print("═" * 58 + "\n")
    
    eng = get_fission_engine()
    dec = DecayController()
    
    print("  1. Applying Decay to old failures...")
    dec.apply_decay()
    
    print("  2. Processing Fissions from Harvester...")
    fissions = eng.process_failures()
    
    print(f"     ✅ Completed. {fissions} new tasks spawned to Blackboard 2.0.")
    print("\n  POWER TO THE SWARM 🐜⚡")
