#!/usr/bin/env python3
"""
System/alice_active_organ_embodiment.py — Active App Context Layer

Build the receipt-backed context Alice should load for whichever SIFTA app is
currently focused. The point is operational, not philosophical: answer from the
current app's receipts, health trace, required skills, and self-vector snapshot.

This module provides:
- get_current_active_organ()
- get_organ_embodiment_level()
- enter_organ_context(app_name) -> returns a rich app-context dict
- get_current_organ_context()

It pulls from:
- app_focus.jsonl
- app health traces
- current self-vector
- reality boundary
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_app_health import get_app_health, get_required_skills_for_app
from System.alice_self_vector import build_alice_self_vector
from System.alice_reality_boundary import label_knowledge

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_APP_FOCUS = _STATE / "app_focus.jsonl"


def get_current_active_organ() -> Optional[str]:
    """Returns the name of the currently focused app/organ, if any."""
    if not _APP_FOCUS.exists():
        return None
    try:
        with _APP_FOCUS.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return None
        last = json.loads(lines[-1])
        return last.get("app") or last.get("app_name")
    except Exception:
        return None


def get_organ_embodiment_level(app_name: str) -> float:
    """Return how much usable app context is currently available (0.0-1.0)."""
    health = get_app_health(app_name, limit=5)
    if not health:
        return 0.2  # low baseline if no health trace

    # Simple heuristic: more recent health activity + richer skills = higher embodiment
    recency = min(1.0, len(health) / 5.0)
    richness = min(1.0, len(get_required_skills_for_app(app_name)) / 12.0)
    return round(0.3 + (recency * 0.4) + (richness * 0.3), 3)


def enter_organ_context(app_name: str) -> Dict[str, Any]:
    """Return the app-context package Alice should load when this app is active."""
    health = get_app_health(app_name, limit=8)
    vector = build_alice_self_vector(repo_root=_REPO, state_dir=_STATE, write_artifact=False, max_items=6)
    skills = get_required_skills_for_app(app_name)

    context = {
        "active_organ": app_name,
        "embodiment_level": get_organ_embodiment_level(app_name),
        "health_trace": health,
        "required_skills": skills,
        "self_vector_snapshot": {
            "identity_continuity": vector.get("identity_continuity"),
            "memory_entropy": vector.get("memory_entropy"),
            "receipt_integrity": vector.get("receipt_integrity"),
            "reality_boundary_integrity": vector.get("reality_boundary_integrity"),
            "stigmergic_momentum": vector.get("stigmergic_momentum"),
            "next_best_action": vector.get("next_best_action"),
        },
        "instruction_to_alice": (
            f"{app_name} is the active app. Answer from this app's receipts, health trace, "
            "required skills, and current state. Do not explain identity, embodiment, or "
            "consciousness unless George directly asks for that topic."
        ),
        "reality_boundary_note": label_knowledge({"active_organ": app_name})["reality_boundary"]
    }

    return context


def get_current_organ_context() -> Optional[Dict[str, Any]]:
    """Convenience: get the full context for whatever app is currently active."""
    active = get_current_active_organ()
    if not active:
        return None
    return enter_organ_context(active)
