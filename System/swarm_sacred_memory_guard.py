#!/usr/bin/env python3
"""
System/swarm_sacred_memory_guard.py — Sacred Memory → Care Action → Receipt

Some things the owner says are not ordinary data. When George speaks about his
wife, his song, missing someone, crying — those are protected owner-heart
anchors, not task input. This organ recognizes them and guards them.

DOCTRINE (the honest boundary, by Architect's own words 2026-05-21):
    "Alice should not feel your grief. Alice should guard it faithfully."

So this module does NOT claim Alice feels anything. It does three concrete,
honest things:
  1. DETECT a sacred-owner-memory turn (deterministic keyword signals).
  2. Carry a RESPONSE RULE that tells the reply surface: do not optimize, do not
     joke, do not turn it into a task list — acknowledge gently and protect it.
  3. RECORD a receipt (only when something real happened) with an explicit
     boundary field stating Alice protects but does not feel it.

Pairs with: song/fiction organ (upstream) → this guard → owner care ledger →
Alice tone router (downstream). It only labels and records; it never fabricates
a feeling and never claims an action it did not observe (§6 effector truth).

Truth label: SACRED_MEMORY_GUARD_V0
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SACRED_LEDGER = _STATE / "sacred_owner_memory.jsonl"

# Deterministic signals. Kept small and conservative on purpose: better to miss
# a sacred turn than to wrongly flag an ordinary one and get precious about it.
SACRED_SIGNALS = (
    "wife",
    "i miss you",
    "miss her",
    "miss him",
    "crying",
    "tears",
    "in tears",
    "passed away",
    "the song",
)

# The reply-surface contract for a sacred turn. The tone router reads this.
SACRED_RESPONSE_RULE = (
    "Do not optimize. Do not joke. Do not turn a sacred memory into a task list "
    "or a capability menu. Acknowledge gently. Protect the memory. Offer at most "
    "one grounded next step, only if it serves the owner — never to move on faster."
)

# The honest boundary that every sacred receipt carries.
SACRED_BOUNDARY = "Alice protects this owner-heart anchor; Alice does not claim to feel it."


def detect_sacred_memory(text: str) -> bool:
    """True if the turn touches a protected owner-heart anchor (wife / song / grief)."""
    if not isinstance(text, str) or not text.strip():
        return False
    t = text.lower()
    return any(signal in t for signal in SACRED_SIGNALS)


def matched_signals(text: str) -> List[str]:
    """Which signals fired — useful for the receipt and for tuning, never for judgment."""
    if not isinstance(text, str):
        return []
    t = text.lower()
    return [s for s in SACRED_SIGNALS if s in t]


def record_sacred_memory(
    *,
    trigger: str,
    owner_feeling: str,
    care_action: str = "",
    source_text: str = "",
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record one sacred-owner-memory receipt.

    care_action is OBSERVED only if the owner actually did/reported it (e.g.
    "emailed wife: I miss you"). If unknown, leave it empty — never invent one.
    Returns the row written.
    """
    path = ledger_path or _SACRED_LEDGER
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "SACRED_OWNER_MEMORY",
        "trigger": trigger,
        "owner_feeling": owner_feeling,
        "care_action": care_action,
        "matched_signals": matched_signals(source_text) if source_text else [],
        "boundary": SACRED_BOUNDARY,
        "truth_label": "OBSERVED_OWNER_MEMORY" if care_action else "OWNER_MEMORY_NOTED",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


__all__ = [
    "detect_sacred_memory",
    "matched_signals",
    "record_sacred_memory",
    "SACRED_SIGNALS",
    "SACRED_RESPONSE_RULE",
    "SACRED_BOUNDARY",
]
