#!/usr/bin/env python3
"""
System/swarm_applescript_effector.py
═══════════════════════════════════════════════════════════════════════════
Generalized AppleScript effector. Allows the OS/Alice to organically control
ANY application on the system that supports Apple events.

This is a powerful effector organ. It deposits to the `stig_applescript` ledger.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "applescript_trace.jsonl"

def _deposit_trace(script: str, result: str, ok: bool) -> None:
    """Writes to the localized ledger, documenting Alice's effector use."""
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "script_snippet": script[:200] + ("..." if len(script) > 200 else ""),
        "ok": ok,
        "result": result
    }
    try:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_applescript", intensity=1.5 if ok else -0.5)
    except Exception:
        pass

def run_script(script: str) -> Dict[str, Any]:
    """Execute raw AppleScript via osascript."""
    try:
        # Wrap the whole block of AppleScript to be passed gracefully
        # Use subprocess list so we don't need to fight bash escaping
        out = subprocess.check_output(
            ["osascript", "-e", script],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=10.0
        ).strip()
        _deposit_trace(script, out, True)
        return {"ok": True, "output": out}
    except subprocess.CalledProcessError as e:
        _deposit_trace(script, e.output.strip(), False)
        return {"ok": False, "error": e.output.strip()}
    except subprocess.TimeoutExpired:
        _deposit_trace(script, "Timeout", False)
        return {"ok": False, "error": "AppleScript execution timed out."}
    except Exception as e:
        _deposit_trace(script, str(e), False)
        return {"ok": False, "error": str(e)}

def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Standard governance hook for Alice's body.
    Verb: 'run'
    Kwargs: 'script' = raw AppleScript string
    """
    if verb == "run":
        script = kwargs.get("script")
        if not script:
            return {"ok": False, "error": "Missing 'script' kwarg"}
        return run_script(script)
    
    return {"ok": False, "error": f"Unknown applescript verb: {verb}"}

if __name__ == "__main__":
    # Smoke test
    res = run_script('return "AppleScript Effector Online"')
    print(json.dumps(res, indent=2))
