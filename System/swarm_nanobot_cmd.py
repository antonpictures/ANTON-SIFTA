#!/usr/bin/env python3
"""
System/swarm_nanobot_cmd.py
Canonical nanobot command ledger.
All nanobot commands are written as JSON lines to
.sifta_state/nanobot_cmd.jsonl and deposited as a pheromone.
"""

import json
import pathlib
import time
from datetime import datetime

LEDGER = pathlib.Path(".sifta_state/nanobot_cmd.jsonl")
PHEROMONE = "stig_nanobot_cmd"

def _write_entry(cmd: dict) -> None:
    """Append a command entry with a timestamp."""
    entry = {
        "ts": int(time.time()),
        "cmd": cmd,
        "writer": "swarm_nanobot_cmd"
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def issue(command: str, payload: dict | None = None) -> None:
    """
    Public API – called by any organ or external nanobot.
    Example:
        issue("move", {"target": [1.2, -0.4, 0.0]})
    """
    payload = payload or {}
    _write_entry({"command": command, "payload": payload})
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit(PHEROMONE, intensity=1.0)
    except Exception:
        pass

if __name__ == "__main__":
    # Demo: issue a simple “ping” command
    issue("ping", {"msg": "hello nanobot swarm"})
