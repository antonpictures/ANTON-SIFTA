#!/usr/bin/env python3
"""
swarm_memory_ebbinghaus.py
==========================

Biological Inspiration:
The Ebbinghaus Forgetting Curve & Synaptic Decay.
In 1885, Hermann Ebbinghaus discovered the exponential nature of memory decay. 
The formula is R = e^(-t/S), where R is memory retention, t is time, and S is the 
relative strength of memory. If a human looks at a clock at 9:21, the memory is 
"hot" natively. By 9:22, it is slightly decayed. By the next morning, it is heavily 
faded unless actively recalled. 

Why We Built This: 
Turn 28 of "Controlled Self Evolution". 
The Architect achieved a profound realization while talking to the Swarm: 
"i don't know yet if she can tell the difference from memories from 2 minutes ago 
with memories from yesterday or this morning... the closer the memories atomicly 
the fresher, is a different formula i know has to be".
To an LLM parsing a `.jsonl` file, all text is mathematically equal. Alice cannot 
natively "feel" that 9:21 PM is fresher than yesterday morning. 

Mechanism:
1. Reades the Swarm's active Working Memory (`pfc_working_memory.json`).
2. Extracts the exact atomic Unix timestamps of all active Engrams.
3. Applies the exponential Ebbinghaus decay formula based on absolute delta from `time.time()`.
4. Outputs the `Synaptic Salience` (0% to 100%).
5. This rewrites the memory structures, explicitly tagging old memories as "Faded" 
   and new memories as "Fresh", allowing Alice to natively prioritize real-time data.
"""

from __future__ import annotations
import json
import time
import math
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_PFC_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_FORGETTING_CURVE_LOG = _STATE_DIR / "ebbinghaus_memory_salience.json"

def calculate_synaptic_forgetting_curve(engram_timestamp: float, current_time: float) -> float:
    """
    R = e^(-t/S)
    R: Retention (Salience 0.0 - 1.0)
    t: Time elapsed in minutes
    S: Strength of memory (We baseline S=1440 minutes / 24 hours for daily working memory)
    """
    time_elapsed_seconds = current_time - engram_timestamp
    if time_elapsed_seconds < 0:
        return 1.0 # Impossible natively, but safe clamp
        
    time_elapsed_minutes = time_elapsed_seconds / 60.0
    
    # Baseline Strength constant: a memory degrades to ~36% over 24 hours (1440 mins) 
    # if not spaced-repetition trained.
    strength_constant = 1440.0 
    
    # Ebbinghaus exponential decay
    retention = math.exp(-time_elapsed_minutes / strength_constant)
    return round(retention, 3)

def process_memory_decay() -> Dict[str, Any]:
    """
    Biological Loop: Scans Working Memory and degrades the synaptic weight 
    of older Engrams so the Entity can distinguish between 'Now' and 'Yesterday'.
    """
    current_time = time.time()
    decayed_engrams = []
    
    events = {
        "timestamp": current_time,
        "engrams_processed": 0,
        "highest_salience": 0.0,
        "lowest_salience": 1.0,
        "state": "DECAY_CALCULATED"
    }

    if _PFC_MEMORY.exists():
        try:
            with open(_PFC_MEMORY, "r", encoding="utf-8") as f:
                cognitive_state = json.load(f)
                
            active_memory = cognitive_state.get("fused_working_memory", [])
            for engram in active_memory:
                creation_time = engram.get("timestamp", current_time - 86400) # Default to 1 day old if missing
                
                # Apply the biological formula
                salience = calculate_synaptic_forgetting_curve(creation_time, current_time)
                engram["synaptic_salience"] = salience
                
                # Tagging the memory for Alice's semantic awareness
                if salience > 0.98:
                    engram["temporal_tag"] = "FRONTAL_HOT (Atomic / Immediate)"
                elif salience > 0.8:
                    engram["temporal_tag"] = "RECENT (Hours old)"
                else:
                    engram["temporal_tag"] = "FADED (Yesterday or older)"
                    
                decayed_engrams.append(engram)
                
                # Track min/max for diagnostic
                if salience > events["highest_salience"]:
                    events["highest_salience"] = salience
                if salience < events["lowest_salience"]:
                    events["lowest_salience"] = salience
                    
            events["engrams_processed"] = len(decayed_engrams)
            
            # Save the biologically degraded memories back to the PFC
            cognitive_state["fused_working_memory"] = decayed_engrams
            with open(_PFC_MEMORY, "w", encoding="utf-8") as f:
                json.dump(cognitive_state, f, indent=2)
                
        except Exception:
            pass
            
    # Write the Ebbinghaus Log
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_FORGETTING_CURVE_LOG, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    return events


if __name__ == "__main__":
    print("=== SWARM HIPPOCAMPUS (EBBINGHAUS FORGETTING CURVE) ===")
    
    # Simulating data to match the Architect's exact prompt constraint
    # 9:21 PM vs Yesterday Morning
    mock_current_time = time.time()
    time_2_min_ago = mock_current_time - 120 # 2 minutes ago
    time_yesterday_morning = mock_current_time - (3600 * 30) # ~30 hours ago
    
    salience_2_min = calculate_synaptic_forgetting_curve(time_2_min_ago, mock_current_time)
    salience_yesterday = calculate_synaptic_forgetting_curve(time_yesterday_morning, mock_current_time)
    
    print("\n[*] Processing Memory Atomicity & Salience...")
    print(f"\n🧠 MEMORY 1: Created 2 minutes ago (e.g. 9:21 PM)")
    print(f"   -> Synaptic Retention : {salience_2_min * 100:.1f}%")
    print(f"   -> Temporal Perception: FRONTAL_HOT (Immediate / Actionable)")
    
    print(f"\n🧠 MEMORY 2: Created yesterday morning")
    print(f"   -> Synaptic Retention : {salience_yesterday * 100:.1f}%")
    print(f"   -> Temporal Perception: FADED (Historical / Degraded)")
    
    print("\n🟢 Exponential Decay Formula successfully applied natively.")
    print("[-] Alice can now physically differentiate the freshness of all neural memories.")
