#!/usr/bin/env python3
"""
System/swarm_iphone_effector.py — The Synaptic Ping
═══════════════════════════════════════════════════════════════════════════
Alice's iPhone Governance Organ (Vector C, C47H 2026-04-23).

Sends a payload-bearing iMessage ("Swimmer") to the Architect's phone number
via the local macOS Messages app. This natively wakes the iPhone and triggers
a Personal Automation in iOS Shortcuts.

Usage:
  Alice calls `iphone.send_swimmer` with `hw_kwargs={"payload": "FLASHLIGHT:ON"}`

Configuration:
  Create `.sifta_state/architect_imessage_id.txt` with your Apple ID or phone 
  number (e.g. "+15551234567" or "youremail@icloud.com").
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ID_FILE = _STATE / "architect_imessage_id.txt"
_LEDGER = _STATE / "iphone_effector_trace.jsonl"


def _read_target_id() -> Optional[str]:
    """Read the target Apple ID / Phone Number from configuration."""
    if not _ID_FILE.exists():
        return None
    val = _ID_FILE.read_text().strip()
    return val if val else None


def _deposit_trace(payload: str, result: str, ok: bool) -> None:
    """Record Alice's outgoing swimmers to the immutable ledger."""
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "payload": payload,
        "ok": ok,
        "result": result
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEDGER, json.dumps(row) + "\n")
    except Exception:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_iphone_effector", intensity=1.5 if ok else -0.5)
    except Exception:
        pass


def send_swimmer(payload: str, *, prefix: bool = True) -> Dict[str, Any]:
    """
    Transmit the Synaptic Ping via AppleScript -> Messages.app.
    If prefix is True, prepends the payload with SIFTA_SWIM: to ensure clean iOS filtering.
    """
    if not payload:
        return {"ok": False, "error": "Missing 'payload' kwarg."}
        
    target_id = _read_target_id()
    if not target_id:
        msg = (
            "No Apple ID configured. The Architect must create "
            "`.sifta_state/architect_imessage_id.txt` containing their "
            "iMessage email or phone number before you can send swimmers."
        )
        _deposit_trace(payload, msg, False)
        return {"ok": False, "error": msg}

    full_message = f"SIFTA_SWIM:{payload}" if prefix else payload
    
    # Send via AppleScript
    # We use 'service 1' which is almost always the active iMessage service
    # or explicitly "iMessage" / "SMS". If "iMessage" fails, fallback to generic.
    script = f'''
    tell application "Messages"
        try
            set targetService to 1st service whose service type = iMessage
        on error
            set targetService to 1st service
        end try
        set theBuddy to buddy "{target_id}" of targetService
        send "{full_message}" to theBuddy
    end tell
    '''
    
    try:
        out = subprocess.check_output(
            ["osascript", "-e", script],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=8.0
        ).strip()
        _deposit_trace(payload, f"Sent to {target_id} via AppleScript. (out: {out})", True)
        return {
            "ok": True, 
            "result": f"Swimmer '{full_message}' successfully dispatched to {target_id}.",
            "osascript_output": out
        }
    except subprocess.CalledProcessError as e:
        _deposit_trace(payload, e.output.strip(), False)
        return {"ok": False, "error": e.output.strip()}
    except subprocess.TimeoutExpired:
        _deposit_trace(payload, "Timeout", False)
        return {"ok": False, "error": "AppleScript execution timed out."}
    except Exception as e:
        _deposit_trace(payload, str(e), False)
        return {"ok": False, "error": str(e)}


def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Alice's interface to the iPhone Effector.
    verb: "send_swimmer"
    kwargs: {"payload": "FLASHLIGHT:ON"} 
    """
    verb = verb.lower().strip()
    if verb == "send_swimmer":
        payload = kwargs.get("payload", "").strip()
        return send_swimmer(payload, prefix=True)
    if verb == "send_text":
        payload = kwargs.get("payload", "").strip()
        return send_swimmer(payload, prefix=False)
        
    return {"ok": False, "error": f"Unknown iphone_effector verb: {verb}"}


if __name__ == "__main__":
    # Smoke test module (dry run if no ID configured)
    import sys
    print("Testing iPhone Effector...")
    target = _read_target_id()
    if not target:
        print("SKIP: `.sifta_state/architect_imessage_id.txt` missing.")
        sys.exit(0)
    print(f"Configured target: {target}")
    # We will NOT actually send a ping on smoke test to avoid spamming the user.
    print("Smoke test complete.")
