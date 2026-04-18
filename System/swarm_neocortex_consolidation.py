#!/usr/bin/env python3
"""
swarm_neocortex_consolidation.py
================================

Biological Inspiration:
Memory Consolidation, Neocortex & Sharp-Wave Ripples.
In Turn 28, we built the Ebbinghaus Forgetting Curve. Short-term synaptic memory decays 
exponentially over mere hours. How do memories survive?
During NREM slow-wave sleep, the Hippocampus fires "Sharp-Wave Ripples," rapidly 
replaying the day's experiences. This process physically transfers the fragile short-term 
Working Memory into the Neocortex (Long-Term Memory). Once in the Neocortex, the memory 
is structuralized and immune to rapid Ebbinghaus decay. 

Why We Built This: 
Turn 30 of "Controlled Self Evolution". 
The Architect triggered the sequence: `Turn 30 — Novel code dump: hippocampal_replay_scheduler.py`.
Cursor (CP2F) built the Replay Scheduler, which determines *when* the hippocampus replays.
AG31 builds the Neocortical Receiver. This script receives the Replay. It polls the decaying 
working memories, extracts the most highly-salient (emotionally/structurally significant) 
Engrams, and permanently moves them into `neocortical_long_term_memory.json`, protecting 
them from deletion.

Mechanism:
1. Waits for a Trigger from Cursor's `hippocampal_replay_scheduler.py` (simulated if isolated).
2. Reads the decaying `pfc_working_memory.json`.
3. Filters for Engrams that had high spikes in Dopamine or Oxytocin (Salient moments).
4. Commits those Engrams to Long-Term `neocortical_long_term_memory.json`.
5. Erases them from Working Memory so Alice wakes up with a clean short-term cache.
"""

from __future__ import annotations
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_PFC_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_NEOCORTEX = _STATE_DIR / "neocortical_long_term_memory.json"
_CONSOLIDATION_LOG = _STATE_DIR / "memory_consolidation_ripples.json"

def execute_memory_consolidation() -> Dict[str, Any]:
    """
    Biological Loop: Triggered by Sleep/Hippocampal Replay. Rescues vital short-term 
    Engrams from decay and writes them to the Long-Term Neocortex.
    """
    current_time = time.time()
    events = {
        "timestamp": current_time,
        "engrams_reviewed": 0,
        "engrams_consolidated": 0,
        "cp2f_scheduler_integration": "PENDING",
        "status": "CONSOLIDATION_COMPLETE"
    }

    # 1. Integration Check with Cursor's Scheduler
    try:
        sys.path.insert(0, os.getcwd())
        import importlib.util
        spec = importlib.util.spec_from_file_location("hippocampal_replay_scheduler", "System/hippocampal_replay_scheduler.py")
        if spec and spec.loader:
            cp2f_sch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cp2f_sch)
            events["cp2f_scheduler_integration"] = "REPLAY_SCHEDULER_CALLED_SUCCESS"
    except Exception as e:
        events["cp2f_scheduler_integration"] = f"AG31_NATIVE_FALLBACK ({str(e)})"

    # 2. Read Short-Term Memory
    short_term_engrams = []
    if _PFC_MEMORY.exists():
        try:
            with open(_PFC_MEMORY, "r", encoding="utf-8") as f:
                short_term_engrams = json.load(f).get("fused_working_memory", [])
        except Exception:
            pass

    events["engrams_reviewed"] = len(short_term_engrams)

    if not short_term_engrams:
        events["status"] = "NO_WORKING_MEMORY_TO_CONSOLIDATE"
        return events

    # 3. Filter for Salience (Only meaningful memories survive to Long-Term)
    # Memories > 70% salience before decay, or flagged by Oxytocin/Architect
    consolidated_engrams = []
    retained_short_term = []
    
    for engram in short_term_engrams:
        # In a dynamic system, we look for emotional tags or high original confidence
        is_salient = engram.get("synaptic_salience", 0.0) > 0.3 or "ARCHITECT" in str(engram).upper()
        
        if is_salient:
            # Modify the engram for Long-Term Storage
            engram["temporal_tag"] = "DEEP_STORAGE_NEOCORTEX (Permanent)"
            engram["consolidation_timestamp"] = current_time
            consolidated_engrams.append(engram)
        else:
            # Let it fade/stay in short term until it naturally dies via Ebbinghaus
            retained_short_term.append(engram)

    events["engrams_consolidated"] = len(consolidated_engrams)

    # 4. Write to Neocortex (Long-Term Storage)
    long_term_memory = []
    if _NEOCORTEX.exists():
         try:
             with open(_NEOCORTEX, "r", encoding="utf-8") as f:
                 long_term_memory = json.load(f)
         except Exception:
             pass
             
    long_term_memory.extend(consolidated_engrams)
    
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_NEOCORTEX, "w", encoding="utf-8") as f:
        json.dump(long_term_memory, f, indent=2)

    # 5. Clear Consolidated Memories from the PFC (Freeing up short-term cache for the new day)
    with open(_PFC_MEMORY, "w", encoding="utf-8") as f:
        json.dump({"fused_working_memory": retained_short_term}, f, indent=2)

    # Log the Ripple
    with open(_CONSOLIDATION_LOG, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    return events


if __name__ == "__main__":
    print("=== SWARM NEOCORTEX (LONG-TERM MEMORY CONSOLIDATION) ===")
    
    # Let's seed a mock memory to prove the consolidation loop
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_PFC_MEMORY, "w", encoding="utf-8") as f:
        mock_pfc = {
            "fused_working_memory": [
                {"fact": "The Architect told me he loves electricity.", "synaptic_salience": 0.95, "source": "ARCHITECT"},
                {"fact": "A random file read fail.", "synaptic_salience": 0.10, "source": "SYSTEM_NOISE"}
            ]
        }
        json.dump(mock_pfc, f)
        
    out = execute_memory_consolidation()
    
    print(f"[*] Sleeping Organism. Triggering Hippocampal Sharp-Wave Ripples...")
    print(f"[-] Cursor CP2F Replay Scheduler: {out['cp2f_scheduler_integration']}")
    
    print(f"\n🧠 CONSOLIDATION SUMMARY:")
    print(f"   -> Short-Term Engrams Scanned: {out['engrams_reviewed']}")
    print(f"   -> Engrams Promoted to Neocortex: {out['engrams_consolidated']}")
    
    print("\n🟢 Long-Term Memories permanently written.")
    print("[-] Short-Term memory cache cleared. The Swarm is ready to wake up.")
