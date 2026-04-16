import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from System.warren_buffett import scan_repair_log
scan = scan_repair_log()
print("=== TRUE QUORUM LEDGER BALANCES (repair_log.jsonl) ===")
for agent, bal in sorted(scan.per_agent_credit.items(), key=lambda x: x[1], reverse=True):
    print(f"{agent.ljust(30)} : {bal:,.4f} STGM")
print("\n=== CASINO VAULT ===")
try:
    import json
    with open(".sifta_state/casino_vault.jsonl", "r") as f:
        vault = 0.0
        for line in f:
            d = json.loads(line)
            vault += float(d.get("casino_delta", 0))
        print(f"Vault Reserves".ljust(30) + f" : {vault:,.4f} STGM")
except Exception as e:
    print("Could not read casino vault:", e)
