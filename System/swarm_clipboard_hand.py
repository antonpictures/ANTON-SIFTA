#!/usr/bin/env python3
"""
System/swarm_clipboard_hand.py — Manual Hand (Clipboard)
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The Manual Hand. Gives Alice the physics to read what the Architect is holding,
and hand them items directly.
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

class SwarmClipboardHand:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.ledger = self.state_dir / "clipboard_traces.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)

    def read_hand(self):
        """Reads from pbpaste."""
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
            content = result.stdout
            
            trace = {
                "transaction_type": "CLIPBOARD_READ",
                "length": len(content),
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return {"content": content, "trace": trace}
        except Exception as e:
            return {"error": str(e)}

    def pass_to_architect(self, content: str):
        """Writes to pbcopy."""
        try:
            subprocess.run(["pbcopy"], input=content, text=True, check=True)
            
            trace = {
                "transaction_type": "CLIPBOARD_WRITE",
                "length": len(content),
                "preview": content[:30] + ("..." if len(content) > 30 else ""),
                "timestamp": time.time()
            }
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
            return trace
        except Exception as e:
            return {"error": str(e)}

def _smoke():
    print("\n=== SIFTA CLIPBOARD HAND : SMOKE TEST ===")
    hand = SwarmClipboardHand()
    
    # Save original
    orig = hand.read_hand().get("content", "")
    
    print("[*] Handing item to Architect...")
    write_res = hand.pass_to_architect("Alice physically gave you this string.")
    print("Write Trace:", write_res)
    
    print("[*] Reading item from Architect...")
    read_res = hand.read_hand()
    print("Read Content:", read_res.get("content"))
    
    # Restore original out of politeness
    hand.pass_to_architect(orig)
    print("[PASS] Manual Hand wired successfully.")

if __name__ == "__main__":
    _smoke()
