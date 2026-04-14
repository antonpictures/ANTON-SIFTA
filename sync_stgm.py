#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent
STATE_DIR = ROOT_DIR / ".sifta_state"
LEDGER_FILE = ROOT_DIR / "repair_log.jsonl"

def sync_wallets():
    print("=== SIFTA STGM Quorum Sync ===")
    
    if not LEDGER_FILE.exists():
        print("[ERROR] Quorum Ledger not found. Cannot sync.")
        return

    # Track mathematically pure balances
    balances = defaultdict(float)

    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                log = json.loads(line)
                event = log.get("event")
                
                if event == "MINING_REWARD":
                    miner = log.get("miner_id")
                    amt = float(log.get("amount_stgm", 0))
                    balances[miner] += amt
                    
                elif event == "FOUNDATION_GRANT":
                    miner = log.get("miner_id")
                    amt = float(log.get("amount_stgm", 0))
                    balances[miner] += amt
                    
                elif event == "INFERENCE_BORROW":
                    borrower = log.get("borrower_id")
                    lender = log.get("lender_ip") # in our single-node simulation, they are upper-cased
                    fee = float(log.get("fee_stgm", 0))
                    
                    balances[borrower] -= fee
                    # We might have lenders that are actual IPs or IDs
                    # To be pure, we sync it exactly as logged.
                    lender_id = str(lender).upper()
                    balances[lender_id] += fee
                    
            except Exception as e:
                pass
                
    STATE_DIR.mkdir(exist_ok=True)
    
    # Write balances back to the wallets
    print("\n[SYNC] Quorum Balances Resolved:")
    for agent_id, bal in balances.items():
        if bal < 0:
            bal = 0.0 # Standard floor
        bal = round(bal, 2)
        print(f" -> {agent_id}: {bal} STGM")
        
        state_file = STATE_DIR / f"{agent_id}.json"
        existing = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as sf:
                    existing = json.load(sf)
            except Exception:
                pass
        
        if not isinstance(existing, dict):
            print(f"Skipping corrupt or list-based state file: {agent_id}")
            continue

        existing["id"] = agent_id
        existing["stgm_balance"] = bal
        
        try:
            with open(state_file, "w") as sf:
                json.dump(existing, sf, indent=2)
        except Exception:
            pass
            
    print("\n=== Wallet Physics Re-Entangled ===")

if __name__ == "__main__":
    sync_wallets()
