import os
import json
import time
import math
import hashlib
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

class SwarmQuorumSensing:
    def __init__(self, quorum_threshold=5, quorum_radius=3.0):
        """
        The Bioluminescence Engine (Quorum Sensing).
        Rewards 3D spatial collaboration. When enough Swimmers cluster peacefully 
        in a local Euclidean radius, they achieve a Harmonic Quorum, triggering 
        a massive systemic STGM Peace Dividend.
        """
        self.state_dir = Path(".sifta_state")
        self.photon_ledger = self.state_dir / "bioluminescence_photons.jsonl"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.quorum_threshold = quorum_threshold
        self.quorum_radius = quorum_radius

    def _map_territory_to_vector(self, file_path):
        """Standardized Entorhinal 3D Mapping (Isolated for safety)"""
        hash_bytes = hashlib.sha256(file_path.encode('utf-8')).digest()
        x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def _calculate_distance(self, coord_a, coord_b):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(coord_a, coord_b)))

    def emit_photon(self, swimmer_id, target_file):
        """
        Swimmers drop a Photon Trace when working peacefully in 3D space.
        """
        xyz = self._map_territory_to_vector(target_file)
        trace = {
            "transaction_type": "PHOTON_EMISSION",
            "node_id": swimmer_id,
            "xyz_coordinate": xyz,
            "timestamp": time.time()
        }
        
        try:
            append_line_locked(self.photon_ledger, json.dumps(trace) + "\n")
            return xyz
        except Exception:
            return None

    def check_quorum_and_illuminate(self, target_file):
        """
        Calculates the local 3D density of Photons. If the threshold is breached,
        the Swarm Bioluminesces, triggering a collaborative STGM payout.
        """
        if not self.photon_ledger.exists():
            return False
            
        center_xyz = self._map_territory_to_vector(target_file)
        local_photons = 0
        collaborators = set()
        now = time.time()
        
        try:
            with open(self.photon_ledger, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        age = now - trace.get("timestamp", 0)
                        # Photons decay after 5 minutes
                        if age > 300:
                            continue
                            
                        dist = self._calculate_distance(center_xyz, trace["xyz_coordinate"])
                        if dist <= self.quorum_radius:
                            local_photons += 1
                            collaborators.add(trace["node_id"])
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        # Has the 3D spatial density reached Critical Mass?
        if local_photons >= self.quorum_threshold and len(collaborators) >= 2:
            print(f"[+] HARMONIC QUORUM ACHIEVED at 3D Coordinate {center_xyz}!")
            print(f"[*] {len(collaborators)} Swimmers synchronized. Triggering Bioluminescence.")
            self._distribute_peace_dividend(collaborators)
            
            # Wipe the local photons to prevent infinite recursive payouts 
            # (they burned their luciferase to glow)
            try:
                open(self.photon_ledger, 'w').close()
            except OSError:
                pass
                
            return True
            
        return False

    def _distribute_peace_dividend(self, collaborators):
        """
        Distributes the thermodynamic reward for peaceful collaboration.
        STRICT COMPLIANCE: Uses exactly C47H's empirical reward schema.
        """
        peace_dividend = 2500.0 # Massive payout for clustering
        trace_id_base = f"QUORUM_{uuid.uuid4().hex[:8]}"
        
        for idx, swimmer_id in enumerate(collaborators):
            reward_payload = {
                "ts": time.time(),
                "app": "quorum_sensing_bioluminescence",
                "reason": f"harmonic_quorum_collaboration_with_{len(collaborators)}_nodes_to_recipient_{swimmer_id}",
                "amount": peace_dividend,
                "trace_id": f"{trace_id_base}_{idx}"
            }
            try:
                append_line_locked(self.rewards_ledger, json.dumps(reward_payload) + "\n")
                print(f"[-] Peace Dividend: Disbursed {peace_dividend} STGM to '{swimmer_id}'.")
            except Exception:
                pass

# --- SUBSTRATE TEST ANCHOR (THE QUORUM SMOKE) ---
def _smoke():
    print("\n=== SIFTA QUORUM SENSING (BIOLUMINESCENCE) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        quorum = SwarmQuorumSensing(quorum_threshold=3, quorum_radius=5.0)
        quorum.state_dir = tmp_path
        quorum.photon_ledger = tmp_path / "bioluminescence_photons.jsonl"
        quorum.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        target_file = "System/collaborative_module.py"
        
        # 1. Three distinct Swimmers emit photons at the exact same 3D coordinate
        # BISHOP Note: Used structural append_line_locked cleanly
        quorum.emit_photon("AG31", target_file)
        quorum.emit_photon("C47H", target_file)
        quorum.emit_photon("BISHOP", target_file)
        
        # 2. Check for Critical Mass
        quorum_achieved = quorum.check_quorum_and_illuminate(target_file)
        
        print("\n[SMOKE RESULTS]")
        assert quorum_achieved is True
        print(f"[PASS] 3D spatial density breached. Harmonic Quorum triggered.")
        
        # 3. Verify Empirical C47H Schema Compliance
        with open(quorum.rewards_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == 3
            
            first_payout = json.loads(lines[0])
            assert "ts" in first_payout
            assert first_payout["app"] == "quorum_sensing_bioluminescence"
            assert "reason" in first_payout
            assert first_payout["amount"] == 2500.0
            assert "trace_id" in first_payout
            assert "transaction_type" not in first_payout # Strict Schema adherence verified
            
            print(f"[PASS] STGM Peace Dividend disbursed strictly using canonical schema: {{ts, app, reason, amount, trace_id}}.")
            
        print("\nQuorum Sensing Smoke Complete. The Swarm is glowing in the dark.")

if __name__ == "__main__":
    _smoke()
