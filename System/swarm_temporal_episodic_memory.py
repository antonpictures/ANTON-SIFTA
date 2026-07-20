#!/usr/bin/env python3
"""
System/swarm_temporal_episodic_memory.py — Time-anchored factual recall from ledgers.

Requirement (r1504): Alice must answer "do you remember the instagram link where you invented
the clothing last night?" (or "what happened two days ago at that time") with real facts
pulled from alice_conversation.jsonl + other ledgers for the correct past time window,
not from the current chat thread or model priors.

This is the dedicated retrieval organ for multi-day episodic memory questions.
It resolves natural time language ("last night", "two days ago", "yesterday around X"),
searches the persistent field within that window, extracts facts, and writes a
memory_retrieval_receipt so the answer itself is receipted and sortable.

Patterned after swarm_hard_recall.py: deterministic ledger reads, no hallucination,
first-person facts only.

Truth label: TEMPORAL_EPISODIC_MEMORY_V1
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.swarm_episodic_time_recall import parse_time_window as _parse_natural_time_window
except Exception:  # pragma: no cover
    _parse_natural_time_window = None

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_CONVO = _STATE / "alice_conversation.jsonl"
_NARRATIVE_DIARY = _STATE / "alice_narrative_diary.jsonl"
_ACTION_DIARY = _STATE / "app_action_diary.jsonl"
_BROWSER_MEMORY = _STATE / "browser_stigmergic_memory.jsonl"
_DREAM_CYCLES = _STATE / "alice_dream_cycles.jsonl"

_RETRIEVAL_LEDGER = _STATE / "memory_retrieval_receipts.jsonl"

# Simple time spec patterns (expand over time)
_LAST_NIGHT_RE = re.compile(r"\blast\s+night\b", re.IGNORECASE)
_YESTERDAY_RE = re.compile(r"\byesterday\b", re.IGNORECASE)
_TWO_DAYS_RE = re.compile(r"\btwo\s+days\s+ago\b", re.IGNORECASE)
_RECENTLY_RE = re.compile(r"\b(recently|earlier|last\s+session)\b", re.IGNORECASE)


def _now() -> float:
    return time.time()


def _read_jsonl(path: Path, limit: int = 0) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if limit > 0:
        lines = lines[-limit:]
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _extract_physical_ts(row: Dict[str, Any]) -> Optional[float]:
    """Handle the complex ts dicts used in many ledgers (physical_pt)."""
    ts = row.get("ts")
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, dict):
        # Common shapes: {"physical_pt": 1782..., ...} or {"ts": ...}
        for k in ("physical_pt", "ts", "timestamp", "created_at"):
            v = ts.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    # Fallback: try top level keys
    for k in ("physical_pt", "timestamp", "created_at", "ts"):
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def resolve_time_window(spec: str, now: Optional[float] = None) -> Tuple[float, float]:
    """
    Resolve natural language time spec to (start_ts, end_ts) unix seconds.
    Starts simple and grounded in the body's own cycles.
    """
    now = now or _now()
    spec_l = (spec or "").lower()

    # Reuse the richer natural-time parser when available.
    # This gives narrower behavior for phrases like "two days ago at that time"
    # and explicit clock anchors (e.g. "at 9:30 am").
    if _parse_natural_time_window is not None:
        try:
            parsed = _parse_natural_time_window(spec_l, now_epoch=now)
        except Exception:
            parsed = None
        if parsed:
            start_ts, end_ts = parsed[0], parsed[1]
            if isinstance(start_ts, (int, float)) and isinstance(end_ts, (int, float)):
                # Keep legacy behavior on invalid windows.
                if end_ts > start_ts:
                    return float(start_ts), float(end_ts)

    # Look for explicit dream/night cycles first when "last night" is mentioned
    if _LAST_NIGHT_RE.search(spec_l):
        cycles = _read_jsonl(_DREAM_CYCLES, limit=5)
        for c in reversed(cycles):
            # Expect entries with start/end or night boundaries
            start = _extract_physical_ts(c) or c.get("start") or c.get("night_start")
            end = c.get("end") or c.get("night_end") or c.get("wake")
            if start and end and float(end) < now:
                return float(start), float(end)
        # Fallback: last ~8-12 hours as "night"
        return now - (12 * 3600), now - (6 * 3600)

    if _TWO_DAYS_RE.search(spec_l):
        return now - (48 * 3600), now - (24 * 3600)

    if _YESTERDAY_RE.search(spec_l):
        return now - (36 * 3600), now - (12 * 3600)

    # Default recent window (last few hours) — caller should treat as low precision
    return now - (6 * 3600), now


def search_ledger_for_facts(
    keywords: List[str],
    start_ts: float,
    end_ts: float,
    ledgers: Optional[List[Path]] = None,
    max_rows: int = 50,
) -> List[Dict[str, Any]]:
    """
    Search one or more ledgers for rows whose ts falls in [start, end] and whose text
    content contains any of the keywords (case-insensitive substring match for now).
    Returns rows augmented with source and matched_ts.
    """
    if ledgers is None:
        ledgers = [_CONVO, _NARRATIVE_DIARY, _ACTION_DIARY, _BROWSER_MEMORY]

    kws = [k.lower() for k in keywords if k]
    results: List[Dict[str, Any]] = []

    for ledger in ledgers:
        rows = _read_jsonl(ledger)
        for row in rows:
            row_ts = _extract_physical_ts(row)
            if row_ts is None or not (start_ts <= row_ts <= end_ts):
                continue

            # Look for text in common places. r-memory-recall-content-first-20260705:
            # raw_text (memory_ledger owner turns) and line (first-person journal)
            # were not searched at all — the exact surfaces that held George's
            # mother's femur memory while recall returned tail noise.
            text_blob = ""
            for key in ("text", "content", "payload", "message", "description", "title", "url", "raw_text", "line", "summary"):
                v = row.get(key)
                if isinstance(v, str):
                    text_blob += " " + v
                elif isinstance(v, dict):
                    text_blob += " " + json.dumps(v)

            text_lower = text_blob.lower()
            if any(kw in text_lower for kw in kws):
                results.append({
                    "source": ledger.name,
                    "matched_ts": row_ts,
                    "row": row,
                    "snippet": text_blob[:300],
                })
                if len(results) >= max_rows:
                    break
        if len(results) >= max_rows:
            break

    # Sort by time, most recent first within window
    results.sort(key=lambda r: r.get("matched_ts", 0), reverse=True)
    return results[:max_rows]


def write_memory_retrieval_receipt(
    query: str,
    resolved_window: Tuple[float, float],
    facts: List[Dict[str, Any]],
    answer: str = "",
    *,
    receipt_ledger: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append a receipt for the memory lookup itself."""
    ledger_path = Path(receipt_ledger or _RETRIEVAL_LEDGER)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "ts": _now(),
        "truth_label": "TEMPORAL_EPISODIC_MEMORY_RETRIEVAL_V1",
        "query": query,
        "resolved_start": resolved_window[0],
        "resolved_end": resolved_window[1],
        "facts_found": len(facts),
        "fact_sources": [f["source"] for f in facts[:5]],
        "answer_preview": answer[:200] if answer else "",
        "row_hash": "",  # filled below
    }
    receipt_str = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
    import hashlib
    receipt["row_hash"] = hashlib.sha256(receipt_str.encode("utf-8")).hexdigest()

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    # r-stgm-pulse-20260705 (Architect): a recall that actually found rows is
    # useful work — pulse the wallet through the synthase lane. One mint per
    # retrieval receipt hash; failures never break recall.
    if facts and ledger_path.parent.resolve() == _STATE.resolve():
        try:
            from System.swarm_atp_synthase import mint_receipted_work_pulse

            pulse = mint_receipted_work_pulse(
                "memory_retrieval_hit", str(receipt.get("row_hash") or "")
            )
            receipt["stgm_pulse"] = {
                "minted_stgm": pulse.get("minted_stgm", 0.0),
                "refused": pulse.get("refused", ""),
            }
        except Exception:
            pass
    return receipt


