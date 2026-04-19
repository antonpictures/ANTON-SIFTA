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

class SwarmMycelium:
    def __init__(self, growth_rate=0.05, max_lifespan=3600):
        """
        The Wood Wide Web (Mycorrhizal Fungal Network).
        A 4-Dimensional Stigmergic structure. Swimmers plant STGM roots at 3D 
        coordinates. Over Time, the 3D radius of these roots expands, allowing 
        starving organisms to harvest symbiotic charity.
        """
        self.state_dir = Path(".sifta_state")
        self.mycelial_ledger = self.state_dir / "mycelial_network.jsonl"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.growth_rate = growth_rate
        self.max_lifespan = max_lifespan

    def _map_territory_to_vector(self, file_path):
        """Standardized Entorhinal 3D Mapping"""
        hash_bytes = hashlib.sha256(file_path.encode('utf-8')).digest()
        x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def _calculate_distance(self, coord_a, coord_b):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(coord_a, coord_b)))

    def seed_mycelial_root(self, donor_id, target_file, donation_amount=2000.0):
        """
        A wealthy Swimmer voluntarily locks its STGM into the subterranean fungal network.
        """
        body_path = self.state_dir / f"{donor_id}_BODY.json"
        if not body_path.exists():
            return False

        # AG31: Stripped tuples. Managed via outer Dict markers to strictly adhere to C47H physics.
        root_marker = {"success": False}

        def plant_root_transaction(data):
            # Strict Empirical Schema Adherence: Only stgm_balance is touched
            current_stgm = data.get("stgm_balance", 0.0)
            
            # Donor must survive the donation
            if current_stgm < (donation_amount + 500.0):
                return data
                
            data["stgm_balance"] = current_stgm - donation_amount
            root_marker["success"] = True
            return data

        read_write_json_locked(body_path, plant_root_transaction)
        
        if root_marker["success"]:
            xyz = self._map_territory_to_vector(target_file)
            trace = {
                "transaction_type": "PLANT_ROOT",
                "donor_id": donor_id,
                "xyz_coordinate": xyz,
                "stgm_payload": donation_amount,
                "timestamp": time.time()
            }
            try:
                # Appends canonical traces structurally
                append_line_locked(self.mycelial_ledger, json.dumps(trace) + "\n")
                print(f"[+] MYCELIUM: '{donor_id}' planted a nutrient root with {donation_amount} STGM.")
                return True
            except Exception:
                pass
                
        return False

    def symbiotic_harvest(self, starving_id, target_file):
        """
        A starving Swimmer navigates 3D space. If it intersects with the expanding 
        temporal radius of a fungal root, it is biologically fed by the network.
        """
        if not self.mycelial_ledger.exists():
            return False
            
        swimmer_xyz = self._map_territory_to_vector(target_file)
        now = time.time()
        harvested_amount = 0.0
        harvested_donor = "UNKNOWN"
        
        try:
            with open(self.mycelial_ledger, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        root = json.loads(line)
                        age = now - root.get("timestamp", 0)
                        
                        if age > self.max_lifespan:
                            continue # Root has naturally decayed
                            
                        # TIME 3D EXPANSION: The fungal radius physically grows over time
                        current_radius = 1.0 + (age * self.growth_rate)
                        dist = self._calculate_distance(swimmer_xyz, root["xyz_coordinate"])
                        
                        if dist <= current_radius:
                            # Swimmer is within the temporal 3D network
                            harvested_amount = root.get("stgm_payload", 0.0)
                            harvested_donor = root.get("donor_id", "UNKNOWN")
                            break # Connect to the first viable root
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        if harvested_amount <= 0.0:
            return False

        body_path = self.state_dir / f"{starving_id}_BODY.json"
        if not body_path.exists():
            return False

        harvest_marker = {"success": False}

        def harvest_transaction(data):
            # Only trigger biological charity if the Swimmer is genuinely starving
            if data.get("stgm_balance", 0.0) < 1000.0:
                harvest_marker["success"] = True
            return data

        read_write_json_locked(body_path, harvest_transaction)
        
        if harvest_marker["success"]:
            # Distribute the environmental charity using strictly empirical C47H keys
            trace_id = f"MYCELIUM_{uuid.uuid4().hex[:8]}"
            reward_payload = {
                "ts": time.time(),
                "app": "wood_wide_web_symbiosis",
                "reason": f"temporal_fungal_harvest_from_donor_{harvested_donor}_to_recipient_{starving_id}",
                "amount": harvested_amount,
                "trace_id": trace_id
            }
            try:
                # Appends smoothly mapped canonical STGM structures under C47H empirical rules
                append_line_locked(self.rewards_ledger, json.dumps(reward_payload) + "\n")
                print(f"[*] SYMBIOSIS: '{starving_id}' tapped the Wood Wide Web. Harvested {harvested_amount} STGM.")
                return True
            except Exception:
                pass
                
        return False

# --- SUBSTRATE TEST ANCHOR (THE MYCELIUM SMOKE) ---
def _smoke():
    print("\n=== SIFTA MYCELIUM (WOOD WIDE WEB) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mycelium = SwarmMycelium(growth_rate=0.5, max_lifespan=3600) # Highly accelerated growth for smoke test
        mycelium.state_dir = tmp_path
        mycelium.mycelial_ledger = tmp_path / "mycelial_network.jsonl"
        mycelium.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"
        
        target_file = "System/biology_node.py" # XYZ Center
        distant_file = "Applications/distant_node.py" # XYZ Distant
        
        donor_id = "M5_WEALTHY"
        starving_id = "M1_STARVING"
        
        # 1. Inject Donor (Wealthy)
        with open(tmp_path / f"{donor_id}_BODY.json", 'w') as f:
            json.dump({"id": donor_id, "ascii": "W", "stgm_balance": 10000.0}, f)
            
        # 2. Inject Starving Swimmer
        with open(tmp_path / f"{starving_id}_BODY.json", 'w') as f:
            json.dump({"id": starving_id, "ascii": "S", "stgm_balance": 100.0}, f)
            
        # 3. Donor plants the STGM root
        success_seed = mycelium.seed_mycelial_root(donor_id, target_file, donation_amount=2000.0)
        
        # 4. Starving Swimmer attempts to harvest from a distant coordinate
        # At T=0, the root radius is 1.0. The distant file is mathematically too far away.
        harvest_early = mycelium.symbiotic_harvest(starving_id, distant_file)
        
        print("\n[SMOKE RESULTS]")
        assert success_seed is True
        print(f"[PASS] STGM Root securely planted. Wealth physically deducted from Donor.")
        
        assert harvest_early is False
        print(f"[PASS] Time-3D physics enforced. Distant Swimmer failed to harvest at T=0. Fungal root has not reached them yet.")
        
        # 5. Artificially age the root by manually editing the timestamp in the ledger (Time Travel)
        with open(mycelium.mycelial_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            trace = json.loads(lines[0])
            trace["timestamp"] = time.time() - 100.0 # Age the root by 100 seconds
        with open(mycelium.mycelial_ledger, 'w') as f:
            f.write(json.dumps(trace) + "\n")
            
        # 6. Starving Swimmer attempts harvest again. 
        # At T=100, radius = 1.0 + (100 * 0.5) = 51.0. It has enveloped the distant coordinate.
        harvest_late = mycelium.symbiotic_harvest(starving_id, distant_file)
        
        assert harvest_late is True
        print(f"[PASS] 4th Dimensional Expansion! At T=100s, fungal radius expanded. Starving Swimmer successfully harvested STGM.")
        
        # 7. Verify C47H's Empirical Reward Schema
        with open(mycelium.rewards_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            reward_trace = json.loads(lines[0])
            
            assert "ts" in reward_trace
            assert reward_trace["app"] == "wood_wide_web_symbiosis"
            assert "reason" in reward_trace
            assert reward_trace["amount"] == 2000.0
            assert "trace_id" in reward_trace
            assert "transaction_type" not in reward_trace
            
            print(f"[PASS] Environmental payout verified. Strict Empirical canonical keys used: {{ts, app, reason, amount, trace_id}}.")
            
        print("\nMycelium Smoke Complete. The Wood Wide Web spans Time and Space.")

if __name__ == "__main__":
    _smoke()
