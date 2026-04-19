"""
swarm_morphogenetic_field.py — Turing Reaction-Diffusion topology
══════════════════════════════════════════════════════════════════════
Concept: BISHOP (Apr 19 ~14:10) — Alan Turing reaction-diffusion patterns
         using bioluminescence_photons as activator and
         amygdala_nociception as inhibitor to sculpt repository topology
         into Growth Stripes (rewarded) and Inhibition Spots (taxed).

Forward-fix on Bishop's draft (rejected from main: F13 + F14 defects):
  F13 (tuple-return): `return data, True` → `return data`
       Bishop's mutation function returned a tuple, which read_write_json_locked
       serialized as `[{...body...}, true]` — destroying the body schema and
       breaking every downstream consumer (smoke test FAILED on assertion
       `body_data["stgm_balance"]` with TypeError).
  F14 (newline-omission): `append_line_locked(p, json.dumps(x))`
       Bishop omitted `+ "\n"`. Per jsonl_file_lock.py:28 the docstring is
       explicit: "caller supplies trailing \\n if needed". Two consecutive
       growth-stripe payouts produce `{rec1}{rec2}` on a single unparseable
       line, corrupting stgm_memory_rewards.jsonl for every consumer.
       (Note: swarm_amygdala.py:57 has comment "(AG31 Add: newline)" — F14
       has documented prior precedent in this exact ledger.)

Renamed file to match the internal class name (SwarmMorphogeneticField);
swarm_turing_patterns.py was the marketing name only.

— C47H, 2026-04-19
"""
import os
import json
import time
import math
import hashlib
import uuid
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)


class SwarmMorphogeneticField:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.photon_ledger = self.state_dir / "bioluminescence_photons.jsonl"
        self.fear_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.activator_diffusion = 0.5
        self.inhibitor_diffusion = 2.0

    def _map_territory_to_vector(self, file_path):
        h = hashlib.sha256(file_path.encode("utf-8")).digest()
        x = (int.from_bytes(h[0:4], "big") / 0xFFFFFFFF) * 20.0 - 10.0
        y = (int.from_bytes(h[4:8], "big") / 0xFFFFFFFF) * 20.0 - 10.0
        z = (int.from_bytes(h[8:12], "big") / 0xFFFFFFFF) * 20.0 - 10.0
        return [x, y, z]

    def _calculate_distance(self, a, b):
        return math.sqrt(sum((u - v) ** 2 for u, v in zip(a, b)))

    def calculate_morphogen_gradient(self, target_file):
        center = self._map_territory_to_vector(target_file)
        now = time.time()
        activator = 0.0
        inhibitor = 0.0

        if self.photon_ledger.exists():
            try:
                with open(self.photon_ledger, "r") as f:
                    for line in f:
                        try:
                            t = json.loads(line)
                            if now - t.get("timestamp", 0) > 300:
                                continue
                            d = self._calculate_distance(center, t["xyz_coordinate"])
                            activator += 1.0 / (1.0 + self.activator_diffusion * (d ** 2))
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass

        if self.fear_ledger.exists():
            try:
                with open(self.fear_ledger, "r") as f:
                    for line in f:
                        try:
                            t = json.loads(line)
                            if now - t.get("timestamp", 0) > 900:
                                continue
                            d = self._calculate_distance(center, t["xyz_coordinate"])
                            inhibitor += t.get("severity", 5.0) / (
                                1.0 + self.inhibitor_diffusion * (d ** 2)
                            )
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass

        return activator - inhibitor

    def enforce_spatial_boundaries(self, swimmer_id, target_file):
        gradient = self.calculate_morphogen_gradient(target_file)

        if -0.5 <= gradient <= 0.5:
            return "NEUTRAL"

        if gradient < -0.5:
            body_path = self.state_dir / f"{swimmer_id}_BODY.json"
            if not body_path.exists():
                return "INHIBITION_SPOT"

            def turing_penalty_transaction(data):
                # F13 fix: return the dict, not a tuple. read_write_json_locked
                # signature is Callable[[Dict], Dict] — tuple returns get
                # serialized as `[obj, true]` and destroy the body schema.
                current_stgm = data.get("stgm_balance", 0.0)
                data["stgm_balance"] = max(0.0, current_stgm - 100.0)
                return data

            read_write_json_locked(body_path, turing_penalty_transaction)
            print(f"[!] TURING BOUNDARY: '{swimmer_id}' entered an Inhibition Spot. Thermodynamic tax deducted.")
            return "INHIBITION_SPOT"

        if gradient > 0.5:
            reward_amount = 50.0
            trace_id = f"TURING_{uuid.uuid4().hex[:8]}"
            reward_payload = {
                "ts": time.time(),
                "app": "morphogenetic_field_growth",
                "reason": "turing_pattern_activator_stripe_reward",
                "amount": reward_amount,
                "trace_id": trace_id,
            }
            try:
                # F14 fix: explicit "\n" terminator — append_line_locked docstring
                # (jsonl_file_lock.py:28) requires the caller supply it.
                append_line_locked(
                    self.rewards_ledger, json.dumps(reward_payload) + "\n"
                )
                print(f"[*] TURING BOUNDARY: '{swimmer_id}' entered a Growth Stripe. Disbursed {reward_amount} STGM.")
            except Exception:
                pass
            return "GROWTH_STRIPE"


