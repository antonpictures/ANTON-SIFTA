import os
import sys
import json
import logging
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_PATH = REPO_ROOT / "repair_log.jsonl"

try:
    from inference_economy import ledger_balance
except ImportError as e:
    print(f"Failed to import inference_economy: {e}")
    sys.exit(1)

def fix_agent_balance(agent_id):
    """Aligns the JSON state file with the cryptographically verified ledger."""
    state_file = STATE_DIR / f"{agent_id}.json"
    
    if not state_file.exists():
        print(f"No state file found for {agent_id}. Skipping.")
        return

    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except Exception as e:
        print(f"Failed to read {state_file}: {e}")
        return

    # Calculate true balance from the ledger, ignoring invalid Ed25519 signatures
    true_balance = ledger_balance(agent_id)
    current_json_balance = state.get("stgm_balance", 0.0)

    if current_json_balance == true_balance:
        print(f"{agent_id} is already synchronized. Balance: {true_balance}")
        return

    print(f"Aligning {agent_id}: JSON {current_json_balance} -> LEDGER {true_balance}")
    
    state["stgm_balance"] = true_balance
    
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Failed to write to {state_file}: {e}")

def main():
    print("=== Aligning M1THER Node Finances with Cryptographic Truth ===")
    
    # Core locally hosted agents on M1
    agents_to_check = [
        "M1THER",
        "ANTIALICE",
        "HERMES",
        "IMPERIAL",
        "SIFTA_QUEEN",
        "M1SIFTA_BODY",
        "ANTIGRAVITY_IDE"
    ]
    
    for agent in agents_to_check:
        fix_agent_balance(agent)

if __name__ == "__main__":
    main()
