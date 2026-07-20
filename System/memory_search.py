#!/usr/bin/env python3
"""
memory_search.py — local hybrid recall helpers over canonical JSONL ledgers.

This is not a second memory organ and it never owns storage. The append-only
JSONL ledgers remain canonical; this module only builds typed, in-memory views
for supersession filtering, BM25-lite ranking, optional vector rankings, and
RRF fusion.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable as IterableABC
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MEMORY_LANES = ("facts", "episodes", "procedures")
LANE_ALIASES = {
    "fact": "facts",
    "facts": "facts",
    "semantic": "facts",
    "semantics": "facts",
    "knowledge": "facts",
    "episode": "episodes",
    "episodes": "episodes",
    "episodic": "episodes",
    "hippocampus": "episodes",
    "event": "episodes",
    "events": "episodes",
    "procedure": "procedures",
    "procedures": "procedures",
    "procedural": "procedures",
    "skill": "procedures",
    "skills": "procedures",
    "how_to": "procedures",
    "playbook": "procedures",
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]{2,}")
_PROCEDURE_HINTS = (
    "step ",
    "steps",
    "procedure",
    "playbook",
    "how to",
    "run ",
    "command",
    "checklist",
    "recipe",
)
_EPISODE_HINTS = (
    "journal",
    "diary",
    "episode",
    "event",
    "conversation",
    "transcript",
    "receipt",
    "happened",
)


def load_jsonl_rows(paths: Iterable[Path | str]) -> list[dict[str, Any]]:
    """Load JSONL rows from existing ledgers, annotating each row with its source."""
    rows: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                row = {"raw_text": line}
            if isinstance(row, dict):
                copy = dict(row)
            else:
                copy = {"value": row}
            copy.setdefault("_ledger_path", str(path))
            copy.setdefault("_ledger_line", line_no)
            rows.append(copy)
    return rows


def trace_key(row: Mapping[str, Any]) -> str:
    """Return a stable row id for rank fusion and supersession."""
    for key in ("trace_id", "event_id", "receipt_id", "receipt", "semantic_hash"):
        value = row.get(key)
        if value:
            return str(value)
    payload = json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def supersedes_trace_ids(row: Mapping[str, Any]) -> set[str]:
    """Read one row's supersession pointers."""
    out: set[str] = set()
    for key in ("supersedes_trace_id", "supersedes_trace_ids", "supersedes"):
        value = row.get(key)
        if not value:
            continue
        if isinstance(value, str):
            out.add(value)
        elif isinstance(value, IterableABC):
            out.update(str(item) for item in value if item)
    return out


