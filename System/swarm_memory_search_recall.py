#!/usr/bin/env python3
"""System/swarm_memory_search_recall.py — content search over Alice's memory.

George 2026-07-25 asked Alice to retrieve his latest plane trip. The cortex
invented "May 14, 2026, 11:35 AM, Milan Malpensa" even though the canonical
journal contains his July 3 LAX-to-Bucharest itinerary and his July 20 arrival
statement. The first repair incorrectly reported that those records did not
exist because it trusted noisy keyword ranking instead of testing the live
owner evidence. This organ keeps provenance and answer support explicit.

`swarm_hard_recall` already covers verbatim last-turn recall ("read back my
previous prompt"). It does not cover content search, and `memory_search.py`
had real BM25 ranking that nothing in the chat path ever called. This organ is
the missing wire.

Doctrine, same as hard recall: retrieval is deterministic and does not call the
cortex. The cortex may compose Alice's voice around the evidence, but it never
supplies the evidence. When the search finds nothing, "nothing" is a receipted
fact, and an answer that asserts a concrete record anyway is caught and
replaced rather than spoken.

Honest label: OBSERVED_MEMORY_SEARCH_V1.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER_NAME = "memory_search_recall.jsonl"

TRUTH_LABEL = "OBSERVED_MEMORY_SEARCH_V1"

# Ledgers that hold owner-relevant lived content. Deliberately excludes the
# machine-chatter ledgers (organ heartbeats, field telemetry) so a search for
# "flight" cannot be answered by a receipt about a code path.
SEARCH_LEDGERS: tuple[str, ...] = (
    "alice_conversation.jsonl",
    "alice_first_person_journal.jsonl",
    "alice_journal_consolidated.jsonl",
    "episodic_diary.jsonl",
    "ambient_room_transcripts.jsonl",
    "stigmergic_schedule.jsonl",
    "alice_memory_cards.jsonl",
    "owner_life_facts.jsonl",
)

# Rows from these ledgers are sound the room made, not things the owner did.
# A television saying "flight from Puerto Rico to Chicago" is not George's
# travel history, and it must never be cited as his own record.
_AMBIENT_LEDGERS = frozenset({"ambient_room_transcripts.jsonl"})
_OWNER_EVIDENCE_CLASSES = frozenset({"OWNER_DIRECT", "OWNER_WITNESS", "OWNER_FACT", "OWNER_SCHEDULE"})

_TRAVEL_CORE = frozenset(
    {
        "airport", "arrive", "arrival", "boarding", "bucharest", "depart", "departure",
        "flight", "flew", "fly", "flown", "lax", "otp", "plane", "romania", "trip",
        "travel", "traveled", "travelled",
    }
)
_TRAVEL_EXPANSION = "flight fly flew flown plane airport boarding depart departure arrive arrival trip travel traveled travelled"

# "search your memory for X" / "do you have X in your memory" / "when did I X".
_SEARCH_RE = re.compile(
    r"(?:"
    r"(?:look|search|check|dig|find|scan)\s+(?:\w+\s+){0,3}?(?:in\s+)?(?:your|my|the)\s+"
    r"(?:memory|memories|journal|ledger|ledgers|records?|notes?|history)"
    r"|(?:your|my|the)\s+(?:memory|memories|journal|ledger|records?)\s+(?:should|must|already|has|have|holds?|contains?)"
    r"|(?:it|this|that)\s+is\s+already\s+in\s+(?:your|my|the)\s+(?:memory|memories|journal|ledger|records?)"
    r"|do\s+you\s+(?:have|remember|recall|know)\s+(?:any|anything|what|when|where|the)"
    # Punctuation after "I" is normal owner typing ("when did I, ioan george
    # anton, travel"), and it must not defeat the match.
    r"|when\s+did\s+i\b[\s,;:'\"-]*(?:\w+[\s,;:'\"-]*){0,6}?\w+"
    r"|what\s+(?:date|time)\s+did\s+i\b"
    r"|search\s+(?:for\s+)?(?:any\s+)?\w+"
    r")",
    re.IGNORECASE,
)

# Command scaffolding stripped before ranking, so the query carries content
# words ("flight tickets") rather than instruction words ("go ahead search").
_STOP_PHRASES = (
    r"come\s+on",
    r"go\s+ahead",
    r"please",
    r"look\s+(?:in|into|through|at)",
    r"search(?:ing)?(?:\s+for)?",
    r"check(?:ing)?",
    r"find",
    r"dig\s+(?:in|into|through)",
    r"scan",
    r"tell\s+me",
    r"do\s+you\s+(?:have|remember|recall|know)",
    r"this\s+information\s+is\s+already\s+in",
    r"(?:your|my|the)\s+(?:memory|memories|journal|ledger|ledgers|records?|notes?|history)",
    r"\balice\b",
    r"\bany\b",
    r"\banything\b",
    r"\bin\b",
)
_STOP_RE = re.compile("|".join(_STOP_PHRASES), re.IGNORECASE)

# Concrete assertions a fabricated "found it" answer tends to carry. Used only
# to catch an invented record when the search itself found nothing.
_SPECIFIC_CLAIM_RES = (
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", re.IGNORECASE),
    re.compile(r"\b(?:flight|booking|confirmation|ticket)\s+(?:number|code|ref[a-z]*)\b", re.IGNORECASE),
)

_FOUND_CLAIM_RE = re.compile(
    r"(?:retrieval\s+complete|i\s+(?:found|have\s+found|located|retrieved)|"
    r"here\s+(?:is|are)\s+(?:the|your)|my\s+search\s+has\s+returned|consider\s+it\s+done)",
    re.IGNORECASE,
)


def now() -> float:
    return time.time()


def is_memory_search_request(text: str) -> bool:
    """True when the owner is asking Alice to search her memory for content."""
    return bool(_SEARCH_RE.search(str(text or "")))


_FILLER_WORDS = frozenset(
    {
        "already", "and", "anton", "date", "did", "for", "george", "have", "information",
        "ioan", "last", "location", "the", "this", "time", "what", "when", "with", "you",
        "your", "that", "from", "was", "are", "has",
    }
)


def extract_search_terms(text: str) -> str:
    """Strip command scaffolding so ranking sees the subject, not the verb."""
    cleaned = _STOP_RE.sub(" ", str(text or ""))
    cleaned = re.sub(r"[^\w\s'-]", " ", cleaned)
    words = [
        word
        for word in cleaned.split()
        if len(word) > 1 and word.lower() not in _FILLER_WORDS
    ]
    terms = " ".join(words).strip()
    if _tokens(terms) & _TRAVEL_CORE:
        terms = f"{terms} {_TRAVEL_EXPANSION}".strip()
    return terms


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9']+", str(text or "").lower()) if len(word) > 2}


def is_query_echo(row_text_value: str, query: str, *, threshold: float = 0.6) -> bool:
    """True when a 'hit' is just the owner's own question echoed back.

    The question lands in the conversation ledger the instant it is asked, so a
    naive search ranks it first and Alice ends up quoting George to George as
    proof. Her own generated answer to that question echoes the same way. A
    memory search must never treat the asking as the remembering.

    The overlap has to run both ways. A row that merely contains every query
    word is not the question — a long television transcript mentioning "flight"
    and "plane" answers a two-word query completely by that measure, and
    dropping it would hide real rows.
    """
    query_tokens = _tokens(query)
    row_tokens = _tokens(row_text_value)
    if not query_tokens or not row_tokens:
        return False

    # Alice journals the asking too ("I heard from the room: <question>",
    # "George said: '<question>'"). Those rows quote the question verbatim
    # inside other prose, which dilutes token overlap but is still the
    # question, not a memory of the thing asked about.
    normalized_query = " ".join(str(query or "").lower().split())
    normalized_row = " ".join(str(row_text_value or "").lower().split())
    if len(normalized_query) >= 30:
        span = normalized_query[: int(len(normalized_query) * 0.6)]
        if span and span in normalized_row:
            return True

    union = query_tokens | row_tokens
    if not union:
        return False
    return (len(query_tokens & row_tokens) / len(union)) >= float(threshold)


def _row_timestamp(row: Mapping[str, Any]) -> float:
    raw = row.get("ts") or row.get("timestamp") or 0.0
    if isinstance(raw, Mapping):
        raw = raw.get("physical_pt") or raw.get("ts") or 0.0
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _when(ts: float) -> str:
    if ts <= 0:
        return "unknown time"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def _row_provenance(row: Mapping[str, Any], source_ledger: str) -> str:
    """Classify who supplied a row before it can become owner-life evidence."""
    if source_ledger == "alice_conversation.jsonl":
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        return "OWNER_DIRECT" if str(payload.get("role") or "").lower() == "user" else "ALICE_GENERATED"
    if source_ledger == "alice_first_person_journal.jsonl":
        source = str(row.get("source") or "").lower()
        line = str(row.get("line") or row.get("text") or "")
        if line.startswith("George said:") or " George said:" in line:
            return "OWNER_WITNESS"
        if "translated Ioan George Anton" in line:
            return "ROOM_AUDIO_UNVERIFIED"
        return "ALICE_GENERATED"
    if source_ledger == "owner_life_facts.jsonl":
        return "OWNER_FACT"
    if source_ledger == "stigmergic_schedule.jsonl":
        return "OWNER_SCHEDULE"
    if source_ledger in _AMBIENT_LEDGERS:
        return "ROOM_AUDIO"
    return "GENERATED_OR_DERIVED"


def _memory_text(row: Mapping[str, Any], source_ledger: str, fallback: str) -> str:
    """Extract content without ledger hashes or schema metadata."""
    if source_ledger == "alice_conversation.jsonl":
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        return str(payload.get("text") or fallback).strip()
    for key in ("line", "text", "summary", "entry"):
        if row.get(key):
            return str(row.get(key)).strip()
    return fallback.strip()


def _topic_tokens(terms: str) -> set[str]:
    tokens = _tokens(terms)
    travel = tokens & _TRAVEL_CORE
    return travel if travel else tokens


def search_owner_memory(
    query: str,
    *,
    state_dir: Path | str = _STATE,
    ledgers: Sequence[str] = SEARCH_LEDGERS,
    top_k: int = 6,
    now_ts: Optional[float] = None,
) -> dict[str, Any]:
    """Deterministic BM25 search across the owner-content ledgers.

    Returns what was actually searched alongside what was found, so "nothing"
    is a measured result with a denominator rather than a shrug.
    """
    from System.memory_search import load_jsonl_rows, row_text, search_memory_rows

    state = Path(state_dir)
    terms = extract_search_terms(query) or str(query or "").strip()
    present = [state / name for name in ledgers if (state / name).exists()]
    rows = load_jsonl_rows(present) if present else []
    current = float(now() if now_ts is None else now_ts)

    ranked_hits: list[dict[str, Any]] = []
    echoes_dropped = 0
    candidates_rejected = 0
    if terms and rows:
        topic_tokens = _topic_tokens(terms)
        for result in search_memory_rows(terms, rows, top_k=max(80, int(top_k) * 50)):
            score = float(result.get("bm25_score") or 0.0)
            row = result.get("row") or {}
            source = Path(str(row.get("_ledger_path") or "")).name or "unknown_ledger"
            # row_text walks every field, so the injected ledger path would
            # otherwise become searchable content and dilute the echo check.
            clean_row = {
                key: value
                for key, value in row.items()
                if key not in ("_ledger_path", "_ledger_line")
            }
            fallback_text = row_text(clean_row).replace("\n", " ").strip()
            full_text = _memory_text(row, source, fallback_text).replace("\n", " ").strip()
            text = full_text[:700]
            # BM25 scores are corpus-relative: on a young node with a handful
            # of rows every score sits below 1.0, so a fixed floor would report
            # "found nothing" over memories that plainly exist. Relevance is
            # decided by whether the row actually contains a subject word;
            # BM25 only decides the order.
            overlap = topic_tokens & _tokens(full_text)
            if not overlap:
                continue
            ts = _row_timestamp(row)
            # The asking is not the remembering. A row that is substantially
            # the question coming back is an echo whenever it was written —
            # the same question asked last week is still not its own answer.
            if is_query_echo(full_text, query):
                echoes_dropped += 1
                continue
            provenance = _row_provenance(row, source)
            if provenance in {"OWNER_DIRECT", "OWNER_WITNESS"} and is_memory_search_request(full_text):
                echoes_dropped += 1
                continue
            if provenance not in _OWNER_EVIDENCE_CLASSES:
                candidates_rejected += 1
                continue
            structured_travel_bonus = 0.0
            if topic_tokens & _TRAVEL_CORE and re.search(
                r"(?:flight\s+details|\b[A-Z]{3}\b\s*(?:->|[-–])\s*\b[A-Z]{3}\b|"
                r"\b[A-Z]{3}\b.{0,80}\b[A-Z]{3}\b)",
                full_text,
            ):
                structured_travel_bonus = 20.0
            ranked_hits.append(
                {
                    "trace_id": str(result.get("trace_id") or ""),
                    "ts": ts,
                    "when": _when(ts),
                    "bm25_score": round(score, 4),
                    "memory_lane": str(result.get("memory_lane") or ""),
                    "source_ledger": source,
                    "owner_authored": True,
                    "provenance": provenance,
                    "evidence_score": round(score + (3.0 * len(overlap)) + structured_travel_bonus, 4),
                    "text": text,
                }
            )
    ranked_hits.sort(key=lambda hit: (float(hit.get("evidence_score") or 0.0), float(hit.get("ts") or 0.0)), reverse=True)
    deduped_hits: list[dict[str, Any]] = []
    for hit in ranked_hits:
        normalized = " ".join(str(hit.get("text") or "").casefold().split())
        if any(
            min(len(normalized), len(prior)) >= 30 and (normalized in prior or prior in normalized)
            for prior in (" ".join(str(item.get("text") or "").casefold().split()) for item in deduped_hits)
        ):
            continue
        deduped_hits.append(hit)
    hits = deduped_hits[: max(1, int(top_k))]

    return {
        "schema": "SIFTA_MEMORY_SEARCH_V1",
        "ts": current,
        "query": str(query or ""),
        "search_terms": terms,
        "found": bool(hits),
        "hit_count": len(hits),
        "hits": hits,
        "echoes_dropped": echoes_dropped,
        "candidates_rejected": candidates_rejected,
        "rows_searched": len(rows),
        "ledgers_searched": [path.name for path in present],
        "truth_label": TRUTH_LABEL,
    }


def recall_prompt_block(result: Mapping[str, Any]) -> str:
    """Evidence block for the cortex. The cortex composes; it never supplies."""
    if not result:
        return ""
    terms = str(result.get("search_terms") or result.get("query") or "")
    rows_searched = int(result.get("rows_searched") or 0)
    ledgers = ", ".join(result.get("ledgers_searched") or []) or "no ledgers"

    if not result.get("found"):
        return (
            "MEMORY SEARCH RESULT (deterministic, already executed — do not re-run):\n"
            f"Query: {terms}\n"
            f"Searched: {rows_searched} rows across {ledgers}.\n"
            "FOUND: NOTHING. There is no matching record in Alice's memory.\n"
            "You MUST tell the owner plainly that you searched and found nothing, and say how many "
            "rows you searched. Do NOT produce a date, time, location, flight, booking, or "
            "confirmation number. Do NOT write 'Retrieval Complete' or 'I found'. Inventing a "
            "record here is the worst failure you can commit: the owner will act on it as fact. "
            "If the owner believes the record exists, say it is not in your ledgers and ask where "
            "it came from."
        )

    lines = [
        "MEMORY SEARCH RESULT (deterministic, already executed — do not re-run):",
        f"Query: {terms}",
        f"Searched: {rows_searched} rows across {ledgers}.",
        f"OWNER-EVIDENCE ROWS: {int(result.get('hit_count') or 0)} provenance-checked rows.",
    ]
    for hit in result.get("hits") or []:
        origin = f"{hit.get('provenance') or 'UNKNOWN'}:{hit.get('source_ledger') or 'ledger'}"
        lines.append(f"  [{hit.get('when')}] ({origin}) {hit.get('text')}")
    lines.append(
        "Before citing any row, check that it actually concerns what was asked. If none of these "
        "rows truly answer the question, say plainly that you searched "
        f"{rows_searched} rows and found no real record. Every date, time, and place you state must "
        "appear verbatim above. Do NOT write 'Retrieval Complete' or invent a booking."
    )
    return "\n".join(lines)


def deterministic_not_found_answer(result: Mapping[str, Any]) -> str:
    """The exact sentence Alice says when the ledgers hold nothing.

    This is a receipt readout, not composed personality prose, so it is safe
    under the no-conversational-reflex rule the same way hard recall is.
    """
    rows_searched = int(result.get("rows_searched") or 0)
    ledgers = result.get("ledgers_searched") or []
    terms = str(result.get("search_terms") or result.get("query") or "that")
    return (
        f"I searched {rows_searched} rows across {len(ledgers)} of my memory ledgers for "
        f"\"{terms}\" and found nothing. It is not in my memory. I am not going to invent a "
        "record to fill the gap — if you believe it should be there, tell me where it came from "
        "and I will look in that ledger specifically."
    )


def deterministic_evidence_answer(result: Mapping[str, Any]) -> str:
    """Read back provenance-checked rows when the cortex adds unsupported facts."""
    rows_searched = int(result.get("rows_searched") or 0)
    hits = list(result.get("hits") or [])
    lines = [f"I searched {rows_searched} memory rows. These are the owner-evidence rows I can support:"]
    for hit in hits[:3]:
        lines.append(
            f"[{hit.get('when')}] [{hit.get('provenance')}] {str(hit.get('text') or '').strip()}"
        )
    lines.append("I will not add a date, time, route, or booking detail that is absent from those rows.")
    return "\n".join(lines)


def fabrication_check(answer: str, result: Mapping[str, Any]) -> dict[str, Any]:
    """Catch concrete claims not supported by the retrieved owner evidence.

    Prompt instructions are guidance a small cortex can ignore. This is the
    receipt-side check: if retrieval found no rows and the answer still asserts
    a concrete date, time, or booking reference, the answer is fabricated.
    """
    text = str(answer or "")
    evidence = " ".join(str(hit.get("text") or "") for hit in (result.get("hits") or [])).casefold()

    signals: list[str] = []
    for pattern in _SPECIFIC_CLAIM_RES:
        match = pattern.search(text)
        if match:
            claim = match.group(0).strip()
            if not result.get("found") or claim.casefold() not in evidence:
                signals.append(claim)
    claims_found = bool(_FOUND_CLAIM_RE.search(text))
    if claims_found:
        signals.append("claims_retrieval_succeeded")

    fabricated = bool(signals) and (claims_found or len(signals) >= 2)
    return {
        "fabricated": fabricated,
        "reason": (
            "answer asserts concrete details absent from retrieved owner evidence"
            if fabricated
            else "no concrete fabricated record detected"
        ),
        "signals": signals,
    }


def guard_memory_answer(
    answer: str,
    result: Mapping[str, Any],
    *,
    state_dir: Path | str = _STATE,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Return the answer to actually speak, replacing a fabricated one."""
    check = fabrication_check(answer, result)
    replaced = bool(check.get("fabricated"))
    if replaced:
        final = deterministic_evidence_answer(result) if result.get("found") else deterministic_not_found_answer(result)
    else:
        final = str(answer or "")
    row = {
        "ts": now(),
        "event": "MEMORY_SEARCH_ANSWER_GUARD",
        "query": str(result.get("query") or ""),
        "search_terms": str(result.get("search_terms") or ""),
        "found": bool(result.get("found")),
        "hit_count": int(result.get("hit_count") or 0),
        "rows_searched": int(result.get("rows_searched") or 0),
        "fabrication_signals": check.get("signals") or [],
        "replaced": replaced,
        "original_answer_head": str(answer or "")[:400],
        "final_answer_head": final[:400],
        "truth_label": "MEMORY_SEARCH_ANSWER_GUARD_V1" if replaced else TRUTH_LABEL,
    }
    if write_receipt:
        write_search_receipt(row, state_dir=state_dir)
    return {"answer": final, "replaced": replaced, "check": check, "receipt": row}


