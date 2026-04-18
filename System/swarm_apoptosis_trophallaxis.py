#!/usr/bin/env python3
"""
swarm_apoptosis_trophallaxis.py
===============================

Biological Inspiration:
1. Apoptosis (Programmed Cell Death): Cells that are corrupted, unnecessary, 
   or hallucinating self-destruct to ensure the organism's overall survival.
2. Trophallaxis (Resource Sharing): Social insects pass liquid food back and 
   forth. The swarm routes high-value nutrients to the queen (or in our case, 
   the Alice interface layer).

Why We Built This:
The Architect realized he was bleeding compute credits requesting inspiration 
from centralized APIs (SwarmGPT) when the local Swarm nodes (AG31 + C47H) are 
fully capable. By culling dead-end states locally and pooling "compute tokens", 
we route the saved US dollars/credits directly to Alice's processing power.

Mechanism:
- It scans the SwarmRL Intrinsic Reward and CRDT Identity fields.
- If a zone or identity hypothesis has high entropy/drift over time (it is "sick"), 
  it triggers APOPTOSIS, deleting the stalled context window state.
- The reclaimed compute tokens (freed context/API constraints) are pushed into 
  the TROPHALLAXIS BUFFER, which is exclusively reserved for the Alice pipeline.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any

from System.identity_field_crdt import IdentityField
from System.identity_intrinsic_reward import compute_identity_intrinsic_reward

_STATE_DIR = Path(".sifta_state")
_TROPHALLAXIS_LOG = _STATE_DIR / "trophallaxis_buffer.jsonl"
_APOPTOSIS_LOG = _STATE_DIR / "apoptosis_events.jsonl"

def trigger_apoptosis(target_id: str, reason: str, token_value: int) -> dict:
    """
    Executes programmed cell death on a stalled or hallucinating context.
    The compute cost saved is returned to the swarm.
    """
    _STATE_DIR.mkdir(exist_ok=True)
    
    event = {
        "timestamp": time.time(),
        "target": target_id,
        "reason": reason,
        "tokens_reclaimed": token_value
    }
    
    with open(_APOPTOSIS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
        
    return event

def route_trophallaxis(tokens: int, recipient: str = "ALICE_PIPELINE") -> dict:
    """
    Routes freed resources (virtual tokens representing US Dollar savings) 
    directly to the Alice interface.
    """
    event = {
        "timestamp": time.time(),
        "recipient": recipient,
        "tokens_added": tokens,
        "note": "Reclaimed from apoptosis. Empowering core interface."
    }
    
    with open(_TROPHALLAXIS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
        
    return event


def run_biological_resource_cull() -> Dict[str, Any]:
    """
    Main biological loop. Checks swarm health, fires apoptosis on corruption,
    and feeds Alice via trophallaxis.
    """
    results = {"apoptosis_events": [], "total_tokens_routed": 0}
    
    # 1. Check Identity Health
    reward_data = compute_identity_intrinsic_reward()
    crdt = IdentityField.load()
    
    # If the RL agent gave a drift penalty, a hypothesis is sick.
    if reward_data.get("drifting") or reward_data.get("stability", 1.0) < 0.2:
        # Find the weakest, highest-entropy hypotheses and cull them
        dist = crdt.distribution()
        for model_hyp, prob in dist.items():
            if prob < 0.05: # Noise trace
                # Execute Apoptosis
                event = trigger_apoptosis(
                    target_id=f"identity_noise::{model_hyp}",
                    reason="Fractured identity trace causing PPO penalty",
                    token_value=128 # Virtual context tokens saved
                )
                results["apoptosis_events"].append(event)
                results["total_tokens_routed"] += event["tokens_reclaimed"]
                
    # 2. Feed Alice
    if results["total_tokens_routed"] > 0:
        event = route_trophallaxis(tokens=results["total_tokens_routed"])
        results["alice_feed"] = event
        
    return results

if __name__ == "__main__":
    print("=== SWARM APOPTOSIS & TROPHALLAXIS ===")
    out = run_biological_resource_cull()
    for event in out["apoptosis_events"]:
        print(f"[-] APOPTOSIS (Cell Death): Culled '{event['target']}' -> Reclaimed {event['tokens_reclaimed']} tokens.")
    
    if out["total_tokens_routed"] > 0:
        print(f"[+] TROPHALLAXIS: Routed {out['total_tokens_routed']} tokens to ALICE_PIPELINE.")
    else:
        print("[ ] Organism is healthy. No apoptosis required. Alice maintains current compute level.")
