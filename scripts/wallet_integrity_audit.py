#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path
from difflib import SequenceMatcher

# Add parent to path so we can import Kernel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Kernel.inference_economy import ledger_balance, _ledger_row_cryptographically_valid
from Kernel.inference_economy import LOG_PATH as LEDGER_PATH

STATE_DIR = Path(".sifta_state")

def similar(a, b):
    return SequenceMatcher(None, a.upper(), b.upper()).ratio()

def main():
    print("Starting Wallet Integrity Audit (Cut 0.1)...")
    
    # 1. Re-verify ledger rows & calculate total global STGM
    print(f"Verifying ledger rows in {LEDGER_PATH}...")
    total_mints = 0.0
    total_burns = 0.0
    invalid_rows = 0
    row_count = 0
    
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                row_count += 1
                try:
                    entry = json.loads(line)
                except:
                    invalid_rows += 1
                    continue
                    
                if not _ledger_row_cryptographically_valid(entry):
                    invalid_rows += 1
                    continue
                    
                event = entry.get("event", "")
                tx_type = entry.get("tx_type", "")
                
                # Dialect A
                if event in ("MINING_REWARD", "FOUNDATION_GRANT"):
                    total_mints += float(entry.get("amount_stgm", 0.0))
                elif event == "INFERENCE_BORROW":
                    # Fee transfer doesn't change global net total
                    pass
                elif event == "UTILITY_MINT":
                    total_mints += float(entry.get("amount", 0.0))
                # Dialect B
                elif tx_type == "STGM_MINT":
                    total_mints += float(entry.get("amount_stgm", 0.0))
                elif tx_type == "STGM_SPEND":
                    total_burns += float(entry.get("amount_stgm", 0.0))

    net_stgm = total_mints - total_burns
    print(f"Processed {row_count} rows. Invalid signatures: {invalid_rows}")
    print(f"Total Minted: {total_mints:.3f} | Total Burned: {total_burns:.3f}")
    print(f"Global Net STGM: {net_stgm:.3f}")
    if net_stgm < 0:
        print("CRITICAL: Global Net STGM is negative!")
        sys.exit(1)

    # 2. Inspect state files for drift, unattributed bags, and aliases
    drift_issues = []
    unattributed_bags = []
    agent_balances = {}
    
    for f in STATE_DIR.glob("*.json"):
        if f.is_file():
            try:
                data = json.loads(f.read_text())
                if isinstance(data, dict):
                    # Only check files that have a stgm_balance or are obviously agents
                    if "stgm_balance" in data or "energy" in data or "homeworld_serial" in data:
                        agent_id = f.stem
                        cache_bal = float(data.get("stgm_balance", 0.0))
                        canonical_bal = ledger_balance(agent_id)
                        
                        agent_balances[agent_id] = {
                            "cache": cache_bal,
                            "canonical": canonical_bal,
                            "homeworld_serial": data.get("homeworld_serial")
                        }
                        
                        if abs(cache_bal - canonical_bal) > 0.001:
                            drift_issues.append((agent_id, cache_bal, canonical_bal))
                            
                        if not data.get("homeworld_serial") and canonical_bal > 0:
                            unattributed_bags.append((agent_id, canonical_bal))
            except Exception:
                pass

    print("\n--- Drift Report ---")
    if not drift_issues:
        print("✅ No drift detected. Cache matches ledger exactly.")
    else:
        for agent, cache, can in drift_issues:
            print(f"⚠️ DRIFT: {agent} | Cache: {cache:.3f} | Canonical: {can:.3f}")

    print("\n--- Unattributed Bags Report ---")
    if not unattributed_bags:
        print("✅ No unattributed STGM bags found.")
    else:
        total_limbo = sum(b for a, b in unattributed_bags)
        print(f"❌ Found {len(unattributed_bags)} agents with no homeworld_serial holding {total_limbo:.3f} STGM!")
        for agent, bal in sorted(unattributed_bags, key=lambda x: -x[1]):
            print(f"   {agent}: {bal:.3f} STGM")

    print("\n--- Alias Cluster Report ---")
    aliases = []
    agents = list(agent_balances.keys())
    for i in range(len(agents)):
        for j in range(i+1, len(agents)):
            a, b = agents[i], agents[j]
            # Replace common suffixes for comparison
            a_clean = a.replace("_31c823", "").replace("_M5", "").replace("SIFTA_", "").replace("_BODY", "")
            b_clean = b.replace("_31c823", "").replace("_M5", "").replace("SIFTA_", "").replace("_BODY", "")
            if a_clean == b_clean or similar(a_clean, b_clean) > 0.8:
                aliases.append((a, b))
    
    if aliases:
        print("⚠️ Potential Alias Clusters:")
        for a, b in aliases:
            print(f"   {a} ↔ {b}")
            
    # Write Receipt
    ts = int(time.time())
    receipt_file = STATE_DIR / f"wallet_audit_{ts}.json"
    receipt = {
        "timestamp": ts,
        "global_net_stgm": net_stgm,
        "invalid_rows": invalid_rows,
        "drift_count": len(drift_issues),
        "unattributed_count": len(unattributed_bags),
        "unattributed_total_stgm": sum(b for a, b in unattributed_bags)
    }
    receipt_file.write_text(json.dumps(receipt, indent=2))
    print(f"\nAudit receipt written to {receipt_file}")
    
    # Append event to ledger (if you want to implement this directly, we write to repair_log.jsonl)
    audit_event = {
        "ts": ts,
        "event": "wallet_audit",
        "details": receipt
    }
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(audit_event) + "\n")
        
    if drift_issues or unattributed_bags:
        print("\n❌ AUDIT FAILED: Wallet hardening required before federation can be enabled.")
        sys.exit(1)
    else:
        print("\n✅ AUDIT PASSED: Safe to proceed to federation.")
        sys.exit(0)

if __name__ == "__main__":
    main()
