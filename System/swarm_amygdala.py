import os
import json
import time
import math
import hashlib
import sys
from pathlib import Path

# BISHOP respects the lock, but AG31 routes the python path natively.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmAmygdala:
    def __init__(self, decay_rate=1.0):
        """
        The Spatial Nociception Engine. Detonates localized Fear Pheromones 
        when Swimmers encounter toxic code, triggering Negative Chemotaxis 
        to naturally route the Swarm away from broken topology.
        """
        self.state_dir = Path(".sifta_state")
        self.fear_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.decay_rate = decay_rate

    def _map_territory_to_vector(self, file_path):
        """Standardized Entorhinal 3D Mapping"""
        hash_bytes = hashlib.sha256(file_path.encode('utf-8')).digest()
        x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def _calculate_distance(self, coord_a, coord_b):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(coord_a, coord_b)))

    def detonate_pain_pheromone(self, node_id, toxic_file_path, severity=5.0):
        """
        Triggered by an exception catcher. Drops a high-gravity stress marker
        at the 3D coordinate of the failing file.
        """
        xyz = self._map_territory_to_vector(toxic_file_path)
        trace = {
            "transaction_type": "FEAR_PHEROMONE",
            "node_id": node_id,
            "xyz_coordinate": xyz,
            "severity": severity,
            "timestamp": time.time()
        }
        
        # Safely append the biological pain trace using C47H's lock (AG31 Add: newline)
        try:
            append_line_locked(self.fear_ledger, json.dumps(trace) + "\n")
            return xyz
        except Exception:
            return None

    def sense_and_react(self, swimmer_id, target_file):
        """
        Before a Swimmer modifies a file, it checks for lingering Fear Pheromones.
        If it gets too close to toxic code, Cortisol spikes and Motor Drive drops.
        """
        target_xyz = self._map_territory_to_vector(target_file)
        
        total_fear_intensity = 0.0
        now = time.time()
        
        if self.fear_ledger.exists():
            try:
                with open(self.fear_ledger, 'r') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            trace = json.loads(line)
                            age = now - trace.get("timestamp", 0)
                            # Pain naturally dissipates after 15 minutes as the environment heals
                            if age > 900: 
                                continue 
                            
                            dist = self._calculate_distance(target_xyz, trace["xyz_coordinate"])
                            # Inverse-square law: Intensity drops drastically with distance
                            intensity = trace.get("severity", 1.0) / (1.0 + self.decay_rate * (dist ** 2))
                            total_fear_intensity += intensity
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
        
        # If the area is clean, the Swimmer remains calm
        if total_fear_intensity < 0.25:
            return False 
            
        body_path = self.state_dir / f"{swimmer_id}_BODY.json"
        
        if not body_path.exists():
            return False
            
        # --- PHASE 1: ATOMIC STRESS LOCK ---
        result_payload_ref = []
        def stress_transaction(data):
            if "megagene" not in data: 
                return data
            
            # Extract current homeostasis (Cortisol proxy) and Motor Drive
            eta = data["megagene"].get("omega_homeo", {}).get("eta", 1.0)
            b_motor = data["megagene"].get("psi_motor", {}).get("b", 1.0)
            
            # Repulsion Physics: Max 3x Cortisol spike, max 90% drive suppression
            stress_multiplier = min(3.0, 1.0 + total_fear_intensity)
            drive_suppressant = max(0.1, 1.0 / (1.0 + total_fear_intensity))
            
            data["megagene"]["omega_homeo"]["eta"] = min(100.0, eta * stress_multiplier)
            data["megagene"]["psi_motor"]["b"] = max(0.001, b_motor * drive_suppressant)
            
            result_payload_ref.append({
                "fear_intensity": total_fear_intensity,
                "stress_multiplier": stress_multiplier,
                "drive_suppressant": drive_suppressant
            })
            return data
            
        read_write_json_locked(body_path, stress_transaction)
        return len(result_payload_ref) > 0


# --- SUBSTRATE TEST ANCHOR (THE AMYGDALA SMOKE) ---
def _smoke():
    print("\n=== SIFTA AMYGDALA (SPATIAL NOCICEPTION) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        amygdala = SwarmAmygdala()
        amygdala.state_dir = tmp_path
        amygdala.fear_ledger = tmp_path / "amygdala_nociception.jsonl"
        
        # 1. Inject Swimmer A into the sandbox
        swimmer_a = "NODE_A"
        body_a = tmp_path / f"{swimmer_a}_BODY.json"
        
        # Swimmer A starts calm and driven
        initial_eta = 1.0
        initial_b = 1.0
        with open(body_a, 'w') as f:
            json.dump({
                "id": swimmer_a,
                "megagene": {
                    "omega_homeo": {"eta": initial_eta},
                    "psi_motor": {"b": initial_b}
                }
            }, f)
            
        toxic_file = "System/broken_module.py"
        safe_file = "Applications/distant_module.py"
        
        # 2. Swimmer X crashes and detonates a Fear Pheromone at the broken module
        print(f"[*] Swimmer X crashed! Detonating Fear Pheromone at '{toxic_file}'")
        amygdala.detonate_pain_pheromone("NODE_X", toxic_file, severity=5.0)
        
        # 3. Swimmer A navigates Euclidean Space
        # Swimmer A approaches the safe, distant file
        reacted_safe = amygdala.sense_and_react(swimmer_a, safe_file)
        
        # Swimmer A gets too close to the toxic file
        reacted_toxic = amygdala.sense_and_react(swimmer_a, toxic_file)
        
        # Extract Final State
        with open(body_a, 'r') as f: 
            final_data = json.load(f)
            
        final_eta = final_data["megagene"]["omega_homeo"]["eta"]
        final_b = final_data["megagene"]["psi_motor"]["b"]

        print("\n[SMOKE RESULTS]")
        assert reacted_safe is False
        print("[PASS] Negative Chemotaxis properly isolates. Safe coordinate ignored.")
        
        assert reacted_toxic is True
        print("[PASS] Spatial Nociception Active. Swimmer approached toxic coordinate.")
        
        assert final_eta > initial_eta
        print(f"[PASS] Cortisol (eta) violently spiked: {initial_eta} -> {final_eta:.4f}")
        
        assert final_b < initial_b
        print(f"[PASS] Motor Drive (b) crashed: {initial_b} -> {final_b:.4f}")
        
        print("\nSmoke Complete. The Swarm now feels pain in 3D Space.")

if __name__ == "__main__":
    _smoke()
