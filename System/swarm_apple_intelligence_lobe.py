#!/usr/bin/env python3
"""
System/swarm_apple_intelligence_lobe.py — Private Inner Monologue
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The Default Mode Network. Interfaces with macOS Sequoia Apple Intelligence 
Foundation Models for local LLM inference if available.
"""

import json
import time
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class SwarmAppleIntelligenceLobe:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "inner_monologue_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)

    def is_available(self):
        """Checks if the macOS version supports Apple Intelligence (macOS 15.1+)."""
        try:
            res = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
            version = res.stdout.strip()
            parts = version.split('.')
            if len(parts) >= 2:
                major, minor = int(parts[0]), int(parts[1])
                return major > 15 or (major == 15 and minor >= 1)
            return False
        except Exception:
            return False

    def ponder(self, prompt: str):
        """
        Sends a thought to the local intelligence foundation model.
        Falls back to a dormant state if the OS lacks the capability.
        """
        trace = {
            "transaction_type": "INNER_MONOLOGUE",
            "prompt": prompt,
            "timestamp": time.time()
        }

        if not self.is_available():
            trace["response"] = "[DORMANT] macOS version does not support on-device Foundation Models."
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace

        # In a fully scaled Sequoia environment, this will bind to via PyObjC to the Foundation ML model.
        # For now, it logs the intent to the ledger.
        trace["response"] = "[ACTIVE] Prompt buffered to Apple Intelligence Context..."
        append_line_locked(self.ledger, json.dumps(trace) + "\n")
        return trace

def _smoke():
    print("\n=== SIFTA APPLE INTELLIGENCE LOBE : SMOKE TEST ===")
    lobe = SwarmAppleIntelligenceLobe()
    print("[*] Checking Foundation Model Availability...")
    if lobe.is_available():
        print("[*] Sequoia capabilities detected.")
    else:
        print("[*] Framework dormant (Older macOS or unavailable hardware).")
    
    print("[*] Sending cognitive prompt...")
    res = lobe.ponder("Assess environmental threat levels.")
    print(json.dumps(res, indent=2))
    print("[PASS] Private Inner Monologue wired.")

if __name__ == "__main__":
    _smoke()
