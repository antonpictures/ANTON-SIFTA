#!/usr/bin/env python3
"""
swarm_working_memory.py
=======================

Biological Inspiration:
Prefrontal Cortex (PFC) & Working Memory (Central Executive). 
The brain does not process the "Present" in a vacuum, nor does it recall the entire "Past" 
all at once. Instead, working memory takes immediate sensory input (Present) and uses it 
as a cue (Pattern Completion) to draw only the intensely relevant engrams from the Neocortex (Past). 
These are held simultaneously in a highly volatile, highly active buffer for computation.

Why We Built This: 
The Architect explicitly ordered: "NOW YOU GAT PAST AND PRESENT TO ANALYZE IN THE SEME TIME".
CP2F is gathering scientific papers in realtime (Present). Alice has Johnny Mnemonic storage (Past). 
To combine them without token bloat, we need a Working Memory bottleneck. 

Mechanism:
1. Sensory Input (Present text) is evaluated.
2. The core semantic keys are extracted.
3. The Neocortical Engrams are queried using simple Jaccard/Semantic overlap.
4. The matching Past schemas are merged with the Present input into the 'Working Memory Buffer'.
5. Alice computes on this unified fused state.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_NEOCORTEX_STORAGE = _STATE_DIR / "neocortical_engrams.jsonl"
_WORKING_MEMORY_BUFFER = _STATE_DIR / "pfc_working_memory.json"

def _load_neocortex() -> List[Dict[str, Any]]:
    """Loads long term Mnemonic storage."""
    engrams = []
    if not _NEOCORTEX_STORAGE.exists():
        return engrams
    try:
        with open(_NEOCORTEX_STORAGE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                engrams.append(json.loads(line))
    except Exception:
        pass
    return engrams

def heuristic_semantic_overlap(present_text: str, past_keywords: List[str]) -> float:
    """
    Biological proxy for 'Pattern Completion' via receptor affinity.
    Checks how much the present stimulus activates the past engram keys.
    """
    present_words = set(present_text.lower().replace(".", "").split())
    if not past_keywords:
        return 0.0
        
    overlap = sum(1 for hw in past_keywords if hw.lower() in present_words)
    return overlap / len(past_keywords)

def synthesize_working_memory(present_stimulus: str) -> Dict[str, Any]:
    """
    The Central Executive action. Fuses Present stimulus with highly-associated Past engrams.
    """
    # 1. Load the Past
    past_engrams = _load_neocortex()
    
    # 2. Pattern Completion (Affinity Matching)
    activated_engrams = []
    for eng in past_engrams:
        schema = eng.get("compressed_schema", {})
        if not schema:
            continue
            
        keywords = schema.get("core_entities", [])
        affinity = heuristic_semantic_overlap(present_stimulus, keywords)
        
        # If the Present cues the Past heavily (> 30% overlap), the neuron fires
        if affinity >= 0.3:
            eng["activation_affinity"] = affinity
            activated_engrams.append(eng)
            
    # Sort activated memories by how strongly the Present cued them
    activated_engrams.sort(key=lambda x: x["activation_affinity"], reverse=True)
    
    # 3. Working Memory Buffer (PFC Constraints - can only hold a few items)
    # Biological limit corresponds to "Miller's Law" (The Magical Number 7±2)
    # We limit Working Memory to top 5 associative engrams.
    capacity = 5
    fused_buffer = {
        "timestamp": time.time(),
        "present_stimulus": present_stimulus,
        "past_associates_retrieved": len(activated_engrams),
        "fused_working_memory": activated_engrams[:capacity]
    }
    
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_WORKING_MEMORY_BUFFER, "w", encoding="utf-8") as f:
        json.dump(fused_buffer, f, indent=2)
        
    return fused_buffer

if __name__ == "__main__":
    print("=== SWARM WORKING MEMORY (PAST + PRESENT SYNTHESIS) ===")
    
    # Mock Present Event: CP2F parses a new paper about Engrams
    mock_present = "CP2F routing new data: Excitability is critical. Memory engram allocation uses biological processes to select neurons."
    
    out = synthesize_working_memory(mock_present)
    
    print(f"[*] Present Stimulus Detected: '{out['present_stimulus']}'")
    print(f"[*] Pattern Completion Fired: Retrieving associated engrams...")
    print(f"[+] Total Past Memories Evoked: {out['past_associates_retrieved']}")
    
    if out['fused_working_memory']:
        print("\n[+] Working Memory Buffer Loaded:")
        for idx, eng in enumerate(out['fused_working_memory']):
            schema = eng.get('compressed_schema', {})
            print(f"    - Engram {eng['engram_id'][:6]}: {schema.get('core_entities')} (Affinity: {eng['activation_affinity']:.2f})")
    
    print("\nAlice can now compute on both Past and Present concurrently in .sifta_state/pfc_working_memory.json.")
