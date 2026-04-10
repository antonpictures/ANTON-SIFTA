"""
identity_feedback.py
──────────────────────────────────────────────────────────────────────────────
IDENTITY PERFORMANCE FEEDBACK LOOP (CONTEXT AWARE)
Tracks identity success relative to specific fault contexts (e.g. "SYNTAX", "NAME").
Enables emergent domain specialization and biological memory decay.
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
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def extract_context(error_message: str) -> str:
    err = str(error_message).lower()
    if "syntax" in err:
        return "SYNTAX"
    if "nameerror" in err:
        return "NAME"
    if "typeerror" in err:
        return "TYPE"
    if "indent" in err:
        return "INDENT"
    return "UNKNOWN"

def record_identity_outcome(identity: str, context: str, success: bool):
    """Logs the outcome of an identity's repair attempt within a specific context."""
    if not identity:
         return
         
    identity = identity.upper().strip()
    key = f"{identity}:{context}"
    data = _load_stats()
    
    if key not in data:
        # Fallback migration check or new entry
        data[key] = {"success": 0, "fail": 0}
        
    if success:
        data[key]["success"] += 1
    else:
        data[key]["fail"] += 1
        
    _save_stats(data)

def get_identity_score(identity: str, context: str) -> float:
    """Returns the contextual effectiveness of an identity [0.0 - 1.0]."""
    if not identity:
        return 0.5
        
    identity = identity.upper().strip()
    key = f"{identity}:{context}"
    data = _load_stats()
    
    stats = data.get(key, None)
    if not stats:
        return 0.5  # neutral baseline

    total = stats["success"] + stats["fail"]
    if total <= 0:
        return 0.5

    return float(stats["success"] / total)

def decay_identity_scores():
    """
    Biological memory evaporation: decays all scores horizontally by 1%.
    Ensures old success does not equal current truth, forcing adaptability.
    """
    data = _load_stats()
    for key in data:
        data[key]["success"] = data[key]["success"] * 0.99
        data[key]["fail"] = data[key]["fail"] * 0.99
    
    _save_stats(data)