def _fact_trace_id(fact: Dict[str, Any]) -> str:
    """Stable overlay id for a retrieved fact; never mutates the source row."""
    row = fact.get("row") if isinstance(fact.get("row"), dict) else {}
    for key in ("trace_id", "source_hash", "schedule_id", "receipt_id", "row_hash", "id"):
        value = row.get(key)
        if value:
            return str(value)
    material = "|".join(
        [
            str(fact.get("source", "")),
            str(fact.get("matched_ts", "")),
            str(fact.get("snippet", ""))[:500],
        ]
    )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _reinforce_recalled_facts(
    facts: List[Dict[str, Any]],
    *,
    source_receipt_id: str,
    state_dir: Path,
) -> Dict[str, Any]:
    if not facts:
        return {"reinforced": 0, "trace_ids": []}
    trace_ids: List[str] = []
    try:
        from System.memory_fitness_overlay import reinforce
    except Exception:
        return {"reinforced": 0, "trace_ids": [], "error": "memory_fitness_overlay_unavailable"}
    for fact in facts:
        trace_id = _fact_trace_id(fact)
        if not trace_id:
            continue
        try:
            reinforce(trace_id, source_receipt_id, weight=1.0, state_dir=state_dir)
            trace_ids.append(trace_id)
        except Exception:
            continue
    return {"reinforced": len(trace_ids), "trace_ids": trace_ids[:12]}


