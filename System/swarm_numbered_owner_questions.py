#!/usr/bin/env python3
"""swarm_numbered_owner_questions.py — r1621-03: answer numbered owner questions.

Glass fail: owner sends 1. 2. 3. after cortex switch; mouth pivots to eBay/Alfred residue.

Pure scaffold for cortex prompt — does not prebrain-answer.

Truth label: NUMBERED_OWNER_QUESTIONS_V1
"""

from __future__ import annotations

import re
from typing import Any

TRUTH_LABEL = "NUMBERED_OWNER_QUESTIONS_V1"

# 1. / 1) / 1: / (1)
_NUM_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:\(?\s*(\d{1,2})\s*[.)\]]\s*|(\d{1,2})\s*[-:]\s+)(.+)",
    re.MULTILINE,
)


def extract_numbered_questions(text: str) -> list[dict[str, Any]]:
    """Return ordered {n, text} for owner lines that look like numbered Qs."""
    raw = str(text or "")
    if not raw.strip():
        return []
    found: list[dict[str, Any]] = []
    seen_n: set[int] = set()
    for m in _NUM_LINE_RE.finditer(raw):
        n_s = m.group(1) or m.group(2) or ""
        body = (m.group(3) or "").strip()
        if not n_s or not body:
            continue
        try:
            n = int(n_s)
        except ValueError:
            continue
        if n < 1 or n > 20 or n in seen_n:
            continue
        # Drop pure switch debris
        if re.search(r"SELF_CODE_|SELF_READ", body, re.I):
            continue
        seen_n.add(n)
        found.append({"n": n, "text": body[:400]})
    found.sort(key=lambda r: int(r["n"]))
    return found


def is_numbered_owner_questions_turn(text: str) -> bool:
    qs = extract_numbered_questions(text)
    return len(qs) >= 2


def numbered_questions_teaching_block(user_text: str = "", *, max_chars: int = 1200) -> str:
    """Force answering each number; forbid topic-steal from browser residue."""
    qs = extract_numbered_questions(user_text)
    if len(qs) < 2:
        return ""
    lines = [
        "NUMBERED OWNER QUESTIONS (r1621-03 — answer EACH number, in order):",
        "Rules: answer 1, then 2, then 3… with explicit '1.' '2.' prefixes.",
        "Do NOT pivot to Alfred/eBay/screenshot/browser residue unless a numbered "
        "question is about that topic.",
        "Do NOT skip a number. If unknown, say so under that number.",
        "Questions:",
    ]
    for q in qs:
        lines.append(f"  {q['n']}. {q['text']}")
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "extract_numbered_questions",
    "is_numbered_owner_questions_turn",
    "numbered_questions_teaching_block",
]
