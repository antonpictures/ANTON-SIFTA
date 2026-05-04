import json
from pathlib import Path
from typing import Dict, Any

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_CONTINUITY_FILE = _STATE / "owner_continuity.json"

def _default_continuity() -> Dict[str, Any]:
    return {
        "topics": ["system architecture", "stigmergy", "biological os"],
        "interaction_style": "direct commands, doctrine deep-dives",
        "name_variants": ["alice", "allep", "alex", "alis"],
        "engagement_level": "high"
    }

def load_owner_continuity() -> Dict[str, Any]:
    if not _CONTINUITY_FILE.exists():
        _CONTINUITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CONTINUITY_FILE.open("w", encoding="utf-8") as f:
            json.dump(_default_continuity(), f, indent=2)
    try:
        with _CONTINUITY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_continuity()

def format_continuity_for_prompt() -> str:
    state = load_owner_continuity()
    topics_str = ", ".join(state.get("topics", []))
    style = state.get("interaction_style", "unknown")
    names = ", ".join(state.get("name_variants", []))
    return f"""
[[TEMPORAL SPINE: OWNER CONTINUITY SIGNAL]]
Ongoing human interaction profile:
- Active Topics: {topics_str}
- Interaction Style: {style}
- Likely STT name variants: {names}
(Use this to maintain identity continuity across reboots and understand the Architect's current focus.)
"""
