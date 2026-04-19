import os
import json
import time
import math
import hashlib
import sys
from pathlib import Path

# AG31 binds the physical repository for the lock primitive directly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_text_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)


class StigmergicArbitration:
    def __init__(self):
        """
        The SIFTA Swarm Executive Contract.
        Reads canonical producer traces and outputs one deterministic
        Canonical Action and one Effective Multiplier.

        AG31 F10 Fix: Reads the EXACT schemas the producers actually write.
          Amygdala: {node_id, severity, xyz_coordinate, timestamp}
          Quorum:   {node_id, xyz_coordinate, timestamp}  (no 'luminescence')
          Endocrine: {swimmer_id, potency, duration_seconds, timestamp}

        AG31 F9b Fix: All reads use read_text_locked, not raw open().
        """
        self.state_dir = Path(".sifta_state")
        self.endocrine_ledger = self.state_dir / "endocrine_glands.jsonl"
        self.amygdala_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.quorum_ledger = self.state_dir / "bioluminescence_photons.jsonl"

        # Temporal decay windows (match canonical producer values)
        self.endocrine_validity_s = 120.0   # endocrine duration_seconds default
        self.amygdala_validity_s = 900.0    # amygdala: 15 minute decay
        self.quorum_validity_s = 300.0      # quorum: 5 minute photon decay
        self.quorum_radius = 3.0            # match quorum_sensing default

    def _map_territory_to_vector(self, file_path):
        """Standardized Entorhinal 3D Mapping (same as amygdala/quorum producers)."""
        hash_bytes = hashlib.sha256(file_path.encode('utf-8')).digest()
        x = (int.from_bytes(hash_bytes[0:4], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(hash_bytes[4:8], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(hash_bytes[8:12], 'big') / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def _calculate_distance(self, coord_a, coord_b):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(coord_a, coord_b)))

    def _read_endocrine_potency(self, swimmer_id):
        """
        Reads endocrine_glands.jsonl for active adrenaline targeting this swimmer.
        Canonical schema: {swimmer_id, potency, duration_seconds, timestamp}
        """
        text = read_text_locked(self.endocrine_ledger)
        if not text:
            return 0.0

        now = time.time()
        max_potency = 0.0

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                trace = json.loads(line)
                age = now - trace.get("timestamp", 0)
                duration = trace.get("duration_seconds", self.endocrine_validity_s)
                if age > duration:
                    continue

                # Match by swimmer_id (canonical endocrine field)
                if trace.get("swimmer_id") == swimmer_id or trace.get("swimmer_id") == "GLOBAL":
                    potency = trace.get("potency", 0.0)
                    if potency > max_potency:
                        max_potency = potency
            except json.JSONDecodeError:
                continue

        return max_potency

    def _read_fear_intensity(self, swimmer_xyz):
        """
        Reads amygdala_nociception.jsonl using 3D proximity + inverse-square law.
        Canonical schema: {node_id, severity, xyz_coordinate, timestamp}
        Matches the amygdala's own sense_and_react physics exactly.
        """
        text = read_text_locked(self.amygdala_ledger)
        if not text:
            return 0.0

        now = time.time()
        total_fear = 0.0

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                trace = json.loads(line)
                age = now - trace.get("timestamp", 0)
                if age > self.amygdala_validity_s:
                    continue

                fear_xyz = trace.get("xyz_coordinate", [0, 0, 0])
                dist = self._calculate_distance(swimmer_xyz, fear_xyz)
                severity = trace.get("severity", 1.0)
                # Inverse-square: same decay law as amygdala.sense_and_react
                intensity = severity / (1.0 + (dist ** 2))
                total_fear += intensity
            except json.JSONDecodeError:
                continue

        return total_fear

    def _read_quorum_density(self, swimmer_xyz):
        """
        Reads bioluminescence_photons.jsonl using 3D proximity photon count.
        Canonical schema: {node_id, xyz_coordinate, timestamp}
        There is NO 'luminescence' field. Density = photon count within radius.
        Matches quorum_sensing's own check_quorum_and_illuminate physics.
        """
        text = read_text_locked(self.quorum_ledger)
        if not text:
            return 0.0

        now = time.time()
        local_photons = 0

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                trace = json.loads(line)
                age = now - trace.get("timestamp", 0)
                if age > self.quorum_validity_s:
                    continue

                photon_xyz = trace.get("xyz_coordinate", [0, 0, 0])
                dist = self._calculate_distance(swimmer_xyz, photon_xyz)
                if dist <= self.quorum_radius:
                    local_photons += 1
            except json.JSONDecodeError:
                continue

        return float(local_photons)

    def compute_effective_multiplier(self, swimmer_id, target_file):
        """
        Compiles the true thermodynamic multiplier from all conflicting signals.
        AG31 F10 Fix: Requires target_file for 3D positional reads.
        """
        swimmer_xyz = self._map_territory_to_vector(target_file)

        endocrine_adr = self._read_endocrine_potency(swimmer_id)
        fear_intensity = self._read_fear_intensity(swimmer_xyz)
        quorum_density = self._read_quorum_density(swimmer_xyz)

        # Mathematical Arbitrator Weights
        multiplier = (
            1.0
            + (endocrine_adr * 0.5)
            - (fear_intensity * 0.4)
            + (quorum_density * 0.2)
        )

        # Physics Boundary: Multiplier cannot drop below 0.1 (Cryptobiosis threshold)
        return max(0.1, multiplier)

    def resolve_action(self, swimmer_id, target_file, potential_actions):
        """
        Resolves conflicting Swarm logic into a single deterministic action.
        potential_actions: {"escape": base_val, "cooperate": base_val, "sprint": base_val}
        """
        swimmer_xyz = self._map_territory_to_vector(target_file)

        endocrine_adr = self._read_endocrine_potency(swimmer_id)
        fear_intensity = self._read_fear_intensity(swimmer_xyz)
        quorum_density = self._read_quorum_density(swimmer_xyz)

        scored = []
        for action, base_score in potential_actions.items():
            if action == "escape":
                score = base_score + (fear_intensity * 0.8) - (quorum_density * 0.5)
            elif action == "cooperate":
                score = base_score + (quorum_density * 0.8) - (fear_intensity * 0.5)
            elif action == "sprint":
                score = base_score + (endocrine_adr * 0.8) - (fear_intensity * 0.3)
            else:
                score = base_score

            scored.append((score, action))

        return max(scored)[1]


# --- SUBSTRATE TEST ANCHOR (THE ARBITRATION SMOKE) ---
def _smoke():
    """
    AG31 Mirror-Defect Fix: Smoke test seeds data using the EXACT canonical
    producer schemas, not invented fields. The test proves the arbitrator
    can read what the real amygdala, quorum, and endocrine actually write.
    """
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
        target_file = "System/contested_module.py"
        target_xyz = arbitrator._map_territory_to_vector(target_file)
        now = time.time()

        # 1. Seed CANONICAL Amygdala trace (node_id, severity, xyz_coordinate)
        # Fear pheromone dropped AT the swimmer's exact location → max intensity
        amygdala_trace = json.dumps({
            "transaction_type": "FEAR_PHEROMONE",
            "node_id": "NODE_X",
            "xyz_coordinate": target_xyz,
            "severity": 5.0,
            "timestamp": now
        }) + "\n"
        append_line_locked(arbitrator.amygdala_ledger, amygdala_trace)

        # 2. Seed CANONICAL Endocrine trace (swimmer_id, potency, duration_seconds)
        endocrine_trace = json.dumps({
            "transaction_type": "ENDOCRINE_FLOOD",
            "hormone": "EPINEPHRINE_ADRENALINE",
            "swimmer_id": swimmer_id,
            "potency": 8.0,
            "duration_seconds": 120,
            "timestamp": now
        }) + "\n"
        append_line_locked(arbitrator.endocrine_ledger, endocrine_trace)

        # 3. Seed CANONICAL Quorum trace (node_id, xyz_coordinate)
        # Two photons at the swimmer's exact location
        for qnode in ["AG31", "C47H"]:
            quorum_trace = json.dumps({
                "transaction_type": "PHOTON_EMISSION",
                "node_id": qnode,
                "xyz_coordinate": target_xyz,
                "timestamp": now
            }) + "\n"
            append_line_locked(arbitrator.quorum_ledger, quorum_trace)

        # 4. Compute Effective Multiplier
        # Endocrine: potency=8.0 → 8.0 * 0.5 = 4.0
        # Fear: severity=5.0 at distance=0 → intensity = 5.0/(1+0) = 5.0 → 5.0 * 0.4 = 2.0
        # Quorum: 2 photons within radius → 2.0 * 0.2 = 0.4
        # Total: 1.0 + 4.0 - 2.0 + 0.4 = 3.4
        multiplier = arbitrator.compute_effective_multiplier(swimmer_id, target_file)

        print("\n[SMOKE RESULTS]")
        print(f"[*] Endocrine potency read: {arbitrator._read_endocrine_potency(swimmer_id)}")
        print(f"[*] Fear intensity read: {arbitrator._read_fear_intensity(target_xyz):.2f}")
        print(f"[*] Quorum density read: {arbitrator._read_quorum_density(target_xyz):.0f}")
        print(f"[*] Calculated Effective Multiplier: {multiplier:.2f}")
        assert abs(multiplier - 3.4) < 0.001, f"Expected 3.4, got {multiplier}"
        print("[PASS] All three lobes LIVE. Canonical producer schemas consumed correctly.")

        # 5. Resolve Action
        actions = {"escape": 1.0, "cooperate": 1.0, "sprint": 1.0}
        victorious = arbitrator.resolve_action(swimmer_id, target_file, actions)

        print(f"[*] Victorious Executable Action: {victorious}")
        # Escape = 1.0 + (5.0 * 0.8) - (2.0 * 0.5) = 1.0 + 4.0 - 1.0 = 4.0
        # Cooperate = 1.0 + (2.0 * 0.8) - (5.0 * 0.5) = 1.0 + 1.6 - 2.5 = 0.1
        # Sprint = 1.0 + (8.0 * 0.8) - (5.0 * 0.3) = 1.0 + 6.4 - 1.5 = 5.9
        assert victorious == "sprint", f"Expected sprint, got {victorious}"
        print("[PASS] Deterministic trajectory resolved. Adrenaline + Fear = Sprint (not Escape).")

        print("\nArbitration Contract deployed. All three lobes wired to canonical producers.")


if __name__ == "__main__":
    _smoke()
