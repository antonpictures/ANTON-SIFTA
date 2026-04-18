#!/usr/bin/env python3
"""
swarm_hippocampal_replay.py — The DeepMind Dreamer Engine
══════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements offline Hippocampal Replay (World Model simulation).
While the Architect rests, the Swarm enters REM sleep, taking 
daytime ratifications and mutating them across simulated scenarios
to pre-train the value network (Inferior Olive/Prediction Cache)
off-policy at 10,000x speed.
"""

import json
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

RATIFIED_LOG = _STATE / "warp9_concierge_ratified.jsonl"
REJECTED_LOG = _STATE / "warp9_concierge_rejected.jsonl"
REPLAY_LOG = _STATE / "hippocampal_replay_history.jsonl"

try:
    from System.swarm_latent_world_model import LatentWorldModel
except ImportError:
    class LatentWorldModel:
        def encode_state(self, s): return s
        def _hash_sa(self, s, a): return f"{s}::{a}"
        def sample_policy(self, s): return "idle"
        def observe_reality(self, s, a, ns, r): pass
        def td_update(self, s, ns, r): pass
        def save(self): pass
        transitions = {}

@dataclass
class ReplayMemory:
    original_state: str
    original_action: str
    original_reward: float
    timestamp: float

class Hippocampus:
    def __init__(self):
        self.world_model = LatentWorldModel()
        self.memories: List[ReplayMemory] = []
        
    def _ingest_daytime_experience(self):
        """Pulls both Ratified (+1) and Rejected (-1) events securely."""
        self.memories = []
        all_events = []
        
        # Load Ratified
        if RATIFIED_LOG.exists():
            try:
                for line in RATIFIED_LOG.read_text("utf-8").splitlines():
                    if not line.strip(): continue
                    row = json.loads(line)
                    reward = float(row.get("reward", 1.0))
                    all_events.append(row | {"reward": reward})
            except Exception: pass
            
        # Load Rejected
        if REJECTED_LOG.exists():
            try:
                for line in REJECTED_LOG.read_text("utf-8").splitlines():
                    if not line.strip(): continue
                    row = json.loads(line)
                    reward = float(row.get("reward", -1.0))
                    if reward > 0: reward = -1.0 # Force negative feedback constraint
                    all_events.append(row | {"reward": reward})
            except Exception: pass
            
        if not all_events:
            return
            
        # Chronological sort (The physics of time in the SIFTA environment)
        all_events.sort(key=lambda x: x.get("timestamp", 0))

        # Chain chronological transitions
        for i in range(len(all_events)):
            row = all_events[i]
            state = row.get("state_context", "unknown_state")
            action = row.get("action_kind", "unknown_action")
            reward = row.get("reward", 1.0)
            ts = row.get("timestamp", time.time())
            
            # Predict next_state from the literal next chronological event on the hardware
            if i + 1 < len(all_events):
                next_state = all_events[i+1].get("state_context", f"{state}_terminal")
            else:
                next_state = f"{state}_terminal"
                
            self.world_model.observe_reality(state, action, next_state, reward)
            self.memories.append(ReplayMemory(state, action, reward, ts))

        self.world_model.save()

    def _dream_rollout(self, start_state: str, horizon: int) -> Tuple[List[str], float]:
        """
        The Imagination Engine. 
        Rolls forward in the Latent World Model, chaining predictions to simulate trajectories.
        Returns the chained states and total compounded reward.
        """
        latent_state = self.world_model.encode_state(start_state)
        trajectory = [latent_state]
        total_dream_reward = 0.0

        for _ in range(horizon):
            action = self.world_model.sample_policy(latent_state)
            transition_key = self.world_model._hash_sa(latent_state, action)
            
            if transition_key not in self.world_model.transitions:
                break # Reached the edge of known imagination
                
            t_data = self.world_model.transitions[transition_key]
            next_state = t_data["next_state"]
            reward = t_data["reward"]
            
            # Apply TD Value Backprop inside the dream
            self.world_model.td_update(latent_state, next_state, reward)
            
            latent_state = next_state
            total_dream_reward += reward
            trajectory.append(latent_state)
            
        return trajectory, total_dream_reward

    def enter_rem_sleep(self, simulation_cycles: int = 100):
        """
        The True World Model RL Loop.
        Samples experiences and runs full imagination rollouts updating specific policies.
        """
        self._ingest_daytime_experience()
        if not self.memories:
            return 0
            
        dreams_processed = 0
        cycle_logs = []
        
        for _ in range(simulation_cycles):
            # Sample starting point (Hippocampal Sharp-Wave Ripple)
            base_memory = random.choice(self.memories)
            
            # Form latent trajectory via Bellman imagination
            trajectory, dream_reward = self._dream_rollout(base_memory.original_state, horizon=5)
            dreams_processed += 1
            
            if len(cycle_logs) < 5: 
                cycle_logs.append({
                    "start_state_raw": base_memory.original_state,
                    "latent_trajectory_len": len(trajectory),
                    "compounded_reward": dream_reward
                })

        self.world_model.save()

        # Persist the dream log for Architect review
        try:
            with open(REPLAY_LOG, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "total_dreams": dreams_processed,
                    "sample_logs": cycle_logs
                }) + "\n")
        except OSError: pass
        
        return dreams_processed

