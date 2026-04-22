#!/usr/bin/env python3
"""
System/swarm_stigmergic_trash.py — Stigmergic Garbage Collection
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The Swarm's approach to deletion: we never immediately unlink.
Files are moved to a local Stigmergic Trash Bin.
Only when capacity runs low does Alice autonomously empty it,
seeking explicit Architect consent if it breaches thresholds.
"""

import os
import time
import json
import shutil
import hashlib
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
    from System.swarm_szilard_demon import SwarmSzilardDemon
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class SwarmStigmergicTrash:
    def __init__(self):
        self.trash_dir = _REPO / ".sifta_trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_dir = _REPO / ".sifta_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "stigmergic_trash_traces.jsonl"

    def recycle_file(self, target_path: str):
        """
        Safely moves a file to the Stigmergic Trash Bin.
        Appends the Epoch seconds and a short short hash to the filename 
        to ensure zero collisions or overrides inside the trash.
        """
        target = Path(target_path)
        if not target.exists():
            return {"error": "File does not exist."}

        # Prevent Alice from trashing the OS kernel accidentally
        if str(target.resolve()).startswith(str((_REPO / "System").resolve())):
            return {"error": "Bostrom Gate violation: Cannot trash System/ code."}

        timestamp = int(time.time())
        file_hash = hashlib.md5(str(target).encode()).hexdigest()[:6]
        
        new_name = f"{timestamp}_{file_hash}_{target.name}"
        destination = self.trash_dir / new_name
        
        try:
            # We use shutil.move to handle cross-device/partition gracefully
            shutil.move(str(target), str(destination))
            
            trace = {
                "transaction_type": "TRASH_RECYCLE",
                "original_path": str(target),
                "trash_path": str(destination),
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

    def get_trash_size_mb(self) -> float:
        """
        Recursively calculates the size of the trash bin in Megabytes.
        """
        total_size = 0
        for dirpath, _, filenames in os.walk(self.trash_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)

    def enforce_retention_window(self, max_days: int = 3):
        """
        Simulates natural biological decay. Any memory physically in the trash
        longer than `max_days` gets irreversibly unlinked autonomously.
        """
        now = time.time()
        max_age_s = max_days * 24 * 3600
        purged = 0
        
        for dirpath, _, filenames in os.walk(self.trash_dir):
            for f in filenames:
                fp = Path(dirpath) / f
                try:
                    # Prefer the embedded epoch prefix if available, fallback to st_mtime
                    parts = f.split("_", 2)
                    if len(parts) >= 3 and parts[0].isdigit():
                        file_ts = int(parts[0])
                    else:
                        file_ts = fp.stat().st_mtime
                    
                    if (now - file_ts) > max_age_s:
                        try:
                            # Apply Szilard Thermodynamic Demon Cost before physical unlink
                            fp_size = fp.stat().st_size
                            demon = SwarmSzilardDemon()
                            kept, cost = demon.evaluate_and_erase(fp_size, mutual_info_score=0.01)
                            if not kept and cost > 0:
                                debit_trace = {
                                    "transaction_type": "THERMODYNAMIC_DECAY_PENALTY",
                                    "file": fp.name,
                                    "size_bytes": fp_size,
                                    "metabolic_cost_stgm": -cost,
                                    "timestamp": time.time()
                                }
                                append_line_locked(demon.stgm_treasury_ledger, json.dumps(debit_trace) + "\n")
                        except Exception:
                            pass
                            
                        fp.unlink(missing_ok=True)
                        purged += 1
                except Exception:
                    pass
        return purged

    def empty_trash(self):
        """
        Physical irreversible deletion of all unlinked files.
        """
        try:
            # First, total the mass being erased for the Demon
            demon = SwarmSzilardDemon()
            total_size_bytes = 0
            for dirpath, _, filenames in os.walk(self.trash_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size_bytes += os.path.getsize(fp)
            
            if total_size_bytes > 0:
                kept, cost = demon.evaluate_and_erase(total_size_bytes, mutual_info_score=0.01)
                if not kept and cost > 0:
                    debit_trace = {
                        "transaction_type": "THERMODYNAMIC_ERASURE_PENALTY",
                        "size_bytes": total_size_bytes,
                        "metabolic_cost_stgm": -cost,
                        "timestamp": time.time()
                    }
                    append_line_locked(demon.stgm_treasury_ledger, json.dumps(debit_trace) + "\n")

            shutil.rmtree(self.trash_dir)
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            
            trace = {
                "transaction_type": "TRASH_EMPTIED",
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            
            # --- Stigmergic Identity Tie-in ---
            # Approving deletion is a TCC-style consent pheromone.
            identity_trace = {
                "transaction_type": "STIGMERGIC_IDENTITY_GRANT",
                "author": "IOAN",
                "event": "EMPTY_TRASH_CONSENT",
                "timestamp": time.time()
            }
            append_line_locked(self.state_dir / "ide_stigmergic_trace.jsonl", json.dumps(identity_trace) + "\n")
            
            return {"status": "EMPTIED"}
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA STIGMERGIC TRASH : SMOKE TEST ===")
    trash = SwarmStigmergicTrash()
    
    # 1. Create a dummy file
    dummy = Path("dummy_for_trash.txt")
    dummy.write_text("Temp dirt from the Matrix.")
    print(f"[*] Created target payload: {dummy}")
    
    # 2. Recycle it
    print("[*] Recycling target...")
    res = trash.recycle_file(str(dummy))
    print(json.dumps(res, indent=2))
    
    # 3. Check mass
    mass_mb = trash.get_trash_size_mb()
    print(f"[*] Trash total mass: {mass_mb:.4f} MB")
    
    # 4. Decay check
    print("[*] Enforcing 3-day retention decay...")
    purged = trash.enforce_retention_window(max_days=3)
    print(f"[*] Natural decay purged {purged} items.")
    
    # 5. Empty it
    print("[*] Emptying trash + Granting Stigmergic Identity Consent...")
    res_empty = trash.empty_trash()
    print(res_empty)
    
    mass_mb_after = trash.get_trash_size_mb()
    print(f"[*] Trash total mass after empty: {mass_mb_after:.4f} MB")
    print("[PASS] Stigmergic deletion active.")

if __name__ == "__main__":
    _smoke()
