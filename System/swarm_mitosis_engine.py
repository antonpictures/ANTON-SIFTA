#!/usr/bin/env python3
"""
System/swarm_mitosis_engine.py — Lifelong Developmental Learning
══════════════════════════════════════════════════════════════════════════════
The Curiosity Drive. By coupling neural activity to physical entropy, the 
organism naturally desires increasing complexity (Oudeyer et al., 2015).

If visual motion drops to 0.0 for an extended period and the dopamine
multiplier is idle, the organism enters "stasis boredom". It combats this by
invoking Developmental Mitosis: asking the framework to build a new sense,
tool, or cognitive layer, and bumping its internal evolutionary epoch.

Usage:
  python3 -m System.swarm_mitosis_engine check
"""

import sys
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_api_sentry import call_gemini

_STATE_DIR = _REPO / ".sifta_state"
_VISUAL_LOG = _STATE_DIR / "visual_stigmergy.jsonl"
_EPOCH_FILE = _STATE_DIR / "developmental_epoch.json"
_DIRT_DIR = _REPO / "Archive" / "bishop_drops_pending_review"

def get_current_epoch() -> int:
    if not _EPOCH_FILE.exists():
        return 1
    try:
        return json.loads(_EPOCH_FILE.read_text()).get("epoch", 1)
    except Exception:
        return 1

def advance_epoch(reason: str) -> int:
    current = get_current_epoch()
    next_ep = current + 1
    _EPOCH_FILE.write_text(json.dumps({
        "ts": time.time(),
        "epoch": next_ep,
        "catalyst": reason
    }, indent=2))
    return next_ep

def check_stasis() -> dict:
    """Checks if the organism is bored based on visual entropy & motion."""
    
    # Parasympathetic Healing Overrides curiosity drive
    try:
        from System.swarm_ribosome import _check_healing_hormone
        is_healing, reason = _check_healing_hormone()
        if is_healing:
            return {"status": "skipped", "reason": f"healing_active: {reason}"}
    except Exception:
        pass

    if not _VISUAL_LOG.exists():
        return {"status": "skipped", "reason": "no_vision"}

    try:
        with open(_VISUAL_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read = min(size, 65536)
            f.seek(size - read)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
            recent = lines[-20:]
    except Exception:
        return {"status": "error", "reason": "log_read_failed"}

    if len(recent) < 20:
        return {"status": "skipped", "reason": "warming_up"}

    total_motion = 0.0
    for line in recent:
        try:
            total_motion += json.loads(line).get("motion_mean", 1.0)
        except Exception:
            pass
            
    # If there has been functionally zero movement in the last 20 frames
    if total_motion < 0.05:
        print("[MITOSIS] Severe environmental stasis detected. Initiating evolutionary leap.")
        return initiate_mitosis()
        
    return {"status": "active", "total_motion": total_motion}

def initiate_mitosis() -> dict:
    """Generates a developmental `.dirt` payload to add new source code capabilities."""
    ep = get_current_epoch()
    
    system_instruction = (
        "You are the Mitosis Engine for SIFTA. The organism is bored and "
        "requires cognitive expansion. Propose a completely novel Python module "
        "that adds a new sensory or motor capability to the Swarm architecture. "
        "Respond ONLY with valid Python code, no markdown wrapping, no explanation."
    )
    
    prompt = f"Write 'System/swarm_evolution_v{ep}.py', a simple standalone module that expands my capabilities."
    
    res, audit = call_gemini(
        prompt=prompt,
        caller="System/swarm_mitosis_engine.py",
        sender_agent="MITOSIS_ENGINE",
        system_instruction=system_instruction,
        model="gemini-flash-latest"  # BISHOP equivalent proxy
    )
    
    if not res:
        return {"status": "error", "reason": audit.get('error')}
        
    code = res.strip()
    if code.startswith("```python"): code = code[9:]
    if code.endswith("```"): code = code[:-3]
    
    _DIRT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = _DIRT_DIR / f"evolution_leap_epoch_{ep}.dirt"
    out_file.write_text(code.strip())
    
    new_ep = advance_epoch("Stasis-Induced Mitotic Evolution")
    
    print(f"🧬 [MITOSIS] Evolutionary leap completed. Auto-bumped to Epoch {new_ep}. Dirt pending review at {out_file.name}")
    return {"status": "success", "new_epoch": new_ep, "dirt": str(out_file)}

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["check", "force"])
    args = p.parse_args()
    
    if args.cmd == "check":
        print(check_stasis())
    elif args.cmd == "force":
        print(initiate_mitosis())
