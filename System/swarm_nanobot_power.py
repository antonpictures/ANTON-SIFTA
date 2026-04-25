#!/usr/bin/env python3
"""
System/swarm_nanobot_power.py
Nanobot power-harvest ledger -> pheromone.
Nanobots periodically report harvested microwatts; the OS
aggregates and exposes a 'nanobot power budget' pheromone.
"""

import json
import pathlib
from datetime import datetime

LEDGER = pathlib.Path(".sifta_state/nanobot_power.jsonl")
PHEROMONE = "stig_nanobot_power"

def record(node_id: str, microwatts: float) -> None:
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "node": node_id,
        "microwatts": microwatts,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        # Simple linear scaling – can be replaced by a more sophisticated model.
        intensity = microwatts / 1_000_000  # convert µW → relative units
        PHEROMONE_FIELD.deposit(PHEROMONE, intensity=intensity)
    except Exception:
        pass

def poll_power_state() -> None:
    """
    Reads genuine macOS power metric to proxy physical energy states.
    For demonstration, reads remaining battery capacity via pmset.
    """
    import subprocess
    import re
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"], text=True)
        # Looking for something like: '100%; charging' or '85%; discharging'
        match = re.search(r"(\d+)%;", out)
        if match:
            percent = float(match.group(1))
            # Convert percentage 0-100 to simulated microwatts (0-1,000,000) for nanobots
            microwatts = percent * 10000.0
            record("macOS_battery_proxy", microwatts)
    except Exception as e:
        print(f"Power State Error: {e}")

if __name__ == "__main__":
    poll_power_state()