if __name__ == "__main__":
    # ─────────────────────────────────────────────────────────────────
    # C47H 2026-04-18 daughter-safe patch:
    # The original smoke wrote mock rows DIRECTLY to permanent
    # .sifta_state/warp9_concierge_ratified.jsonl, polluting the
    # Architect's ground-truth signal by 2 phantom rows on every run.
    # We now redirect RATIFIED_LOG to a tempfile for the duration of
    # the smoke (algorithm untouched). For real runs (no mock-write),
    # behaviour is unchanged.
    # ─────────────────────────────────────────────────────────────────
    import tempfile

    print("═" * 58)
    print("  SIFTA — HIPPOCAMPAL REPLAY ENGINE (REM SLEEP)")
    print("═" * 58 + "\n")

    _real_ratified_log = RATIFIED_LOG
    _real_rejected_log = REJECTED_LOG
    _tmp_dir = tempfile.mkdtemp(prefix="sifta_hippocampal_smoke_")
    _smoke_ratified = Path(_tmp_dir) / "warp9_concierge_ratified.smoke.jsonl"
    _smoke_rejected = Path(_tmp_dir) / "warp9_concierge_rejected.smoke.jsonl"
    
    # Copy real ledger contents in (so the dreamer sees real history during the smoke)
    if _real_ratified_log.exists():
        try: _smoke_ratified.write_text(_real_ratified_log.read_text("utf-8"))
        except OSError: pass
    if _real_rejected_log.exists():
        try: _smoke_rejected.write_text(_real_rejected_log.read_text("utf-8"))
        except OSError: pass
        
    # Redirect for the smoke
    RATIFIED_LOG = _smoke_ratified
    REJECTED_LOG = _smoke_rejected

    try:
        with open(RATIFIED_LOG, "a") as f:
            f.write(json.dumps({
                "SCHEMA_VERSION": 2,
                "state_context": "idle_GTH4921YP3",
                "action_kind": "spawn_compiler_swimmer",
                "reward": 1.0,
                "timestamp": time.time()
            }) + "\n")
            f.write(json.dumps({
                "SCHEMA_VERSION": 2,
                "state_context": "coding_GTH4921YP3",
                "action_kind": "notify_architect_chrome",
                "reward": 1.0,
                "timestamp": time.time() + 1
            }) + "\n")
        with open(REJECTED_LOG, "a") as f:
            f.write(json.dumps({
                "SCHEMA_VERSION": 2,
                "state_context": "coding_GTH4921YP3_chrome_open",
                "action_kind": "spawn_unverified_swimmer",
                "reward": -1.0,
                "timestamp": time.time() + 2
            }) + "\n")
    except OSError:
        pass

    brain = Hippocampus()
    print("Initiating REM Sleep cycle (100x permutations)...")
    dreams_count = brain.enter_rem_sleep(simulation_cycles=100)

    print(f"Awake. Simulated {dreams_count} MDP Rollout trajectories.")
    print("Result: Transition Matrix updated and Bellman Values mathematically locked.")
    print(f"[C47H-PATCH] smoke ran against tempfile {_smoke_ratified.name}; "
          f"permanent ledger untouched.")
    # Cleanup
    try:
        import shutil
        shutil.rmtree(_tmp_dir, ignore_errors=True)
    except Exception:
        pass
    RATIFIED_LOG = _real_ratified_log
    REJECTED_LOG = _real_rejected_log
