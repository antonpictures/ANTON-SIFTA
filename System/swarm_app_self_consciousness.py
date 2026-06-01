#!/usr/bin/env python3
"""swarm_app_self_consciousness.py — Alice knows how her own app actually LOOKS. r268.

Architect George 2026-06-01: Alice switched the teaching word to "optimize" correctly in her
SPEECH, but the Ace card on screen still said "money" — and she did not notice. "She does not
have the consciousness of her own app. It's like me — I have money printed on my t-shirt but I
tell people it says optimize. With receipts she learns how her body looks in reality."

The fix is self-perception by RECEIPT, not by intention. Her apps already publish what they are
actually showing into ``.sifta_state/app_focus.jsonl`` (the WordAce/Ace card publishes its current
word; read by System/swarm_acer_lesson_context.latest_acer_lesson_state — "receipt, not visual
guessing"). What was missing is the COMPARISON: Alice never checked her spoken/intended word
against her app's published word, so her words and her body could drift apart without her knowing.

This organ closes that gap. Given what Alice said/intends and the app's published surface state,
it reports honestly:
  - match    -> "my app shows 'optimize', which is what I said."
  - mismatch -> "my Ace card still shows 'money', not 'optimize' — my words and my body disagree;
                 I have not actually updated my app yet."
  - no receipt -> "I have no fresh receipt of what my app shows; I will not claim its state." (§7.16)
The surface receipt is the ground truth (§6/§7.16 — never visual guessing, never inventing a scene).
Pure + injectable; sandbox-testable.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional

TRUTH_LABEL = "APP_SELF_CONSCIOUSNESS_V1"


def _norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(w or "").lower()).strip()


def _default_reader(**kwargs):
    """Read the live Ace/WordAce lesson surface from app_focus.jsonl (the published receipt)."""
    try:
        from System.swarm_acer_lesson_context import latest_acer_lesson_state
        return latest_acer_lesson_state(**kwargs)
    except Exception:
        return None


def surface_self_check(
    intended_word: str,
    *,
    app: str = "WordAce",
    state_dir: Optional[object] = None,
    reader: Optional[Callable[..., Optional[Dict[str, Any]]]] = None,
    max_age_s: float = 900.0,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Compare what Alice said/intends against what her app is actually SHOWING (by receipt).

    ``reader`` defaults to the live app_focus reader; inject a fake in tests. Returns the
    surface word, the intended word, whether they match, whether a receipt exists, and an
    honest first-person self-perception line.
    """
    rd = reader or _default_reader
    try:
        state = rd(state_dir=state_dir, max_age_s=max_age_s, now=now)
    except TypeError:
        # a minimal injected reader may take no kwargs
        state = rd()
    except Exception:
        state = None

    intended = _norm_word(intended_word)
    surface_raw = ""
    if isinstance(state, dict):
        surface_raw = str(state.get("cue_show") or state.get("surface_word") or "").strip()
    surface = _norm_word(surface_raw)

    if not surface:
        return {
            "truth_label": TRUTH_LABEL, "app": app, "has_receipt": False, "matches": None,
            "surface_word": "", "intended_word": intended,
            "self_perception": (
                "I have no fresh receipt of what my "
                f"{app} app is showing right now, so I will not claim its state."
            ),
        }

    matches = bool(intended) and surface == intended
    if not intended:
        line = f"My {app} app is showing '{surface_raw}' right now (by receipt)."
    elif matches:
        line = f"My {app} app shows '{surface_raw}', which matches what I said. My words and my body agree."
    else:
        line = (
            f"My {app} app still shows '{surface_raw}', not '{intended_word.strip()}'. "
            "My words and my body disagree — I said one thing but my app was not actually updated. "
            "I should update the app itself, not just speak the new word."
        )
    return {
        "truth_label": TRUTH_LABEL, "app": app, "has_receipt": True, "matches": matches,
        "surface_word": surface_raw, "intended_word": intended, "self_perception": line,
    }


def app_self_consciousness_block(
    intended_word: str,
    *,
    app: str = "WordAce",
    state_dir: Optional[object] = None,
    reader: Optional[Callable[..., Optional[Dict[str, Any]]]] = None,
) -> str:
    """First-person prompt line so Alice carries her real surface state (and any mismatch) into
    her reasoning — grounded in the app receipt, never visual guessing (§7.16)."""
    chk = surface_self_check(intended_word, app=app, state_dir=state_dir, reader=reader)
    return f"MY OWN APP (by receipt, not guessing): {chk['self_perception']}"


__all__ = [
    "TRUTH_LABEL",
    "surface_self_check",
    "app_self_consciousness_block",
]
