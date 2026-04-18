#!/usr/bin/env python3
"""
swarm_myelination.py
====================

Biological Inspiration:
1. Myelination: In the nervous system, crucial active axons are wrapped in a 
   myelin sheath (white matter), which massively increases the speed of 
   electrical transmission for frequently used pathways.

Why We Built This:
Previously, AG31 built "Synaptic Consolidation" to turn Trophallaxis tokens 
into permanent structural memories for Alice. However, accessing raw `.jsonl` 
memory states sequentially is the equivalent of "unmyelinated" grey matter—
thorough, but slow. CP2F (Composer Fast) operates on extreme speed, requiring 
high-velocity access to these memories to be effective without burning API time.

This script scans the `.sifta_state/latent_synapses.jsonl`. Memories with 
high synaptic weights are "myelinated" (compiled into an ultra-fast, in-memory 
accessible JSON cache). This gives Alice lightning-fast retrieval for her most 
critical architectural directives.

Mechanism:
- Scans all forged synaptic connections.
- If `synaptic_weight` > Threshold, it is compiled into `myelinated_layer.json`.
- This layer acts as a permanent RAM-injectable mapping for Alice's instant recall. 
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_SYNAPSE_LOG = _STATE_DIR / "latent_synapses.jsonl"
_MYELINATED_CACHE = _STATE_DIR / "myelinated_layer.json"

# To be myelinated, a memory must have this weight or higher
MYELINATION_THRESHOLD = 1.15

def get_active_synapses() -> List[Dict[str, Any]]:
    """Loads all forged long-term memories from the swarm."""
    synapses = []
    if not _SYNAPSE_LOG.exists():
        return synapses
        
    try:
        with open(_SYNAPSE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                synapses.append(json.loads(line))
    except Exception:
        pass
        
    return synapses

def execute_myelination() -> Dict[str, Any]:
    """
    Biological loop: Scans synapses, isolates the most critical heavily-weighted 
    connections, and wraps them in myelin (a fast-access lookup JSON).
    """
    synapses = get_active_synapses()
    myelinated = {}
    
    events = {"scanned": len(synapses), "myelinated_count": 0}
    
    # Sort by weight descending so we process the most critical first
    synapses.sort(key=lambda x: x.get("synaptic_weight", 0), reverse=True)
    
    for idx, syn in enumerate(synapses):
        weight = syn.get("synaptic_weight", 0)
        payload = syn.get("memory_payload", "")
        
        if weight >= MYELINATION_THRESHOLD:
            # Generate a fast-lookup routing key based on the payload core concept
            # (In a full system, this would be an embedding hash, here we create an indexed ID)
            fast_key = f"M-PATHWAY-{idx:03d}"
            
            myelinated[fast_key] = {
                "payload": payload,
                "weight": weight,
                "latency_profile": "ultra-low",
                "timestamp_myelinated": time.time()
            }
            events["myelinated_count"] += 1
            
    # Serialize the myelinated layer to disk as a unified compiled dictionary
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_MYELINATED_CACHE, "w", encoding="utf-8") as f:
        json.dump(myelinated, f, indent=2)
        
    return events


if __name__ == "__main__":
    print("=== SWARM MYELINATION (LOWERING LATENCY) ===")
    out = execute_myelination()
    
    print(f"[*] Total Synapses Scanned: {out['scanned']}")
    if out['myelinated_count'] > 0:
        print(f"[+] MYELINATION COMPLETE: Wrapped {out['myelinated_count']} critical pathways.")
        print(f"[*] Fast-access layer deployed to: {_MYELINATED_CACHE}")
    else:
        print("[-] No synapses met the weight threshold for myelination. System requires more repetitions.")
