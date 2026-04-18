import os
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from Kernel.inference_economy import ledger_balance

state_dir = REPO_ROOT / ".sifta_state"
print("=== SIFTA TRUE LEDGER BALANCE AUDIT ===")
print("Reconciling JSON state with cryptographic ledger truth...\n")

import time
from System.jsonl_file_lock import rewrite_text_locked
from System.ledger_append import append_jsonl_line

total_stgm = 0.0

for file_path in state_dir.glob("*.json"):
    # Skip non-agent system jsons
    if file_path.name in [
        "app_fitness.json", "chorus_consent.json", "circadian_m1.json",
        "circadian_m5.json", "fs_pheromone.json", "identity_stats.json",
        "identity_topology.json", "intelligence_settings.json",
        "m1queen_identity_anchor.json", "marketplace_listings.json",
        "node_pki_registry.json", "owner_genesis.json", "physical_registry.json",
        "scheduler_m5.json", "state_bus.json", "territory_manifest.json",
        "wm_pheromone.json", "warren_snapshot.json"
    ]:
        continue

    agent_id = file_path.stem
    
    try:
        true_balance = ledger_balance(agent_id)
        
        with open(file_path, "r") as f:
            state = json.load(f)
            
        json_balance = state.get("stgm_balance", 0.0)
        
        if json_balance != true_balance:
            print(f"⚠️  RECONCILED: {agent_id} (Fake JSON: {json_balance} STGM -> True Ledger: {true_balance} STGM)")
            state["stgm_balance"] = true_balance
            rewrite_text_locked(file_path, json.dumps(state, indent=2) + "\n")
            
            audit_entry = {
                "ts": time.time(),
                "agent_id": agent_id,
                "drift_before": json_balance,
                "drift_after": true_balance,
                "file": str(file_path.name)
            }
            append_jsonl_line(state_dir / "reconcile_audit.jsonl", audit_entry)
                
        if true_balance > 0:
            print(f"✅ HOLDER: {agent_id.ljust(25)} | {true_balance} STGM")
            total_stgm += true_balance
            
    except Exception as e:
        # Some JSON files might not be valid agents; ignore parsing errors
        pass

print(f"\n--- Total Cryptographically Verified Swarm Circulation: {total_stgm} STGM ---")