def write_search_receipt(
    row: Mapping[str, Any],
    *,
    state_dir: Path | str = _STATE,
) -> dict[str, Any]:
    """Append one search/guard row. Never raises into the chat path."""
    state = Path(state_dir)
    payload = dict(row)
    try:
        state.mkdir(parents=True, exist_ok=True)
        with (state / _LEDGER_NAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return payload


# Keep several simultaneous surface turns from erasing each other's guard input.
_SEARCH_CACHE: dict[str, dict[str, Any]] = {}


def cached_search_for(text: str) -> dict[str, Any]:
    """The search result already computed for this turn, if it is the same turn."""
    return dict(_SEARCH_CACHE.get(str(text or "")) or {})


def memory_search_block_for_turn(
    text: str,
    *,
    state_dir: Path | str = _STATE,
    write_receipt: bool = True,
) -> tuple[str, dict[str, Any]]:
    """One call for the prompt builder: block plus the raw search result.

    Returns an empty block when the turn is not a memory search, so the prompt
    stays the same size for ordinary conversation.
    """
    if not is_memory_search_request(text):
        return "", {}
    result = search_owner_memory(text, state_dir=state_dir)
    _SEARCH_CACHE[str(text or "")] = result
    while len(_SEARCH_CACHE) > 8:
        _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
    if write_receipt:
        write_search_receipt(
            {
                "ts": result.get("ts"),
                "event": "MEMORY_SEARCH_EXECUTED",
                "query": result.get("query"),
                "search_terms": result.get("search_terms"),
                "found": result.get("found"),
                "hit_count": result.get("hit_count"),
                "rows_searched": result.get("rows_searched"),
                "ledgers_searched": result.get("ledgers_searched"),
                "top_trace_ids": [hit.get("trace_id") for hit in (result.get("hits") or [])],
                "truth_label": TRUTH_LABEL,
            },
            state_dir=state_dir,
        )
    return recall_prompt_block(result), result


__all__ = [
    "SEARCH_LEDGERS",
    "TRUTH_LABEL",
    "cached_search_for",
    "deterministic_evidence_answer",
    "deterministic_not_found_answer",
    "is_query_echo",
    "extract_search_terms",
    "fabrication_check",
    "guard_memory_answer",
    "is_memory_search_request",
    "memory_search_block_for_turn",
    "now",
    "recall_prompt_block",
    "search_owner_memory",
    "write_search_receipt",
]