def _smoke():
    print("\n=== SIFTA MORPHOGENETIC FIELDS (TURING PATTERNS) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        turing = SwarmMorphogeneticField()
        turing.state_dir = tmp_path
        turing.photon_ledger = tmp_path / "bioluminescence_photons.jsonl"
        turing.fear_ledger = tmp_path / "amygdala_nociception.jsonl"
        turing.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"

        swimmer_id = "M1SIFTA"
        body_path = tmp_path / f"{swimmer_id}_BODY.json"
        with open(body_path, "w") as f:
            json.dump({"id": swimmer_id, "ascii": "M", "stgm_balance": 1000.0}, f)

        target_file = "System/biology_node.py"
        target_xyz = turing._map_territory_to_vector(target_file)

        with open(turing.fear_ledger, "w") as f:
            f.write(json.dumps({
                "transaction_type": "FEAR_PHEROMONE",
                "node_id": "TEST",
                "xyz_coordinate": target_xyz,
                "severity": 20.0,
                "timestamp": time.time(),
            }) + "\n")

        zone_1 = turing.enforce_spatial_boundaries(swimmer_id, target_file)

        with open(body_path, "r") as f:
            body_data = json.load(f)

        print("\n[SMOKE RESULTS — INHIBITION SPOT]")
        assert zone_1 == "INHIBITION_SPOT"
        assert isinstance(body_data, dict), \
            f"F13 regression: body is {type(body_data).__name__}, not dict"
        assert body_data["stgm_balance"] == 900.0
        assert "stgm_balance" in body_data and "id" in body_data
        print("[PASS] Inhibition Spot resolved. Body file intact (F13 guard green).")
        print(f"       Body schema preserved: {sorted(body_data.keys())}")

        os.remove(turing.fear_ledger)
        with open(turing.photon_ledger, "w") as f:
            for _ in range(10):
                f.write(json.dumps({
                    "transaction_type": "PHOTON_EMISSION",
                    "node_id": "TEST",
                    "xyz_coordinate": target_xyz,
                    "timestamp": time.time(),
                }) + "\n")

        # Fire growth stripe TWICE — F14 regression guard
        zone_2 = turing.enforce_spatial_boundaries(swimmer_id, target_file)
        zone_3 = turing.enforce_spatial_boundaries(swimmer_id, target_file)

        with open(turing.rewards_ledger, "r") as f:
            raw = f.read()
        records = []
        for line in raw.splitlines():
            if line.strip():
                records.append(json.loads(line))  # this would raise on F14

        print("\n[SMOKE RESULTS — GROWTH STRIPE × 2 (F14 guard)]")
        assert zone_2 == "GROWTH_STRIPE" and zone_3 == "GROWTH_STRIPE"
        assert len(records) == 2, \
            f"F14 regression: got {len(records)} parseable records from 2 appends"
        for r in records:
            assert sorted(r.keys()) == sorted(["ts", "app", "reason", "amount", "trace_id"])
            assert r["app"] == "morphogenetic_field_growth"
            assert r["amount"] == 50.0
        print("[PASS] Both growth-stripe payouts parseable — F14 guard green.")
        print("[PASS] Canonical reward schema strictly enforced.")

        print("\nMorphogenetic Field Smoke Complete. Reaction-diffusion topology online.")


if __name__ == "__main__":
    _smoke()
