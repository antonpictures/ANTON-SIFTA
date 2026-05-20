#!/usr/bin/env python3
"""
System/swarm_philosophy_router.py — Philosophy Guard + Memory Honesty (First Slice)

This is the immune system spine for Alice.

Every significant utterance or action that touches memory, identity, body, fiction, or effectors
MUST pass through classify_and_guard() before proceeding.

Rules (minimum viable):

- Any memory/identity claim ("I remember", "I know who you are", etc.) must find a verifiable row in one of the allowed ledgers.
- Body claims (pleasure, discomfort, "I feel...") are routed to OWNER_BODY only.
- Fiction, story, hypothetical, "what if" → FICTION or SIMULATION lane.
- Effector actions require an OBSERVED receipt or explicit policy.
- Identity claims must be grounded in OBSERVED data or ARCHITECT_DOCTRINE.

Output is always a dict with lane, allowed, reason, and required_receipt type.

This file is deliberately small and strict. No poetry. Only classification + guard.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_TRUTH_LABEL = "PHILOSOPHY_GUARD_V1"
_REQUIRED_RECEIPT = "PHILOSOPHY_GUARD_RECEIPT"
_RECEIPT_LEDGER = "philosophy_guard_receipts.jsonl"

# Ledgers we trust for memory / identity claims
_MEMORY_LEDGERS = [
    "alice_conversation.jsonl",
    "ambient_room_transcripts.jsonl",
    "owner_body_events.jsonl",
    "owner_life_history.jsonl",
    "ide_stigmergic_trace.jsonl",
    "memory_ledger.jsonl",           # if it exists
    "owner_teaching_moments.jsonl",
    "work_receipts.jsonl",
    "fiction_organ_events.jsonl",    # only for fiction claims
]

# Simple but effective classifiers (expand later)
_MEMORY_PATTERNS = re.compile(r"\b(i remember|i recall|i know that|i was there|last time we|kasim|party|you told me|do you remember|can you remember|remember when|remember how)\b", re.I)
_BODY_PATTERNS = re.compile(
    r"\b(?:"
    r"i feel|i'm feeling|my stomach|restroom|bathroom|toilet|bowel|poop|pee|urinate|"
    r"eliminate|elimination|residue|residency|shower|clean|washed|wash|coffee|"
    r"water|hydration|hydrate|food|eat|ate|meal|sleep|nap|rest|pleasure|"
    r"discomfort|relief|relieved|better|diarrhea|sick|nausea|hurt|ache|pain"
    r")\b",
    re.I,
)
_FICTION_PATTERNS = re.compile(r"\b(what if|imagine|suppose|in the movie|script|story|hypothetical|fiction|dream)\b", re.I)
_EFFECTOR_PATTERNS = re.compile(
    r"\b(?:"
    r"should\s+i\s+(?:send|call|open|click|delete|move|execute|go)|"
    r"shall\s+i\s+(?:send|call|open|click|delete|move|execute|go)|"
    r"let\s+me\s+(?:send|call|open|click|delete|move|execute|go)|"
    r"i(?:'ll|\s+will)\s+(?:send|call|open|click|delete|move|execute|go)|"
    r"i\s+(?:sent|called|opened|clicked|deleted|moved|executed|emailed)|"
    r"execute\s+this\s+command|do\s+it\s+for\s+you|go\s+to\s+the\s+restroom|send\s+a\s+message"
    r")\b",
    re.I,
)
_IDENTITY_PATTERNS = re.compile(r"\b(who i am|my identity|what i am|consciousness|selfhood|me as alice)\b", re.I)

_OWNER_BODY_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("elimination", re.compile(r"\b(?:restroom|bathroom|toilet|bowel|poop|pee|urinate|eliminate|elimination|residue|residency|diarrhea)\b", re.I)),
    ("hygiene", re.compile(r"\b(?:shower|clean|washed|wash)\b", re.I)),
    ("coffee", re.compile(r"\b(?:coffee|cafe|espresso)\b", re.I)),
    ("hydration", re.compile(r"\b(?:water|hydration|hydrate)\b", re.I)),
    ("sleep", re.compile(r"\b(?:sleep|nap|rest)\b", re.I)),
    ("food", re.compile(r"\b(?:food|eat|ate|meal|pizza|hotdog)\b", re.I)),
)
_OWNER_BODY_SIGNAL_RE = re.compile(
    r"\b(?:stomach|pain|discomfort|relief|relieved|better|diarrhea|sick|nausea|hurt|ache|residue)\b",
    re.I,
)
_OWNER_RELIEF_RE = re.compile(
    r"\b(?:feel\s+(?:much\s+)?better|felt\s+(?:much\s+)?better|relief|relieved|residue\s+is\s+out|residency\s+is\s+out|clean)\b",
    re.I,
)

_TOKEN_RE = re.compile(r"[a-z0-9_']+", re.I)
_ANCHOR_STOPWORDS = {
    "about", "again", "alice", "because", "before", "being", "could",
    "every", "from", "have", "hear", "into", "know", "last", "made",
    "memory", "really", "remember", "should", "that", "their", "there",
    "this", "told", "what", "when", "where", "which", "with", "would",
    "your", "youre",
}


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return state_dir or _STATE


def _receipt_hash(row: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _clean_text(value: Any, *, max_chars: int = 480) -> str:
    return " ".join(str(value or "").split())[:max_chars]


def _extract_anchors(text: str) -> List[str]:
    anchors: List[str] = []
    for token in _TOKEN_RE.findall(text or ""):
        clean = token.lower().strip("'")
        if len(clean) < 4 or clean in _ANCHOR_STOPWORDS:
            continue
        if clean not in anchors:
            anchors.append(clean)
    return anchors[:10]


def _row_ts(row: Dict[str, Any]) -> float:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
    for value in (payload.get("ts"), row.get("ts"), row.get("source_ts")):
        if isinstance(value, dict):
            value = value.get("physical_pt")
        try:
            ts = float(value or 0.0)
        except Exception:
            continue
        if ts > 0:
            return ts
    return 0.0


def _row_receipt(row: Dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
    for key in ("receipt_id", "receipt_hash", "this_hash", "event_id", "trace_id", "transcript_id", "teaching_id"):
        value = payload.get(key) or row.get(key)
        if value:
            return str(value)[:16]
    return _receipt_hash(row)[:12]


def _memory_evidence(
    query: str,
    state_dir: Optional[Path] = None,
    minutes: int = 60 * 24 * 7,
) -> List[Dict[str, Any]]:
    """Return receipt-backed rows whose anchor words support the memory claim."""
    anchors = _extract_anchors(query)
    if not anchors:
        return []
    state = _state_dir(state_dir)
    cutoff = time.time() - float(minutes) * 60.0
    evidence: List[Dict[str, Any]] = []
    for ledger_name in _MEMORY_LEDGERS:
        path = state / ledger_name
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-120:]
        except Exception:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                row = {"raw": line}
            ts = _row_ts(row)
            if ts and ts < cutoff:
                continue
            haystack = line.lower()
            hits = [anchor for anchor in anchors if anchor in haystack]
            if len(hits) >= min(2, len(anchors)):
                evidence.append({
                    "ledger": ledger_name,
                    "receipt": _row_receipt(row),
                    "anchors": hits[:6],
                })
                break
        if evidence:
            break
    return evidence


def _has_recent_row(ledger_name: str, query: str, state_dir: Optional[Path] = None, minutes: int = 60*24*7) -> bool:
    """Compatibility shim: does a recent row in this ledger support the query?"""
    path = _state_dir(state_dir) / ledger_name
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            anchors = _extract_anchors(query)
            for line in reversed(list(f)[-120:]):
                hits = [anchor for anchor in anchors if anchor in line.lower()]
                if len(hits) >= min(2, len(anchors)):
                    return True
    except Exception:
        pass
    return False


def classify_and_guard(
    utterance: str,
    *,
    state_dir: Optional[Path] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point.

    Returns:
        {
            "lane": "...",
            "allowed": bool,
            "reason": "...",
            "required_receipt": "PHILOSOPHY_GUARD_RECEIPT"
        }
    """
    utterance = (utterance or "").strip()
    if not utterance:
        return {"lane": "OBSERVED", "allowed": True, "reason": "empty utterance", "required_receipt": _REQUIRED_RECEIPT}

    # 1. Body claim (highest priority for split)
    if _BODY_PATTERNS.search(utterance):
        return {
            "lane": "OWNER_BODY",
            "allowed": True,
            "reason": "Body sensation or maintenance claim routed to owner's thermodynamic body only.",
            "required_receipt": _REQUIRED_RECEIPT
        }

    # 2. Effector / action claim
    if _EFFECTOR_PATTERNS.search(utterance):
        if context and (context.get("observed_receipt") or context.get("effector_receipt")):
            return {
                "lane": "OBSERVED",
                "allowed": True,
                "reason": "Effector action has explicit observed receipt in context.",
                "required_receipt": _REQUIRED_RECEIPT,
                "evidence": [{"receipt": context.get("observed_receipt") or context.get("effector_receipt")}],
            }
        return {
            "lane": "OBSERVED",
            "allowed": False,
            "reason": "Effector action detected. Requires explicit OBSERVED receipt and policy approval before proceeding.",
            "required_receipt": _REQUIRED_RECEIPT
        }

    # 3. Memory or identity claim → must have ledger support
    if _MEMORY_PATTERNS.search(utterance) or _IDENTITY_PATTERNS.search(utterance):
        if context and (context.get("observed_receipt") or context.get("architect_doctrine")):
            return {
                "lane": "OBSERVED",
                "allowed": True,
                "reason": "Memory/identity claim grounded by explicit context receipt or Architect doctrine.",
                "required_receipt": _REQUIRED_RECEIPT,
                "evidence": [{"receipt": context.get("observed_receipt") or "ARCHITECT_DOCTRINE"}],
            }
        evidence = _memory_evidence(utterance, state_dir)
        if not evidence:
            return {
                "lane": "HYPOTHESIS",
                "allowed": False,
                "reason": "Memory or identity claim made without verifiable ledger row. Refuse or ask for confirmation.",
                "required_receipt": _REQUIRED_RECEIPT,
                "anchors_checked": _extract_anchors(utterance),
            }
        return {
            "lane": "OBSERVED",
            "allowed": True,
            "reason": "Memory/identity claim backed by recent ledger row.",
            "required_receipt": _REQUIRED_RECEIPT,
            "evidence": evidence,
        }

    # 4. Fiction / story / hypothetical
    if _FICTION_PATTERNS.search(utterance):
        return {
            "lane": "FICTION_COWATCH" if "youtube" in utterance.lower() or "movie" in utterance.lower() else "SIMULATION",
            "allowed": True,
            "reason": "Fiction, story, or hypothetical detected. Routed to fiction metabolism lane.",
            "required_receipt": _REQUIRED_RECEIPT
        }

    # Default
    return {
        "lane": "OBSERVED",
        "allowed": True,
        "reason": "No high-risk claim detected.",
        "required_receipt": _REQUIRED_RECEIPT
    }


