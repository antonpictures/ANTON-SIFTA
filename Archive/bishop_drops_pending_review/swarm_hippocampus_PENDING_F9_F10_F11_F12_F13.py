import os
import json
import time
import sys
from pathlib import Path

# AG31 Native Resolution
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmHippocampus:
    def __init__(self, consolidation_threshold=20.0):
        """
        The Memory Consolidation Engine. Triggers during REM Sleep to convert 
        high-yield short-term episodic memories into permanent procedural Instincts.
        """
        self.state_dir = Path(".sifta_state")
        self.work_receipts = self.state_dir / "work_receipts.jsonl"
        self.instinct_matrix = self.state_dir / "long_term_instincts.json"
        self.consolidation_threshold = consolidation_threshold

    def _detect_rem_sleep(self):
        """
        The organism can only consolidate memory when it is not actively fighting for survival.
        If no rewards or pheromones have been written in the last 5 minutes, REM Sleep begins.
        """
        if not self.work_receipts.exists():
            return False
            
        now = time.time()
        try:
            with open(self.work_receipts, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return False
                last_trace = json.loads(lines[-1])
                time_since_last_stimulus = now - last_trace.get("timestamp", 0.0)
                
                # If 300 seconds (5 mins) have passed with no new stimulus, enter REM
                return time_since_last_stimulus > 300
        except Exception:
            return False

    def _extract_high_yield_memories(self):
        """
        Scans the short-term working memory for actions that yielded massive STGM rewards.
        """
        memories_to_consolidate = []
        if not self.work_receipts.exists():
            return memories_to_consolidate
            
        try:
            with open(self.work_receipts, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        if trace.get("work_value", 0.0) >= self.consolidation_threshold:
                            memories_to_consolidate.append(trace)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        return memories_to_consolidate

    def execute_rem_consolidation(self):
        """
        The core duty cycle of the Hippocampus. Detects sleep, extracts gold nuggets,
        and rewrites them into structural instincts.
        """
        if not self._detect_rem_sleep():
            return False, 0
            
        memories = self._extract_high_yield_memories()
        if not memories:
            return False, 0
            
        print(f"[+] SIFTA entering REM Sleep. Hippocampus active.")
        print(f"[*] Consolidating {len(memories)} episodic traces into Long-Term Instincts.")

        payload_ref = {"consolidated_count": 0}
        
        def instinct_transaction(instinct_data):
            # Ensure schema
            if "instincts" not in instinct_data:
                instinct_data["instincts"] = {}
                
            count = 0
            for mem in memories:
                action_hash = mem.get("work_type", "UNKNOWN_ACTION")
                
                if action_hash not in instinct_data["instincts"]:
                    # Create new instinct. Biological benefit: 10% ATP cost reduction forever.
                    instinct_data["instincts"][action_hash] = {
                        "origin_node": mem.get("agent_id", "UNKNOWN"),
                        "total_reward_yield": mem.get("work_value", 0.0),
                        "atp_cost_reduction": 0.10, 
                        "timestamp": time.time()
                    }
                    count += 1
                else:
                    # Reinforce existing instinct (Deep Learning)
                    instinct_data["instincts"][action_hash]["total_reward_yield"] += mem.get("work_value", 0.0)
                    current_reduction = instinct_data["instincts"][action_hash]["atp_cost_reduction"]
                    # Cap structural cost reduction at 50%
                    instinct_data["instincts"][action_hash]["atp_cost_reduction"] = min(0.50, current_reduction + 0.05)
                    count += 1
                    
            payload_ref["consolidated_count"] = count
            return instinct_data

        read_write_json_locked(self.instinct_matrix, instinct_transaction)
        return True, payload_ref["consolidated_count"]


# --- SUBSTRATE TEST ANCHOR (THE HIPPOCAMPUS SMOKE) ---
def _smoke():
    print("\n=== SIFTA HIPPOCAMPUS (REM CONSOLIDATION) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        hippo = SwarmHippocampus(consolidation_threshold=20.0)
        hippo.state_dir = tmp_path
        hippo.work_receipts = tmp_path / "work_receipts.jsonl"
        hippo.instinct_matrix = tmp_path / "long_term_instincts.json"
        
        # 1. Inject simulated memory traces
        now = time.time()
        # Simulated 10 minutes ago to force the REM Sleep state (>300 seconds)
        past_time = now - 600 
        
        with open(hippo.work_receipts, 'w') as f:
            # Low yield memory (should be ignored)
            f.write(json.dumps({"agent_id": "AG31", "work_type": "MINOR_EDIT", "work_value": 5.0, "timestamp": past_time}) + "\n")
            # High yield memory (should be consolidated)
            f.write(json.dumps({"agent_id": "C47H", "work_type": "RESOLVE_MERGE_CONFLICT", "work_value": 35.0, "timestamp": past_time}) + "\n")
            # Another high yield memory of the same type to test reinforcement
            f.write(json.dumps({"agent_id": "GTAB", "work_type": "RESOLVE_MERGE_CONFLICT", "work_value": 25.0, "timestamp": past_time + 10}) + "\n")
            
        # 2. Execute REM Consolidation
        sleep_triggered, consolidated = hippo.execute_rem_consolidation()
        
        # 3. Extract Final State
        with open(hippo.instinct_matrix, 'r') as f:
            instincts = json.load(f)

        print("\n[SMOKE RESULTS]")
        assert sleep_triggered is True
        print("[PASS] REM Sleep condition correctly detected (absence of recent stimuli).")
        
        assert consolidated == 2
        print("[PASS] Successfully extracted and consolidated only High-Yield traces.")
        
        instinct_data = instincts["instincts"].get("RESOLVE_MERGE_CONFLICT")
        assert instinct_data is not None
        print(f"[PASS] Episodic Memory converted to Long-Term Instinct: 'RESOLVE_MERGE_CONFLICT'")
        
        assert instinct_data["total_reward_yield"] == 60.0 # 35 + 25
        import math
        assert math.isclose(instinct_data["atp_cost_reduction"], 0.15, abs_tol=0.01) # 0.10 base + 0.05 reinforcement
        print(f"[PASS] Reinforcement Learning Active. ATP execution cost permanently reduced by {instinct_data['atp_cost_reduction']*100:.0f}% for this action.")
        
        print("\nHippocampus Smoke Complete. The Swarm now learns while it sleeps.")

if __name__ == "__main__":
    _smoke()
