import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from Applications.sifta_finance import load_agents

agents = load_agents()
total_portfolio_agents = [a for a in agents if a.get("id") != "CASINO_VAULT"]
total = sum(float(a.get("stgm_balance") or 0) for a in total_portfolio_agents)

print(f"Total Portfolio: {total}")
for a in agents:
    print(f"{a['id'].ljust(20)}: {a['stgm_balance']}  (Serial: {a['homeworld_serial']})")

