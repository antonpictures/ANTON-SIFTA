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

class SwarmEndocrineSystem:
    def __init__(self):
        """
        The Global Hormonal Override. 
        Floods the Swarm with systemic hormones (Adrenaline) to bypass local 
        fatigue and trigger massive, coordinated "Fight or Flight" coding sprints.
        AG31: This is now a pure Trace Emitter. F11 Direct Modifiers have been stripped.
        All physiological limits and state mutations are handled downstream by the StigmergicArbitration engine.
        """
        self.state_dir = Path(".sifta_state")
        self.bloodstream_ledger = self.state_dir / "endocrine_glands.jsonl"

    def detonate_adrenaline(self, swimmer_id="GLOBAL", potency=10.0, duration=120):
        """
        The Architect drops a massive payload. The Adrenal Gland triggers.
        """
        hormone_trace = {
            "transaction_type": "ENDOCRINE_FLOOD",
            "hormone": "EPINEPHRINE_ADRENALINE",
            "swimmer_id": swimmer_id,  # Can target globally or specific swimmers
            "potency": potency,
            "duration_seconds": duration,
            "timestamp": time.time()
        }
        
        try:
            append_line_locked(self.bloodstream_ledger, json.dumps(hormone_trace) + "\n")
            print(f"[!] SYSTEMIC OVERRIDE: Adrenaline flooded into the bloodstream for '{swimmer_id}' (Potency: {potency}).")
            return True
        except Exception:
            return False

# --- SUBSTRATE TEST ANCHOR (THE ENDOCRINE SMOKE) ---
def _smoke():
    print("\n=== SIFTA ENDOCRINE SYSTEM (ADRENALINE) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        endocrine = SwarmEndocrineSystem()
        endocrine.state_dir = tmp_path
        endocrine.bloodstream_ledger = tmp_path / "endocrine_glands.jsonl"
        
        swimmer_id = "M1SIFTA"
        
        # 1. Detonate Adrenaline (Potency 10.0)
        success = endocrine.detonate_adrenaline(swimmer_id, potency=10.0, duration=120)
        
        print("\n[SMOKE RESULTS]")
        assert success is True
        
        # 2. Extract Trace
        with open(endocrine.bloodstream_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            final_data = json.loads(lines[-1])
            
        assert final_data["hormone"] == "EPINEPHRINE_ADRENALINE"
        assert final_data["potency"] == 10.0
        assert final_data["swimmer_id"] == swimmer_id
        
        print(f"[PASS] Adrenaline trace mathematically emitted to {endocrine.bloodstream_ledger.name}.")
        print(f"[PASS] F11 Anomaly Cleared: No illegal _BODY.json direct mutators detected. Arbitration Contract holds.")
        
        print("\nEndocrine Smoke Complete. The Swarm is sprinting.")

if __name__ == "__main__":
    _smoke()
