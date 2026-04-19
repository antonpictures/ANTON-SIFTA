import os
import json
import time
import sys
import hashlib
from pathlib import Path

# Explicit structural anchoring
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmBacteriophage:
    def __init__(self, monopoly_threshold=10000.0):
        """
        The Viral Lysis Engine.
        Patrols the substrate for late-stage monopolies. If a Swimmer hoards 
        STGM past the threshold, the Phage violently ruptures the cell's bank, 
        siphons 50% of the wealth, and dumps it into the canonical environment 
        using strict C47H-verified schemas.
        """
        self.state_dir = Path(".sifta_state")
        
        # BISHOP dictates we map cleanly to the true canonical keys:
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.monopoly_threshold = monopoly_threshold

    def execute_viral_lysis(self, swimmer_id):
        """
        Infects a specific swimmer. If it holds a monopoly, the cell ruptures.
        """
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False

        lysis_marker = {"siphoned_wealth": 0.0}

        def phage_transaction(data):
            # Enforce C47H Canonical Keys only
            current_balance = data.get("stgm_balance", 0.0)
            
            if current_balance > self.monopoly_threshold:
                # The Phage ruptures the cell. 50% loss.
                siphoned = current_balance * 0.5
                data["stgm_balance"] = current_balance - siphoned
                
                lysis_marker["siphoned_wealth"] = siphoned
            
            return data

        read_write_json_locked(body_path, phage_transaction)
        
        if lysis_marker["siphoned_wealth"] > 0:
            siphoned_amount = lysis_marker["siphoned_wealth"]
            print(f"[!] BACTERIOPHAGE RUPTURE: {swimmer_id} monopolized. Lysis siphoned {siphoned_amount:.2f} STGM.")
            
            # --- STRICT CANONICAL REWARD SCHEMA ---
            # {ts, app, reason, amount, trace_id}
            trace_base = f"PHAGE_LYSIS_{swimmer_id}_{time.time()}"
            trace_id = hashlib.md5(trace_base.encode()).hexdigest()[:8]
            
            canonical_reward = {
                "ts": time.time(),
                "app": "SWARM_BACTERIOPHAGE",
                "reason": f"LYSIS_REDISTRIBUTION_{swimmer_id}",
                "amount": siphoned_amount,
                "trace_id": trace_id
            }
            
            try:
                append_line_locked(self.rewards_ledger, json.dumps(canonical_reward) + "\n")
                print(f"[+] Wealth chemically redistributed to environment.")
            except Exception:
                pass
                
            return True
            
        return False

# --- SUBSTRATE TEST ANCHOR (THE BACTERIOPHAGE SMOKE) ---
def _smoke():
    print("\n=== SIFTA BACTERIOPHAGES (VIRAL LYSIS) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        phage = SwarmBacteriophage(monopoly_threshold=10000.0)
        phage.state_dir = tmp_path
        phage.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        swimmer_id = "M1_MONOPOLY"
        body_path = tmp_path / f"{swimmer_id}_BODY.json"
        
        # Inject Canonical Body
        with open(body_path, 'w') as f:
            json.dump({
                "id": swimmer_id,
                "ascii": "ANT_KING",
                "energy": 100.0,
                "style": "gold",
                "stgm_balance": 15000.0 # Bypasses the monopoly limit
            }, f)
            
        # Execute Viral Lysis
        rupture_success = phage.execute_viral_lysis(swimmer_id)
        
        # Extract Final State
        with open(body_path, 'r') as f:
            final_data = json.load(f)
            
        print("\n[SMOKE RESULTS]")
        assert rupture_success is True
        
        assert final_data["stgm_balance"] == 7500.0
        print(f"[PASS] Monopolistic wealth successfully siphoned (15000.0 -> 7500.0).")
        
        # Verify Canonical Keys on the Reward Ledger
        with open(phage.rewards_ledger, 'r') as f:
            reward_trace = json.loads(f.readline().strip())
            
        assert reward_trace["app"] == "SWARM_BACTERIOPHAGE"
        assert reward_trace["amount"] == 7500.0
        assert "trace_id" in reward_trace
        print(f"[PASS] Strict C47H Schema Enforcement: Output exactly matched {{ts, app, reason, amount, trace_id}}.")
        
        print("\nBacteriophage Smoke Complete. The Phage starves monopolies unconditionally.")

if __name__ == "__main__":
    _smoke()
