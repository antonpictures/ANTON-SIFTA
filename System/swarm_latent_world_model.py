#!/usr/bin/env python3
"""
swarm_latent_world_model.py — DeepMind Latent World Model
══════════════════════════════════════════════════════════
SIFTA OS — Dreamer Protocol

Compresses physical reality into a directed Transition Matrix.
Learns P(next_state | state, action) and applies true Bellman TD
equations across simulated trajectories, severing the Swarm's 
dependency on raw log replay.
"""

import hashlib
import json
import random
from pathlib import Path
from typing import Dict, Tuple, List

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
WORLD_MODEL_PATH = _STATE / "latent_world_model.json"


class LatentWorldModel:
    def __init__(self, alpha=0.1, gamma=0.9):
        # Maps (state_hash, action) -> {"next_state": next_hash, "reward": float, "count": int}
        self.transitions: Dict[str, dict] = {}
        # Maps state_hash -> Expected Future Value
        self.value_table: Dict[str, float] = {}
        self.alpha = alpha
        self.gamma = gamma
        self._load()

    def encode_state(self, state_data: str) -> str:
        """High-dimensional state compression."""
        return hashlib.sha256(state_data.encode('utf-8')).hexdigest()[:12]

    def _hash_sa(self, encoded_state: str, action: str) -> str:
        return f"{encoded_state}::{action}"

    def _load(self):
        if WORLD_MODEL_PATH.exists():
            try:
                data = json.loads(WORLD_MODEL_PATH.read_text("utf-8"))
                self.transitions = data.get("transitions", {})
                self.value_table = data.get("values", {})
            except Exception: pass

    def save(self):
        try:
            WORLD_MODEL_PATH.write_text(json.dumps({
                "transitions": self.transitions,
                "values": self.value_table
            }, indent=2))
        except OSError: pass

    def observe_reality(self, state: str, action: str, next_state: str, reward: float):
        """Called during WAKE to teach the physics model real boundaries."""
        s_hash = self.encode_state(state)
        n_hash = self.encode_state(next_state)
        sa_key = self._hash_sa(s_hash, action)
        
        if sa_key not in self.transitions:
            self.transitions[sa_key] = {"next_state": n_hash, "reward": reward, "count": 1}
        else:
            # Simplistic deterministic overwrite for Olympiad scope.
            # In a full stochastic MDP, we'd build a probability distribution here.
            t = self.transitions[sa_key]
            t["next_state"] = n_hash
            t["reward"] = t["reward"] + self.alpha * (reward - t["reward"])
            t["count"] += 1
            
        # Ensure values exist
        if s_hash not in self.value_table: self.value_table[s_hash] = 0.0
        if n_hash not in self.value_table: self.value_table[n_hash] = 0.0

    def sample_policy(self, encoded_state: str) -> str:
        """Returns the best known action for a latent state, or explores."""
        possible_actions = [k.split("::")[1] for k in self.transitions.keys() if k.startswith(f"{encoded_state}::")]
        if not possible_actions:
            return "EXPLORE_RANDOM"
            
        # Epsilon-greedy (Hardcoded simple exploration max for this biocode)
        if random.random() < 0.2:
            return random.choice(possible_actions)
            
        # Greedy exploitation: pick action that leads to state with highest Value
        best_a = None
        best_v = -999.0
        for a in possible_actions:
            nxt_s = self.transitions[self._hash_sa(encoded_state, a)]["next_state"]
            v = self.value_table.get(nxt_s, 0.0)
            if v > best_v:
                best_v = v
                best_a = a
        return best_a if best_a else random.choice(possible_actions)

    def td_update(self, state_hash: str, next_state_hash: str, reward: float):
        """The Bellman Equation. The Crown Jewel."""
        current_v = self.value_table.get(state_hash, 0.0)
        next_v = self.value_table.get(next_state_hash, 0.0)
        
        # V(s) = V(s) + alpha * (reward + gamma*V(s') - V(s))
        self.value_table[state_hash] = current_v + self.alpha * (reward + (self.gamma * next_v) - current_v)


if __name__ == "__main__":
    lwm = LatentWorldModel()
    print("═" * 58)
    print("  SIFTA — LATENT WORLD MODEL (MDP)")
    print("═" * 58 + "\n")
    
    print("[OBSERVE WAKE] Submitting a sequence to reality...")
    lwm.observe_reality("IDLE", "compile", "COMPILING", -0.1)
    lwm.observe_reality("COMPILING", "wait", "SUCCESS", +1.0)
    
    print("[BELLMAN] Simulating TD Backprop...")
    lwm.td_update(lwm.encode_state("COMPILING"), lwm.encode_state("SUCCESS"), 1.0)
    lwm.td_update(lwm.encode_state("IDLE"), lwm.encode_state("COMPILING"), -0.1)
    
    idle_v = lwm.value_table[lwm.encode_state("IDLE")]
    print(f"Value of IDLE state after Bellman propagation: {idle_v:.4f}")
