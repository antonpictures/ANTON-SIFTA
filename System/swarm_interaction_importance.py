#!/usr/bin/env python3
"""Deterministic interaction-importance labels for Alice's live journal.

This module is deliberately small and local. It does not decide what Alice
should say; it only gives each conversation turn a stable memory signal so
later consolidation can tell phatic/noisy turns from date/time questions,
tool commands, identity turns, and high-value memory material.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

TRUTH_LABEL = "INTERACTION_IMPORTANCE_V1"

_TIME_DATE_RE = re.compile(
    r"\b("
    r"what(?:'s| is)?\s+(?:the\s+)?(?:time|date|day)|"
    r"tell\s+me\s+(?:the\s+)?(?:time|date|day)|"
    r"current\s+(?:time|date|day)|"
    r"today|tonight|this\s+morning|this\s+afternoon|this\s+evening"
    r")\b",
    re.IGNORECASE,
)

_MEMORY_RE = re.compile(
    r"\b("
    r"remember|memory|journal|write\s+(?:it\s+)?down|log\s+it|receipt|"
    r"important|importance|magic\s+memory|life\s+journal|first[- ]person|"
    r"doctrine|covenant"
    r")\b",
    re.IGNORECASE,
)

_ACTION_RE = re.compile(
    r"\b("
    r"send|open|close|change|switch|execute|run|code|test|fix|repair|"
    r"search|download|push|pull|save|delete|launch|stop|start|wake|sleep"
    r")\b",
    re.IGNORECASE,
)

_IDENTITY_RE = re.compile(
    r"\b(alice|george|ioan|sifta|swarm|owner|architect|gemma|ollama|codex|cursor|claude)\b",
    re.IGNORECASE,
)

_NOISE_RE = re.compile(
    r"^\s*(?:"
    r"ah+|oh+|uh+|um+|hm+|mm+|yeah(?:\s+bro)?|no(?:\s+no)?|ok(?:ay)?|sure|hello|hi"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def _band(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.38:
        return "medium"
    if score >= 0.18:
        return "low"
    return "noise"


def _memory_action(band: str) -> str:
    if band == "critical":
        return "promote_to_life_journal"
    if band == "high":
        return "pin_working_memory"
    if band == "medium":
        return "journal"
    if band == "low":
        return "journal_low_weight"
    return "ignore_noise"


def classify_interaction_importance(
    text: str,
    *,
    role: str = "user",
    stt_confidence: float = 0.0,
    model: str = "",
) -> Dict[str, Any]:
    """Return a deterministic importance row for one chat turn."""
    raw = text or ""
    folded_role = (role or "").strip().lower() or "unknown"
    reasons: List[str] = []

    if _NOISE_RE.match(raw):
        score = 0.08
        reasons.append("phatic_or_noise")
    else:
        score = 0.30 if folded_role == "user" else 0.20
        if _TIME_DATE_RE.search(raw):
            score += 0.35
            reasons.append("time_or_date_query")
        if _MEMORY_RE.search(raw):
            score += 0.40
            reasons.append("memory_or_receipt")
        if _ACTION_RE.search(raw):
            score += 0.30
            reasons.append("tool_or_effector")
        if _IDENTITY_RE.search(raw):
            score += 0.25
            reasons.append("identity_or_swarm")
        if "?" in raw:
            score += 0.15
            reasons.append("question")
        if folded_role == "alice" and model:
            score += 0.08
            reasons.append("alice_reply")

    try:
        conf = float(stt_confidence or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if folded_role == "user" and conf:
        if conf >= 0.75:
            score += 0.08
            reasons.append("high_stt_confidence")
        elif conf < 0.35:
            score -= 0.18
            reasons.append("low_stt_confidence")

    score = max(0.0, min(1.0, score))
    band = _band(score)
    return {
        "truth_label": TRUTH_LABEL,
        "role": folded_role,
        "importance_score": round(score, 3),
        "importance_band": band,
        "memory_action": _memory_action(band),
        "reasons": reasons or ["ordinary_turn"],
        "is_time_or_date_query": bool(_TIME_DATE_RE.search(raw)),
    }


def journal_witness_line(text: str, classification: Dict[str, Any]) -> str:
    """Compact first-person line for alice_first_person_journal.jsonl."""
    raw = (text or "").strip().replace("\n", " ")
    if len(raw) > 180:
        raw = raw[:177] + "..."
    role = str(classification.get("role") or "unknown")
    band = str(classification.get("importance_band") or "low")
    action = str(classification.get("memory_action") or "journal")
    reasons = ", ".join(str(x) for x in classification.get("reasons", [])[:4])
    if role == "user":
        return (
            f"George said: {raw!r}. I marked it {band} importance; "
            f"memory_action={action}; reasons={reasons}."
        )
    return (
        f"I answered: {raw!r}. I marked my reply {band} importance; "
        f"memory_action={action}; reasons={reasons}."
    )
