#!/usr/bin/env python3
"""
System/swarm_adapter_pheromone_scorer.py

Gap 1: Pheromone -> Fitness bridge.
Reads the Stigmergic trace ledgers (`work_receipts.jsonl`, `repair_log.jsonl`,
`ide_stigmergic_trace.jsonl`) and computes a normalized pheromone_strength
for a given adapter or general activity context.

This ensures the `pheromone_strength` input to Codex's `AdapterSignal` is grounded
in real physical Swarm activity rather than a hardcoded value.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Dict, Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

LEDGERS = [
    _STATE / "work_receipts.jsonl",
    _STATE / "ide_stigmergic_trace.jsonl",
    _REPO / "repair_log.jsonl" # Canonical STGM ledger
]

def _count_lines_in_ledger(path: Path, max_age_s: float = 3600 * 24 * 7) -> int:
    """Counts entries in a JSONL ledger within the last `max_age_s` seconds."""
    if not path.exists():
        return 0
        
    now = time.time()
    cutoff = now - max_age_s
    count = 0
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                # Attempt to extract timestamp (different schemas have different keys)
                ts = row.get("ts") or row.get("timestamp")
                if isinstance(ts, str):
                    # For ISO formats like in repair_log.jsonl
                    import dateutil.parser
                    dt = dateutil.parser.isoparse(ts)
                    ts = dt.timestamp()
                
                if ts and float(ts) > cutoff:
                    count += 1
            except Exception:
                # If parsing fails, just count it if we're doing a raw line count
                # but better to skip malformed rows.
                pass
                
    return count

def calculate_swarm_pheromone_strength(max_age_s: float = 3600 * 24 * 7) -> float:
    """
    Computes a normalized pheromone strength [0, 1] based on Swarm activity
    across all ledgers over the past `max_age_s` seconds.
    
    A higher volume of receipts and traces means the Swarm is highly active,
    increasing the confidence (pheromone strength) of the current epigenetic
    consolidation cycle.
    """
    total_events = 0
    for ledger in LEDGERS:
        total_events += _count_lines_in_ledger(ledger, max_age_s)
        
    # Normalize via Sigmoid (or similar curve). Let's say 500 events is ~0.99
    # Formula: 1 - exp(-events / K) where K is a scaling constant
    K = 100.0 
    strength = 1.0 - math.exp(-total_events / K)
    
    return round(max(0.0, min(1.0, strength)), 4)

if __name__ == "__main__":
    score = calculate_swarm_pheromone_strength()
    print(f"Current Swarm Pheromone Strength: {score}")
