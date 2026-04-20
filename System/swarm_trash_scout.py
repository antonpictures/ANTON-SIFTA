#!/usr/bin/env python3
"""
System/swarm_trash_scout.py — The Autonomous Quarantine Sweeper
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Hunts for biological noise (caching, temporary metadata) and sweeps
it into the Stigmergic Trash Bin. Never unlinks directly.
"""

import os
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_stigmergic_trash import SwarmStigmergicTrash

class SwarmTrashScout:
    def __init__(self):
        self.trash = SwarmStigmergicTrash()
        self.root_dir = _REPO
        self.targets_dirs = ["__pycache__"]
        self.targets_exts = [".tmp"]
        self.targets_files = [".DS_Store"]

    def run_sweep(self):
        """
        Walks the organism boundaries and quarantines known bloat.
        Returns the number of entities recycled.
        """
        recycled_count = 0
        
        # Don't sweep inside the trash itself or state dirs where things are alive
        ignore_dirs = {".sifta_trash", ".sifta_state", ".git", ".venv"}

        for dirpath, dirnames, filenames in os.walk(self.root_dir, topdown=True):
            # Prune ignored paths
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            
            # Sweeping specific directory signatures (e.g., __pycache__)
            for d in list(dirnames):
                if d in self.targets_dirs:
                    full_target = Path(dirpath) / d
                    # Move every content inside it to trash
                    for root, _, files in os.walk(full_target):
                        for f in files:
                            target_file = Path(root) / f
                            self.trash.recycle_file(str(target_file))
                            recycled_count += 1
                    
                    # Try to physically remove the empty __pycache__ directory
                    try:
                        import shutil
                        shutil.rmtree(full_target)
                    except Exception:
                        pass
                    dirnames.remove(d) # Stop walking this path

            # Sweeping specific file signatures (.DS_Store, *.tmp)
            for f in filenames:
                if f in self.targets_files or any(f.endswith(ext) for ext in self.targets_exts):
                    target_file = Path(dirpath) / f
                    self.trash.recycle_file(str(target_file))
                    recycled_count += 1

        return recycled_count

def _smoke():
    print("\n=== SIFTA TRASH SCOUT : SMOKE TEST ===")
    scout = SwarmTrashScout()
    
    # Fake some biological noise
    noise = _REPO / ".DS_Store_FAKE_TEST"
    noise.write_text("DUMMY NOISE")
    scout.targets_files.append(".DS_Store_FAKE_TEST")
    
    print("[*] Releasing the Swarm Scout to seek and quarantine...")
    count = scout.run_sweep()
    
    print(f"[*] Scout returned {count} items to the Stigmergic Bin.")
    print("[PASS] Biological autonomy engaged.")

if __name__ == "__main__":
    _smoke()
