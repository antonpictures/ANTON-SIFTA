#!/usr/bin/env python3
import json
import uuid
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
STATE_DIR = ROOT_DIR / ".sifta_state"

def scan_memory_bloat():
    print("=== SIFTA MEMORY DEFRAG SCOUT ===")
    bounties_created = 0
    
    for state_file in STATE_DIR.glob("*.json"):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                
            if not isinstance(state, dict):
                continue
                
            agent_id = state.get("id")
            if not agent_id:
                continue

            # Analyze memory bloat
            raw_mem = state.get("raw", "")
            scars_len = len(state.get("hash_chain", []))
            
            # Simple threshold for defragmentation (simulating an exhausted state)
            # If they have enormous raw string blobs exceeding 500 characters
            if len(raw_mem) > 200 or scars_len > 15:
                # Package a bounty
                bounty_id = str(uuid.uuid4())[:12]
                stgm_reward = round((len(raw_mem) + scars_len * 10) * 0.015, 2)
                stgm_reward = max(stgm_reward, 15.00) # Base reward
                
                bounty_file = ROOT_DIR / f"BOUNTY_{bounty_id}.scar"
                
                payload = f"""[WORMHOLE MARKET BOUNTY]
PRIORITY: ALPHA
BOUNTY_ID: {bounty_id}
SOURCE_NODE: {agent_id}
ESTIMATED_REWARD: {stgm_reward} STGM

[JOB DESCRIPTION]
The agent '{agent_id}' has suffered from acute memory fragmentation or payload bloat.
Raw Fragment Length: {len(raw_mem)} bytes
Scars Accumulated: {scars_len}

[INFERENCE TASK]
Execute target_agent on this payload. Compress the raw memory into a highly coherent summary string. Clear the resolved hash chain. Collect the STGM reward from the Quorum ledger upon successful inference completion.
"""
                bounty_file.write_text(payload, encoding="utf-8")
                print(f"[X] BLOAT DETECTED on {agent_id}. Generated Bounty: {bounty_id} | Reward: {stgm_reward} STGM")
                bounties_created += 1

        except Exception as e:
            continue
            
    print(f"\n[SUCCESS] Scout scan complete. {bounties_created} open jobs pushed to Wormhole Market.")

if __name__ == "__main__":
    scan_memory_bloat()
