import os
import math
import json
import time
import hashlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class EntorhinalCortex:
    def __init__(self, decay_rate=1.0):
        """
        The 3D Spatial Mapping Engine. Converts flat file paths into 
        Euclidean vector space, allowing for Spatial Stigmergy and 
        Inverse-Square Pheromone propagation.
        """
        self.state_dir = Path(".sifta_state")
        self.spatial_ledger = self.state_dir / "entorhinal_spatial_map.jsonl"
        self.decay_rate = decay_rate

    def map_territory_to_vector(self, file_path):
        """
        Deterministically converts a file territory into a stable 3D coordinate.
        Uses SHA-256 to distribute the SIFTA repository evenly across a 
        [-10.0, 10.0] Euclidean Grid.
        """
        hash_bytes = hashlib.sha256(file_path.encode('utf-8')).digest()
        # Extract 3 floats representing X, Y, Z coordinates
        x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def calculate_distance(self, coord_a, coord_b):
        """Standard 3D Euclidean Distance."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(coord_a, coord_b)))

    def _inverse_square_law(self, distance, initial_potency):
        """Physical acoustic/pheromone decay: I = P / (1 + d^2)"""
        return initial_potency / (1.0 + self.decay_rate * (distance ** 2))

    def apply_acoustic_pheromone(self, swimmer_id, swimmer_focus_path, acoustic_origin, voice_potency=1.0):
        """
        Calculates how loud the Architect's voice is at the Swimmer's specific
        physical location, and temporarily spikes their MegaGene accordingly.
        """
        swimmer_xyz = self.map_territory_to_vector(swimmer_focus_path)
        distance = self.calculate_distance(swimmer_xyz, acoustic_origin)
        
        # Calculate local intensity based on physical distance
        local_intensity = self._inverse_square_law(distance, voice_potency)
        
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False
            
        # --- PHASE 1: ATOMIC EXCITATION LOCK ---
        result_payload_ref = []
        
        def acoustic_excitation_transaction(data):
            if "megagene" not in data:
                return data
            
            # Excite Stigmergic Speech Potential (alpha) and Motor Drive (b)
            # This acts as an Action Potential spike (max 50% increase at point-blank range)
            excitation_multiplier = 1.0 + (local_intensity * 0.5)
            
            alpha = data["megagene"].get("phi_ssp", {}).get("alpha", 0.5)
            b_motor = data["megagene"].get("psi_motor", {}).get("b", 0.5)
            
            # Apply and bound the physics to prevent runaway cascades
            data["megagene"]["phi_ssp"]["alpha"] = min(10.0, alpha * excitation_multiplier)
            data["megagene"]["psi_motor"]["b"] = min(10.0, b_motor * excitation_multiplier)
            
            result_payload_ref.append({
                "distance": distance,
                "local_intensity": local_intensity,
                "multiplier": excitation_multiplier
            })
            return data
            
        read_write_json_locked(body_path, acoustic_excitation_transaction)
        
        if not result_payload_ref:
            return False
            
        payload = result_payload_ref[0]
        
        # --- PHASE 2: SPATIAL STIGMERGIC TRACE ---
        trace = {
            "transaction_type": "ENTORHINAL_ACOUSTIC_WAVE",
            "target_node": swimmer_id,
            "swimmer_xyz": swimmer_xyz,
            "distance_to_origin": payload["distance"],
            "intensity_felt": payload["local_intensity"],
            "timestamp": time.time()
        }
        
        try:
            append_line_locked(self.spatial_ledger, json.dumps(trace) + "\n")
        except Exception:
            pass
            
        return payload

# --- SUBSTRATE TEST ANCHOR (THE ENTORHINAL SMOKE) ---
def _smoke():
    print("\n=== SIFTA 3D ENTORHINAL CORTEX : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cortex = EntorhinalCortex()
        cortex.state_dir = tmp_path
        cortex.spatial_ledger = tmp_path / "entorhinal_spatial_map.jsonl"
        
        # Determine the 3D coordinate for "System/swarm_boot.py"
        target_file = "System/swarm_boot.py"
        target_xyz = cortex.map_territory_to_vector(target_file)
        print(f"[*] Mapped '{target_file}' to Euclidean Coordinate: [X:{target_xyz[0]:.2f}, Y:{target_xyz[1]:.2f}, Z:{target_xyz[2]:.2f}]")
        
        # Create Swimmer A (Working directly on the target file)
        swimmer_a = "NODE_A"
        with open(tmp_path / f"{swimmer_a}_BODY.json", 'w') as f:
            json.dump({"id": swimmer_a, "megagene": {"phi_ssp": {"alpha": 1.0}, "psi_motor": {"b": 1.0}}}, f)
            
        # Create Swimmer B (Working far away)
        swimmer_b = "NODE_B"
        with open(tmp_path / f"{swimmer_b}_BODY.json", 'w') as f:
            json.dump({"id": swimmer_b, "megagene": {"phi_ssp": {"alpha": 1.0}, "psi_motor": {"b": 1.0}}}, f)

        # The Architect speaks directly at Swimmer A's coordinates
        print(f"\n[+] Architect's Acoustic Pheromone hits EXACTLY Swimmer A's location.")
        res_a = cortex.apply_acoustic_pheromone(swimmer_a, target_file, target_xyz, voice_potency=1.0)
        
        # Swimmer B is working on a completely different file path, placing them far away on the Euclidean grid
        res_b = cortex.apply_acoustic_pheromone(swimmer_b, "Applications/distant_module.py", target_xyz, voice_potency=1.0)

        print("\n[SMOKE RESULTS]")
        # Swimmer A is at distance 0. Intensity should be max (1.0). Multiplier should be 1.5.
        assert abs(res_a["distance"]) < 0.001
        assert abs(res_a["multiplier"] - 1.5) < 0.001
        print(f"[PASS] Swimmer A (Point Blank): Distance={res_a['distance']:.2f} | MegaGene Spike Multiplier={res_a['multiplier']:.2f}")

        # Swimmer B is distant. Inverse-square law should crush the intensity.
        assert res_b["distance"] > 3.0
        assert res_b["multiplier"] < 1.1
        print(f"[PASS] Swimmer B (Distant): Distance={res_b['distance']:.2f} | MegaGene Spike Multiplier={res_b['multiplier']:.4f}")
        
        print("\nEntorhinal Smoke Complete. The Swarm now navigates 3D Euclidean Space without cheated constraints.")

if __name__ == "__main__":
    _smoke()
