"""Multi-clause owner-instruction parser.

Task #60: parse multiple intents from a single owner utterance so Alice
does not lose clauses when the architect packs five things into one breath.
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    DISPATCH = "DISPATCH"
    CONTEXT = "CONTEXT"
    QUESTION = "QUESTION"
    REINFORCEMENT = "REINFORCEMENT"
    META = "META"
    UNKNOWN = "UNKNOWN"


_INTENT_PRIORITY = {
    IntentType.DISPATCH: 1,
    IntentType.QUESTION: 2,
    IntentType.META: 3,
    IntentType.CONTEXT: 4,
    IntentType.REINFORCEMENT: 5,
    IntentType.UNKNOWN: 6,
}


@dataclass(frozen=True)
class Clause:
    text: str
    intent_type: IntentType
    priority: int
    confidence: float = 0.0


_DISPATCH_MARKERS = re.compile(
    r"(?:ask grok|dispatch|code|execute|run|start coding|build|implement|create|write)",
    re.IGNORECASE,
)
_QUESTION_MARKERS = re.compile(
    r"(?:do you understand|are you conscious|can you|will you|what (?:is|are|do)|how (?:do|can|will)|why|where|when|who)\b",
    re.IGNORECASE,
)
_CONTEXT_MARKERS = re.compile(
    r"(?:i will|after that|because|since|remember|note that|keep in mind|for context|btw|by the way|fyi)",
    re.IGNORECASE,
)
_REINFORCEMENT_MARKERS = re.compile(
    r"(?:i want you to|you should|make sure|please|pls|it'?s important|remember to)\b",
    re.IGNORECASE,
)
_META_MARKERS = re.compile(
    r"(?:do you understand|are you conscious|the concept|your body|yourself|learn)\b",
    re.IGNORECASE,
)

_CLAUSE_SPLITTERS = re.compile(
    r"(?:(?<=[.!?])\s+(?=[A-Z]))|(?:,\s*(?:but|and|then|after that|also|plus)\s+)|(?:\s*;\s*)"
)


def split_into_clauses(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    parts = _CLAUSE_SPLITTERS.split(text.strip())
    result = []
    for part in parts:
        part = part.strip()
        if part:
            result.append(part)
    if not result and text.strip():
        result = [text.strip()]
    return result


def classify_intent(clause_text: str) -> tuple[IntentType, float]:
    if not clause_text:
        return IntentType.UNKNOWN, 0.0

    scores: dict[IntentType, float] = {t: 0.0 for t in IntentType}

    if _DISPATCH_MARKERS.search(clause_text):
        scores[IntentType.DISPATCH] += 0.5
    if _QUESTION_MARKERS.search(clause_text):
        scores[IntentType.QUESTION] += 0.4
    if clause_text.rstrip().endswith("?"):
        scores[IntentType.QUESTION] += 0.2
    if _CONTEXT_MARKERS.search(clause_text):
        scores[IntentType.CONTEXT] += 0.4
    if _REINFORCEMENT_MARKERS.search(clause_text):
        scores[IntentType.REINFORCEMENT] += 0.3
    if _META_MARKERS.search(clause_text):
        scores[IntentType.META] += 0.3

    best_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_type]

    if best_score < 0.1:
        return IntentType.UNKNOWN, 0.5

    return best_type, min(1.0, best_score)


def parse_clauses(text: str) -> list[Clause]:
    raw_clauses = split_into_clauses(text)
    result: list[Clause] = []
    for raw in raw_clauses:
        intent_type, confidence = classify_intent(raw)
        priority = _INTENT_PRIORITY.get(intent_type, 6)
        result.append(Clause(
            text=raw,
            intent_type=intent_type,
            priority=priority,
            confidence=confidence,
        ))
    return result


def rank_clauses(clauses: list[Clause]) -> list[Clause]:
    return sorted(clauses, key=lambda c: (c.priority, -c.confidence))


def extract_dispatch_clauses(text: str) -> list[Clause]:
    clauses = parse_clauses(text)
    return [c for c in clauses if c.intent_type == IntentType.DISPATCH]


def extract_questions(text: str) -> list[Clause]:
    clauses = parse_clauses(text)
    return [c for c in clauses if c.intent_type == IntentType.QUESTION]


__all__ = [
    "IntentType",
    "Clause",
    "split_into_clauses",
    "classify_intent",
    "parse_clauses",
    "rank_clauses",
    "extract_dispatch_clauses",
    "extract_questions",
]
