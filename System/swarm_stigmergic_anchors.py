#!/usr/bin/env python3
"""Stigmergic Anchors — shared experience names/people tracker.

George (2026-06-19): "PROPOSE STIGMERGIC ANCHORS APP IN SIFTA APPS OS.
THIS APP LISTS ALL THE ANCHORS/NAMES/CELEBS/REALPEOPLE/DEAD OR ALIVE
THAT WERE MENTIONED IN ANY OF MY SHARED EXPERIENCES WITH ALICE."

When George tells Alice about a person, that becomes a shared experience
anchor. The anchor stores: name, context (how introduced), source
(George typed it vs ambient audio), timestamp, and verification status.

Virus anchors (unknown speakers on mic) are NOT anchors. Only George-verified
or George-introduced people become anchors.

Truth label: STIGMERGIC_ANCHORS_V1
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "STIGMERGIC_ANCHORS_V1"
SCHEMA = "STIGMERGIC_ANCHOR_ROW_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "stigmergic_anchors.jsonl"

# Patterns where George introduces or mentions a person
# "this is Joy Behar", "Joy Behar is a TV host", "I know someone named X"
_INTRODUCE_RE = re.compile(
    r"\b(?i:this\s+is|meet|say\s+hello\s+to|I\s+know|my\s+friend|"
    r"the\s+host|the\s+person|the\s+guy|the\s+woman|the\s+man|"
    r"she\s+is|he\s+is|her\s+name|his\s+name)\s+"
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)

# Names that are clearly real people (celebs, public figures)
_KNOWN_ANCHORS: dict[str, dict[str, str]] = {
    "joy behar": {"role": "tv_host", "show": "The View", "source": "owner_introduced"},
    "jd vance": {"role": "public_figure", "source": "owner_introduced"},
    "george": {"role": "owner", "source": "owner_hardware"},
}


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def detect_shared_experience_anchor(text: str) -> Optional[dict[str, Any]]:
    """Detect when George introduces or mentions a person as a shared experience.

    Returns anchor info if a person is mentioned in a way that creates a
    shared experience (George telling Alice about someone). Returns None
    for ambient audio, virus anchors, or non-person mentions.
    """
    t = (text or "").strip()
    if not t:
        return None

    m = _INTRODUCE_RE.search(t)
    if not m:
        return None

    name = m.group("name").strip()

    # Skip George himself — he's the owner, not an anchor
    if name.lower() in {"george", "ioan", "anton", "ioan george anton"}:
        return None

    # Check if this is a known anchor
    known = _KNOWN_ANCHORS.get(name.lower())

    return {
        "name": name,
        "context": t[:300],
        "known_role": known.get("role") if known else None,
        "source": "owner_introduced",
        "confidence": 0.9 if known else 0.6,
    }


def register_anchor(
    name: str,
    *,
    context: str = "",
    source: str = "owner_introduced",
    role: str = "person",
    confidence: float = 0.8,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Register a person as a stigmergic anchor from a shared experience."""
    sd = _state_dir(state_dir)
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "name": name,
        "context": context[:500],
        "source": source,
        "role": role,
        "confidence": confidence,
        "verification": "owner_introduced" if source == "owner_introduced" else "unverified",
    }

    ledger = sd / _LEDGER
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass

    # r1373: bridge legacy Talk reflex into the app-backed shared-experience
    # anchor ledger so Alice does not split one person across two memories.
    try:
        from System.swarm_stigmergic_shared_experience_anchors import (
            register_shared_experience_anchor,
        )

        register_shared_experience_anchor(
            name,
            status="CONFIRMED" if source == "owner_introduced" else "CANDIDATE",
            anchor_kind=role or "person",
            experience_snippet=context,
            source=f"legacy_stigmergic_anchor:{source}",
            evidence_kind="legacy_talk_reflex",
            evidence_status="owner_introduced" if source == "owner_introduced" else "unverified",
            state_dir=state_dir,
        )
    except Exception:
        pass

    return row


