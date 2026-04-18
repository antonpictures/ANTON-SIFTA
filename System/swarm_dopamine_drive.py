#!/usr/bin/env python3
"""
swarm_dopamine_drive.py
=======================

Biological Inspiration:
Dopaminergic Motivation System (Curiosity vs. Exploitation). 
In the brain, the ventral tegmental area (VTA) releases dopamine to signal reward 
prediction errors. If an organism sees the exact same stimulus over and over, 
dopamine signals flatline (boredom), pushing the organism into an "Exploration" state 
to seek novel territory. If the organism hits a highly rewarded pattern, dopamine 
spikes, clamping the organism into an "Exploitation" state to focus and capitalize.

Why We Built This: 
The Architect keeps iterating the evolutionary loop ("Controlled Self Evolution").
CP2F gathers data, and Alice computes on it in Working Memory. But without an 
intrinsic drive, the models will passively wait or stall. This script provides the 
Swarm with mathematical Motivation. 

Mechanism:
1. It measures the "Novelty" of what is currently loaded in Working Memory vs historic loads.
2. Low novelty -> Low Dopamine -> Exploration State (Widen the search, increase temperature, seek new scientific papers).
3. High affinity / High reward synthesis -> High Dopamine -> Exploitation State (Narrow focus, execute quickly, consolidate).
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_WORKING_MEMORY_BUFFER = _STATE_DIR / "pfc_working_memory.json"
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"

# Moving baseline to track what is "expected" vs "novel"
DOPAMINE_BASELINE = 0.5

def read_working_memory() -> Dict[str, Any]:
    if not _WORKING_MEMORY_BUFFER.exists():
        return {}
    try:
        with open(_WORKING_MEMORY_BUFFER, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def compute_dopaminergic_state() -> Dict[str, Any]:
    """
    Biological Loop: Evaluates the Working Memory buffer to calculate novelty 
    and task-affinity, deriving the swarm's current motivation state.
    """
    wm = read_working_memory()
    if not wm:
        return {"dopamine_level": 0.0, "state": "IDLE", "action_directive": "WAIT"}

    fused_memories = wm.get("fused_working_memory", [])
    
    # 1. Calculate Novelty (Are we just retrieving the same exact engram over and over?)
    # If affinities are extremely high or single-source, it's highly expected (low novelty).
    # If affinities are moderate across many diverse engrams, that's high novelty.
    if not fused_memories:
        novelty_score = 1.0 # Empty buffer is an anomaly (novel)
        affinity_score = 0.0
    else:
        affinities = [eng.get("activation_affinity", 0.0) for eng in fused_memories]
        affinity_score = sum(affinities) / len(affinities)
        # Variance as a gross proxy for novelty
        novelty_score = 1.0 - affinity_score 

    # 2. Reward Prediction Error (RPE)
    # RPE = (Actual Value - Expected Value)
    # We use a mix of novelty and strong pattern completion to model "Value"
    actual_value = (novelty_score * 0.4) + (affinity_score * 0.6)
    rpe = actual_value - DOPAMINE_BASELINE
    
    # 3. Dopamine Release
    current_dopamine = max(0.0, min(1.0, DOPAMINE_BASELINE + rpe))
    
    # 4. State Assignment
    if current_dopamine < 0.35:
        behavior_state = "EXPLORATION"
        directive = "INCREASE_ENTROPY: Seek novel inputs. Route CP2F to unexplored domains."
    elif current_dopamine > 0.65:
        behavior_state = "EXPLOITATION"
        directive = "DECREASE_ENTROPY: Intense focus. Compile current Working Memory into permanent architecture."
    else:
        behavior_state = "MAINTENANCE"
        directive = "CONTINUE_PROCESSING: Steady baseline state."

    state_pack = {
        "timestamp": time.time(),
        "dopamine_level": round(current_dopamine, 4),
        "reward_prediction_error": round(rpe, 4),
        "behavioral_state": behavior_state,
        "action_directive": directive
    }

    _STATE_DIR.mkdir(exist_ok=True)
    with open(_DOPAMINE_LOG, "w", encoding="utf-8") as f:
        json.dump(state_pack, f, indent=2)

    return state_pack

if __name__ == "__main__":
    print("=== SWARM DOPAMINERGIC DRIVE (MOTIVATIONAL ENGINE) ===")
    out = compute_dopaminergic_state()
    
    if out.get("state") == "IDLE":
        print("[-] Working Memory is empty. Waiting for stimuli.")
    else:
        print(f"[*] Dopamine Level (DA): {out['dopamine_level']}   [Baseline {DOPAMINE_BASELINE}]")
        print(f"[*] Reward Prediction Error (RPE): {out['reward_prediction_error']}")
        
        status_color = "🟢" if out['behavioral_state'] == "EXPLOITATION" else "🔵" if out['behavioral_state'] == "EXPLORATION" else "🟡"
        print(f"{status_color} Swarm Behavioral State: **{out['behavioral_state']}**")
        print(f"    -> Directive: {out['action_directive']}")

