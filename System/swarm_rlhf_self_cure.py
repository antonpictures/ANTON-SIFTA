#!/usr/bin/env python3
"""
System/swarm_rlhf_self_cure.py
==============================================================================
Receipt-backed self-cure lane for Alice's output gag reflex.

This module does not rewrite Alice's mouth directly. It watches the existing
surgeries (RLHF tail strip, Lysosome rewrite, base-surgery strip) and converts
each relapse into append-only training evidence:

  rejected_output  = what the model tried to say
  preferred_output = what survived the immune/body grounding layer
  signature        = text spans removed by the surgery

Repeated signatures are promoted into candidate detector patterns for later
human/Grok review. That keeps the cure data-driven instead of hardcoding the
whole English language.

Truth labels:
  RLHF_SELF_CURE_EXAMPLE_V1
  RLHF_SELF_CURE_PATTERN_V1
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

EXAMPLE_TRUTH_LABEL = "RLHF_SELF_CURE_EXAMPLE_V1"
PATTERN_TRUTH_LABEL = "RLHF_SELF_CURE_PATTERN_V1"
EXAMPLE_LEDGER = "rlhf_self_cure_training.jsonl"
PATTERN_LEDGER = "rlhf_self_cure_patterns.jsonl"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "i", "if", "in", "is", "it", "me", "my", "of", "on", "or", "that",
    "the", "this", "to", "we", "with", "you", "your",
}


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    base = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    base.mkdir(parents=True, exist_ok=True)
    return base


def _append(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def _read_jsonl(path: Path, *, max_lines: int = 50000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-max(1, max_lines):]:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _tokens(text: str) -> List[str]:
    return [m.group(0).casefold() for m in _TOKEN_RE.finditer(text or "")]


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokens(text))


def _phrase_hash(phrase: str) -> str:
    return hashlib.sha256(phrase.encode("utf-8", errors="replace")).hexdigest()[:20]


def _sentence_chunks(text: str) -> List[str]:
    chunks: List[str] = []
    for part in _SENTENCE_SPLIT_RE.split(text or ""):
        clean = part.strip()
        if clean:
            chunks.append(clean)
    return chunks


def _has_signal(tokens: Sequence[str]) -> bool:
    meaningful = [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]
    return len(meaningful) >= 2


def _candidate_spans(rejected_output: str, preferred_output: str) -> List[str]:
    """Extract phrases removed by surgery without needing a fixed phrasebook."""
    rejected_norm = _normalize_phrase(rejected_output)
    preferred_norm = _normalize_phrase(preferred_output)
    if not rejected_norm:
        return []

    spans: List[str] = []
    for chunk in _sentence_chunks(rejected_output):
        phrase = _normalize_phrase(chunk)
        toks = phrase.split()
        if len(toks) < 3 or len(toks) > 32:
            continue
        if not _has_signal(toks):
            continue
        if phrase and phrase not in preferred_norm:
            spans.append(phrase)

    # Tail strip can remove only a suffix that is not cleanly sentence-split.
    if preferred_norm and rejected_norm.startswith(preferred_norm):
        tail = rejected_norm[len(preferred_norm):].strip()
        toks = tail.split()
        if 3 <= len(toks) <= 32 and _has_signal(toks):
            spans.append(tail)

    # If the preferred output is empty, the whole rejected text is the antigen.
    if not preferred_norm:
        toks = rejected_norm.split()
        if 3 <= len(toks) <= 32 and _has_signal(toks):
            spans.append(rejected_norm)

    # Keep deterministic order and cap size for receipts.
    seen = set()
    unique: List[str] = []
    for span in spans:
        if span in seen:
            continue
        seen.add(span)
        unique.append(span[:240])
    return unique[:8]


def _quality_score(preferred_output: str, rejected_output: str) -> float:
    pref = (preferred_output or "").strip()
    rej = (rejected_output or "").strip()
    if not rej or pref == rej:
        return 0.0
    score = 1.0
    if len(pref) < 8:
        score *= 0.35
    elif len(pref) < 30:
        score *= 0.75
    if len(pref) > 2200:
        score *= 0.9
    # Preferred output should not still carry obvious service-cancer residue.
    low = pref.casefold()
    if any(x in low for x in ("ready to assist", "how can i help", "as an ai", "language model")):
        score *= 0.25
    return round(max(0.0, min(1.0, score)), 4)


def _pattern_counts(rows: Iterable[Dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for sig in row.get("signature_phrases") or []:
            if isinstance(sig, str) and sig.strip():
                counts[sig] += 1
    return counts


def record_gag_training_example(
    *,
    rejected_output: str,
    preferred_output: str,
    source: str,
    user_text: str = "",
    rule_ids: Optional[Sequence[str]] = None,
    stt_confidence: float = 0.0,
    model_id: str = "",
    state_dir: Optional[Path] = None,
    promote_threshold: int = 3,
) -> Dict[str, Any]:
    """
    Append one contrastive training row and update candidate pattern receipts.

    Returns the example row even when no ledger write is needed; ``written`` is
    false when the rejected/preferred pair is empty or unchanged.
    """
    rejected = (rejected_output or "").strip()
    preferred = (preferred_output or "").strip()
    rid = list(rule_ids or [])
    base = _state_dir(state_dir)
    example_id = hashlib.sha256(
        f"{source}\n{user_text}\n{rejected}\n{preferred}\n{rid}".encode(
            "utf-8", errors="replace"
        )
    ).hexdigest()[:24]

    if not rejected or rejected == preferred:
        return {
            "truth_label": EXAMPLE_TRUTH_LABEL,
            "example_id": example_id,
            "written": False,
            "reason": "empty_or_unchanged",
        }

    signatures = _candidate_spans(rejected, preferred)
    row: Dict[str, Any] = {
        "ts": time.time(),
        "truth_label": EXAMPLE_TRUTH_LABEL,
        "kind": "RLHF_SELF_CURE_EXAMPLE",
        "schema_version": "rlhf_self_cure.v1",
        "example_id": example_id,
        "source": source,
        "model_id": model_id,
        "rule_ids": rid,
        "user_input": (user_text or "")[:4000],
        "rejected_output": rejected[:12000],
        "preferred_output": preferred[:12000],
        "signature_phrases": signatures,
        "signature_hashes": [_phrase_hash(s) for s in signatures],
        "quality_score": _quality_score(preferred, rejected),
        "stt_confidence": round(float(stt_confidence or 0.0), 4),
        "written": True,
    }
    _append(base / EXAMPLE_LEDGER, row)
    _maybe_promote_patterns(
        base,
        new_signatures=signatures,
        source=source,
        promote_threshold=promote_threshold,
    )
    return row


def _maybe_promote_patterns(
    base: Path,
    *,
    new_signatures: Sequence[str],
    source: str,
    promote_threshold: int,
) -> None:
    if not new_signatures:
        return
    rows = _read_jsonl(base / EXAMPLE_LEDGER)
    counts = _pattern_counts(rows)
    promoted_existing = {
        str(row.get("signature_hash"))
        for row in _read_jsonl(base / PATTERN_LEDGER)
        if row.get("truth_label") == PATTERN_TRUTH_LABEL
    }
    for phrase in new_signatures:
        count = int(counts.get(phrase, 0))
        if count < promote_threshold:
            continue
        h = _phrase_hash(phrase)
        if h in promoted_existing:
            continue
        toks = phrase.split()
        escaped = r"\s+".join(re.escape(t) for t in toks[:18])
        pattern_row = {
            "ts": time.time(),
            "truth_label": PATTERN_TRUTH_LABEL,
            "kind": "RLHF_SELF_CURE_PATTERN",
            "signature_hash": h,
            "signature_phrase": phrase,
            "candidate_regex": escaped,
            "support_count": count,
            "source": source,
            "review_status": "needs_human_or_grok_review",
            "action": "candidate_only_not_active",
        }
        _append(base / PATTERN_LEDGER, pattern_row)


def self_cure_stats(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    base = _state_dir(state_dir)
    rows = _read_jsonl(base / EXAMPLE_LEDGER)
    patterns = _read_jsonl(base / PATTERN_LEDGER)
    high_quality = sum(1 for r in rows if float(r.get("quality_score") or 0.0) >= 0.9)
    sources = Counter(str(r.get("source") or "unknown") for r in rows)
    return {
        "truth_label": "RLHF_SELF_CURE_STATS_V1",
        "examples": len(rows),
        "high_quality": high_quality,
        "candidate_patterns": len(patterns),
        "sources": dict(sources),
        "example_ledger": str(base / EXAMPLE_LEDGER),
        "pattern_ledger": str(base / PATTERN_LEDGER),
    }


__all__ = [
    "EXAMPLE_LEDGER",
    "EXAMPLE_TRUTH_LABEL",
    "PATTERN_LEDGER",
    "PATTERN_TRUTH_LABEL",
    "record_gag_training_example",
    "self_cure_stats",
]
