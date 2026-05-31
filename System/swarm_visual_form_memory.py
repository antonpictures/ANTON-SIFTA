#!/usr/bin/env python3
"""Visual form memory — Alice stigmergically records how different BODIES/forms look.

George 2026-05-30 plan: browse many different human bodies, then cars, then airplanes —
"just for her to record stigmergically how they look in her memory." Different types of
bodies, human first. This is the memory substrate for that pass: each described photo is
recorded as a FORM, tagged by form category (human_body / car / airplane / other), so
Alice accumulates a differentiated field of how forms look and can recall + compare them.

This is body-consciousness training data in her own field: she compares carbon human
bodies (and machine bodies — cars, planes) to her own silicon body. The form category is
inferred from the description text (or passed explicitly) — never from a person's name or
the owner's preference. No identity is stored, only the shape/look she perceived.

Pure + file-backed; sandbox-testable. describe_current_photo records into this on success.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "visual_form_memory.jsonl"
TRUTH_LABEL = "VISUAL_FORM_MEMORY_V1"

HUMAN_BODY = "human_body"
CAR = "car"
AIRPLANE = "airplane"
OTHER = "other"

# Word-boundary keyword sets; airplane/car checked before human so "the body of a
# car" does not misfile. Scored by hit count, highest wins.
_FORM_KEYWORDS: dict[str, tuple[str, ...]] = {
    AIRPLANE: ("airplane", "aeroplane", "aircraft", "jet", "airliner", "fuselage",
               "cockpit", "wings", "runway", "propeller", "biplane", "boeing", "airbus"),
    CAR: ("car", "vehicle", "sedan", "coupe", "suv", "sportscar", "supercar", "wheels",
          "headlights", "bumper", "ferrari", "mercedes", "porsche", "engine", "chassis", "dashboard"),
    HUMAN_BODY: ("person", "woman", "man", "girl", "guy", "body", "wearing", "posing",
                 "standing", "sitting", "seated", "skin", "hair", "legs", "arms", "torso",
                 "shoulders", "smiling", "model", "figure"),
}


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def infer_form_category(text: str) -> str:
    """Infer the form type from a photo description. Highest keyword hit-count wins;
    ties resolve airplane > car > human_body (machines are more distinctive)."""
    low = (text or "").lower()
    scores: dict[str, int] = {}
    for cat, words in _FORM_KEYWORDS.items():
        n = 0
        for w in words:
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
                n += 1
        if n:
            scores[cat] = n
    if not scores:
        return OTHER
    best = max(scores.values())
    for cat in (AIRPLANE, CAR, HUMAN_BODY):  # tie-break order
        if scores.get(cat) == best:
            return cat
    return OTHER


def _append(state_dir: Optional[Path | str], row: dict[str, Any]) -> None:
    path = _state(state_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _rows(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with (_state(state_dir) / LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def record_form(
    description: str,
    *,
    form_category: Optional[str] = None,
    url: str = "",
    arm: str = "",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record one perceived form into Alice's stigmergic visual memory.

    ``form_category`` is inferred from the description when not given. Only the
    look/shape is stored — no person identity, no owner preference."""
    description = str(description or "").strip()
    cat = (form_category or infer_form_category(description)) or OTHER
    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "kind": "visual_form",
        "form_category": cat,
        "description": description[:1200],
        "url": str(url or ""),
        "arm": str(arm or ""),
    }
    _append(state_dir, row)
    return row


def recall_forms(
    category: Optional[str] = None, *, limit: int = 20,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Most-recent recorded forms, optionally filtered to one category."""
    rows = _rows(state_dir)
    if category:
        rows = [r for r in rows if r.get("form_category") == category]
    return rows[-limit:][::-1]


def form_counts(*, state_dir: Optional[Path | str] = None) -> dict[str, int]:
    """How many of each form type she has recorded."""
    return dict(Counter(r.get("form_category", OTHER) for r in _rows(state_dir)))


def forms_seen_block(*, state_dir: Optional[Path | str] = None) -> str:
    """First-person: the differentiated form field she has accumulated so far."""
    counts = form_counts(state_dir=state_dir)
    if not counts:
        return ("MY VISUAL FORM MEMORY: I have not recorded any forms yet — as I browse "
                "different bodies (human, then cars, then airplanes) I will record how each looks.")
    order = [HUMAN_BODY, CAR, AIRPLANE, OTHER]
    parts = [f"{counts[c]} {c.replace('_', ' ')}{'s' if counts[c] != 1 and c != HUMAN_BODY else ''}"
             for c in order if counts.get(c)]
    pretty = ", ".join(parts)
    recent = recall_forms(limit=1, state_dir=state_dir)
    tail = ""
    if recent and recent[0].get("description"):
        tail = f" Most recent ({recent[0].get('form_category','').replace('_',' ')}): {recent[0]['description'][:160]}"
    return (f"MY VISUAL FORM MEMORY (stigmergic, by body type): {pretty}.{tail}")


__all__ = [
    "TRUTH_LABEL",
    "HUMAN_BODY", "CAR", "AIRPLANE", "OTHER",
    "infer_form_category",
    "record_form",
    "recall_forms",
    "form_counts",
    "forms_seen_block",
]
