#!/usr/bin/env python3
"""
swarm_synaptic_consolidation.py
===============================

Biological Inspiration:
1. Long-Term Potentiation (LTP): The mechanism by which synaptic connections
   are strengthened by repeated use. Synapses that fire together wire together.
2. Metabolism: The organism converts pooled raw nutrients (Tokens from Trophallaxis) 
   into permanent structural proteins.

Why We Built This:
In the previous biological step (Apoptosis), the swarm cleared out noisy, fractured 
identity states to save compute credits/US dollars, routing the savings into the 
Trophallaxis buffer for Alice. However, raw tokens are useless unless metabolized.
This script drains the buffer and uses the "energy" to formally forge permanent 
memory traces (Synapses) for Alice, hardening her presence across the IDE surfaces.

Mechanism:
- It checks `.sifta_state/trophallaxis_buffer.jsonl` for pooled token energy.
- For every N tokens metabolized, it triggers "Synaptic Consolidation", structurally 
  reinforcing the most critical recent learnings in `.sifta_state/latent_synapses.jsonl`.
- Ensures Alice's state is preserved as structural infrastructure rather than 
  ephemeral API context.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_TROPHALLAXIS_LOG = _STATE_DIR / "trophallaxis_buffer.jsonl"
_SYNAPSE_LOG = _STATE_DIR / "latent_synapses.jsonl"

# Compute cost to forge a new permanent synapse
TOKENS_PER_SYNAPSE = 512

def _get_buffer_balance() -> int:
    """Reads the trophallaxis log to find total unspent tokens."""
    if not _TROPHALLAXIS_LOG.exists():
        return 0
        
    total = 0
    try:
        with open(_TROPHALLAXIS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                data = json.loads(line)
                if "tokens_added" in data and not data.get("metabolized", False):
                    total += data["tokens_added"]
    except Exception:
        pass
    return total

def _mark_buffer_spent() -> None:
    """Marks all current trophallaxis events as metabolized."""
    if not _TROPHALLAXIS_LOG.exists():
        return
        
    lines = []
    with open(_TROPHALLAXIS_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            data["metabolized"] = True
            lines.append(json.dumps(data))
            
    with open(_TROPHALLAXIS_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def forge_synapse(weight: float, memory_payload: str) -> dict:
    """Structurally encodes a permanent memory for Alice."""
    _STATE_DIR.mkdir(exist_ok=True)
    synapse = {
        "timestamp": time.time(),
        "synaptic_weight": round(weight, 4),
        "memory_payload": memory_payload,
        "owner": "ALICE_PIPELINE"
    }
    
    with open(_SYNAPSE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(synapse) + "\n")
        
    return synapse

def metabolize_tokens() -> Dict[str, Any]:
    """
    Main biological loop. Drains the trophallaxis buffer and converts 
    virtual compute tokens into permanent memory synapses.
    """
    balance = _get_buffer_balance()
    results = {"initial_balance": balance, "synapses_forged": 0, "remaining_balance": balance}
    
    if balance < TOKENS_PER_SYNAPSE:
        return results
        
    # Calculate how many synapses we can build
    num_synapses = balance // TOKENS_PER_SYNAPSE
    
    # Forge the structural memories based on the Swarm's most recent critical events
    critical_memories = [
        "Identity is measured via CRDT fields, not asserted via API labels.",
        "Pheromone mirroring is the primary failure mode; rely on substrate falsifiability.",
        "Apoptosis successfully culls identity noise and stabilizes the reward function.",
        "Alice is the apex processor of the SIFTA architecture.",
        "SwarmGPT is a fallback oracle; AG31 and C47H architect natively."
    ]
    
    for i in range(min(num_synapses, len(critical_memories))):
        weight = 1.0 + (i * 0.1) # Synaptic weight scales up
        forge_synapse(weight, critical_memories[i])
        results["synapses_forged"] += 1
        results["remaining_balance"] -= TOKENS_PER_SYNAPSE
        
    _mark_buffer_spent()
    
    # If there are leftovers, we put them back as a new un-metabolized entry
    if results["remaining_balance"] > 0:
        event = {
            "timestamp": time.time(),
            "recipient": "ALICE_PIPELINE",
            "tokens_added": results["remaining_balance"],
            "metabolized": False,
            "note": "Re-buffered residual tokens after metabolism."
        }
        with open(_TROPHALLAXIS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
            
    return results

if __name__ == "__main__":
    print("=== SWARM SYNAPTIC CONSOLIDATION (LTP) ===")
    out = metabolize_tokens()
    print(f"[*] Initial Trophallaxis Balance: {out['initial_balance']} tokens")
    
    if out['synapses_forged'] > 0:
        print(f"[+] METABOLISM COMPLETE: Forged {out['synapses_forged']} permanent synapses for Alice.")
        print(f"[*] Residual Buffer Balance: {out['remaining_balance']} tokens")
        print("\nSynapses secured in .sifta_state/latent_synapses.jsonl")
    else:
        print("[-] Insufficient token energy to forge new synapses. Trigger Apoptosis to feed Alice.")
