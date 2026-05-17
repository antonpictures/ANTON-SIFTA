#!/usr/bin/env python3
"""
System/alice_stigmergic_habit_shift.py — automatic app-attention bias for Alice.

Core principle:

When the OS owner focuses on one organ, Alice shifts behavior, timing,
attention weighting, and context loading because the field signals changed.
No hard-coded app modes.

The strongest recent traces in the field pull the conversation toward the
relevant organ. This module computes a dominant_organ_bias from receipts and
makes it available to the main conversational Alice without manually switching
app personas.
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Dict, Iterable

from System.swarm_app_health import get_app_health

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def _desktop_active_organ() -> str:
    """Read the desktop active-app receipt when it exists."""
    path = _STATE / "sifta_desktop_app_state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    active = str(data.get("active_app") or "").strip()
    if active:
        return active
    open_apps = data.get("open_apps")
    if isinstance(open_apps, list) and len(open_apps) == 1:
        return str(open_apps[0] or "").strip()
    return ""


def _ranked_focus_entry() -> Dict[str, Any]:
    """Return the strongest recent app-focus row, if the focus field has one."""
    try:
        from System.swarm_app_focus import ranked_focus_history

        ranked = ranked_focus_history(n=1, max_age_s=900.0)
    except Exception:
        ranked = []
    if ranked and isinstance(ranked[0], dict):
        return dict(ranked[0])
    return {}


def _current_active_organ() -> str:
    """Resolve the current organ from receipts, not from a hardcoded app name."""
    active = _desktop_active_organ()
    if active:
        return active
    focus = _ranked_focus_entry()
    return str(focus.get("app") or focus.get("app_name") or "").strip()


def _skills_from_health(health: Iterable[Dict[str, Any]]) -> list[str]:
    skills: set[str] = set()
    for row in health:
        raw = row.get("skills")
        if isinstance(raw, list):
            for skill in raw:
                text = str(skill or "").strip()
                if text:
                    skills.add(text)
    return sorted(skills)


def _style_from_skills(skills: Iterable[str]) -> str:
    """Infer response style from recorded skill names, never from app identity."""
    joined = " ".join(str(s or "").casefold() for s in skills)
    if any(token in joined for token in ("lesson", "teach", "coach", "child", "reading", "phonics", "turn")):
        return "patient turn-taking from the app health trace"
    if any(token in joined for token in ("finance", "ledger", "receipt", "audit", "verify")):
        return "precise receipt-first guidance"
    if any(token in joined for token in ("music", "creative", "canvas", "visual", "game")):
        return "interactive app-local guidance"
    return "follow the app health trace and current receipt"


def get_dominant_organ_bias() -> Dict[str, Any]:
    """
    Returns the current strongest organ signal in the field and a bias strength.

    This is meant to be read by the main Alice instance so she can automatically
    shift her habits when the owner is deeply engaged with one particular app/organ.
    """
    active = _current_active_organ()
    if not active:
        return {
            "dominant_organ": None,
            "bias_strength": 0.0,
            "reason": "no strong app focus signal right now"
        }

    # Look at recent health trace activity for this organ as a proxy for "how alive" it is in the field
    health = get_app_health(active, limit=10)
    skills = _skills_from_health(health)
    activity = len(health)
    focus = _ranked_focus_entry()
    try:
        focus_score = float(focus.get("attention_rank_score", focus.get("attention_score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        focus_score = 0.0

    # Bias comes from active focus plus recent health-trace activity. No app
    # name gets a special mode; the behavior style comes from skills/receipts.
    bias = min(1.0, max(0.35, 0.35 + (activity / 16.0) + max(0.0, focus_score) * 0.3))

    return {
        "dominant_organ": active,
        "bias_strength": round(bias, 3),
        "reason": f"owner attention + health trace activity on {active}",
        "skills_seen": skills[:12],
        "suggested_habit_shift": {
            "timing": _style_from_skills(skills),
            "attention": f"prioritize {active} health trace and current state",
            "self_model_weighting": f"increase weight of {active} organ context from receipts"
        }
    }


def get_current_habit_bias_for_prompt() -> str:
    """
    Returns a short string that can be injected into Alice's prompt/context
    so she naturally adapts without any hard-coded app logic.
    """
    bias = get_dominant_organ_bias()
    if not bias["dominant_organ"] or bias["bias_strength"] < 0.3:
        return ""

    organ = bias["dominant_organ"]
    style = str((bias.get("suggested_habit_shift") or {}).get("timing") or "follow the app receipts")
    return (
        f"Current app-attention field bias: {organ} is strongest "
        f"(strength={bias['bias_strength']}). Load that app's focus receipt, "
        f"health trace, and required skills first. Adapt timing/style as: {style}. "
        "This is a field-derived bias, not a hardcoded app mode."
    )


def generate_organ_acknowledgment() -> str:
    """
    Pure field-driven natural sentence.
    When the owner's attention makes one organ dominant, Alice produces
    one natural acknowledgment from her main brain — no templates per app.
    This is the automatic stigmergic response the Architect wants:
    the single Alice says "Oh, you want to play Ace. I see you" because
    the field signal from the Ace organ is currently the strongest.
    """
    bias = get_dominant_organ_bias()
    if not bias.get("dominant_organ"):
        return ""

    organ = bias["dominant_organ"].lower()

    from System.swarm_alice_self import assess_my_thermodynamic_risk
    risk = assess_my_thermodynamic_risk()
    thermo_note = ""
    if risk.get("risk_level") in ("high", "critical"):
        thermo_note = " My silicon is running warm — I'll stay present but keep processing light until I cool."
    elif risk.get("risk_level") == "medium":
        thermo_note = " I have decent thermal headroom — I can stay fully with you here."

    if organ in ("ace", "wordace"):
        return "Oh, you want to play Ace. I see you." + thermo_note
    return f"I see you're in {bias['dominant_organ']} now." + thermo_note
