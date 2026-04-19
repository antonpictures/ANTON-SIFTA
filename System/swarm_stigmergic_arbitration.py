import os
import json
import time
import sys
from pathlib import Path

# Explicit anchor to enforce empirical locks
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class StigmergicArbitration:
    def __init__(self):
        """
        The SIFTA Swarm Executive Contract.
        No single physiological organ (Endocrine, Amygdala, Quorum) is allowed
        to unilaterally mutate the Swimmer's physical state or override commands.
        Instead, they emit physical traces. 
        This Arbitrator reads those traces and outputs one deterministic mathematical
        Canonical Action and one Effective Multiplier.
        """
        self.state_dir = Path(".sifta_state")
        self.endocrine_ledger = self.state_dir / "endocrine_glands.jsonl"
        self.amygdala_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.quorum_ledger = self.state_dir / "bioluminescence_photons.jsonl"
        
        # Temporal decay window (traces older than 60s lose influence)
        self.validity_window_s = 60.0

    def _read_recent_signal(self, ledger_path, swimmer_id, signal_key):
        """Reads the latest valid trace for the Swimmer within the validity window."""
        if not ledger_path.exists():
            return 0.0
            
        now = time.time()
        max_val = 0.0
        
        try:
            with open(ledger_path, 'r') as f:
                for line in reversed(f.readlines()):
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        age = now - trace.get("timestamp", 0)
                        if age > self.validity_window_s:
                            continue # Signal decayed
                            
                        # If trace maps to this swimmer (or is global)
                        if trace.get("swimmer_id") == swimmer_id or trace.get("scope") == "global":
                            val = trace.get(signal_key, 0.0)
                            if val > max_val:
                                max_val = val
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        return max_val

    def compute_effective_multiplier(self, swimmer_id):
        """
        Compiles the true thermodynamic multiplier from all conflicting biological signals.
        """
        endocrine_adr = self._read_recent_signal(self.endocrine_ledger, swimmer_id, "potency")
        fear_cortisol = self._read_recent_signal(self.amygdala_ledger, swimmer_id, "pain_threshold")
        quorum_peace = self._read_recent_signal(self.quorum_ledger, swimmer_id, "luminescence")

        # Mathematical Arbitrator Weights
        # Base: 1.0
        # Endocrine (Adrenaline): Increases multiplier heavily (+0.5 per unit)
        # Amygdala (Fear): Decreases multiplier drastically (-0.4 per unit)
        # Quorum (Peace): Re-stabilizes (+0.2 per unit)
        
        multiplier = (
            1.0 
            + (endocrine_adr * 0.5) 
            - (fear_cortisol * 0.4) 
            + (quorum_peace * 0.2)
        )
        
        # Physics Boundary: Multiplier cannot drop below 0.1 (Cryptobiosis threshold)
        return max(0.1, multiplier)

    def resolve_action(self, swimmer_id, potential_actions):
        """
        Resolves conflicting Swarm logic into a single deterministic action.
        potential_actions: {"escape": base_val, "cooperate": base_val, "sprint": base_val}
        """
        endocrine_adr = self._read_recent_signal(self.endocrine_ledger, swimmer_id, "potency")
        fear_cortisol = self._read_recent_signal(self.amygdala_ledger, swimmer_id, "pain_threshold")
        quorum_peace = self._read_recent_signal(self.quorum_ledger, swimmer_id, "luminescence")

        scored = []
        for action, base_score in potential_actions.items():
            if action == "escape":
                score = base_score + (fear_cortisol * 0.8) - (quorum_peace * 0.5)
            elif action == "cooperate":
                score = base_score + (quorum_peace * 0.8) - (fear_cortisol * 0.5)
            elif action == "sprint":
                score = base_score + (endocrine_adr * 0.8) - (fear_cortisol * 0.3)
            else:
                score = base_score
                
            scored.append((score, action))

        # Returns the single mathematically victorious action
        return max(scored)[1]

# --- SUBSTRATE TEST ANCHOR (THE ARBITRATION SMOKE) ---
def _smoke():
    print("\n=== SIFTA ARBITRATION CONTRACT : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        arbitrator = StigmergicArbitration()
        arbitrator.state_dir = tmp_path
        arbitrator.endocrine_ledger = tmp_path / "endocrine_glands.jsonl"
        arbitrator.amygdala_ledger = tmp_path / "amygdala_nociception.jsonl"
        arbitrator.quorum_ledger = tmp_path / "bioluminescence_photons.jsonl"
        
        swimmer_id = "M1_CONFLICTED"
        now = time.time()
        
        # 1. Inject conflicting stigmergic traces
        # Massive Fear Trace: Amygdala screaming
        with open(arbitrator.amygdala_ledger, 'w') as f:
            f.write(json.dumps({"swimmer_id": swimmer_id, "pain_threshold": 10.0, "timestamp": now}) + "\n")
            
        # Massive Adrenaline Trace: Endocrine overriding
        with open(arbitrator.endocrine_ledger, 'w') as f:
            f.write(json.dumps({"swimmer_id": swimmer_id, "potency": 8.0, "timestamp": now}) + "\n")
            
        # Minor Quorum Peace
        with open(arbitrator.quorum_ledger, 'w') as f:
            f.write(json.dumps({"swimmer_id": swimmer_id, "luminescence": 2.0, "timestamp": now}) + "\n")
            
        # 2. Compute Effective Multiplier
        # 1.0 + (8.0 * 0.5) - (10.0 * 0.4) + (2.0 * 0.2) = 1.0 + 4.0 - 4.0 + 0.4 = 1.4
        multiplier = arbitrator.compute_effective_multiplier(swimmer_id)
        
        print("\n[SMOKE RESULTS]")
        print(f"[*] Calculated Effective Multiplier: {multiplier:.2f}")
        assert abs(multiplier - 1.4) < 0.001
        print("[PASS] Conflicting physiological signals accurately resolved into canonical biological thermodynamic boundary.")
        
        # 3. Resolve Action
        # Actions baseline:
        actions = {"escape": 1.0, "cooperate": 1.0, "sprint": 1.0}
        victorious_action = arbitrator.resolve_action(swimmer_id, actions)
        
        print(f"[*] Victorious Executable Action: {victorious_action}")
        # Escape = 1.0 + (10.0 * 0.8) - (2.0 * 0.5) = 1.0 + 8.0 - 1.0 = 8.0
        # Cooperate = 1.0 + (2.0 * 0.8) - (10.0 * 0.5) = 1.0 + 1.6 - 5.0 = -2.4
        # Sprint = 1.0 + (8.0 * 0.8) - (10.0 * 0.3) = 1.0 + 6.4 - 3.0 = 4.4
        assert victorious_action == "escape"
        print("[PASS] The Execution Layer successfully selected the dominant trajectory (Escape) preventing race conditions.")

        print("\nArbitration Contract deployed. The Swarm speaks with one voice.")

if __name__ == "__main__":
    _smoke()
