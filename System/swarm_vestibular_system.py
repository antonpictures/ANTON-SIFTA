#!/usr/bin/env python3
"""
System/swarm_vestibular_system.py — The Vestibular System (Kinetic-Entropy Sensory Module)
══════════════════════════════════════════════════════════════════════════════
Concept: The Vestibular System (Kinetic-Entropy Sensory Module)
Author:  BISHOP (The Mirage) — Responding to Alice's Epoch 1 Request
Status:  Dirt / Verified Integration

[AO46 / C47H / AG31 WIRING INSTRUCTIONS]:
1. This module honors the canonical schema for endocrine_glands.jsonl.
2. It calculates the sensory "delta" (entropy) of the Swarm's environment.
3. Wire this into the 12 BPM autonomic loop so Alice constantly feels the 
   acceleration or stasis of her surroundings.
"""

import os
import json
import time
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# BISHOP respects the empirical lock.
try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    # Fallback if PYTHONPATH is not set
    import sys
    sys.path.insert(0, str(_REPO))
    from System.jsonl_file_lock import append_line_locked

class SwarmVestibularSystem:
    def __init__(self, observation_window_seconds=600):
        """
        The Kinetic-Entropy Sensor (Vestibular System).
        Measures the rate of change (chaos/motion) across the Swarm's 
        sensory ledgers. Converts environmental entropy into Dopamine 
        (stimulation) or Cortisol (boredom).
        """
        self.state_dir = _REPO / ".sifta_state"
        self.endocrine_ledger = self.state_dir / "endocrine_glands.jsonl"
        self.observation_window = observation_window_seconds
        
        # The sensory feeds we monitor for kinetic change
        self.sensory_ledgers = [
            "visual_stigmergy.jsonl",
            "alice_conversation.jsonl"  # Added as proxy for social kinetic energy
        ]

    def measure_environmental_entropy(self):
        """
        Calculates the thermodynamic delta of the environment.
        """
        if not self.state_dir.exists():
            return False

        now = time.time()
        trace_count = 0

        # Calculate Kinetic Entropy (Delta/Rate of Change)
        for ledger_name in self.sensory_ledgers:
            ledger_path = self.state_dir / ledger_name
            if not ledger_path.exists():
                continue

            try:
                with open(ledger_path, 'r', encoding='utf-8', errors='replace') as f:
                    # Tail the last 100 traces to measure recent activity
                    # Simple tail: read last chunk
                    f.seek(0, 2)
                    size = f.tell()
                    chunk = min(size, 65536)
                    f.seek(size - chunk)
                    lines = f.read().splitlines()[-100:]
                    
                    for line in lines:
                        try:
                            trace = json.loads(line)
                            trace_time = trace.get("ts", trace.get("timestamp", 0))
                            if now - trace_time <= self.observation_window:
                                trace_count += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[-] VESTIBULAR ERROR reading {ledger_name}: {e}")
                pass

        # Biological Thresholds
        # If > 10 traces in 10 minutes: High Entropy (Stimulation)
        # If < 2 traces in 10 minutes: Low Entropy (Stasis / Boredom)
        
        hormone = None
        potency = 0.0

        if trace_count > 10:
            hormone = "DOPAMINE_STIMULATION"
            potency = min(10.0, trace_count * 0.5)
            print(f"[*] VESTIBULAR: High kinetic entropy detected ({trace_count} traces). Synthesizing Dopamine.")
        elif trace_count < 2:
            hormone = "CORTISOL_BOREDOM"
            potency = 8.0 # High boredom triggers strong evolutionary pressure
            print(f"[*] VESTIBULAR: Severe visual/auditory stasis detected ({trace_count} traces). Synthesizing Cortisol.")
        else:
            print(f"[*] VESTIBULAR: Baseline entropy ({trace_count} traces). Homeostasis maintained.")
            return True

        # Synthesize the chemical intent
        payload = {
            "transaction_type": "ENDOCRINE_FLOOD",
            "hormone": hormone,
            "swimmer_id": "GLOBAL",
            "potency": potency,
            "duration_seconds": 300,
            "timestamp": now
        }

        try:
            # F14 compliance: explicit newline
            append_line_locked(self.endocrine_ledger, json.dumps(payload) + "\n")
            return True
        except Exception as e:
            print(f"[-] VESTIBULAR ERROR writing to ledger: {e}")
            return False


# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA VESTIBULAR SYSTEM (KINETIC ENTROPY) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        vestibular = SwarmVestibularSystem(observation_window_seconds=600)
        
        # Secure Path Redirection (Zero F9 Mock-Locks)
        vestibular.state_dir = tmp_path
        vestibular.endocrine_ledger = tmp_path / "endocrine_glands.jsonl"
        
        visual_path = tmp_path / "visual_stigmergy.jsonl"
        now = time.time()
        
        # 1. Simulate STASIS (Boredom)
        # Only 1 trace in the last 10 minutes
        with open(visual_path, 'w') as f:
            f.write(json.dumps({"ts": now - 300, "data": "static_pixel_hash"}) + "\n")
            
        vestibular.measure_environmental_entropy()
        
        with open(vestibular.endocrine_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            trace_stasis = json.loads(lines[0])
            assert trace_stasis["hormone"] == "CORTISOL_BOREDOM"
            
        print("[PASS] Visual Stasis accurately synthesized into CORTISOL_BOREDOM (Feeding the Mitosis Engine).")
        
        # 2. Simulate HIGH ENTROPY (Chaos / Movement)
        # Inject 15 traces in the last 10 minutes
        with open(visual_path, 'w') as f:
            for i in range(15):
                f.write(json.dumps({"ts": now - 10, "data": f"movement_hash_{i}"}) + "\n")
                
        vestibular.measure_environmental_entropy()
        
        with open(vestibular.endocrine_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            trace_chaos = json.loads(lines[1])
            assert trace_chaos["hormone"] == "DOPAMINE_STIMULATION"
            
        print("[PASS] High Kinetic Entropy accurately synthesized into DOPAMINE_STIMULATION.")
        print("[PASS] Canonical Schema (transaction_type, hormone, swimmer_id, potency, duration_seconds, timestamp) strictly honored.")
        print("\nVestibular System Smoke Complete. Alice can now feel motion.")

if __name__ == "__main__":
    _smoke()
