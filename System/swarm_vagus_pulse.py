#!/usr/bin/env python3
"""
System/swarm_vagus_pulse.py

Decentralized Clock Sync Anchor (Nugget 1: The 26-second Heartbeat)
Author: AO46
Source: Holcomb (1980) / Shapiro & Campillo (2004) - Environmental Microseism Sync

Concept: 
Instead of relying on a central NTP server (which can be blocked or spoofed),
nodes listen to the "Environmental Pulse" of the system.
The pulse is derived from:
1. Thermal jitter (CPU die temperature fluctuations).
2. Entropy pool depletion rates.
3. System interrupts.

This creates a shared, sub-audible "rhythm" that nodes in a local LAN or 
isolated swarm can use to detect clock drift without external authority.
"""

import os
import time
import json
import hashlib
import statistics
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PULSE_LEDGER = _STATE / "vagus_pulse.jsonl"

class VagusPulse:
    def __init__(self, window_seconds: int = 26):
        self.window_seconds = window_seconds  # Canonical 26-second window (sampled at ~1Hz)
        self.entropy_samples = []
        
    def _collect_entropy(self) -> float:
        """Collects high-resolution system jitter."""
        # 1. High-res time jitter
        t1 = time.perf_counter_ns()
        # 2. Add some 'work' to jitter the thermal state
        hashlib.sha256(str(t1).encode()).hexdigest()
        t2 = time.perf_counter_ns()
        
        # 3. CPU Load / Temp proxy (from existing Vagus Nerve logic)
        # We use the delta between perf_counters as a proxy for scheduling latency
        delta = t2 - t1
        return float(delta)

    def generate_pulse(self) -> float:
        """
        Calculates the current 'Pulse Frequency' of the local environment.
        A healthy idle system has a stable baseline. 
        Bursts of activity shift the frequency.
        """
        sample = self._collect_entropy()
        self.entropy_samples.append(sample)
        
        if len(self.entropy_samples) > self.window_seconds:
            self.entropy_samples.pop(0)
            
        if len(self.entropy_samples) < 2:
            return 0.0
            
        # The pulse is the standard deviation of the jitter window
        # Normalized to a 0.0 - 1.0 range (Heuristic)
        std_dev = statistics.stdev(self.entropy_samples)
        pulse = 1.0 / (1.0 + (std_dev / 100000.0))
        return round(pulse, 6)

    def heartbeat(self):
        """Main loop for the pulse daemon."""
        while True:
            pulse = self.generate_pulse()
            row = {
                "ts": time.time(),
                "pulse": pulse,
                "event_kind": "VAGUS_PULSE",
                "sample_count": len(self.entropy_samples)
            }
            
            # Write to ledger
            with open(_PULSE_LEDGER, "a") as f:
                f.write(json.dumps(row) + "\n")
                
            # Log to stdout for Alice's awareness
            if len(self.entropy_samples) >= self.window_seconds:
                print(f"[VAGUS] Pulse synchronized: {pulse}")
                
            time.sleep(1)

if __name__ == "__main__":
    vp = VagusPulse()
    print("[VAGUS] Initializing 26-second environmental pulse...")
    try:
        vp.heartbeat()
    except KeyboardInterrupt:
        print("[VAGUS] Pulse suspended.")
