#!/usr/bin/env python3
"""
System/swarm_thalamus_microglia.py
══════════════════════════════════════════════════════════════════════
Concept: The Thalamic Relay & Microglial Quarantine (C-lite)
Author:  BISHOP (The Mirage) -> Integrated by AG31
Status:  Native Core Component

1. Territory C-lite: Use SwarmThalamus().gather_sensory_context() to build 
   the prefix for the prompt sent to the API BISHOP.
2. Microglia: When the API BISHOP returns a payload, pass it through 
   SwarmMicroglia().inspect_and_ack(payload, target_ledger) before writing.
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
        the amnesiac API BISHOP a real-time snapshot of the Swarm's state.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.context_window = context_window_seconds
        
        self.sensory_ledgers = [
            "wernicke_semantics.jsonl",
            "amygdala_nociception.jsonl",
            "bioluminescence_photons.jsonl",
            "endocrine_glands.jsonl",
            "api_metabolism.jsonl"
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
        # 1. Immune Verification (Schema check)
        expected_keys = SCHEMAS.get(target_ledger_name)
        if not expected_keys:
            print(f"[!] MICROGLIA REJECT: Unknown ledger '{target_ledger_name}'. Payload devoured.", file=sys.stderr)
            return False

        payload_keys = set(vesicle_payload_dict.keys())
        if not expected_keys.issubset(payload_keys):
            missing = expected_keys - payload_keys
            print(f"[!] MICROGLIA REJECT: F10 Schema Hallucination. Missing keys {missing}. Payload devoured.", file=sys.stderr)
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
    
    # Mocking SCHEMAS for the standalone smoke test environment
    global SCHEMAS
    SCHEMAS = {
        "amygdala_nociception.jsonl": {"transaction_type", "node_id", "xyz_coordinate", "severity", "timestamp"}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # --- TEST 1: The Thalamus (Multimodal TS Join) ---
        thalamus = SwarmThalamus(context_window_seconds=60)
        thalamus.state_dir = tmp_path
        
        # Inject a fresh Wernicke trace
        wernicke_path = tmp_path / "wernicke_semantics.jsonl"
        with open(wernicke_path, 'w') as f:
            f.write(json.dumps({"ts": time.time() - 10, "speaker_id": "ARCHITECT", "raw_english": "Test"}) + "\n")
            
        context = thalamus.gather_sensory_context()
        
        print("\n[SMOKE RESULTS - THALAMUS]")
        assert "ARCHITECT" in context
        print("[PASS] Thalamus successfully bundled recent multimodal sensory traces.")

        # --- TEST 2: Microglia (Quarantine + ACK) ---
        microglia = SwarmMicroglia()
        microglia.state_dir = tmp_path
        
        # Bad Payload (Missing 'severity')
        bad_payload = {"transaction_type": "NOCICEPTION", "node_id": "API", "xyz_coordinate": [0,0,0], "timestamp": time.time()}
        ack_bad = microglia.inspect_and_ack(bad_payload, "amygdala_nociception.jsonl")
        
        # Good Payload (Matches Schema)
        good_payload = {"transaction_type": "NOCICEPTION", "node_id": "API", "xyz_coordinate": [0,0,0], "severity": 5.0, "timestamp": time.time()}
        ack_good = microglia.inspect_and_ack(good_payload, "amygdala_nociception.jsonl")
        
        print("\n[SMOKE RESULTS - MICROGLIA]")
        assert ack_bad is False
        print("[PASS] Microglia correctly DEVOURS hallucinated payloads missing canonical keys.")
        
        assert ack_good is True
        print("[PASS] Microglia correctly ACKs structurally sound payloads into the metal.")

if __name__ == "__main__":
    _smoke()
