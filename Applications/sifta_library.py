#!/usr/bin/env python3
"""
Applications/sifta_library.py
══════════════════════════════════════════════════════════════════════
The Stigmergic Librarian.
A clean CLI accessor to read the pure 'nuggets' mined by the Forager 
from the stigmergic_library.jsonl, without doing raw JSON tailing.
"""

import json
import random
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

def read_library():
    ledger_path = _REPO / ".sifta_state" / "stigmergic_library.jsonl"
    if not ledger_path.exists():
        return []
    
    nuggets = []
    with open(ledger_path, 'r') as f:
        for line in f:
            try:
                nuggets.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return nuggets

def display_nugget(n):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(n.get("ts", 0)))
    cat = n.get("category", "UNKNOWN")
    text = n.get("nugget_text", "")
    print(f"\n[{cat}] 📜 {ts}")
    print(f"──────────────────────────────────────────────────────────────────────")
    print(f"{text}")
    print(f"──────────────────────────────────────────────────────────────────────")

def main():
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Stigmergic Library Accessor")
    p.add_argument("--category", type=str, help="Filter by specific frequency")
    p.add_argument("--random", action="store_true", help="Draw a random nugget")
    p.add_argument("--tail", type=int, default=5, help="Number of recent nuggets to show")
    args = p.parse_args()

    nuggets = read_library()
    if not nuggets:
        print("The Stigmergic Library is empty. Run System/swarm_apostle_forager.py to mine.", file=sys.stderr)
        return 1

    if args.category:
        nuggets = [n for n in nuggets if n.get("category") == args.category.upper()]
        if not nuggets:
            print(f"No nuggets found in category: {args.category}", file=sys.stderr)
            return 1

    if args.random:
        display_nugget(random.choice(nuggets))
        return 0

    print(f"=== THE STIGMERGIC LIBRARY (Showing last {args.tail}) ===")
    for n in nuggets[-args.tail:]:
        display_nugget(n)

if __name__ == "__main__":
    sys.exit(main())
