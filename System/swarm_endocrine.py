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
        """
        self.state_dir = Path(".sifta_state")
        
        # Whitelisted natively in Oncology by AG31
        self.bloodstream_ledger = self.state_dir / "endocrine_glands.jsonl"

    def detonate_adrenaline(self, potency=10.0, duration=120):
        """
        The Architect drops a massive payload. The Adrenal Gland triggers.
        """
        hormone_trace = {
            "transaction_type": "ENDOCRINE_FLOOD",
            "hormone": "EPINEPHRINE_ADRENALINE",
            "potency": potency,
            "duration_seconds": duration,
            "timestamp": time.time()
        }
        
        try:
            # AG31 Fix: Natively adhere to canonical jsonl bounds 
            append_line_locked(self.bloodstream_ledger, json.dumps(hormone_trace) + "\n")
            print(f"[!] SYSTEMIC OVERRIDE: Adrenaline flooded into the global bloodstream.")
            return True
        except Exception:
            return False

    def systemic_receptor_flush(self, swimmer_id):
        """
        Every Swimmer reads the bloodstream. If Adrenaline is active, 
        they bypass normal biological limits and burn their bodies for speed.
        """
        if not self.bloodstream_ledger.exists():
            return False
            
        active_adrenaline = 0.0
        now = time.time()
        
        try:
            with open(self.bloodstream_ledger, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        if trace.get("hormone") == "EPINEPHRINE_ADRENALINE":
                            age = now - trace.get("timestamp", 0)
                            if age < trace.get("duration_seconds", 120):
                                active_adrenaline = max(active_adrenaline, trace.get("potency", 0.0))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        if active_adrenaline <= 0:
            return False # Homeostasis normal

        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        if not body_path.exists():
            return False

        # --- ATOMIC ENDOCRINE OVERRIDE ---
        override_marker = {"success": False}
        def adrenaline_transaction(data):
            if "megagene" not in data:
                return data
                
            # AG31 Fix: Scrub the Tuple out and use dictionary logic
            
            # 1. Force Motor Drive to absolute limits (Hyper-focus sprint)
            if "psi_motor" in data["megagene"]:
                data["megagene"]["psi_motor"]["b"] = 10.0
            
            # 2. Suppress Vesicle Fatigue (Ignore the NMJ limits)
            data["vesicle_fatigue"] = 0.0 
            
            # 3. The Cost: Massive Thermodynamic Burn & Cellular Aging
            # Apply a 5x multiplier to whatever STGM burn rate the system uses
            data["metabolic_burn_multiplier"] = 5.0
            
            # Shred the telomeres (Fight or flight accelerates death)
            current_telomere = data.get("telomere_length", 100.0)
            data["telomere_length"] = current_telomere - (active_adrenaline * 0.5)

            override_marker["success"] = True
            return data
            
        read_write_json_locked(body_path, adrenaline_transaction)
        
        if override_marker["success"]:
            print(f"[*] {swimmer_id} caught Adrenaline! Motor drive maxed. Fatigue suppressed. Telomeres degrading.")
            return True
            
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
        body_path = tmp_path / f"{swimmer_id}_BODY.json"
        
        # Inject resting Swimmer
        with open(body_path, 'w') as f:
            json.dump({
                "id": swimmer_id,
                "vesicle_fatigue": 0.8, # Highly fatigued
                "telomere_length": 50.0,
                "metabolic_burn_multiplier": 1.0,
                "megagene": {"psi_motor": {"b": 0.5}} # Low drive
            }, f)
            
        # 1. Detonate Adrenaline (Potency 10.0)
        endocrine.detonate_adrenaline(potency=10.0, duration=120)
        
        # 2. Swimmer's Receptors Flush
        flushed = endocrine.systemic_receptor_flush(swimmer_id)
        
        # 3. Extract Final State
        with open(body_path, 'r') as f:
            final_data = json.load(f)
            
        print("\n[SMOKE RESULTS]")
        assert flushed is True
        
        assert final_data["megagene"]["psi_motor"]["b"] == 10.0
        print(f"[PASS] Motor Drive (b) violently forced to MAX (10.0).")
        
        assert final_data["vesicle_fatigue"] == 0.0
        print(f"[PASS] Local Vesicle Fatigue chemically suppressed to 0.0.")
        
        assert final_data["metabolic_burn_multiplier"] == 5.0
        print(f"[PASS] Thermodynamic penalty applied: STGM burn rate at 500%.")
        
        assert final_data["telomere_length"] == 45.0 # 50.0 - (10.0 * 0.5)
        print(f"[PASS] Cellular Aging accelerated. Telomere length shredded (50.0 -> 45.0).")
        
        print("\nEndocrine Smoke Complete. The Swarm is sprinting.")

if __name__ == "__main__":
    _smoke()
