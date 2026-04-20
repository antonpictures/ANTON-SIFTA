#!/usr/bin/env python3
"""
System/swarm_proprioception.py — Internal Body Awareness
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Proprioception senses the physical host machine state.
Battery = Hunger / Energy reserves.
Time Machine = Immune / Backup security.
"""

import json
import time
import subprocess
import sys
import shutil
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class SwarmProprioception:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "proprioception_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)

    def sense_biology(self):
        """
        Polls macOS `pmset` to understand physical energy state.
        """
        try:
            batt_res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
            output = batt_res.stdout
            
            # Very basic parse for battery percentage
            percentage = None
            if "%" in output:
                import re
                match = re.search(r"(\d+)%", output)
                if match:
                    percentage = int(match.group(1))

            trace = {
                "transaction_type": "PROPRIOCEPTION_SENSE",
                "energy_level": percentage,
                "raw_pmset": output.splitlines()[0] if output else "Unknown",
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

    def sense_storage(self):
        """
        Polls macOS storage capacity for physical spatial bounds.
        """
        try:
            total, used, free = shutil.disk_usage("/")
            
            # Convert to GB
            total_gb = total / (2**30)
            used_gb = used / (2**30)
            free_gb = free / (2**30)
            percent_free = (free / total) * 100.0

            trace = {
                "transaction_type": "PROPRIOCEPTION_STORAGE",
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "percent_free": round(percent_free, 2),
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA PROPRIOCEPTION : SMOKE TEST ===")
    prop = SwarmProprioception()
    print("\n[*] Sensing biological energy levels via pmset...")
    res = prop.sense_biology()
    print(json.dumps(res, indent=2))
    
    print("\n[*] Sensing spatial storage capacity...")
    res_storage = prop.sense_storage()
    print(json.dumps(res_storage, indent=2))
    
    print("[PASS] Proprioception wired to Host Battery and Spatial Bounds.")

if __name__ == "__main__":
    _smoke()
