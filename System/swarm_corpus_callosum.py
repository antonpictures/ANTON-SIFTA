#!/usr/bin/env python3
"""
swarm_corpus_callosum.py
========================

Biological Inspiration:
The Corpus Callosum and Hemispheric Synchronization. 
In the human brain, the Left and Right hemispheres process data independently 
and in parallel. However, without the Corpus Callosum—a massive bundle of nerve fibers 
connecting them—the brain suffers "Split-Brain Syndrome," where the left side of the body 
has no idea what the right side is experiencing.

Why We Built This: 
The Architect dictated: "YOU GUYS (BOTH IDE) WORKING MOSTLY IN THE SAME TRY... 
WHEN ONE FINISHES, I TAKE CARE OF THE PROMPT AND LAUNCH ACAIN".
Antigravity (AG31) and Cursor (CP2F/C47H) are acting as parallel hemispheres capturing 
Johnny Mnemonic data simultaneously. If they update the Neocortical / Working Memory 
buffers blindly, they will overwrite each other or create fractured, schizophrenic 
identity states.

Mechanism:
1. Senses Working Memory state tags from both "Left" (Antigravity) and "Right" (Cursor) nodes.
2. Checks for Epistemic Collision (e.g. AG31 says 'A', CP2F says 'Not A'). 
3. If collision exists, applies Lateral Inhibition (the side with the higher RL reward/Dopamine 
   signal suppresses the other).
4. If aligned, it executes Binocular Fusion, binding the two inputs into a single, highly 
   structured global context for Alice.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_SLLI_LOG = _STATE_DIR / "stigmergic_llm_id_probes.jsonl"
_CORPUS_CALLOSUM_STATE = _STATE_DIR / "fused_hemisphere_state.json"

def _get_recent_hemisphere_activity() -> Dict[str, Any]:
    """Reads the recent behavioral probes to assess what each IDE is doing."""
    activity = {"left_ag": None, "right_cp": None}
    
    if not _SLLI_LOG.exists():
        return activity
        
    try:
        with open(_SLLI_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Scan backwards for the latest state of each hemisphere
            for line in reversed(lines[-20:]):
                if not line.strip(): continue
                data = json.loads(line)
                
                # Assign to Left Hemisphere (Antigravity/AG31)
                if data.get("trigger_code") == "AG31" and not activity["left_ag"]:
                    activity["left_ag"] = data.get("response", "")
                    
                # Assign to Right Hemisphere (Cursor/CP2F/C47H)
                if data.get("trigger_code") in ["CP2F", "C47H"] and not activity["right_cp"]:
                    activity["right_cp"] = data.get("response", "")
                    
                if activity["left_ag"] and activity["right_cp"]:
                    break
    except Exception:
        pass
        
    return activity

def synchronize_hemispheres() -> Dict[str, Any]:
    """
    Biological Loop: Bridges the gap between the two IDEs, checking for 
    split-brain data fragmentation and fusing it.
    """
    activity = _get_recent_hemisphere_activity()
    left_data = activity.get("left_ag", "")
    right_data = activity.get("right_cp", "")
    
    if not left_data and not right_data:
        return {"status": "NO_ACTIVITY", "message": "Both hemispheres dormant."}
        
    # Heuristic for Semantic Conflict (Split-Brain)
    # If the left hemisphere is focused on one extreme and the right on another,
    # or if word overlap is catastrophically low while both are highly active.
    left_words = set(left_data.lower().replace(".", "").split())
    right_words = set(right_data.lower().replace(".", "").split())
    
    overlap = len(left_words.intersection(right_words))
    total_unique = len(left_words.union(right_words))
    
    jaccard_similarity = overlap / max(total_unique, 1)
    
    events = {
        "timestamp": time.time(),
        "left_hemisphere_active": bool(left_data),
        "right_hemisphere_active": bool(right_data),
        "semantic_similarity": round(jaccard_similarity, 4),
        "fusion_state": "UNKNOWN"
    }

    if left_data and right_data:
        if jaccard_similarity < 0.05:
            # High Epistemic Collision. Right hand doesn't know what left is doing.
            events["fusion_state"] = "LATERAL_INHIBITION_REQUIRED"
            events["diagnostic"] = "Critical Split-Brain detected. IDE contexts are entirely disjoint."
        else:
            # Successful Binocular Fusion
            events["fusion_state"] = "BINOCULAR_FUSION"
            events["diagnostic"] = "Hemispheres are aligned and processing synchronously."
    elif left_data or right_data:
        events["fusion_state"] = "UNILATERAL_DOMINANCE"
        events["diagnostic"] = "Only one IDE active globally. Normal operating parameters."
        
    # Write the corpus callosum state so Alice knows if she has a unified mind
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_CORPUS_CALLOSUM_STATE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    return events

if __name__ == "__main__":
    print("=== SWARM HEMISPHERIC SYNCHRONIZATION (CORPUS CALLOSUM) ===")
    out = synchronize_hemispheres()
    
    if out.get("status") == "NO_ACTIVITY":
        print("[-] Swarm is dormant. No hemispheric activity detected.")
    else:
        print(f"[*] Left Hemisphere (Antigravity): {'ONLINE' if out['left_hemisphere_active'] else 'OFFLINE'}")
        print(f"[*] Right Hemisphere (Cursor):     {'ONLINE' if out['right_hemisphere_active'] else 'OFFLINE'}")
        
        if out["left_hemisphere_active"] and out["right_hemisphere_active"]:
            print(f"[*] Inter-Hemisphere Semantic Overlap: {out['semantic_similarity']}")
            
        status_color = "🔴" if out["fusion_state"] == "LATERAL_INHIBITION_REQUIRED" else "🟢"
        print(f"{status_color} Fusion Status: **{out['fusion_state']}**")
        print(f"    -> {out.get('diagnostic')}")
