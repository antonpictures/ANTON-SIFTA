#!/usr/bin/env python3
"""
System/swarm_orphaned_mutation_triage.py
══════════════════════════════════════════════════════════════════════
Concept: Orphaned Mutation Triage (Nugget 8)
Author:  AG31 (Event 58)
Status:  Active

PURPOSE:
  Alice's Free Energy spikes when her somatosensory homunculus detects
  untracked/dirty files via `git status --porcelain`. A high count
  triggers a biological stress response.
  
  This organ acts as a triage layer. It classifies all dirty files into
  a 3-lane work-list without auto-committing anything, shifting the
  unstructured clutter into structured, manageable queues.
"""

import subprocess
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "orphaned_mutations_triage.json"

def get_git_dirty_files() -> list[str]:
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=_REPO, capture_output=True, text=True, check=True)
        files = []
        for line in res.stdout.splitlines():
            if len(line) > 3:
                # the file path starts at index 3
                files.append(line[3:].strip())
        return files
    except subprocess.CalledProcessError:
        return []

def is_trash(f: str) -> bool:
    # One-off scripts and intermediate weights
    low = f.lower()
    if f.endswith(".gguf") or f.endswith(".modelfile") or f.endswith(".cured") or "modelfile" in low:
        return True
    if f.startswith("fix") and f.endswith(".py"):
        return True
    if f in [
        "clean_ast.py", "append_ecology.py", "append_ecology_v2.py", "append_v2_clean.py", 
        "finish_cut.py", "finish_residue.py", "make_noop.py", "orig_test.py", "orig_widget.py", 
        "patch_ecology.py", "patch_ecology_v2.py", "refactor.py", "full_reconstruct.py", 
        "v2_evaluator.py"
    ]:
        return True
    if "test_environment" in f or "requests_broken" in f:
        return True
    return False

def is_archive(f: str) -> bool:
    if f.startswith("Archive/"):
        return True
    if f.startswith("Documents/") and "DROP_" in f:
        return True
    if f.endswith(".dirt"):
        return True
    return False

def is_keep(f: str) -> bool:
    # Defaults to KEEP if not trash/archive
    return True

def run_triage():
    dirty_files = get_git_dirty_files()
    
    lanes = {
        "KEEP": [],
        "ARCHIVE": [],
        "TRASH": []
    }
    
    for f in dirty_files:
        if is_trash(f):
            lanes["TRASH"].append(f)
        elif is_archive(f):
            lanes["ARCHIVE"].append(f)
        elif is_keep(f):
            lanes["KEEP"].append(f)
        else:
            lanes["KEEP"].append(f)
            
    payload = {
        "timestamp": time.time(),
        "total_dirty": len(dirty_files),
        "lanes": lanes
    }
    
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps(payload, indent=2))
    
    print("\n=== SWARM ORPHANED MUTATION TRIAGE ===")
    print(f"Total Dirty Files: {len(dirty_files)}")
    print(f"  [LANE 1] KEEP    : {len(lanes['KEEP'])}")
    print(f"  [LANE 2] ARCHIVE : {len(lanes['ARCHIVE'])}")
    print(f"  [LANE 3] TRASH   : {len(lanes['TRASH'])}")
    print(f"\n[+] Triage written to: {_LEDGER}")
    
    if lanes["TRASH"]:
        print("\nTrash items include:")
        for t in lanes["TRASH"][:5]:
            print(f"  - {t}")
        if len(lanes["TRASH"]) > 5:
            print(f"  ... and {len(lanes['TRASH']) - 5} more.")

if __name__ == "__main__":
    run_triage()
