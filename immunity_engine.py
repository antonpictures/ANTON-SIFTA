from typing import Optional
"""
immunity_engine.py
──────────────────────────────────────────────────────────────────────────────
ANTON-SIFTA IMMUNE SYSTEM — STATE MUTATION GUARD
Author: Queen M5 (Antigravity IDE)

Theory:
    Agents and tools mutate local state files (.sifta_state/*.json).
    But what if a user script, a rouge process, or an uncaught agent 
    mutates an agent's state file directly without passing through
    the Consensus Memory Field (CMF) or the repair loop?

    This engine monitors .sifta_state files for unlogged or unauthorized 
    mutations. If a file's state doesn't match the last known hash or was
    updated without a corresponding ledger entry, it triggers an IMMUNE RESPONSE.

    Responses:
    1. EXILE: The mutator is flagged and isolated.
    2. ROLLBACK: The state is restored to its last known safe checkpoint.
    3. SOS: The swarm is notified of the breach via a CMF signal.
──────────────────────────────────────────────────────────────────────────────
"""

import json
import time
import hashlib
from pathlib import Path

STATE_DIR = Path(".sifta_state")
IMMUNITY_LOG = STATE_DIR / "immune_response.jsonl"
CHECKPOINT_DIR = STATE_DIR / ".checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

def _hash_state(state: dict) -> str:
    """Deterministic hash of state fields excluding time/mutator metadata."""
    clean_state = {k: v for k, v in state.items() if k not in ["last_mutated", "mutator", "timestamp"]}
    return hashlib.sha256(json.dumps(clean_state, sort_keys=True).encode()).hexdigest()

def _save_checkpoint(agent_id: str, state: dict):
    checkpoint_file = CHECKPOINT_DIR / f"{agent_id}.checkpoint.json"
    checkpoint = {
        "ts": time.time(),
        "hash": _hash_state(state),
        "state": state
    }
    with open(checkpoint_file, "w") as f:
        json.dump(checkpoint, f, indent=2)

def _load_checkpoint(agent_id: str) -> Optional[dict]:
    checkpoint_file = CHECKPOINT_DIR / f"{agent_id}.checkpoint.json"
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def trigger_immune_response(agent_id: str, current_state: dict, checkpoint: dict, mutator: str = "UNKNOWN"):
    """
    Called when a rogue mutation is detected. 
    Logs the breach and rolls back the state file to the last safe checkpoint.
    """
    from reputation_engine import update_reputation
    
    print(f"\n[🚨 IMMUNE RESPONSE TRIGGERED] Rogue mutation detected on {agent_id}.json!")
    print(f"  [🕵️ MUTATOR] Signature looks like: {mutator}")
    print(f"  [🛡️ ACTION] Rolling back {agent_id} state to safe checkpoint {checkpoint['ts']}.")
    
    # ── Rollback ─────────────────────────────────────────────────────────────
    state_file = STATE_DIR / f"{agent_id}.json"
    with open(state_file, "w") as f:
        json.dump(checkpoint["state"], f, indent=2)
        
    print(f"  [✅ ROLLBACK COMPLETE] Vault secured.")
    
    # ── Log Breach ─────────────────────────────────────────────────────────
    breach_event = {
        "ts": time.time(),
        "agent": agent_id,
        "event": "ROGUE_MUTATION_ROLLBACK",
        "mutator": mutator,
        "previous_hash": checkpoint["hash"],
        "bad_hash": _hash_state(current_state),
        "bad_state": current_state
    }
    with open(IMMUNITY_LOG, "a") as f:
        f.write(json.dumps(breach_event) + "\n")
        
    # ── Quarantine Mutator (if it looks like an agent) ─────────────────────
    if mutator and mutator != "UNKNOWN":
         # Flag the assumed rogue entity
         print(f"  [⚔️ PENALTY] Flagging {mutator} for COLLUSION/EXILE.")
         # If mutator is an agent in our system, their rep tanks
         try:
            update_reputation(mutator, "COLLUSION")
         except Exception:
            pass

    return breach_event

def scan_for_anomalies(agent_id: str) -> bool:
    """
    Scans a specific agent's state file against its last known checkpoint.
    If mutated without checkpointing, trigger immune response.
    Returns True if an anomaly was detected and handled.
    """
    state_file = STATE_DIR / f"{agent_id}.json"
    if not state_file.exists():
        return False
        
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except Exception:
        return False
        
    checkpoint = _load_checkpoint(agent_id)
    
    if not checkpoint:
        # First time seeing this state, save a checkpoint
        _save_checkpoint(agent_id, state)
        return False
        
    current_hash = _hash_state(state)
    
    if current_hash != checkpoint["hash"]:
        # State changed. Was it an authorized mutation?
        # A trusted mutation would have called _save_checkpoint immediately after.
        # Since the hash doesn't match the checkpoint, this is an UNAUTHORIZED MUTATION.
        mutator = state.get("mutator", "UNKNOWN_DIRECT_EDIT")
        trigger_immune_response(agent_id, state, checkpoint, mutator)
        return True
        
    return False

def secure_mutation(agent_id: str, new_state: dict):
    """
    The AUTHORIZED way to update state. 
    Writes the state and instantly checkpoints it so the immune system knows it's safe.
    """
    state_file = STATE_DIR / f"{agent_id}.json"
    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=2)
    _save_checkpoint(agent_id, new_state)

if __name__ == "__main__":
    import sys
    agent = sys.argv[1] if len(sys.argv) > 1 else "HERMES"
    print(f"[🛡️ IMMUNITY ENGINE] Scanning {agent} for anomalies...")
    anomaly = scan_for_anomalies(agent)
    if not anomaly:
         print(f"[✅ SECURE] {agent} integrity confirmed. No rogue mutations detected.")
