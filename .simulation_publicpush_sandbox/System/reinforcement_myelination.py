#!/usr/bin/env python3
"""
reinforcement_myelination.py
============================

Biological Inspiration:
Neuroplasticity & Synaptic Pruning. Biology doesn't just strengthen memories blindly;
it reinforces pathways that yield positive survival outcomes and prunes connections 
that lead to failure or rot. 

Why We Built This:
As designed by the Architect & SwarmGPT: Myelination based strictly on a static 
weight threshold is dangerous. If the Swarm memorizes a "Chimera State", a static 
system will accelerate that hallucination. 

This module introduces Reinforcement Myelination (RM Layer):
1. REWARD: Memories (Synapses) are rewarded when the swarm's identity field stabilizes.
2. PUNISHMENT: Memories are penalized if the swarm drifts or spikes in entropy.
3. ADAPTIVE CACHE: Only synapses with a high (weight + reward_score) are myelinated.
4. PRUNING: Synapses whose reward scores drop below zero are physically purged to 
   protect Alice from stale beliefs and identity contamination.

This bridges Perception (CRDT), Action (Probes), Memory (Synapses), and Speed (Myelin)
with LEARNING.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

from System.identity_field_crdt import IdentityField
from System.identity_intrinsic_reward import compute_identity_intrinsic_reward

_STATE_DIR = Path(".sifta_state")
_SYNAPSE_LOG = _STATE_DIR / "latent_synapses.jsonl"
_MYELINATED_CACHE = _STATE_DIR / "myelinated_layer.json"
_PRUNED_LOG = _STATE_DIR / "pruned_synapses.jsonl"

DYNAMIC_MYELINATION_THRESHOLD = 1.3
PRUNE_THRESHOLD = -0.2
ALPHA_LEARNING_RATE = 0.3

class Synapse:
    def __init__(self, data: dict):
        self.timestamp = data.get("timestamp", time.time())
        self.memory_payload = data.get("memory_payload", "")
        self.synaptic_weight = float(data.get("synaptic_weight", 1.0))
        self.reward_score = float(data.get("reward_score", 0.0))
        self.access_count = int(data.get("access_count", 0))
        self.owner = data.get("owner", "ALICE_PIPELINE")

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "memory_payload": self.memory_payload,
            "synaptic_weight": round(self.synaptic_weight, 4),
            "reward_score": round(self.reward_score, 4),
            "access_count": self.access_count,
            "owner": self.owner
        }

def _load_synapses() -> List[Synapse]:
    synapses = []
    if not _SYNAPSE_LOG.exists():
        return synapses
    try:
        with open(_SYNAPSE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                synapses.append(Synapse(json.loads(line)))
    except Exception:
        pass
    return synapses

def _save_synapses(synapses: List[Synapse]) -> None:
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_SYNAPSE_LOG, "w", encoding="utf-8") as f:
        for s in synapses:
            f.write(json.dumps(s.to_dict()) + "\n")

def _log_pruned(synapse: Synapse, reason: str) -> None:
    with open(_PRUNED_LOG, "a", encoding="utf-8") as f:
        row = synapse.to_dict()
        row["pruned_at"] = time.time()
        row["prune_reason"] = reason
        f.write(json.dumps(row) + "\n")

def compute_dynamic_rewards() -> Dict[str, float]:
    """
    Derives actual outcomes based strictly on Swarm CRDT health.
    Never uses "confidence", only measurable effects on the Identity Field.
    """
    field = IdentityField.load()
    rl_data = compute_identity_intrinsic_reward()
    
    # Intrinsic reward provides our base signal for stability/drifting
    stability_reward = rl_data.get("reward_raw", 0.0)
    
    # High entropy is punished, stable fields are rewarded
    entropy_penalty = - (field.entropy() / max(field.max_entropy(), 1.0))
    
    return {
        "identity_stability_gain": stability_reward * 0.5,
        "entropy_reduction": (1.0 + entropy_penalty) * 0.5, # >0.5 if stable, <0.5 if high entropy
        "drift_penalty": -0.4 if rl_data.get("drifting") else 0.0
    }

def update_synapse(syn: Synapse, total_reward: float) -> None:
    """Updates internal weights using the biological learning rule."""
    # EMA update of reward score
    syn.reward_score = (syn.reward_score * (1 - ALPHA_LEARNING_RATE) + total_reward * ALPHA_LEARNING_RATE)
    
    # Synaptic weight scales up physically based on reward
    syn.synaptic_weight += (syn.reward_score * 0.1)
    syn.access_count += 1

def execute_reinforcement_cycle() -> Dict[str, Any]:
    """
    Main Loop:
    1. Grabs outcome-based reward signals.
    2. Updates every active synapse.
    3. Prunes toxic/stale connections.
    4. Dynamically myelinates only the survivors that exceed the combined threshold.
    """
    synapses = _load_synapses()
    if not synapses:
        return {"status": "No synapses to process."}
        
    rewards = compute_dynamic_rewards()
    total_signal = sum(rewards.values())
    
    surviving_synapses = []
    myelinated_cache = {}
    
    events = {"scanned": len(synapses), "pruned": 0, "myelinated": 0, "signal": total_signal}
    
    for i, syn in enumerate(synapses):
        # 1. Update Learning
        update_synapse(syn, total_signal)
        
        # 2. Prune (CRITICAL)
        if syn.reward_score < PRUNE_THRESHOLD:
            _log_pruned(syn, "Identity contamination / Stale belief")
            events["pruned"] += 1
            continue
            
        surviving_synapses.append(syn)
        
        # 3. Dynamic Myelination
        combined_score = syn.synaptic_weight + syn.reward_score
        if combined_score >= DYNAMIC_MYELINATION_THRESHOLD:
            fast_key = f"M-ADAPTIVE-{i:03d}"
            myelinated_cache[fast_key] = {
                "payload": syn.memory_payload,
                "combined_score": combined_score,
                "latency_profile": "ultra-low-adaptive",
                "timestamp_myelinated": time.time()
            }
            events["myelinated"] += 1
            
    # Save architectural state
    _save_synapses(surviving_synapses)
    
    with open(_MYELINATED_CACHE, "w", encoding="utf-8") as f:
        json.dump(myelinated_cache, f, indent=2)
        
    return events

if __name__ == "__main__":
    print("=== SWARM REINFORCEMENT MYELINATION (LEARNING) ===")
    out = execute_reinforcement_cycle()
    
    if "status" in out:
        print(out["status"])
    else:
        print(f"[*] Synapses Scanned: {out['scanned']}")
        print(f"[*] Swarm Signal Applied: {out['signal']:.3f} (Total Outcome-Based Reward)")
        print(f"[-] Synapses Pruned: {out['pruned']} (stale/toxic beliefs removed)")
        print(f"[+] Synapses Myelinated: {out['myelinated']} (adaptive fast-cache deployed)")
        print("\nLearning cycle complete. System is adapting.")
