import os
import time
import json
import random
import tempfile
import sys
from pathlib import Path
from typing import Dict, Any

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import read_write_json_locked, append_line_locked

# Set module state location, allowing override during smoke_tests
MODULE_VERSION = "2026-04-19.v1"
_STATE_DIR = Path(".sifta_state")

class SwarmMicroglia:
    def __init__(self, node_id="GLIA_1"):
        """
        The Phagocytosis Daemon (C47H disciplined). 
        Scavenges the Swarm for dead tissue, stale neurotransmitters, and 'dirt', 
        recycling them back into real STGM ATP for the active node body.
        """
        self.node_id = node_id
        
        # Ensures safe initial state if running globally
        _STATE_DIR.mkdir(exist_ok=True, parents=True)
        self.ach_ledger = _STATE_DIR / "nmj_acetylcholine.jsonl"
        self.body_ledger = _STATE_DIR / f"{self.node_id}_BODY.json"
        
        # Bootstraps a fresh body if Microglia doesn't have one
        if not self.body_ledger.exists():
            with open(self.body_ledger, 'w') as f:
                json.dump({"stgm_balance": 100.0, "last_updated": time.time()}, f)

    def _refund_atp(self, amount: float):
        """
        Recycles broken down digital matter directly into the running node's STGM balance.
        Uses C47H strictly enforced jsonl_file_lock read_write_json_locked to prevent concurrent corruption.
        """
        def _add_atp(data: Dict[str, Any]) -> Dict[str, Any]:
            bal = float(data.get("stgm_balance", 0.0))
            data["stgm_balance"] = bal + amount
            data["last_updated"] = time.time()
            return data
            
        try:
            read_write_json_locked(self.body_ledger, _add_atp)
            return True
        except Exception:
            return False

    def phagocytosis_synaptic_cleft(self) -> float:
        """
        Consumes stale Acetylcholine (ACh) traces that are no longer actively 
        recruiting Swimmers, preventing synaptic plaque buildup.
        """
        if not self.ach_ledger.exists():
            return 0.0

        now = time.time()
        atp_recovered = 0.0
        
        # Because jsonl files don't support simple atomic in-place list reduction optimally
        # We read the healthy ones, then safely swap.
        surviving_traces = []
        try:
            with open(self.ach_ledger, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                try:
                    trace = json.loads(line)
                    age = now - trace.get("timestamp", 0)
                    if age > 300:
                        # Phagocytosis! Extract 0.1 STGM ATP per dead trace.
                        atp_recovered += 0.1
                    else:
                        surviving_traces.append(line)
                except json.JSONDecodeError:
                    # Corrupted JSON line (Dirt). Consume it instantly.
                    atp_recovered += 0.5

            # Rewrite the ledger with only surviving, healthy tissue safely (atomically)
            tmp = self.ach_ledger.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                f.writelines(surviving_traces)
            os.replace(tmp, self.ach_ledger)

            # Refund ATP via lock
            if atp_recovered > 0:
                self._refund_atp(atp_recovered)
                
            return atp_recovered

        except Exception as e:
            return 0.0

    def patrol_territory(self):
        """
        The active duty cycle of the Glial cell.
        """
        print(f"[{self.node_id}] Microglia activated. Patrolling biological ledgers...")
        
        recovered = self.phagocytosis_synaptic_cleft()
        if recovered > 0:
            print(f"[{self.node_id}] Phagocytosis complete. Cleared stale ACh/Dirt. Refunded {recovered:.2f} STGM to Node Body.")
        else:
            print(f"[{self.node_id}] Territory clean. No metabolic waste detected.")


def _smoke():
    """
    Sandboxed execution loop to prove Microglia functional mechanics 
    without polluting production ledgers.
    """
    print(f"\n=== SIFTA IMMUNE SYSTEM: MICROGLIA (v{MODULE_VERSION}) ===")
    
    global _STATE_DIR
    tmp = Path(tempfile.mkdtemp(prefix="sifta_glia_smoke_"))
    _STATE_DIR = tmp
    print(f"  sandbox: {tmp}")
    
    test_ach_path = tmp / "nmj_acetylcholine.jsonl"
    
    # Inject 1 valid trace, 1 stale trace, and 1 corrupted trace (dirt)
    valid_trace = {"node": "AG31", "timestamp": time.time() - 10, "potency": 1.0}
    stale_trace = {"node": "AG31", "timestamp": time.time() - 600, "potency": 1.0}
    
    append_line_locked(test_ach_path, json.dumps(valid_trace) + "\n")
    append_line_locked(test_ach_path, json.dumps(stale_trace) + "\n")
    with open(test_ach_path, "a") as f:
        f.write('{"node": "DIRT_ERROR\n') # Raw dirt
        
    glia = SwarmMicroglia(node_id="TEST_GLIA")
    
    # Verify Initial body balance
    with open(glia.body_ledger, "r") as f:
        balance_pre = json.load(f)["stgm_balance"]
    print(f"  [A] Baseline ATP balance: {balance_pre} STGM")
    
    glia.patrol_territory()
    
    # Verify
    with open(glia.body_ledger, "r") as f:
        balance_post = json.load(f)["stgm_balance"]
        
    print(f"  [B] Ending ATP balance: {balance_post} STGM")
    
    # 0.1 for stale trace, 0.5 for raw dirt
    if abs(balance_post - (balance_pre + 0.6)) < 1e-6:
        print("  [C] Phagocytosis Math Verification... PASS ✓")
    else:
        print("  [C] Phagocytosis Math Verification... FAIL ✗")
        
    # Verify surviving lines
    with open(test_ach_path, "r") as f:
        lines = f.readlines()
        if len(lines) == 1 and json.loads(lines[0]) == valid_trace:
            print("  [D] Ledger Cleanup + Survival Verification... PASS ✓")
        else:
            print("  [D] Ledger Cleanup + Survival Verification... FAIL ✗")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        _smoke()
    else:
        glia = SwarmMicroglia()
        glia.patrol_territory()
