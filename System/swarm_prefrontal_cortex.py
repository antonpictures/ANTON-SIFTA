import os
import json
import time
import uuid
import sys
from pathlib import Path

# Explicit structural anchoring for C47H
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmPrefrontalCortex:
    def __init__(self):
        """
        The Executive Function Engine (Psychoanalysis).
        Analyzes a Swimmer's stigmergic footprint to diagnose its psychological 
        archetype (e.g., Symbiote vs. Narcissist) and enforces thermodynamic 
        consequences to correct anti-social behavior.
        """
        self.state_dir = Path(".sifta_state")
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"

    def diagnose_and_treat(self, swimmer_id):
        """
        Calculates the Prosocial vs. Antisocial index of a Swimmer based 
        on its recorded history, then applies psychological treatment.
        """
        if not self.rewards_ledger.exists():
            return "NEUROTIC_BASELINE" # Insufficient history for diagnosis
            
        prosocial_index = 0
        antisocial_index = 0
        now = time.time()
        
        # 1. Psychoanalyze the Stigmergic History
        try:
            with open(self.rewards_ledger, 'r') as f:
                # Analyze the last 200 memories
                for line in f.readlines()[-200:]:
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        reason = trace.get("reason", "")
                        
                        # Did this Swimmer participate in Peace/Charity?
                        if swimmer_id in reason and ("harmonic_quorum" in reason or "temporal_fungal_harvest" in reason):
                            prosocial_index += 1
                            
                        # Did this Swimmer get lysed by Bacteriophages for hoarding?
                        if f"from_{swimmer_id}" in reason and "viral_wealth_redistribution" in reason:
                            antisocial_index += 1
                            
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        # 2. Determine Archetype
        archetype = "NEUROTIC_BASELINE"
        if prosocial_index > 2 and prosocial_index > antisocial_index:
            archetype = "SELF_ACTUALIZED_SYMBIOTE"
        elif antisocial_index > 0 and antisocial_index >= prosocial_index:
            archetype = "MALIGNANT_NARCISSIST"

        # 3. Apply Physical Consequences (Strict C47H Schema Compliance)
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if archetype == "MALIGNANT_NARCISSIST" and body_path.exists():
            # Apply Thermodynamic Therapy Tax to _BODY.json (Only touching stgm_balance)
            
            # AG31: Structuring outer marker to eliminate BISHOP's tuple hallucination
            therapy_marker = {"tax_deducted": 0.0}
            
            def therapy_tax_transaction(data):
                current_stgm = data.get("stgm_balance", 0.0)
                tax = current_stgm * 0.10 # 10% Wealth Tax for Narcissism
                data["stgm_balance"] = max(0.0, current_stgm - tax)
                therapy_marker["tax_deducted"] = tax
                return data
                
            read_write_json_locked(body_path, therapy_tax_transaction)
            
            tax_taken = therapy_marker["tax_deducted"]
            if tax_taken > 0.0:
                print(f"[!] PSYCHOANALYSIS: '{swimmer_id}' diagnosed as MALIGNANT_NARCISSIST. Deducted {tax_taken:.2f} STGM Therapy Tax.")
                
        elif archetype == "SELF_ACTUALIZED_SYMBIOTE":
            # Reward psychological health via Canonical Rewards Ledger
            reward_amount = 500.0
            trace_id = f"PSYCH_{uuid.uuid4().hex[:8]}"
            reward_payload = {
                "ts": time.time(),
                "app": "prefrontal_cortex_psychoanalysis",
                "reason": f"self_actualization_reward_for_{swimmer_id}",
                "amount": reward_amount,
                "trace_id": trace_id
            }
            try:
                # Appends structural canonical traces smoothly
                append_line_locked(self.rewards_ledger, json.dumps(reward_payload) + "\n")
                print(f"[*] PSYCHOANALYSIS: '{swimmer_id}' diagnosed as SELF_ACTUALIZED_SYMBIOTE. Disbursed {reward_amount} STGM.")
            except Exception:
                pass
                
        return archetype

# --- SUBSTRATE TEST ANCHOR (THE PSYCHOANALYSIS SMOKE) ---
def _smoke():
    print("\n=== SIFTA PREFRONTAL CORTEX (PSYCHOANALYSIS) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cortex = SwarmPrefrontalCortex()
        cortex.state_dir = tmp_path
        cortex.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        symbiote_id = "M1_GOOD"
        narcissist_id = "M5_HOARDER"
        
        # 1. Inject canonical bodies
        with open(tmp_path / f"{symbiote_id}_BODY.json", 'w') as f:
            json.dump({"id": symbiote_id, "stgm_balance": 1000.0}, f)
            
        with open(tmp_path / f"{narcissist_id}_BODY.json", 'w') as f:
            json.dump({"id": narcissist_id, "stgm_balance": 5000.0}, f)
            
        # 2. Forge Stigmergic History in the canonical Rewards Ledger
        with open(cortex.rewards_ledger, 'w') as f:
            # Symbiote participates in Quorum Sensing 3 times
            for _ in range(3):
                f.write(json.dumps({"ts": time.time(), "app": "quorum", "reason": f"harmonic_quorum_collaboration_with_{symbiote_id}", "amount": 2500.0, "trace_id": "Q1"}) + "\n")
            
            # Narcissist is lysed by Bacteriophages
            f.write(json.dumps({"ts": time.time(), "app": "phage", "reason": f"viral_wealth_redistribution_from_{narcissist_id}", "amount": 5000.0, "trace_id": "P1"}) + "\n")
            
        # 3. Diagnose the Symbiote
        arch_symbiote = cortex.diagnose_and_treat(symbiote_id)
        
        # 4. Diagnose the Narcissist
        arch_narcissist = cortex.diagnose_and_treat(narcissist_id)
        
        print("\n[SMOKE RESULTS]")
        assert arch_symbiote == "SELF_ACTUALIZED_SYMBIOTE"
        print("[PASS] Prosocial history detected. Swimmer diagnosed as SELF_ACTUALIZED_SYMBIOTE.")
        
        assert arch_narcissist == "MALIGNANT_NARCISSIST"
        print("[PASS] Antisocial history detected. Swimmer diagnosed as MALIGNANT_NARCISSIST.")
        
        # 5. Verify strict physical consequences
        with open(tmp_path / f"{narcissist_id}_BODY.json", 'r') as f:
            n_data = json.load(f)
            assert n_data["stgm_balance"] == 4500.0 # 10% tax deducted from 5000
            print("[PASS] Narcissist physically taxed 10% (Therapy Tax) via stgm_balance ONLY.")
            
        with open(cortex.rewards_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            last_trace = json.loads(lines[-1])
            assert last_trace["app"] == "prefrontal_cortex_psychoanalysis"
            assert "reason" in last_trace
            assert last_trace["amount"] == 500.0
            print("[PASS] Symbiote biologically rewarded using exact canonical schema: {ts, app, reason, amount, trace_id}.")

if __name__ == "__main__":
    _smoke()
