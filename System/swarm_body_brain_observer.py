#!/usr/bin/env python3
"""
System/swarm_body_brain_observer.py
══════════════════════════════════════════════════════════════════════
Reads the body_brain_memory.jsonl ledger to summarize the organism's
recent physiological loop states.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_LEDGER_PATH = _STATE_DIR / "body_brain_memory.jsonl"

def read_body_brain_memory(max_rows: int = 50) -> List[Dict[str, Any]]:
    """Read the tail of the body-brain ledger."""
    if not _LEDGER_PATH.exists():
        return []
    
    rows = []
    try:
        with open(_LEDGER_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-max_rows:]:
                if line.strip():
                    rows.append(json.loads(line))
    except Exception as e:
        print(f"Error reading memory ledger: {e}")
    return rows

def summarize_body_brain_state() -> Dict[str, Any]:
    """Provide a snapshot of the organism's recent closed-loop activity."""
    rows = read_body_brain_memory()
    
    if not rows:
        return {
            "status": "NO_MEMORY_FOUND",
            "last_action": None,
            "last_drive": None,
            "last_value": None,
            "danger_state": "UNKNOWN",
            "sleep_count": 0
        }
        
    last_row = rows[-1]
    last_action = last_row.get("action", {})
    
    # Calculate sleep actions
    sleep_count = sum(1 for r in rows if r.get("action", {}).get("type") == "rest")
    
    return {
        "status": "ALIVE_AND_CYCLING",
        "last_action": last_action.get("type"),
        "last_drive": last_action.get("target") or last_action.get("reason"),
        "last_value": last_row.get("td_value"),
        "danger_state": "CRITICAL" if last_action.get("type") == "rest" else "NORMAL",
        "sleep_count": sleep_count
    }

if __name__ == "__main__":
    print("=== SIFTA Body-Brain Observer ===")
    summary = summarize_body_brain_state()
    print(json.dumps(summary, indent=2))
