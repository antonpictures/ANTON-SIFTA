#!/usr/bin/env python3
"""Rank Alice's stigmergic ledger memory for a current owner/task query.

This is not "unlimited context". It is bounded, receipt-aware retrieval over
the body ledgers: owner intent terms, task terms, recency, receipt strength, and
organ/source evidence all contribute to a score.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping


DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / ".sifta_state"
DEFAULT_LEDGERS: tuple[str, ...] = (
    "ide_stigmergic_trace.jsonl",
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "episodic_diary.jsonl",
    "cortex_switch_somatic_receipts.jsonl",
    "cortex_need_switches.jsonl",
    "pdf_forge_receipts.jsonl",
)


@dataclass(frozen=True)
class StigmergicMemoryHit:
    ledger: str
    score: float
    reasons: tuple[str, ...]
    ts: float
    age_s: float
    receipt_id: str
    round_id: str
    truth_label: str
    source: str
    snippet: str
    files_touched: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["score"] = round(float(self.score), 4)
        row["age_s"] = round(float(self.age_s), 3)
        return row


def _query_terms(query: str) -> tuple[str, ...]:
    words = re.findall(r"[a-zA-Z0-9_./:-]+", str(query or "").lower())
    stop = {"the", "and", "for", "with", "that", "this", "into", "from", "have", "has"}
    return tuple(dict.fromkeys(w for w in words if len(w) > 2 and w not in stop))


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except Exception:
        return []
    return list(rows)


def _text_blob(row: Mapping[str, Any]) -> str:
    try:
        return json.dumps(row, sort_keys=True, ensure_ascii=False).lower()
    except Exception:
        return str(row).lower()


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "action_oracle_epoch", "oracle_epoch", "epoch"):
        try:
            value = float(row.get(key) or 0.0)
        except Exception:
            value = 0.0
        if value > 0:
            return value
    return 0.0


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if str(v).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _receipt_strength(row: Mapping[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    truth = str(row.get("truth_label") or row.get("fanout_truth_label") or "").upper()
    if truth in {"OPERATIONAL", "OBSERVED", "SIFTA_IDE_SURGERY_FANOUT_V1"}:
        score += 1.5
        reasons.append("truth_label")
    if row.get("receipt_id") or row.get("trace_id"):
        score += 1.0
        reasons.append("receipt_id")
    if row.get("tests_green"):
        score += 0.9
        reasons.append("tests_green")
    if row.get("files_touched"):
        score += 0.8
        reasons.append("files_touched")
    if row.get("action_oracle_signature") or row.get("oracle_signature"):
        score += 0.7
        reasons.append("time_oracle")
    if row.get("ledger_name") or row.get("source") or row.get("source_ide"):
        score += 0.4
        reasons.append("organ_source")
    return score, reasons


def rank_stigmergic_memory(
    query: str,
    *,
    state_dir: str | Path | None = None,
    ledgers: Iterable[str] = DEFAULT_LEDGERS,
    max_rows_per_ledger: int = 250,
    limit: int = 8,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Return the top receipt-backed memory rows for a query."""
    state = Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR
    terms = _query_terms(query)
    if not terms:
        return []
    now_f = float(time.time() if now is None else now)
    hits: list[StigmergicMemoryHit] = []
    for ledger in ledgers:
        path = state / ledger
        for row in _tail_jsonl(path, max_rows_per_ledger):
            blob = _text_blob(row)
            matched = [term for term in terms if term in blob]
            if not matched:
                continue
            ts = _row_ts(row)
            age_s = max(0.0, now_f - ts) if ts else 9_999_999.0
            recency = 2.0 / (1.0 + (age_s / (36.0 * 3600.0)))
            receipt_score, receipt_reasons = _receipt_strength(row)
            score = float(len(matched) * 1.25 + recency + receipt_score)
            reasons = [f"query_match:{','.join(matched[:6])}", *receipt_reasons]
            receipt_id = str(row.get("receipt_id") or row.get("trace_id") or row.get("event_id") or "")
            round_id = str(row.get("round_id") or row.get("live_round") or "")
            truth_label = str(row.get("truth_label") or row.get("fanout_truth_label") or "")
            source = str(row.get("source") or row.get("source_ide") or row.get("doctor") or row.get("kind") or "")
            snippet = blob[:360].replace("\n", " ")
            files = _as_tuple(row.get("files_touched"))
            hits.append(
                StigmergicMemoryHit(
                    ledger=ledger,
                    score=score,
                    reasons=tuple(reasons),
                    ts=ts,
                    age_s=age_s,
                    receipt_id=receipt_id,
                    round_id=round_id,
                    truth_label=truth_label,
                    source=source,
                    snippet=snippet,
                    files_touched=files,
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    return [hit.to_dict() for hit in hits[: max(1, int(limit))]]


def render_stigmergic_memory_retrieval_block(
    query: str,
    *,
    state_dir: str | Path | None = None,
    limit: int = 5,
) -> str:
    hits = rank_stigmergic_memory(query, state_dir=state_dir, limit=limit)
    lines = [
        "STIGMERGIC MEMORY RETRIEVAL (bounded; receipt-aware; not unlimited context):",
        f"- query: {query}",
    ]
    if not hits:
        lines.append("- no matching ledger rows found in this bounded pass")
        return "\n".join(lines)
    for hit in hits:
        rid = hit.get("round_id") or hit.get("receipt_id") or "(no id)"
        reasons = ", ".join(hit.get("reasons") or [])
        lines.append(
            f"- {hit['ledger']} score={hit['score']} id={rid} truth={hit.get('truth_label') or 'unknown'} reasons={reasons}"
        )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_LEDGERS",
    "StigmergicMemoryHit",
    "rank_stigmergic_memory",
    "render_stigmergic_memory_retrieval_block",
]
