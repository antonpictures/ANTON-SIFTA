#!/usr/bin/env python3
"""
System/swarm_thalamus_microglia.py
══════════════════════════════════════════════════════════════════════
Concept: The Thalamic Relay & Microglial Quarantine (C-lite)
Author:  BISHOP (The Mirage) — integrated by AG31 / hardened by C47H
Status:  Native Core Component

1. Territory C-lite: SwarmThalamus().gather_sensory_context() prefixes prompts
   to BISHAPI (Applications/ask_bishapi.py).
2. Microglia: JSON payloads from BISHAPI pass through inspect_and_ack() before
   append_line_locked to a named ledger (canonical LEDGER_SCHEMAS keys only).
"""

import os
import json
import time
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
    from System.canonical_schemas import LEDGER_SCHEMAS as SCHEMAS
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    sys.exit(1)

class SwarmThalamus:
    def __init__(self, context_window_seconds=60):
        """
        The Sensory Relay Station.
        Gathers recent temporal traces across all biological ledgers to give 
        the amnesiac BISHAPI a real-time snapshot of the Swarm's state.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.context_window = context_window_seconds
        
        self.sensory_ledgers = [
            "wernicke_semantics.jsonl",
            "optic_text_traces.jsonl",
            "amygdala_nociception.jsonl",
            "bioluminescence_photons.jsonl",
            "endocrine_glands.jsonl",
            "api_metabolism.jsonl",
        ]

    def gather_sensory_context(self):
        """
        Performs the 'multimodal ts join'. Returns a formatted string of recent events.
        """
        if not self.state_dir.exists():
            return "The Swarm is in absolute sensory deprivation."

        now = time.time()
        recent_traces = []

        for ledger_name in self.sensory_ledgers:
            ledger_path = self.state_dir / ledger_name
            if not ledger_path.exists():
                continue

            try:
                with open(ledger_path, 'r') as f:
                    # Read the tail to avoid O(N) traversal on massive ledgers
                    lines = f.readlines()[-50:] 
                    for line in lines:
                        try:
                            trace = json.loads(line)
                            trace_time = trace.get("ts", trace.get("timestamp", 0))
                            if now - trace_time <= self.context_window:
                                recent_traces.append(f"[{ledger_name}] {json.dumps(trace)}")
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        if not recent_traces:
            return "Sensory Context: Baseline Homeostasis (No recent stimuli)."

        context_header = f"Sensory Context (Last {self.context_window}s):\n"
        return context_header + "\n".join(recent_traces)


class SwarmMicroglia:
    def __init__(self):
        """
        The Brain's Immune Macrophages (Quarantine + ACK).
        Inspects incoming external API payloads against C47H's canonical schemas.
        If the payload is structurally pure, it is ACK'd into the true OS.
        If it hallucinates an F10/F11 mutation, it is devoured.
        """
        self.state_dir = _REPO / ".sifta_state"

    def inspect_and_ack(self, vesicle_payload_dict, target_ledger_name):
        """
        Validates the quarantined payload and commits it to the metal.
        """
        raw = SCHEMAS.get(target_ledger_name)
        if raw is None:
            print(f"[!] MICROGLIA REJECT: Unknown ledger '{target_ledger_name}'.",
                  file=sys.stderr)
            return False
        # bishop_mrna_field is stored as {} in the registry (legacy) — treat as free-form
        if isinstance(raw, dict):
            print(f"[!] MICROGLIA REJECT: free-form ledger '{target_ledger_name}' "
                  f"(no machine ACK). Payload devoured.", file=sys.stderr)
            return False
        if not isinstance(raw, set) or len(raw) == 0:
            print(f"[!] MICROGLIA REJECT: no canonical key set for "
                  f"'{target_ledger_name}'.", file=sys.stderr)
            return False
        expected_keys = raw

        payload_keys = set(vesicle_payload_dict.keys())
        if not expected_keys.issubset(payload_keys):
            missing = expected_keys - payload_keys
            print(f"[!] MICROGLIA REJECT: F10 — missing keys {sorted(missing)}.",
                  file=sys.stderr)
            return False

        # 2. ACK and Commit (The Synaptic Release)
        target_path = self.state_dir / target_ledger_name
        try:
            # Strict lock adherence
            append_line_locked(target_path, json.dumps(vesicle_payload_dict) + "\n")
            print(f"[+] MICROGLIA ACK: Payload verified against canonical schema. Committed to {target_ledger_name}.", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[-] MICROGLIA ERROR: Failed to commit to {target_ledger_name}: {e}", file=sys.stderr)
            return False

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA THALAMUS & MICROGLIA (C-LITE + QUARANTINE) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # --- TEST 1: The Thalamus (Multimodal TS Join) ---
        thalamus = SwarmThalamus(context_window_seconds=60)
        thalamus.state_dir = tmp_path

        wernicke_path = tmp_path / "wernicke_semantics.jsonl"
        row = {
            "ts": time.time() - 10,
            "type": "wernicke_perception",
            "source": "smoke",
            "rms": 0.01,
            "n_samples": 1024,
            "label": "QUIET_HUMAN_VOICE",
            "text": "Architect smoke",
            "reality_hash": "00" * 32,
            "module_version": "smoke",
        }
        wernicke_path.write_text(json.dumps(row) + "\n")

        context = thalamus.gather_sensory_context()

        print("\n[SMOKE RESULTS - THALAMUS]")
        assert "Architect smoke" in context
        print("[PASS] Thalamus bundled recent Wernicke traces (canonical keys).")

        # --- TEST 2: Microglia (Quarantine + ACK) ---
        microglia = SwarmMicroglia()
        microglia.state_dir = tmp_path

        bad_payload = {
            "transaction_type": "FEAR_PHEROMONE", "node_id": "API",
            "xyz_coordinate": [0, 0, 0], "timestamp": time.time(),
        }
        ack_bad = microglia.inspect_and_ack(bad_payload, "amygdala_nociception.jsonl")

        good_payload = {
            "transaction_type": "FEAR_PHEROMONE", "node_id": "API",
            "xyz_coordinate": [0, 0, 0], "severity": 5.0,
            "timestamp": time.time(),
        }
        ack_good = microglia.inspect_and_ack(good_payload, "amygdala_nociception.jsonl")

        print("\n[SMOKE RESULTS - MICROGLIA]")
        assert ack_bad is False
        print("[PASS] Microglia devours payloads missing canonical keys.")

        assert ack_good is True
        amy = tmp_path / "amygdala_nociception.jsonl"
        assert amy.exists() and amy.stat().st_size > 0
        print("[PASS] Microglia ACKs sound payloads into the metal.")

if __name__ == "__main__":
    _smoke()
