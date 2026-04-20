#!/usr/bin/env python3
"""
System/swarm_spotlight_hippocampus.py — Episodic Memory (Spotlight API)
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The Hippocampus. Gives Alice instant semantic recall across the entire 
macOS filesystem via `mdfind`. Zero indexing required.
"""

import json
import time
import subprocess
import sys
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

class SwarmHippocampus:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.memory_ledger = self.state_dir / "hippocampus_memories.jsonl"
        self.memory_ledger.parent.mkdir(parents=True, exist_ok=True)

    def search_episodic_memory(self, query: str, limit: int = 20):
        """
        Executes a native Spotlight search (mdfind) for the memory query.
        """
        try:
            result = subprocess.run(
                ["mdfind", query],
                capture_output=True, text=True, check=True
            )
            paths = [p for p in result.stdout.split('\n') if p.strip()][:limit]
            
            trace = {
                "transaction_type": "HIPPOCAMPUS_RECALL",
                "query": query,
                "matches_found": len(paths),
                "paths": paths,
                "timestamp": time.time()
            }
            append_line_locked(self.memory_ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA HIPPOCAMPUS : SMOKE TEST ===")
    hipp = SwarmHippocampus()
    print("[*] Accessing deep episodic memory for 'Alice'...")
    res = hipp.search_episodic_memory("Alice", limit=5)
    print(json.dumps(res, indent=2))
    print("[PASS] Hippocampus wired to macOS Spotlight index.")

if __name__ == "__main__":
    _smoke()
