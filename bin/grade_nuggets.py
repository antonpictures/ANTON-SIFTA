#!/usr/bin/env python3
"""
bin/grade_nuggets.py
══════════════════════════════════════════════════════════════════════
Stigmergic RL: Continual Learning Grading Interface
Allows the Architect to grade nuggets (+1 or -1) to shape Alice's foraging.
"""

import json
import os
from pathlib import Path

# Fix path to point to .sifta_state correctly
_REPO = Path(__file__).resolve().parent.parent
LIBRARY_PATH = _REPO / ".sifta_state" / "stigmergic_library.jsonl"

def main():
    if not LIBRARY_PATH.exists():
        print(f"No stigmergic library found at {LIBRARY_PATH}")
        return
        
    with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    updated = []
    graded_count = 0
    
    for line in lines:
        if not line.strip(): continue
        try:
            nugget = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
            
        if "reward" not in nugget:
            os.system('clear')
            print("=== UNGRADED NUGGET ===")
            print(f"Domain : {nugget.get('domain', 'UNKNOWN')}")
            print(f"Q      : {nugget.get('question', 'Manual Injection')}")
            print(f"Source : {nugget.get('source_api', 'UNKNOWN')}")
            print(f"\nNugget : {nugget.get('nugget_text', '')}\n")
            print("─────────────────────────────────────────────────────")
            ans = input("Grade this yield: [N]ugget (+1) / [T]rash (-1) / [S]kip: ").strip().lower()
            if ans == 'n':
                nugget["reward"] = 1.0
                graded_count += 1
            elif ans == 't':
                nugget["reward"] = -1.0
                graded_count += 1
            
            updated.append(json.dumps(nugget, ensure_ascii=False) + "\n")
        else:
            updated.append(line)
            
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        f.writelines(updated)
        
    os.system('clear')
    print(f"\n[+] Stigmergic Grading complete. {graded_count} nuggets methylated.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Grading cleanly aborted.")
