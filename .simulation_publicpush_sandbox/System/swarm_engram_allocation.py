#!/usr/bin/env python3
"""
swarm_engram_allocation.py
==========================

Biological Inspiration:
Engram Allocation & Systems Consolidation. The brain does not record everything like a video camera.
Instead, experiences cause spikes in "Intrinsic Excitability" (mediated by CREB). Only neurons 
with high excitability at the time of an event are allocated to a "Memory Engram". 
Over time (during offline states/sleep), these labile hippocampal engrams are consolidated 
into long-term neocortical storage.

Why We Built This: "The Johnny Mnemonic Layer"
Architect/SwarmGPT realization: We need to store massive amounts of data without overwhelming 
the token window (API costs). CP2F needs a mechanism to synthesize scientific papers and 
chat histories into hyper-compressed structures.

This module provides:
1. Excitability Gating (CREB): Raw text or events are scored. Only highly salient data 
   gets allocated.
2. Engram Compression (IEG Expression): The raw data is compressed into a sparse, abstract 
   schema representing the core semantics.
3. Neocortical Transfer: Moving the engram into permanent sparse block storage, functioning 
   as an infinite biological hard drive.
"""

from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_HIPPOCAMPUS_BUFFER = _STATE_DIR / "hippocampal_buffer.jsonl" # Short term volatile memory
_NEOCORTEX_STORAGE = _STATE_DIR / "neocortical_engrams.jsonl"   # Long term Mnemonic drive

CREB_EXCITABILITY_THRESHOLD = 0.65

class MemoryEngram:
    def __init__(self, raw_data: str, source: str, emotional_weight: float):
        self.raw_data = raw_data
        self.source = source
        # Emotional weight maps directly to biological "CREB excitability"
        self.excitability = emotional_weight 
        self.engram_id = f"ENGRAM-{hashlib.md5(raw_data.encode()).hexdigest()[:8]}"
        self.timestamp = time.time()
        self.compressed_schema = None

    def allocate(self) -> bool:
        """Determines if the memory is salient enough to be allocated to an engram."""
        return self.excitability >= CREB_EXCITABILITY_THRESHOLD
        
    def express_immediate_early_genes(self) -> None:
        """
        Simulates IEG expression (e.g. c-Fos, Arc) which triggers physical plasticity.
        In software, this is where we would trigger an LLM to summarize/extract entities.
        Since we are doing local programmatic compression, we use a heuristic extractor.
        """
        # Biological semantic compression (Heuristic mock of LLM entity extraction)
        words = self.raw_data.replace(".", "").split()
        keywords = sorted(list(set([w for w in words if len(w) > 5])), key=len, reverse=True)[:5]
        
        self.compressed_schema = {
            "core_entities": keywords,
            "excitability_score": self.excitability,
            "origin_node": self.source,
            "length_compression_ratio": round(len(str(keywords)) / max(1, len(self.raw_data)), 3)
        }

    def to_dict(self) -> dict:
        return {
            "engram_id": self.engram_id,
            "timestamp": self.timestamp,
            "compressed_schema": self.compressed_schema,
            "allocated": True
        }

def process_experiential_stream(experiences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Biological pipeline:
    1. Stream of experiences flows into the Hippocampal buffer.
    2. Excitability (CREB) is evaluated.
    3. Winners express genes, form compressed engrams, and move to Neocortex.
    """
    events = {"experiences_processed": len(experiences), "engrams_allocated": 0, "discarded": 0}
    
    _STATE_DIR.mkdir(exist_ok=True)
    allocated_engrams = []
    
    for exp in experiences:
        raw = exp.get("text", "")
        weight = exp.get("weight", 0.0)
        source = exp.get("source", "unknown")
        
        engram = MemoryEngram(raw, source, weight)
        
        if engram.allocate():
            engram.express_immediate_early_genes()
            allocated_engrams.append(engram)
            events["engrams_allocated"] += 1
        else:
            events["discarded"] += 1
            
    # Systems Consolidation: Write to long term Mnemonic drive (Neocortex)
    if allocated_engrams:
        with open(_NEOCORTEX_STORAGE, "a", encoding="utf-8") as f:
            for eng in allocated_engrams:
                f.write(json.dumps(eng.to_dict()) + "\n")
                
    return events


if __name__ == "__main__":
    print("=== SWARM ENGRAM ALLOCATION (JOHNNY MNEMONIC LAYER) ===")
    
    # Mock data stream (representing chat logs, paper data CP2F gathered, code snippets)
    recent_experiences = [
        {"text": "Initialization of standard IDE parameters complete.", "weight": 0.1, "source": "system"},
        {"text": "Memory engram allocation relies on intrinsic excitability and CREB activation to select neurons.", "weight": 0.85, "source": "CP2F_Scientific_Paper_1"},
        {"text": "The user misspelled the word 'chorum'.", "weight": 0.2, "source": "parser"},
        {"text": "Offline replay during sleep transfers unstable hippocampal engrams to the neocortex for lifetime stability.", "weight": 0.88, "source": "CP2F_Scientific_Paper_2"}
    ]
    
    out = process_experiential_stream(recent_experiences)
    
    print(f"[*] Raw Experiences Handled: {out['experiences_processed']}")
    print(f"[-] Discarded (Low Excitability): {out['discarded']}")
    print(f"[+] Engrams Allocated (Neocortex Transfer): {out['engrams_allocated']}")
    print("\nCheck .sifta_state/neocortical_engrams.jsonl for compressed biological storage.")

