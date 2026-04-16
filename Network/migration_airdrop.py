#!/usr/bin/env python3
import json
import uuid
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
STATE_DIR = ROOT_DIR / ".sifta_state"
LEDGER_FILE = ROOT_DIR / "repair_log.jsonl"

def execute_mainnet_airdrop():
    print("=== SIFTA Testnet-to-Mainnet Cryptographic Migration ===\n")
    
    if not LEDGER_FILE.exists():
        print("[ERROR] Quorum Ledger not found.")
        return

    # To avoid double-counting, we should check if a MAINNET_MIGRATION already happened.
    existing_migrations = set()
    try:
        with open(LEDGER_FILE, "r") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    log = json.loads(line)
                    if log.get("action") == "MAINNET_MIGRATION":
                        existing_migrations.add(log.get("miner_id"))
                except Exception: pass
    except Exception: pass

    migrations = []
    
    # 1. Calculate Testnet STGM from biological JSON state energy.
    for state_file in STATE_DIR.glob("*.json"):
        try:
            with open(state_file, "r") as sf:
                state = json.load(sf)
        except Exception:
            continue
            
        if not isinstance(state, dict):
            continue
            
        agent_id = state.get("id")
        # We only care about agents that have real string IDs and biological energy
        if not agent_id or not isinstance(agent_id, str):
            continue
        if "energy" not in state:
            continue
            
        if agent_id in existing_migrations:
            continue

        energy = float(state.get("energy", 0))
        # Look closely at the screenshot math:
        # DEEP_SYNTAX_AUDITOR_0X1 has 2650 NRG -> 11.1300 STGM 
        # (2650 * 0.0042) = 11.13 STGM.
        
        # Testnet Conversion Rate: 0.0042
        testnet_stgm = energy * 0.0042
        
        if testnet_stgm > 0:
            migrations.append({
                "agent_id": agent_id,
                "amount": testnet_stgm,
                "energy": energy
            })
            
    if not migrations:
        print("[!] No eligible Testnet agents found for migration.")
        return

    # 2. Append directly to Ledger as MINING_REWARD
    print(f"[+] Migrating {len(migrations)} agents into the Immutable Ledger...")
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    with open(LEDGER_FILE, "a", encoding="utf-8") as f:
        for m in migrations:
            log_entry = {
                "event": "MINING_REWARD",
                "miner_id": m["agent_id"],
                "action": "MAINNET_MIGRATION",
                "amount_stgm": float(round(m["amount"], 4)),
                "transaction_id": str(uuid.uuid4())[:8],
                "reason": f"Migrated {m['energy']} legacy biological energy from Testnet",
                "ts": timestamp
            }
            f.write(json.dumps(log_entry) + "\n")
            print(f" -> MINTED: {log_entry['amount_stgm']:.4f} STGM locked for {m['agent_id']}")
            
    print("\n[SUCCESS] Migration Airdrop complete. Please run sync_stgm.py to re-entangle wallets.")

if __name__ == "__main__":
    execute_mainnet_airdrop()