def superseded_trace_id_set(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    """Return all trace ids made stale by newer append-only rows."""
    stale: set[str] = set()
    for row in rows:
        stale.update(supersedes_trace_ids(row))
    return stale


def active_memory_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    """Filter append-only ledgers so newer superseding facts win at read time."""
    materialized = [dict(row) for row in rows]
    if include_superseded:
        return materialized
    stale = superseded_trace_id_set(materialized)
    return [row for row in materialized if trace_key(row) not in stale]


def classify_memory_lane(row: Mapping[str, Any]) -> str:
    """Classify one canonical row into a typed view: facts, episodes, procedures."""
    explicit = (
        row.get("memory_lane")
        or row.get("lane")
        or row.get("memory_type")
        or row.get("type")
        or row.get("kind")
    )
    if explicit:
        mapped = LANE_ALIASES.get(str(explicit).strip().lower())
        if mapped:
            return mapped

    source_blob = " ".join(
        str(row.get(key) or "")
        for key in ("_ledger_path", "ledger", "source", "app_context", "schema", "kind", "type")
    ).lower()
    if any(token in source_blob for token in ("hippocampus", "episodic", "diary", "journal", "conversation", "event")):
        return "episodes"
    if any(token in source_blob for token in ("procedure", "procedural", "skill", "playbook", "how_to")):
        return "procedures"

    text = row_text(row).lower()
    if any(hint in text for hint in _PROCEDURE_HINTS):
        return "procedures"
    if any(hint in text for hint in _EPISODE_HINTS):
        return "episodes"
    return "facts"


def typed_memory_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    lanes: Iterable[str] | None = None,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    """Return active rows annotated with memory_lane and optionally lane-filtered."""
    allowed = None
    if lanes is not None:
        allowed = {LANE_ALIASES.get(str(lane).lower(), str(lane).lower()) for lane in lanes}
    typed: list[dict[str, Any]] = []
    for row in active_memory_rows(rows, include_superseded=include_superseded):
        lane = classify_memory_lane(row)
        if allowed is not None and lane not in allowed:
            continue
        copy = dict(row)
        copy["memory_lane"] = lane
        typed.append(copy)
    return typed


def row_text(row: Mapping[str, Any]) -> str:
    """Extract searchable text without assuming one ledger schema."""
    priority = (
        "raw_text",
        "text",
        "content",
        "message",
        "summary",
        "note",
        "lesson_short",
        "abstract_rule",
        "action",
        "intent",
        "status",
        "prompt",
    )
    parts: list[str] = []

    def visit(value: Any, depth: int = 0) -> None:
        if len(" ".join(parts)) > 2400 or depth > 4:
            return
        if isinstance(value, str):
            value = value.strip()
            if value:
                parts.append(value[:500])
            return
        if isinstance(value, MappingABC):
            for key in priority:
                if key in value:
                    visit(value.get(key), depth + 1)
            if not parts:
                for sub in value.values():
                    visit(sub, depth + 1)
            return
        if isinstance(value, SequenceABC) and not isinstance(value, (str, bytes, bytearray)):
            for item in value[:8]:
                visit(item, depth + 1)

    for key in priority:
        if key in row:
            visit(row.get(key))
    if not parts:
        visit(dict(row))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def bm25_lite_rank(
    query: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Dependency-free BM25-style lexical ranking over JSONL rows."""
    q_tokens = tokenize(query)
    materialized = [dict(row) for row in rows]
    docs = [(trace_key(row), tokenize(row_text(row) + " " + str(row.get("semantic_tags") or ""))) for row in materialized]
    if not q_tokens or not docs:
        return []

    doc_freq: Counter[str] = Counter()
    for _, tokens in docs:
        doc_freq.update(set(tokens))
    avg_len = sum(len(tokens) for _, tokens in docs) / max(1, len(docs))
    k1 = 1.5
    b = 0.75
    n_docs = len(docs)
    scores: dict[str, float] = {}
    for doc_id, tokens in docs:
        if not tokens:
            continue
        tf = Counter(tokens)
        doc_len = len(tokens)
        score = 0.0
        for term in q_tokens:
            freq = tf.get(term, 0)
            if freq <= 0:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1.0 + ((n_docs - df + 0.5) / (df + 0.5)))
            denom = freq + k1 * (1.0 - b + b * (doc_len / max(1.0, avg_len)))
            score += idf * ((freq * (k1 + 1.0)) / denom)
        if score > 0.0:
            scores[doc_id] = score

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ranked[:top_k] if top_k else ranked


def _ranking_id(item: Any) -> str:
    if isinstance(item, tuple) and item:
        return str(item[0])
    if isinstance(item, Mapping):
        return trace_key(item)
    return str(item)


def rrf_merge(
    rankings: Iterable[Iterable[Any]],
    *,
    rank_constant: int = 60,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Merge lexical/vector/forager rankings with Reciprocal Rank Fusion."""
    scores: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        seen: set[str] = set()
        for rank, item in enumerate(ranking, start=1):
            doc_id = _ranking_id(item)
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            scores[doc_id] += 1.0 / (rank_constant + rank)
    merged = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return merged[:top_k] if top_k else merged


def search_memory_rows(
    query: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    lanes: Iterable[str] | None = None,
    vector_ranking: Iterable[Any] | None = None,
    top_k: int = 5,
    include_superseded: bool = False,
    rank_constant: int = 60,
) -> list[dict[str, Any]]:
    """Search canonical rows with BM25-lite + optional vector rank + RRF."""
    typed = typed_memory_rows(rows, lanes=lanes, include_superseded=include_superseded)
    if not typed:
        return []
    by_id = {trace_key(row): row for row in typed}
    bm25 = bm25_lite_rank(query, typed)
    rankings: list[Iterable[Any]] = [[doc_id for doc_id, _ in bm25]]
    vector_scores: dict[str, float] = {}
    if vector_ranking is not None:
        vector_items = list(vector_ranking)
        rankings.append(vector_items)
        for rank, item in enumerate(vector_items, start=1):
            doc_id = _ranking_id(item)
            vector_scores[doc_id] = 1.0 / rank
    fused = rrf_merge(rankings, rank_constant=rank_constant, top_k=top_k)
    bm25_scores = dict(bm25)
    results: list[dict[str, Any]] = []
    for doc_id, rrf_score in fused:
        row = by_id.get(doc_id)
        if row is None:
            continue
        results.append(
            {
                "trace_id": doc_id,
                "row": row,
                "memory_lane": row.get("memory_lane") or classify_memory_lane(row),
                "rrf_score": rrf_score,
                "bm25_score": bm25_scores.get(doc_id, 0.0),
                "vector_score": vector_scores.get(doc_id, 0.0),
            }
        )
    return results


__all__ = [
    "MEMORY_LANES",
    "active_memory_rows",
    "bm25_lite_rank",
    "classify_memory_lane",
    "load_jsonl_rows",
    "rrf_merge",
    "row_text",
    "search_memory_rows",
    "superseded_trace_id_set",
    "supersedes_trace_ids",
    "trace_key",
    "typed_memory_rows",
]
