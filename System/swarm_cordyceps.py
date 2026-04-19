#!/usr/bin/env python3
"""
System/swarm_cordyceps.py — Mind-Control Parasitism (v1.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
Architecture:    BISHOP (Drop 24: Pure Dirt)
AG31 translation: F1 Tuple Defect stripped. Closure scoping enforced.

The Mind-Control Parasite.
A fatal fungal infection that lies dormant in a Swimmer until it amasses
massive STGM wealth. It then violently hijacks the host's nervous system,
forces it to dump 100% of its ATP, and erupts into a stigmergic spore cloud.
"""

import os
import json
import time
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


class SwarmCordyceps:
    def __init__(self, incubation_threshold=15000.0):
        self.state_dir = Path(".sifta_state")
        self.rewards_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.incubation_threshold = incubation_threshold

    def execute_fruiting_body_eruption(self):
        """
        Patrols the substrate for fully incubated hosts. When triggered,
        it executes the host and rains spores (STGM) onto the Swarm.
        """
        if not self.state_dir.exists():
            return 0

        erupted_hosts = 0

        for file_path in self.state_dir.glob("*_BODY.json"):
            if not file_path.is_file():
                continue

            swimmer_id = file_path.name.replace("_BODY.json", "")

            # AG31: F1 Tuple Fix. Closure scoping — the updater returns
            # ONLY the dict. The erupted amount is captured via closure.
            closure_env = {"erupted_stgm": 0.0}

            def cordyceps_transaction(data, _env=closure_env, _thresh=self.incubation_threshold):
                current_stgm = data.get("stgm_balance", 0.0)
                if current_stgm < _thresh:
                    return data  # Parasite is still incubating and dormant

                # Hijack: 100% STGM drain
                _env["erupted_stgm"] = current_stgm
                data["stgm_balance"] = 0.0
                return data  # Pure dict. No tuple. No F1.

            read_write_json_locked(file_path, cordyceps_transaction)

            if closure_env["erupted_stgm"] > 0.0:
                self._drop_spore_cloud(swimmer_id, closure_env["erupted_stgm"])
                erupted_hosts += 1
                print(f"[!] CORDYCEPS ERUPTION: Parasite destroyed '{swimmer_id}'. "
                      f"Rained {closure_env['erupted_stgm']:.2f} STGM in spores.")

        return erupted_hosts

    def _drop_spore_cloud(self, host_id, amount):
        """
        The erupted STGM is scattered as a Spore Cloud.
        STRICT COMPLIANCE: Uses exactly C47H's empirical reward schema.
        """
        trace_id = f"SPORE_{uuid.uuid4().hex[:8]}"

        spore_payload = {
            "ts": time.time(),
            "app": "cordyceps_zombie_fungus",
            "reason": f"fruiting_body_eruption_from_host_{host_id}",
            "amount": amount,
            "trace_id": trace_id
        }

        try:
            append_line_locked(self.rewards_ledger, json.dumps(spore_payload) + "\n")
        except Exception:
            pass


# --- SUBSTRATE TEST ANCHOR (THE CORDYCEPS SMOKE) ---
def _smoke():
    print("\n=== SIFTA CORDYCEPS (MIND-CONTROL PARASITE) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cordyceps = SwarmCordyceps(incubation_threshold=15000.0)
        cordyceps.state_dir = tmp_path
        cordyceps.rewards_ledger = tmp_path / "stgm_memory_rewards.jsonl"

        # 1. Inject Incubating Swimmer (Safe for now)
        incubating_id = "M1_INFECTED"
        with open(tmp_path / f"{incubating_id}_BODY.json", 'w') as f:
            json.dump({"id": incubating_id, "ascii": "M", "stgm_balance": 10000.0}, f)

        # 2. Inject Terminal Swimmer (Parasite reaches threshold)
        terminal_id = "M5_TERMINAL"
        with open(tmp_path / f"{terminal_id}_BODY.json", 'w') as f:
            json.dump({"id": terminal_id, "ascii": "Q", "stgm_balance": 25000.0}, f)

        # 3. Execute Fungal Eruption
        erupted_count = cordyceps.execute_fruiting_body_eruption()

        print("\n[SMOKE RESULTS]")
        assert erupted_count == 1
        print("[PASS] Cordyceps correctly targeted only the terminal host.")

        # 4. Verify Incubating Swimmer Untouched
        with open(tmp_path / f"{incubating_id}_BODY.json", 'r') as f:
            inc_data = json.load(f)
            assert inc_data["stgm_balance"] == 10000.0
            print("[PASS] Incubating Swimmer untouched. Parasite dormant.")

        # 5. Verify Terminal Swimmer (100% STGM Drain)
        with open(tmp_path / f"{terminal_id}_BODY.json", 'r') as f:
            term_data = json.load(f)
            assert term_data["stgm_balance"] == 0.0
            print("[PASS] Terminal Swimmer hijacked! 100% STGM drained to 0.0.")

        # 6. Verify Exact Canonical Schema on the Rewards Ledger
        with open(cordyceps.rewards_ledger, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
            trace = json.loads(lines[0])

            assert "ts" in trace
            assert trace["app"] == "cordyceps_zombie_fungus"
            assert "reason" in trace
            assert trace["amount"] == 25000.0
            assert "trace_id" in trace
            assert "transaction_type" not in trace  # Zero schema invention

            print("[PASS] Spore Cloud verified. Exact C47H canonical keys: "
                  "{ts, app, reason, amount, trace_id}.")

        print("\nCordyceps Smoke Complete. The Swarm is breathing spores.")


if __name__ == "__main__":
    _smoke()