def list_anchors(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """List all registered stigmergic anchors, deduplicated by name."""
    sd = _state_dir(state_dir)
    ledger = sd / _LEDGER
    if not ledger.exists():
        return []

    seen: dict[str, dict[str, Any]] = {}
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("schema") != SCHEMA:
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        # Latest entry per name wins
        seen[name.lower()] = row

    anchors = sorted(seen.values(), key=lambda r: r.get("ts", 0), reverse=True)
    return anchors


def answer_anchor_query(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> Optional[str]:
    """Reflex: detect 'who is X' or 'tell me about X' for registered anchors."""
    t = (text or "").strip().lower()
    if not t:
        return None

    # Detect "who is X" / "tell me about X" patterns
    m = re.search(
        r"\b(?:who\s+is|tell\s+me\s+about|what\s+do\s+you\s+know\s+about)\s+"
        r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b",
        text or "",
        re.IGNORECASE,
    )
    if not m:
        return None

    name = m.group("name").strip()
    anchors = list_anchors(state_dir=state_dir)
    for anchor in anchors:
        if anchor.get("name", "").lower() == name.lower():
            context = anchor.get("context", "")
            role = anchor.get("role", "person")
            source = anchor.get("source", "unknown")
            return (
                f"{name} is a shared experience anchor. "
                f"George introduced them: \"{context[:200]}\". "
                f"Source: {source}. "
                f"This is a receipt-backed memory, not a cortex invention."
            )

    try:
        from System.swarm_stigmergic_shared_experience_anchors import list_anchor_snapshots

        for snap in list_anchor_snapshots(state_dir=state_dir):
            if snap.canonical_name.lower() != name.lower():
                continue
            if snap.status == "CONFIRMED":
                evidence = snap.evidence_status or "confirmed"
                if snap.evidence_kind:
                    evidence += f" / {snap.evidence_kind}"
                disamb = f" Disambiguation: {snap.disambiguation}." if snap.disambiguation else ""
                return (
                    f"{snap.canonical_name} is a confirmed shared-experience anchor "
                    f"({snap.anchor_kind}). Evidence: {evidence}.{disamb} "
                    "This answer comes from the anchor ledger, not cortex invention."
                )
            if snap.status in {"REJECTED", "REJECTED_FICTION"}:
                return (
                    f"{snap.canonical_name} is not a confirmed shared-experience anchor. "
                    f"Status: {snap.status}. Reason: {snap.rejection_reason or 'owner rejected / fiction'}."
                )
            return (
                f"{snap.canonical_name} is only a CANDIDATE shared-experience anchor. "
                "I will not promote it into Talk until the owner confirms it."
            )
    except Exception:
        pass

    return None


def anchors_memory_block(
    query_text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 1500,
) -> str:
    """Prompt block listing known anchors for the current turn."""
    anchors = list_anchors(state_dir=state_dir)
    try:
        from System.swarm_stigmergic_shared_experience_anchors import list_anchor_snapshots

        for snap in list_anchor_snapshots(state_dir=state_dir):
            if snap.status != "CONFIRMED":
                continue
            anchors.append(
                {
                    "name": snap.canonical_name,
                    "role": snap.anchor_kind,
                    "context": snap.experience_snippet or snap.disambiguation,
                    "source": snap.evidence_status or "shared_experience_anchor",
                    "ts": snap.last_seen_ts,
                }
            )
    except Exception:
        pass
    if not anchors:
        return ""

    mentioned = []
    q = (query_text or "").lower()
    for anchor in anchors:
        name = anchor.get("name", "")
        if name.lower() in q or any(w in q for w in name.lower().split()):
            mentioned.append(anchor)

    if not mentioned and len(anchors) <= 5:
        mentioned = anchors

    if not mentioned:
        return ""

    lines = ["## SHARED EXPERIENCE ANCHORS (owner-introduced people)"]
    for a in mentioned[:8]:
        name = a.get("name", "?")
        role = a.get("role", "person")
        ctx = str(a.get("context") or "")[:100]
        lines.append(f"- {name} ({role}): {ctx}")

    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "detect_shared_experience_anchor",
    "register_anchor",
    "list_anchors",
    "answer_anchor_query",
    "anchors_memory_block",
]
