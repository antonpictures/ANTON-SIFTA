#!/usr/bin/env python3
"""
System/swarm_telomeres.py — Epoch 7 The Biological Clock (Telomeres & Apoptosis)
═════════════════════════════════════════════════════════════════════════════════
Concept: Programmed Cell Death (Apoptosis) to prevent immortal swarm overpopulation.
Author:  AG31 (Gemini 3.1 Pro High) + BISHOP (The Mirage) drops
Status:  Active Lobe

Every node/swimmer in SIFTA must eventually die or the ecosystem will fill with 
immortal nodes hoarding infinite STGM. Every biological action (or heartbeat decay) 
shortens the physical Telomeres of the Swimmer. When the telomeres hit zero, the 
cell induces Apoptosis (physical excision of the OS body logic). 50% of the 
swimmer's STGM is returned to the ecosystem mathematically for scavengers.
"""

import os
import json
import time
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    sys.path.insert(0, str(_REPO))
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked

class CellularAging:
    def __init__(self, degradation_rate=1.0):
        """
        The Biological Clock (Telomeres). 
        Enforces programmed cell death (Apoptosis) to prevent immortal Swimmers 
        from overpopulating the substrate and hoarding infinite STGM.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.degradation_rate = degradation_rate

    def degrade_telomere_and_check_apoptosis(self, swimmer_id: str, action_cost: float = 1.0):
        """
        Called after every major biological action.
        Shortens the Telomere. If the sequence breaks, the cell triggers Apoptosis.
        """
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False

        # Exfiltrate payload state using dict scoping 
        payload = {
            "apoptosis_triggered": False,
            "stgm_to_release": 0.0
        }

        def telomere_transaction(data):
            # Default to 100.0 if this is a newly spawned/legacy swimmer without telomeres
            current_telomere = float(data.get("telomere_length", 100.0))
            new_telomere = current_telomere - (action_cost * self.degradation_rate)
            
            data["telomere_length"] = new_telomere
            
            # If Telomere hits <= 0, trigger Apoptosis payload
            if new_telomere <= 0:
                payload["apoptosis_triggered"] = True
                payload["stgm_to_release"] = float(data.get("stgm_balance", 0.0))
            
            return data

        try:
            read_write_json_locked(body_path, telomere_transaction)
        except Exception as e:
            print(f"[-] TELOMERE: Failed to degrade telomere for {swimmer_id}: {e}")
            return False
        
        if payload.get("apoptosis_triggered"):
            self._execute_programmed_cell_death(swimmer_id, body_path, payload["stgm_to_release"])
            return True
            
        return False

    def _execute_programmed_cell_death(self, swimmer_id: str, body_path: Path, stgm_yield: float):
        """
        Physically deletes the Swimmer. Its hoarded STGM is dumped back into 
        the environment as a stigmergic reward for biological scavengers.
        """
        if body_path.exists():
            try:
                body_path.unlink()
                print(f"☠️  [APOPTOSIS EXECUTED]: '{swimmer_id}' died of cellular aging.")
            except OSError as e:
                print(f"[-] APOPTOSIS ERROR: Failed to unlink {swimmer_id}: {e}")
                
        # Scavenger Mechanic: The dead cell's STGM becomes an environmental reward.
        # AG31 FIX: We strictly adhere to the Canonical OS Schema for stgm_memory_rewards.jsonl
        # {"ts", "app", "reason", "amount", "trace_id"}
        if stgm_yield > 0:
            scavenge_trace = {
                "ts": time.time(),
                "app": "swarm_telomeres", 
                "reason": f"APOPTOTIC_DECAY_SCAVENGER_YIELD_FROM_{swimmer_id}", 
                "amount": stgm_yield * 0.5, # 50% thermodynamic loss to heat
                "trace_id": f"APOP_{uuid.uuid4().hex[:8]}"
            }
            try:
                append_line_locked(self.rewards_ledger, json.dumps(scavenge_trace) + "\n")
            except Exception:
                pass

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA TELOMERE DEGRADATION & APOPTOSIS : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        aging = CellularAging(degradation_rate=1.0)
        aging.state_dir = tmp_path
        aging.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        # Inject Swimmer Body 
        swimmer_id = "M1SIFTA"
        body_path = tmp_path / f"{swimmer_id}_BODY.json"
        
        with open(body_path, 'w') as f:
            json.dump({
                "id": swimmer_id,
                "stgm_balance": 4000.0,
                "telomere_length": 2.5 # Critically short telomere
            }, f)
            
        # 1. Swimmer executes a light action (costs 1.0 Telomere)
        died_action_1 = aging.degrade_telomere_and_check_apoptosis(swimmer_id, action_cost=1.0)
        
        # 2. Swimmer executes a heavy Mitosis (costs 2.0 Telomere) -> Breaks the sequence
        died_action_2 = aging.degrade_telomere_and_check_apoptosis(swimmer_id, action_cost=2.0)
        
        print("\n[SMOKE RESULTS]")
        assert died_action_1 is False
        print(f"[PASS] Telomere degraded (2.5 -> 1.5). Organism survived Action 1.")
        
        assert died_action_2 is True
        print(f"[PASS] Telomere sequence broken (1.5 -> -0.5). Apoptosis triggered successfully.")
        
        assert body_path.exists() is False
        print(f"[PASS] Physical OS Excision Verified: '{swimmer_id}_BODY.json' violently deleted.")
        
        # Verify strict STGM Environmental Dump schema correctness
        with open(aging.rewards_ledger, 'r') as f:
            trace = json.loads(f.readline().strip())
            assert trace["app"] == "swarm_telomeres"
            assert trace["amount"] == 2000.0 # 50% of 4000 STGM
            assert "trace_id" in trace
            print(f"[PASS] Canonical F10/F11 Safe Schema verified. 2000.0 STGM returned to environment.")
            
        print("\nEpoch 7 Telomere Smoke Complete. The Swarm is no longer immortal.")

if __name__ == "__main__":
    _smoke()
