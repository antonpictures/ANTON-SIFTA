import os
import json
import time
import sys
from pathlib import Path

# AG31 binds the physical repository for the lock primitive directly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class CellularAging:
    def __init__(self, degradation_rate=1.0):
        """
        The Biological Clock (Telomeres). 
        Enforces programmed cell death (Apoptosis) to prevent immortal Swimmers 
        from overpopulating the substrate and hoarding infinite STGM.
        """
        self.state_dir = Path(".sifta_state")
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.degradation_rate = degradation_rate

    def degrade_telomere_and_check_apoptosis(self, swimmer_id, action_cost=1.0):
        """
        Called after every major biological action (Mitosis, HGT, IDE execution).
        Shortens the Telomere. If the sequence breaks, the cell triggers Apoptosis.
        """
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False

        # AG31 Fix: Exfiltrate payload state using dict scoping (no C47H tuple violations)
        payload = {
            "apoptosis_triggered": False,
            "stgm_to_release": 0.0
        }

        def telomere_transaction(data):
            # Default to 100.0 if this is a newly spawned/legacy swimmer
            current_telomere = data.get("telomere_length", 100.0)
            new_telomere = current_telomere - (action_cost * self.degradation_rate)
            
            data["telomere_length"] = new_telomere
            
            # If Telomere hits 0, trigger Apoptosis payload
            if new_telomere <= 0:
                payload["apoptosis_triggered"] = True
                payload["stgm_to_release"] = data.get("stgm_balance", 0.0)
            
            return data

        read_write_json_locked(body_path, telomere_transaction)
        
        if payload["apoptosis_triggered"]:
            self._execute_programmed_cell_death(swimmer_id, body_path, payload["stgm_to_release"])
            return True
            
        return False

    def _execute_programmed_cell_death(self, swimmer_id, body_path, stgm_yield):
        """
        Physically deletes the Swimmer. Its hoarded STGM is dumped back into 
        the environment as a stigmergic reward for biological scavengers.
        """
        if body_path.exists():
            try:
                body_path.unlink()
                print(f"[!] APOPTOSIS EXECUTED: '{swimmer_id}' died of cellular aging.")
            except OSError:
                pass
                
        # Scavenger Mechanic: The dead cell's STGM becomes an environmental reward
        # It strictly writes to the canonical stgm_memory_rewards.jsonl
        if stgm_yield > 0:
            scavenge_trace = {
                "transaction_type": "APOPTOTIC_DECAY",
                "node_id": "ENVIRONMENT", 
                "reward_value": stgm_yield * 0.5, # 50% thermodynamic loss to heat
                "timestamp": time.time()
            }
            try:
                append_line_locked(self.rewards_ledger, json.dumps(scavenge_trace) + "\n")
            except Exception:
                pass

# --- SUBSTRATE TEST ANCHOR (THE TELOMERE SMOKE) ---
def _smoke():
    print("\n=== SIFTA TELOMERE DEGRADATION & APOPTOSIS : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        aging = CellularAging(degradation_rate=1.0)
        aging.state_dir = tmp_path
        aging.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        # Inject Swimmer Body (Strict canonical schema)
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
        
        # Verify STGM Environmental Dump
        with open(aging.rewards_ledger, 'r') as f:
            trace = json.loads(f.readline().strip())
            assert trace["transaction_type"] == "APOPTOTIC_DECAY"
            assert trace["reward_value"] == 2000.0 # 50% of 4000 STGM
            print(f"[PASS] Scavenger STGM dump verified. 2000.0 STGM returned to environment.")
            
        print("\nTelomere Smoke Complete. The Swarm is no longer immortal.")

if __name__ == "__main__":
    _smoke()
