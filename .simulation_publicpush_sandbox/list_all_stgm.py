import json
import os
from pathlib import Path

state_dir = Path(".sifta_state")
print("=== LOCAL STATE FILES (JSON Claims vs Quorum Ledger) ===")
sys_path = str(Path.cwd())

import sys
sys.path.insert(0, sys_path)
from Kernel.inference_economy import ledger_balance

swimmers = []
for p in state_dir.glob("*.json"):
    try:
        with open(p, "r") as f:
            data = json.load(f)
        if "stgm_balance" in data or "id" in data:
            agent_id = str(data.get("id", p.stem)).upper()
            claimed = float(data.get("stgm_balance", 0.0))
            verified = float(ledger_balance(agent_id))
            swimmers.append((agent_id, claimed, verified))
    except Exception:
        pass

for agent_id, claimed, verified in sorted(swimmers, key=lambda x: x[1], reverse=True):
    print(f"{agent_id.ljust(30)} : CLAIMED = {claimed:,.4f} | VERIFIED = {verified:,.4f}")