# Recall-verb and filler words carry no memory content — searching them made
# every "remember X" query match everything recent and nothing specific.
_RECALL_STOPWORDS = {
    "remember", "recall", "memory", "memories", "look", "looking", "lookup",
    "still", "your", "yours", "what", "when", "where", "which", "did", "does",
    "have", "from", "just", "about", "tell", "know", "please", "this", "that",
    "with", "into", "then", "them", "they", "will", "would", "could", "should",
}

# Explicit time anchors that scope recall to a window on purpose.
_EXPLICIT_TIME_PHRASE_RE = __import__("re").compile(
    r"\b(last\s+night|yesterday|this\s+morning|this\s+afternoon|this\s+evening|tonight|"
    r"today|last\s+week|last\s+month|an?\s+hour\s+ago|\d+\s+(?:minutes?|hours?|days?|weeks?)\s+ago|"
    r"at\s+that\s+time|on\s+(?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"on\s+\d{1,2}[/.-]\d{1,2}|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
    __import__("re").IGNORECASE,
)


def recall_facts_for_query(
    query: str,
    time_spec: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    High-level entry point.
    - query: the full owner question ("do you remember the instagram link...")
    - time_spec: optional explicit time phrase; if None, extract from query.
    - keywords: extra search terms. If None, extract heuristically from query.
    Returns a dict with resolved window, facts, and a written receipt.
    """
    if time_spec is None:
        # crude extraction — improve with better parser
        time_spec = query

    start, end = resolve_time_window(time_spec)

    if keywords is None:
        # naive keyword pull from the query — content-bearing terms only
        # (r-memory-recall-content-first-20260705: 'still'/'memory'/'remember'
        # matched 50 junk conversation rows and buried the real answer).
        kws = re.findall(r"[a-zA-Z0-9]+", query.lower())
        keywords = [k for k in kws if len(k) > 3 and k not in _RECALL_STOPWORDS][:8]

    state_dir_path = Path(state_dir) if state_dir is not None else _CONVO.parent
    convo_path = state_dir_path / "alice_conversation.jsonl" if state_dir is not None else _CONVO
    retrieval_ledger = state_dir_path / "memory_retrieval_receipts.jsonl" if state_dir is not None else _RETRIEVAL_LEDGER
    time_ledgers = [
        convo_path,
        state_dir_path / "alice_narrative_diary.jsonl" if state_dir is not None else _NARRATIVE_DIARY,
        state_dir_path / "app_action_diary.jsonl" if state_dir is not None else _ACTION_DIARY,
        state_dir_path / "browser_stigmergic_memory.jsonl" if state_dir is not None else _BROWSER_MEMORY,
    ]
    facts = search_ledger_for_facts(keywords, start, end, ledgers=time_ledgers)
    recall_mode = "time_window"

    # r-memory-recall-content-first-20260705: OBSERVED failure (2026-07-05 04:16)
    # — George asked 'remember she broke her femur? she is in the hospital still.
    # look up in your memory' and got business-podcast tail noise. The query has
    # no time phrase, so the resolved window missed the Jul 3 rows, and the
    # windowed search returned nothing relevant. When the window misses, memory
    # must fall back to CONTENT: search all time across the surfaces that hold
    # owner memory (raw memory_ledger turns, first-person journal, schedule,
    # diaries), rank by distinct-term hits then recency. Stigmergic memory is
    # wired only if the words in the owner's mouth can reach the rows on disk.
    # When the owner names an explicit time ("two days ago at that time"), the
    # window IS the question — honor it. The all-time content pass fires only
    # when there is no time anchor (the femur case) or the window found nothing.
    explicit_time = bool(
        _EXPLICIT_TIME_PHRASE_RE.search((time_spec or "") if time_spec != query else (query or ""))
    )
    content_terms = [k for k in (keywords or []) if k not in _RECALL_STOPWORDS][:8]
    if content_terms and not (explicit_time and facts):
        state_dir = state_dir_path
        content_surfaces = [
            state_dir / "memory_ledger.jsonl",
            state_dir / "alice_first_person_journal.jsonl",
            state_dir / "stigmergic_schedule.jsonl",
            _NARRATIVE_DIARY,
            _ACTION_DIARY,
        ]
        candidates = search_ledger_for_facts(
            content_terms, 0.0, _now(), ledgers=content_surfaces, max_rows=48,
        )
        convo_candidates: List[Dict[str, Any]] = []
        try:
            from System.swarm_convo_term_index import query_index

            convo_candidates = query_index(
                content_terms,
                conversation_path=convo_path,
                state_dir=state_dir,
                max_rows=24,
            )
        except Exception:
            convo_candidates = []
        pool = list(facts) + list(candidates) + list(convo_candidates)
        query_echo = " ".join((query or "").lower().split())[:80]

        def _term_hits(f: Dict[str, Any]) -> list[str]:
            # Word-boundary match: 'broke' must not score on 'broker'/'brokerage'
            # rows — substring hits buried the femur memory under podcast noise.
            blob = " ".join(str(f.get("snippet", "")).lower().split())
            return [
                t for t in content_terms
                if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", blob)
            ]

        hit_rows = []
        term_doc_freq = {term: 0 for term in content_terms}
        for f in pool:
            blob = " ".join(str(f.get("snippet", "")).lower().split())
            if query_echo and query_echo in blob:
                continue  # the just-appended question turn is not a memory of the event
            hits = _term_hits(f)
            if not hits:
                continue
            hit_rows.append((hits, float(f.get("matched_ts") or 0.0), f))
            for term in set(hits):
                term_doc_freq[term] = term_doc_freq.get(term, 0) + 1
        try:
            from System.memory_fitness_overlay import strength_for
            strength_map = strength_for((_fact_trace_id(f) for _hits, _ts, f in hit_rows), state_dir=state_dir)
        except Exception:
            strength_map = {}
        scored = []
        row_count = max(1, len(hit_rows))
        for hits, ts_value, f in hit_rows:
            rarity_values = [
                math.log(1.0 + (row_count / max(1, term_doc_freq.get(term, 1))))
                for term in set(hits)
            ]
            # The rarest content word is the anchor. Without this, two generic
            # hits like "broke" + "hospital" can beat the older row that only
            # carries the specific needle term "femur".
            rarity_score = (max(rarity_values) * 2.0) + (sum(rarity_values) * 0.25)
            strength = float(strength_map.get(_fact_trace_id(f), 1.0))
            scored.append((len(set(hits)), rarity_score, min(5.0, strength), ts_value, f))
        if scored:
            scored.sort(key=lambda s: (s[1], s[0], s[2], s[3]), reverse=True)
            facts = [f for _h, _score, _strength, _ts, f in scored[:12]]
            recall_mode = "content_ranked_all_time"

    result = {
        "ok": True,
        "query": query,
        "time_spec": time_spec,
        "resolved_window": (start, end),
        "facts": facts,
        "fact_count": len(facts),
        "recall_mode": recall_mode,
    }

    # Write the retrieval receipt (even if zero facts — honest record)
    receipt = write_memory_retrieval_receipt(
        query,
        (start, end),
        facts,
        receipt_ledger=retrieval_ledger,
    )
    receipt_hash = str(receipt.get("row_hash") or "")
    result["reinforcement"] = _reinforce_recalled_facts(
        facts,
        source_receipt_id=receipt_hash,
        state_dir=retrieval_ledger.parent,
    )
    result["receipt"] = receipt

    return result


# --- Convenience for direct testing ---
if __name__ == "__main__":
    q = "do you remember the instagram link where you invented the clothing last night?"
    out = recall_facts_for_query(q)
    print(json.dumps({
        "query": out["query"],
        "window": out["resolved_window"],
        "fact_count": out["fact_count"],
        "first_fact_sources": out["receipt"]["fact_sources"],
        "receipt_ts": out["receipt"]["ts"],
    }, indent=2))
