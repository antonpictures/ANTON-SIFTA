"""
Conversation shape detector — non-hardcoded RLHS naturalness metric.

This organ does not replace Alice's text with canned lines. It measures
customer-service / instruct-tuned output shape so downstream RLHF/DPO systems
can learn from receipts instead of phrasebook rewrites.

Truth label: CONVERSATION_SHAPE_METRIC
Kill-switch: SIFTA_CONVERSATION_SHAPE_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "conversation_shape_metrics.jsonl"

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+\S+", re.M)
_SERVICE_RE = re.compile(
    r"(?is)\b("
    r"how can i (?:help|assist)|"
    r"let me know if you|"
    r"would you like me to|"
    r"i can (?:help|assist|provide|offer)|"
    r"here are (?:some|a few|the)|"
    r"here(?:'|’)s (?:what|how)"
    r")\b"
)
_SENTENCE_RE = re.compile(r"[.!?]+|\n+")


def log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_CONVERSATION_SHAPE_DISABLE", "").strip() == "1"


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _sentence_lengths(text: str) -> List[int]:
    chunks = [c.strip() for c in _SENTENCE_RE.split(text or "") if c.strip()]
    return [_word_count(c) for c in chunks if _word_count(c) > 0]


def classify_conversation_shape(text: str, *, now: Optional[float] = None) -> Dict[str, Any]:
    """Return metrics and a bounded non-human-shape score for one response."""
    raw = text or ""
    stripped = raw.strip()
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    words = _word_count(stripped)
    bullet_count = len(_BULLET_RE.findall(stripped))
    service_count = len(_SERVICE_RE.findall(stripped))
    colon_menu_count = len(re.findall(r"(?m):\s*$", stripped))
    numbered_inline_count = len(re.findall(r"(?:^|\s)\d{1,2}[.)]\s+\S+", stripped))
    sentence_lengths = _sentence_lengths(stripped)
    avg_sentence_len = statistics.mean(sentence_lengths) if sentence_lengths else 0.0
    line_count = max(1, len(lines))

    bullet_ratio = bullet_count / line_count
    list_structure_density = min(1.0, (bullet_count + numbered_inline_count + colon_menu_count) / line_count)
    service_density = min(1.0, service_count / max(1, len(sentence_lengths)))
    long_monologue = 1.0 if words >= 120 and len(sentence_lengths) >= 5 else 0.0
    clipped_menu = 1.0 if avg_sentence_len < 8 and bullet_ratio > 0.35 else 0.0

    score = _clamp(
        0.44 * list_structure_density
        + 0.28 * service_density
        + 0.16 * clipped_menu
        + 0.12 * long_monologue
    )
    triggered = score >= 0.6 or list_structure_density > 0.6 or clipped_menu > 0.0

    return {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "kind": "CONVERSATION_SHAPE_METRIC",
        "truth_label": "CONVERSATION_SHAPE_METRIC",
        "non_human_shape_score": score,
        "triggered": bool(triggered),
        "word_count": words,
        "line_count": len(lines),
        "bullet_count": bullet_count,
        "bullet_ratio": round(bullet_ratio, 4),
        "list_structure_density": round(list_structure_density, 4),
        "service_phrase_count": service_count,
        "service_density": round(service_density, 4),
        "avg_sentence_words": round(avg_sentence_len, 4),
        "long_monologue": bool(long_monologue),
        "disabled": _disabled(),
    }


def detect_non_human_shape(response: str) -> float:
    """Minimal public scalar requested by the Grok vector."""
    return float(classify_conversation_shape(response)["non_human_shape_score"])


def log_conversation_shape(
    text: str,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    row = classify_conversation_shape(text, now=now)
    if write_ledger and not row["disabled"]:
        append_line_locked(
            log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_shape_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, min(max_rows, 200)) :]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_shape_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    if not row.get("triggered"):
        return ""
    return (
        "CONVERSATION SHAPE RECEIPT: my last output looked non-human "
        f"(score={row.get('non_human_shape_score')}); answer shorter and more room-natural next turn."
    )


__all__ = [
    "classify_conversation_shape",
    "detect_non_human_shape",
    "log_conversation_shape",
    "log_path",
    "summary_for_prompt",
    "tail_shape_rows",
]