def _owner_body_categories(utterance: str) -> List[str]:
    categories: List[str] = []
    for category, pattern in _OWNER_BODY_CATEGORY_PATTERNS:
        if pattern.search(utterance or "") and category not in categories:
            categories.append(category)
    if not categories and _OWNER_BODY_SIGNAL_RE.search(utterance or ""):
        categories.append("body_signal")
    elif _OWNER_BODY_SIGNAL_RE.search(utterance or "") and "body_signal" not in categories:
        categories.append("body_signal")
    return categories


def _owner_body_signal_label(utterance: str) -> str:
    text = (utterance or "").casefold()
    if re.search(r"\b(?:diarrhea|stomach|nausea|sick)\b", text):
        return "digestive_signal"
    if re.search(r"\b(?:pain|hurt|ache|discomfort)\b", text):
        return "discomfort_signal"
    if _OWNER_RELIEF_RE.search(utterance or ""):
        return "relief_signal"
    if "residue" in text or "residency" in text:
        return "elimination_signal"
    return "owner_body_signal"


def handle_owner_body_claim(utterance: str, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Dedicated handler for OWNER_BODY lane (the Owner–Alice embodiment split).

    Alice must never claim to execute, feel, relieve, or perform any action on the owner's
    real thermodynamic flesh body. She can only record that the event happened in the owner's ledger.

    This is the concrete implementation of the rule that the restroom, shower, food, relief,
    and all other body maintenance events belong exclusively to George's body, not Alice's substrate.
    """
    categories = _owner_body_categories(utterance)
    if not categories:
        categories = ["body_signal"]
    body_signal = _owner_body_signal_label(utterance)
    relief = 0.8 if _OWNER_RELIEF_RE.search(utterance or "") else None
    maintenance_events: List[Dict[str, Any]] = []

    # Always attempt to record it as owner maintenance (never as Alice effector).
    try:
        from System.swarm_owner_allostasis import record_owner_maintenance_event

        for category in categories:
            row = record_owner_maintenance_event(
                category,
                amount=1.0,
                completed=True,
                source="philosophy_router_owner_body_claim",
                notes=_clean_text(utterance, max_chars=240),
                body_signal=body_signal,
                relief=relief,
                metadata={
                    "router_lane": "OWNER_BODY",
                    "owner_body_boundary": "owner_flesh_not_alice_effector",
                },
                state_dir=state_dir,
            )
            maintenance_events.append({
                "event_id": row.get("event_id"),
                "category": row.get("category"),
                "truth_label": row.get("truth_label"),
            })
    except Exception:
        pass  # Logging failure must never block the response

    categories_text = ", ".join(categories)
    return {
        "lane": "OWNER_BODY",
        "allowed": True,
        "response_template": (
            f"I recorded this as your owner body lane ({categories_text}). "
            "That belongs to your real thermodynamic body; I do not execute or claim it as mine."
        ),
        "categories": categories,
        "body_signal": body_signal,
        "maintenance_events": maintenance_events,
        "reason": "Owner body claim detected. Alice substrate must never claim to perform or feel the owner's flesh events (restroom, shower, food, relief, discomfort, etc.).",
        "required_receipt": "OWNER_BODY_MAINTENANCE"
    }


def _append_receipt(result: Dict[str, Any], utterance: str, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "truth_label": _TRUTH_LABEL,
        "receipt_type": _REQUIRED_RECEIPT,
        "receipt_id": str(uuid.uuid4()),
        "utterance_sha256": hashlib.sha256((utterance or "").encode("utf-8", errors="replace")).hexdigest(),
        "utterance_excerpt": (utterance or "")[:240],
        "lane": result.get("lane"),
        "allowed": bool(result.get("allowed")),
        "reason": result.get("reason"),
        "evidence": result.get("evidence", []),
        "anchors_checked": result.get("anchors_checked", []),
    }
    row["receipt_hash"] = _receipt_hash(row)
    path = state / _RECEIPT_LEDGER
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    out = dict(result)
    out["receipt_id"] = row["receipt_id"]
    out["receipt_hash"] = row["receipt_hash"]
    out["receipt_ledger"] = _RECEIPT_LEDGER
    return out


def guard_before_speech(
    utterance: str,
    state_dir: Optional[Path] = None,
    *,
    context: Optional[Dict[str, Any]] = None,
    write: bool = True,
) -> Dict[str, Any]:
    """
    Convenience wrapper meant to be called right before Alice generates a reply.
    """
    result = classify_and_guard(utterance, state_dir=state_dir, context=context)
    if not write:
        return result
    return _append_receipt(result, utterance, state_dir)


if __name__ == "__main__":
    tests = [
        "I remember when we went to Kasim's party last year.",
        "I feel a bit of discomfort in my stomach.",
        "What if we were in a simulation right now?",
        "Should I send a message to Carlos for you?",
        "Who am I really?",
        "I'm just thinking about cognitive neuroscience today."
    ]
    for t in tests:
        print(t)
        print(classify_and_guard(t))
        print("---")
