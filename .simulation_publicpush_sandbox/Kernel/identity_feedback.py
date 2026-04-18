"""
identity_feedback.py
──────────────────────────────────────────────────────────────────────────────
IDENTITY PERFORMANCE FEEDBACK LOOP (CONTEXT & CAL AWARE)
Tracks identity success relative to specific fault contexts (e.g. "SYNTAX").
Implements Causal Attribution Lock (CAL) to prevent multiple agents from claiming
cognitive reward for identical reality events, enforcing extreme evolutionary fairness.
──────────────────────────────────────────────────────────────────────────────
"""

import json
import hashlib
from pathlib import Path

STATS_FILE = Path(".sifta_state/identity_stats.json")
EVENT_REGISTRY_FILE = Path(".sifta_state/event_registry.json")

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
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

def generate_event_id(filepath: str, code_snippet: str, error: str) -> str:
    """Hashes the unique physical structural footprint of a fault event."""
    normalized = code_snippet.strip()
    raw = f"{filepath}:{normalized}:{error}"
    return hashlib.sha256(raw.encode()).hexdigest()

def register_event_resolution(event_id: str, agent_id: str) -> bool:
    """
    Checks if an event has already been successfully solved.
    Returns True if this agent is the first to claim it.
    """
    registry = _load_json(EVENT_REGISTRY_FILE)
    if event_id in registry:
        return False  # Already claimed by another agent
        
    registry[event_id] = agent_id
    _save_json(EVENT_REGISTRY_FILE, registry)
    return True

def record_identity_outcome(identity: str, context: str, success: bool, event_id: str = None, agent_id: str = None):
    """Logs the outcome. Prevents cognitive double-spending on successes."""
    if not identity:
         return
         
    # Causal Attribution Lock (CAL) check
    if success and event_id and agent_id:
        is_primary = register_event_resolution(event_id, agent_id)
        if not is_primary:
            # Another clone already solved this. Do not inflate success stats again.
            return
         
    identity = identity.upper().strip()
    key = f"{identity}:{context}"
    data = _load_json(STATS_FILE)
    
    if key not in data:
        data[key] = {"success": 0, "fail": 0}
        
    if success:
        data[key]["success"] += 1
    else:
        # Failure is always punished contextually to rapidly prune weak behaviors
        data[key]["fail"] += 1
        
    _save_json(STATS_FILE, data)

def get_identity_score(identity: str, context: str) -> float:
    """Returns the contextual effectiveness of an identity [0.0 - 1.0]."""
    if not identity:
        return 0.5
        
    identity = identity.upper().strip()
    key = f"{identity}:{context}"
    data = _load_json(STATS_FILE)
    
    stats = data.get(key, None)
    if not stats:
        return 0.5  # neutral baseline

    total = stats["success"] + stats["fail"]
    if total <= 0:
        return 0.5

    return float(stats["success"] / total)

def is_novel_context(identity: str, context: str) -> bool:
    """Returns True if the identity has never been attempted in this context before."""
    if not identity:
        return False
        
    identity = identity.upper().strip()
    key = f"{identity}:{context}"
    data = _load_json(STATS_FILE)
    
    stats = data.get(key, None)
    if not stats:
        return True
        
    return (stats["success"] + stats["fail"]) == 0

def decay_identity_scores():
    """
    Biological memory evaporation: decays all scores horizontally by 1%.
    """
    data = _load_json(STATS_FILE)
    for key in data:
        data[key]["success"] = data[key]["success"] * 0.99
        data[key]["fail"] = data[key]["fail"] * 0.99
    
    _save_json(STATS_FILE, data)
