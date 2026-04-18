import sys
from pathlib import Path
import json

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from inference_economy import ledger_balance

# agents to check
agents_to_check = ["M1THER", "ANTIALICE", "HERMES", "SIFTA_QUEEN", "M1SIFTA_BODY", "M5SIFTA_BODY", "ANTIGRAVITY_IDE"]

for agent in agents_to_check:
    true_balance = ledger_balance(agent)
    print(f"{agent} LEDGER BALANCE: {true_balance}")

