import json
from pathlib import Path
from body_state import SwarmBody

STATE_DIR = Path(".sifta_state")
QUARANTINE_DIR = Path("QUARANTINE")

def load_agent_state(agent_id: str) -> dict:
    file_path = STATE_DIR / f"{agent_id.upper()}.json"
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def bury(old_state: dict, cause: str):
    """Write a formal retirement record to the QUARANTINE without destroying history."""
    QUARANTINE_DIR.mkdir(exist_ok=True)
    agent_id = old_state.get("id", "UNKNOWN")
    seq = old_state.get("seq", 0)
    
    dead_path = QUARANTINE_DIR / f"{agent_id}-SEQ{seq:03d}.quarantined"
    epitaph = (
        f"# QUARANTINE — {agent_id} SEQ[{seq:03d}]\n"
        f"CAUSE: {cause}\n"
        f"FINAL_ENERGY: {old_state.get('energy', 0)}\n"
        f"LAST_BODY: {old_state.get('raw', '')}\n"
    )
    dead_path.write_text(epitaph, encoding="utf-8")
    print(f"  [📜 LEDGER] Retirement recorded at {dead_path.name}")

def safe_rename_check(old_id: str) -> bool:
    """Block deletion if agent has active history."""
    state = load_agent_state(old_id)
    if state and state.get("seq", 0) > 0:
        print(f"  [BLOCK] {old_id} has {state['seq']} sequence swims in its hash chain.")
        print(f"  You must run retire_and_succeed() to enact a formal biological transfer.")
        return False
    return True

def retire_and_succeed(old_id: str, new_id: str, hardware_origin: str = "SWARM_MATRIX"):
    old_id = old_id.upper()
    new_id = new_id.upper()
    
    old_state = load_agent_state(old_id)
    
    if not old_state:
        print(f"[FATAL] {old_id} does not exist. Cannot commence succession.")
        return
        
    print(f"\n--- INITIATING SUCCESSION CEREMONY: {old_id} ➔ {new_id} ---")
    
    # 1. Bury the old agent formally
    bury(old_state, cause=f"RETIRED — succeeded by {new_id}")
    
    # Unlink the physical file so the old private key is formally destroyed
    old_file = STATE_DIR / f"{old_id}.json"
    old_file.unlink()
    print(f"  [WIPED] {old_id}'s original private key discarded.")
    
    # 2. Rebirth the successor
    seal = f"ARCHITECT_SEAL_{new_id}"
    new_agent = SwarmBody(new_id, architect_seal=seal)
    
    # 3. Lineage Transfer: The new agent inherits the sequence swim count
    # Note: We manually insert this into the json after generation, 
    # but the founding body hash will permanently record the SUCCESSION origin
    
    print(f"  [🧬] Etching lineage into new Ed25519 genesis block...")
    new_agent.generate_body(
        origin="QUARANTINE",
        destination="SWARM_MATRIX",
        payload=f"SUCCESSION_FROM_{old_id}",
        action_type="SUCCESSION",
        style="NOMINAL",
        energy=100
    )
    
    # Port over the sequence history logically 
    new_state = load_agent_state(new_id)
    new_state["seq"] = old_state.get("seq", 0) + 1
    
    with open(STATE_DIR / f"{new_id}.json", "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)
        
    print(f"--- SUCCESSION COMPLETE ---")
    print(f"{new_id} is now alive at SEQ {new_state['seq']}.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        retire_and_succeed(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "check":
        print("Usage: python succession_protocol.py [OLD_ID] [NEW_ID]")
    else:
        print("Usage: python succession_protocol.py [OLD_ID] [NEW_ID]")
