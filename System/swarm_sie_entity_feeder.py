#!/usr/bin/env python3
"""swarm_sie_entity_feeder.py — r1622-03: NER proposals into human-anchor feeder.

George: human anchors already exist. SIE extract is OPTIONAL feeder only —
proposes new surface phrases / people, never replaces seed anchors.

When SIE offline: light regex person-like tokens from owner text as proposals.

Truth label: SIE_ENTITY_FEEDER_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "sie_entity_proposals.jsonl"

TRUTH_LABEL = "SIE_ENTITY_FEEDER_V1"

# Capitalized multi-word names (very light; not a real NER replacement)
_NAME_RE = re.compile(
    r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b"
)
_STOP = frozenset(
    {
        "Alice",
        "George",
        "Talk",
        "Browser",
        "Instagram",
        "Youtube",
        "Please",
        "When",
        "What",
        "Where",
        "This",
        "That",
        "System",
        "Documents",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def extract_entity_proposals(text: str) -> list[dict[str, Any]]:
    """Propose entities from owner text. Never claims SIE when offline."""
    raw = str(text or "")
    proposals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _NAME_RE.finditer(raw):
        name = m.group(1).strip()
        if name in _STOP or name.lower() in seen:
            continue
        if len(name) < 3:
            continue
        seen.add(name.lower())
        proposals.append(
            {
                "surface": name,
                "kind": "person_or_org_guess",
                "source": "regex_offline",
                "confidence": 0.35,
            }
        )
    # Try SIE extract if bridge says reachable (still optional)
    try:
        from System.swarm_sie_embedding_bridge import probe_sie

        p = probe_sie(write_receipt=False, timeout_s=0.3)
        if p.get("ok"):
            # SDK not wired — mark that live SIE would upgrade these
            for row in proposals:
                row["sie_note"] = "sie_up_would_rerun_extract"
    except Exception:
        pass
    return proposals


def deposit_proposals(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Append proposal rows. Does NOT rewrite concept_human_anchors seeds."""
    props = extract_entity_proposals(text)
    root = _state_dir(state_dir)
    row = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "owner_preview": str(text or "")[:240],
        "proposals": props,
        "note": "feeder only — human anchors remain source of truth",
    }
    if write and props:
        try:
            root.mkdir(parents=True, exist_ok=True)
            with (root / _LEDGER).open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return row


def feeder_prompt_block(user_text: str = "", *, max_chars: int = 500) -> str:
    props = extract_entity_proposals(user_text)
    if not props:
        return ""
    names = ", ".join(p["surface"] for p in props[:8])
    block = (
        "ENTITY FEEDER (r1622-03 — proposals only, do not invent founders):\n"
        f"- candidate surfaces: {names}\n"
        "- Existing concept_human_anchor seeds stay authoritative; these are optional."
    )
    return block[:max_chars]


__all__ = [
    "TRUTH_LABEL",
    "extract_entity_proposals",
    "deposit_proposals",
    "feeder_prompt_block",
]
