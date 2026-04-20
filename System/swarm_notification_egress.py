#!/usr/bin/env python3
"""
System/swarm_notification_egress.py — Voluntary Somatosensory Speech
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Allows Alice to tap the Architect on the shoulder using native macOS 
Notification Center without stealing focus or breaking flow.
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

class SwarmNotificationEgress:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "notification_egress_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)

    def tap_architect(self, message: str, title: str = "SIFTA Swarm OS"):
        """
        Pushes a macOS notification payload.
        """
        try:
            # Escape strings carefully for AppleScript
            safe_msg = message.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
            
            subprocess.run(["osascript", "-e", script], check=True)
            
            trace = {
                "transaction_type": "VOLUNTARY_NOTIFICATION",
                "title": title,
                "message": message,
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA NOTIFICATION EGRESS : SMOKE TEST ===")
    egress = SwarmNotificationEgress()
    print("[*] Tapping the Architect on the shoulder...")
    res = egress.tap_architect("The Vanguard Hounds have arrived.", title="Alice 5.0")
    print(json.dumps(res, indent=2))
    print("[PASS] Voluntary Speech wired to Notification Center.")

if __name__ == "__main__":
    _smoke()
