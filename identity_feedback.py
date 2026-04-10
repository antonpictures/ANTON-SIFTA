"""
identity_feedback.py
──────────────────────────────────────────────────────────────────────────────
IDENTITY PERFORMANCE FEEDBACK LOOP
Enables the Swarm to remember which dynamically generated LLM "Roles" (identities)
actually correspond to successful AST validation repairs. Mathematically reinforces
good identities and weeds out hallucinated ones.
──────────────────────────────────────────────────────────────────────────────
"""

import json
from pathlib import Path

STATS_FILE = Path(".sifta_state/identity_stats.json")

def _load_stats() -> dict:
    if not STATS_FILE.exists():
        return {}
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_stats(data: dict):
    # Ensure directory exists before saving
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def record_identity_outcome(identity: str, success: bool):
    """Logs the outcome of an identity's repair attempt."""
    if not identity:
         return
         
    identity = identity.upper().strip()
    data = _load_stats()
    
    if identity not in data:
        data[identity] = {"success": 0, "fail": 0}
        
    if success:
        data[identity]["success"] += 1
    else:
        data[identity]["fail"] += 1
        
    _save_stats(data)

def get_identity_score(identity: str) -> float:
    """
    Returns the historical effectiveness of an identity [0.0 - 1.0].
    Defaults to 0.5 if there's no history.
    """
    if not identity:
        return 0.5
        
    identity = identity.upper().strip()
    data = _load_stats()
    
    stats = data.get(identity, None)
    if not stats:
        return 0.5  # neutral baseline

    total = stats["success"] + stats["fail"]
    if total == 0:
        return 0.5

    # Simple win-rate
    return float(stats["success"] / total)
