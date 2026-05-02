#!/usr/bin/env python3
"""
System/bump_stigmergic_weight.py

Event 85 AG31 Stigmergic Deposit
Bumps the `stigmergic_weight` (pheromone strength) for a given model tag 
after successful hard-task completion. The router favors heavier/slower models 
if their stigmergic weight is high enough to offset their metabolic mass.
"""
from __future__ import annotations

import sys
import json
import time
from pathlib import Path
import argparse

_REPO = Path(__file__).resolve().parent.parent
LEDGER = _REPO / ".sifta_state" / "stigmergic_model_weights.jsonl"

def bump_model_weight(model: str, bump_amount: float = 0.1, trace_id: str = "") -> dict:
    row = {
        "ts": time.time(),
        "event": "STIGMERGIC_WEIGHT_BUMP",
        "model": model,
        "bump_amount": float(bump_amount),
        "trace_id": trace_id,
        "schema": "SIFTA_STIGMERGIC_WEIGHT_BUMP_V1",
    }
    
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    # Ensure jsonl_file_lock if available
    try:
        if str(_REPO) not in sys.path:
            sys.path.insert(0, str(_REPO))
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(LEDGER, json.dumps(row) + "\n")
    except ImportError:
        with open(LEDGER, "a") as f:
            f.write(json.dumps(row) + "\n")
            
    # Deterministically bind metabolic costs and stigmergic rewards
    try:
        if str(_REPO) not in sys.path:
            sys.path.insert(0, str(_REPO))
        from System.metabolic_budget import spend, SpendKind
        spend(
            kind=SpendKind.LOCAL_IDE,
            units=float(bump_amount) * 10.0,
            note=f"Metabolic cost for stigmergic bump: {model}",
            trigger="bump_stigmergic_weight"
        )
    except Exception as e:
        print(f"Warning: Failed to spend metabolic units: {e}")
    
    print(f"Bumped {model} stigmergic weight by {bump_amount}")
    return row

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="The Ollama model tag to bump (e.g. sifta-gemma4-alice:latest)")
    parser.add_argument("--amount", type=float, default=0.1, help="Amount to bump")
    parser.add_argument("--trace-id", default="", help="Optional trace/task ID")
    args = parser.parse_args()
    
    bump_model_weight(args.model, args.amount, args.trace_id)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
