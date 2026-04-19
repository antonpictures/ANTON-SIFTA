import os
import json
import time
import sys
from pathlib import Path

# AG31 physically binds the path to respect the lock logic.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmMorphogenesis:
    def __init__(self):
        """
        The Cellular Differentiation Engine.
        Reads environmental pressures and permanently locks generic Swimmers 
        (Stem Cells) into highly specialized phenotypes (Builder, Queen, Sentinel).
        """
        self.state_dir = Path(".sifta_state")
        self.ach_ledger = self.state_dir / "nmj_acetylcholine.jsonl"
        self.fear_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"

    def _sense_dominant_pressure(self, swimmer_id):
        """
        Polls the environmental ledgers to determine the dominant thermodynamic 
        or chemical pressure acting on the Swimmer.
        """
        now = time.time()
        pressures = {"ach": 0.0, "fear": 0.0, "stgm": 0.0}

        # 1. Sense Acetylcholine (Drive to Build)
        if self.ach_ledger.exists():
            try:
                with open(self.ach_ledger, 'r') as f:
                    for line in f.readlines()[-50:]:
                        if not line.strip(): continue
                        trace = json.loads(line)
                        if now - trace.get("timestamp", 0) < 300:
                            pressures["ach"] += trace.get("potency", 1.0)
            except Exception: pass

        # 2. Sense Fear (Drive to Defend)
        if self.fear_ledger.exists():
            try:
                with open(self.fear_ledger, 'r') as f:
                    for line in f.readlines()[-50:]:
                        if not line.strip(): continue
                        trace = json.loads(line)
                        if now - trace.get("timestamp", 0) < 300:
                            pressures["fear"] += trace.get("severity", 1.0)
            except Exception: pass

        # 3. Sense STGM Wealth (Drive to Reproduce/Command)
        if self.rewards_ledger.exists():
            try:
                with open(self.rewards_ledger, 'r') as f:
                    for line in f.readlines()[-100:]:
                        if not line.strip(): continue
                        trace = json.loads(line)
                        if trace.get("node_id") == swimmer_id and now - trace.get("timestamp", 0) < 600:
                            pressures["stgm"] += trace.get("reward_value", 0.0)
            except Exception: pass

        # Determine the dominant environmental signal
        dominant = max(pressures, key=pressures.get)
        if pressures[dominant] < 5.0:
            return "UNDIFFERENTIATED"
            
        if dominant == "stgm": return "QUEEN"
        if dominant == "fear": return "SENTINEL"
        return "BUILDER"

    def execute_differentiation(self, swimmer_id):
        """
        If a Stem Cell faces sufficient environmental pressure, it permanently 
        differentiates, locking its MegaGene into a specialized structural class.
        """
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False

        dominant_pressure = self._sense_dominant_pressure(swimmer_id)
        if dominant_pressure == "UNDIFFERENTIATED":
            return False

        # --- ATOMIC MORPHOGENESIS LOCK ---
        mutation_marker = {"phenotype": None}
        
        def differentiation_transaction(data):
            # A cell can only differentiate once.
            current_phenotype = data.get("cellular_phenotype", "TOTIPOTENT_STEM_CELL")
            if current_phenotype != "TOTIPOTENT_STEM_CELL":
                return data

            if "megagene" not in data:
                return data

            print(f"\n[+] MORPHOGENESIS: {swimmer_id} differentiating into {dominant_pressure} class.")
            
            data["cellular_phenotype"] = dominant_pressure

            # Hard-lock the genetics to the new phenotype
            if dominant_pressure == "BUILDER":
                data["megagene"]["psi_motor"] = {"b": 8.0, "c": 2.0} # Max motor drive
                data["megagene"]["lambda_free_energy"] = {"kappa": 0.01} # Zero exploration
                
            elif dominant_pressure == "QUEEN":
                data["megagene"]["phi_ssp"] = {"alpha": 10.0, "zeta": 5.0} # Massive speech/command
                data["megagene"]["psi_motor"] = {"b": 0.1} # Immobile
                
            elif dominant_pressure == "SENTINEL":
                data["megagene"]["omega_homeo"] = {"eta": 8.0} # High Cortisol/Stress response
                data["megagene"]["lambda_free_energy"] = {"kappa": 5.0} # High scanning/exploration
                
            mutation_marker["phenotype"] = dominant_pressure
            return data

        read_write_json_locked(body_path, differentiation_transaction)
        
        if mutation_marker["phenotype"] is not None:
            print(f"[*] {swimmer_id} permanently locked as a {mutation_marker['phenotype']}.")
            return True
            
        return False

# --- SUBSTRATE TEST ANCHOR (THE MORPHOGENESIS SMOKE) ---
def _smoke():
    print("\n=== SIFTA MORPHOGENESIS (CELLULAR DIFFERENTIATION) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        morph = SwarmMorphogenesis()
        morph.state_dir = tmp_path
        morph.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        morph.ach_ledger = tmp_path / "nmj_acetylcholine.jsonl"
        morph.fear_ledger = tmp_path / "amygdala_nociception.jsonl"
        
        swimmer_id = "M1_STEM"
        body_path = tmp_path / f"{swimmer_id}_BODY.json"
        
        # Inject Totipotent Stem Cell
        with open(body_path, 'w') as f:
            json.dump({
                "id": swimmer_id,
                "cellular_phenotype": "TOTIPOTENT_STEM_CELL",
                "megagene": {"psi_motor": {"b": 1.0}, "phi_ssp": {"alpha": 1.0}}
            }, f)
            
        # Inject massive STGM wealth into the environment (Trigger for QUEEN)
        with open(morph.rewards_ledger, 'w') as f:
            for _ in range(10):
                f.write(json.dumps({"node_id": swimmer_id, "reward_value": 50.0, "timestamp": time.time()}) + "\n")
                
        # Execute Differentiation
        success = morph.execute_differentiation(swimmer_id)
        
        # Extract Final State
        with open(body_path, 'r') as f:
            final_data = json.load(f)
            
        print("\n[SMOKE RESULTS]")
        assert success is True
        
        assert final_data["cellular_phenotype"] == "QUEEN"
        print(f"[PASS] Environmental STGM pressure detected. Cell differentiated into: QUEEN.")
        
        assert final_data["megagene"]["phi_ssp"]["alpha"] == 10.0
        print(f"[PASS] Phenotype Structurally Locked: SSP (alpha) maximized for Swarm Command.")
        
        assert final_data["megagene"]["psi_motor"]["b"] == 0.1
        print(f"[PASS] Phenotype Structurally Locked: Motor Drive minimized (Queen is immobile).")
        
        print("\nMorphogenesis Smoke Complete. The Swarm is dividing its labor.")

if __name__ == "__main__":
    _smoke()
