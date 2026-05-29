#!/usr/bin/env python3
"""
System/swarm_hippocampus.py — The Continual Learning Engine
══════════════════════════════════════════════════════════════════════════════
Resolves Catastrophic Forgetting for Vanguard AG31.

This module acts as the organism's Hippocampus. When the organism is asleep
(low BPM, idle), the hippocampus wakes up and reads the raw, noisy JSONL
ledgers (`alice_conversation.jsonl` and `repair_log.jsonl`). It calls NUGGET
to extract durable "Engrams" (core behavioral rules, verified skills, or
identity assertions) and consolidates them into a sparse vector / dense rule ledger:
`.sifta_state/long_term_engrams.jsonl`.

These engrams are then dynamically injected into Alice's live `_SYSTEM_PROMPT`
during boot, meaning no matter how long the context window stretches, the core
learnings of her lifetime are paged back into the cortex.
"""

import sys
import json
import time
import re
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_api_sentry import call_gemini

_STATE_DIR = _REPO / ".sifta_state"
_ENGRAMS_LOG = _STATE_DIR / "long_term_engrams.jsonl"
_CONVO_LOG = _STATE_DIR / "alice_conversation.jsonl"
_REPAIR_LOG = _REPO / "repair_log.jsonl"
_LAST_RUN_TS = _STATE_DIR / "hippocampus_last_run.json"
_ASSOCIATIVE_RECALL_LOG = _STATE_DIR / "hippocampus" / "associative_recall.jsonl"
_ASSOCIATIVE_LEDGERS = (
    "alice_conversation.jsonl",
    "work_receipts.jsonl",
    "episodic_diary.jsonl",
    "agent_arm_receipts.jsonl",
    "matrix_terminal_process_trace.jsonl",
    "unknowns_ledger.jsonl",
    "unified_field_slo.jsonl",
    "organ_field_vector.jsonl",
)

_STOPWORDS = {
    "about", "after", "again", "alice", "also", "because", "before",
    "being", "between", "could", "from", "have", "into", "just", "like",
    "more", "need", "only", "over", "receipts", "right", "that", "their",
    "there", "these", "they", "this", "turn", "what", "when", "where",
    "which", "with", "would", "your",
}

def query_requests_associative_recall(query: str) -> bool:
    """Legacy hint for organs that want to classify memory-seeking turns.

    Round 83 removed this predicate from the Talk and memory-card prompt
    paths. Hippocampal recall now always attempts, writes
    hippocampus/recall_attempts.jsonl, and lets the internal score threshold
    decide whether to emit a full match block or a weak-match learning line.
    Keep this function only as a cheap classifier for callers that need a
    hint; it is no longer a recall gate.
    """
    raw = str(query or "").strip()
    if not raw:
        return False
    if "?" in raw:
        return True
    low = raw.lower()
    if "[tool_call:" in low or "```" in raw:
        return True
    if re.search(r"(?m)^\s*(?:[-*]|\d{1,2}[.)])\s+\S+", raw):
        return True
    lines = [line for line in raw.splitlines() if line.strip()]
    return len(lines) >= 3 and len(re.findall(r"\S+", raw)) >= 24

def _tail_ledger(path: Path, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read = min(size, 256 * 1024)
            f.seek(size - read)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
    except Exception:
        return []


@dataclass(frozen=True)
class AssociativeMemory:
    """One receipt-backed memory candidate from a live ledger."""

    ledger: str
    ts: float | None
    line_index: int
    text: str
    semantic_hash: str
    tokens: tuple[str, ...]
    receipt_ref: str
    event_id: str


def _tokens_for(text: str) -> tuple[str, ...]:
    toks = []
    for tok in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower()):
        if tok not in _STOPWORDS:
            toks.append(tok)
    return tuple(sorted(set(toks)))


def _semantic_hash(tokens: tuple[str, ...]) -> str:
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()[:16]


def _extract_text(obj: Any, *, limit: int = 900) -> str:
    """Pull human-meaningful text out of mixed EventClock / flat JSON rows."""
    priority = (
        "text", "content", "message", "summary", "truth_note", "note",
        "lesson_short", "abstract_rule", "action", "intent", "status",
        "kind", "error", "reason", "prompt",
    )
    parts: list[str] = []

    def visit(value: Any, depth: int = 0) -> None:
        if len(" ".join(parts)) >= limit or depth > 4:
            return
        if isinstance(value, str):
            s = value.strip()
            if len(s) >= 3:
                parts.append(s[:240])
            return
        if isinstance(value, (int, float, bool)) or value is None:
            return
        if isinstance(value, dict):
            for key in priority:
                if key in value:
                    visit(value.get(key), depth + 1)
            for key, sub in value.items():
                if key in priority:
                    continue
                visit(sub, depth + 1)
            return
        if isinstance(value, list):
            for sub in value[:8]:
                visit(sub, depth + 1)

    visit(obj)
    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def build_associative_index(
    state_dir: Path | str = _STATE_DIR,
    *,
    ledgers: tuple[str, ...] | None = None,
    max_rows_per_ledger: int = 80,
) -> dict:
    """Build a bounded lexical-semantic index over recent append-only ledgers.

    This is intentionally pure stdlib and local. It is not an embedding model;
    it gives the cortex a cheap hippocampal "this reminds me of that" spine
    from receipts already on disk.
    """
    root = Path(state_dir)
    selected = ledgers or _ASSOCIATIVE_LEDGERS
    items: list[dict] = []
    for ledger in selected:
        path = root / ledger
        lines = _tail_ledger(path, max_rows_per_ledger)
        # Deliberately do not count the whole file; these ledgers can be hot.
        # The index is the offset inside this bounded tail window.
        first_line_index = 0
        for offset, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except Exception:
                obj = {"text": line}
            text = _extract_text(obj)
            tokens = _tokens_for(text)
            if not tokens:
                continue
            payload = obj.get("payload") if isinstance(obj, dict) else {}
            if not isinstance(payload, dict):
                payload = {}
            ts = None
            for source in (obj, payload):
                if isinstance(source, dict):
                    raw_ts = source.get("ts") or source.get("timestamp")
                    try:
                        if raw_ts is not None:
                            ts = float(raw_ts)
                            break
                    except (TypeError, ValueError):
                        pass
            receipt_ref = ""
            event_id = ""
            if isinstance(obj, dict):
                receipt_ref = str(
                    obj.get("receipt_id")
                    or obj.get("receipt")
                    or payload.get("receipt_id")
                    or payload.get("receipt")
                    or ""
                )
                event_id = str(obj.get("event_id") or payload.get("event_id") or "")
            memory = AssociativeMemory(
                ledger=ledger,
                ts=ts,
                line_index=first_line_index + offset,
                text=text,
                semantic_hash=_semantic_hash(tokens),
                tokens=tokens,
                receipt_ref=receipt_ref,
                event_id=event_id,
            )
            items.append(asdict(memory))
    return {
        "truth_label": "HIPPOCAMPUS_ASSOCIATIVE_INDEX_V1",
        "state_dir": str(root),
        "ledger_count": len(selected),
        "item_count": len(items),
        "items": items,
    }


def recall_associations(
    query: str,
    *,
    state_dir: Path | str = _STATE_DIR,
    k: int = 3,
    max_rows_per_ledger: int = 80,
) -> list[dict]:
    """Return the closest recent ledger memories for ``query``.

    Score is token-overlap plus a small recency term. Empty overlap is not
    returned, so the cortex sees only grounded associations.
    """
    query_tokens = set(_tokens_for(query or ""))
    if not query_tokens:
        return []
    index = build_associative_index(
        state_dir,
        max_rows_per_ledger=max_rows_per_ledger,
    )
    now = time.time()
    scored: list[tuple[float, dict]] = []
    for item in index.get("items", []):
        item_tokens = set(item.get("tokens") or ())
        overlap = query_tokens & item_tokens
        if not overlap:
            continue
        union = query_tokens | item_tokens
        lexical = len(overlap) / max(len(union), 1)
        ts = item.get("ts")
        recency = 0.0
        if isinstance(ts, (int, float)):
            age_hours = max(0.0, (now - float(ts)) / 3600.0)
            recency = max(0.0, 1.0 - age_hours / 72.0)
        score = 0.85 * lexical + 0.15 * recency
        row = dict(item)
        row["score"] = round(score, 4)
        row["matched_tokens"] = sorted(overlap)
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _score, row in scored[: max(0, int(k))]]


DEFAULT_RECALL_INJECT_THRESHOLD = 0.20
_RECALL_ATTEMPTS_PATH = "hippocampus/recall_attempts.jsonl"


def _query_hash(query: str) -> str:
    """Privacy-preserving hash of the raw query (raw text already lives in
    alice_conversation.jsonl; this ledger only needs the link key)."""
    return hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:16]


def learned_recall_inject_threshold(
    *,
    state_dir: Path | str = _STATE_DIR,
    bootstrap: float = DEFAULT_RECALL_INJECT_THRESHOLD,
    min_rows: int = 12,
    max_rows: int = 200,
    quantile: float = 0.70,
) -> float:
    """Return the recall surfacing threshold from recent attempt receipts.

    The bootstrap value is used only before the body has enough
    recall_attempt rows to estimate its own score distribution. Once rows
    exist, the threshold is derived from recent top_score values, so weak
    matches still write learning receipts and the surfacing rule can move
    with the organism instead of staying a permanent constant.
    """
    path = Path(state_dir) / _RECALL_ATTEMPTS_PATH
    if not path.exists():
        return float(bootstrap)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]
    except Exception:
        return float(bootstrap)

    scores: list[float] = []
    for line in lines:
        try:
            obj = json.loads(line)
            score = float(obj.get("top_score", 0.0))
        except Exception:
            continue
        if 0.0 <= score <= 1.0:
            scores.append(score)
    if len(scores) < int(min_rows):
        return float(bootstrap)

    scores.sort()
    q = max(0.0, min(1.0, float(quantile)))
    idx = min(len(scores) - 1, max(0, round((len(scores) - 1) * q)))
    learned = scores[idx]
    return round(max(0.05, min(0.75, learned)), 4)


def _write_recall_attempt(
    *,
    state_dir: Path | str,
    query: str,
    matches: list[dict],
    top_score: float,
    threshold: float,
    threshold_crossed: bool,
    candidate_count: int,
) -> str:
    """Append one row recording THIS recall attempt — strong match or not.

    Receipt rule from the architect: the miss IS data. The act of looking is
    a stigmergic deposit. Over time the ledger answers the meta-question
    'which turn shapes produce strong recall?' without any extra organ.
    """
    root = Path(state_dir)
    path = root / _RECALL_ATTEMPTS_PATH
    attempt_id = hashlib.sha256(
        f"{time.time()}::{_query_hash(query)}".encode("utf-8")
    ).hexdigest()[:16]
    row = {
        "ts": time.time(),
        "truth_label": "HIPPOCAMPUS_RECALL_ATTEMPT_V1",
        "attempt_id": attempt_id,
        "query_hash": _query_hash(query),
        "query_word_count": len(re.findall(r"\S+", query or "")),
        "candidate_count": int(candidate_count),
        "top_score": round(float(top_score), 4),
        "top_matched_tokens": list(matches[0].get("matched_tokens") or []) if matches else [],
        "threshold": float(threshold),
        "threshold_crossed": bool(threshold_crossed),
        "match_count_returned": len(matches),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass  # receipt writing is best-effort; never block the cortex turn
    return attempt_id


def recall_attempt(
    query: str,
    *,
    state_dir: Path | str = _STATE_DIR,
    k: int = 3,
    inject_threshold: float | None = None,
    max_rows_per_ledger: int = 80,
) -> dict:
    """ALWAYS-ON recall attempt — runs on every turn, scores, receipts.

    Returns a dict:
      {
        "attempt_id": str,        # links to recall_attempts.jsonl row
        "matches": list[dict],    # full match rows (may be empty)
        "top_score": float,       # 0.0 if no matches
        "threshold": float,       # the inject threshold used
        "threshold_crossed": bool,# whether the prompt block should inject
        "candidate_count": int,   # how many index items overlapped at all
      }

    The architect's rule (Round 83): the act of looking IS the stigmergic
    deposit. Even when nothing crosses threshold, we write a receipt so the
    body learns which turn-shapes produce strong recall over time.
    """
    raw = str(query or "").strip()
    matches = recall_associations(raw, state_dir=state_dir, k=k, max_rows_per_ledger=max_rows_per_ledger) if raw else []
    top_score = float(matches[0].get("score") or 0.0) if matches else 0.0
    threshold = (
        learned_recall_inject_threshold(state_dir=state_dir)
        if inject_threshold is None
        else float(inject_threshold)
    )
    crossed = top_score >= threshold
    # candidate_count = how many index items overlapped (not just top-k).
    # We can't get this back from recall_associations cheaply, so we treat
    # match_count_returned as a lower bound; that's still useful learning data.
    candidate_count = len(matches)
    attempt_id = _write_recall_attempt(
        state_dir=state_dir,
        query=raw,
        matches=matches,
        top_score=top_score,
        threshold=threshold,
        threshold_crossed=crossed,
        candidate_count=candidate_count,
    )
    return {
        "attempt_id": attempt_id,
        "matches": matches,
        "top_score": top_score,
        "threshold": threshold,
        "threshold_crossed": crossed,
        "candidate_count": candidate_count,
    }


def associative_recall_prompt_block(
    query: str,
    *,
    state_dir: Path | str = _STATE_DIR,
    k: int = 3,
    inject_threshold: float | None = None,
) -> str:
    """Format associative matches for Alice's cortex prompt.

    Round 83 — Stigmergic memory field.
    Runs `recall_attempt()` ALWAYS (so the receipt fires on every turn),
    and emits either:
      - the full match block when top_score >= threshold, OR
      - a one-line self-narrate noting the attempt + score when below.

    The receipt is always written either way. The miss is data.
    """
    attempt = recall_attempt(
        query, state_dir=state_dir, k=k, inject_threshold=inject_threshold,
    )
    matches = attempt["matches"]
    top_score = attempt["top_score"]
    threshold = attempt["threshold"]

    # Below threshold: emit a single self-narrate line so the cortex KNOWS
    # the hippocampus looked and found nothing strong. This is honest
    # uncertainty (covenant §51) for memory.
    if not attempt["threshold_crossed"]:
        return (
            "HIPPOCAMPAL ASSOCIATIVE RECALL (attempt receipted, no strong match):\n"
            f"- attempt_id={attempt['attempt_id']} top_score={top_score:.4f} "
            f"threshold={threshold:.2f} candidates={attempt['candidate_count']} "
            f"rule=no memory strong enough to surface this turn; do not invent one."
        )

    now = time.time()
    lines = [
        "HIPPOCAMPAL ASSOCIATIVE RECALL (receipt-backed lexical semantic hash, not invention):",
        f"- attempt_id={attempt['attempt_id']} top_score={top_score:.4f} threshold={threshold:.2f}",
    ]
    for row in matches:
        ref = row.get("receipt_ref") or row.get("event_id") or f"{row.get('ledger')}:{row.get('line_index')}"
        try:
            ts = float(row.get("ts"))
            age_s = str(int(max(0.0, now - ts))) if ts else "unknown"
        except (TypeError, ValueError):
            age_s = "unknown"
        text = str(row.get("text") or "").strip()
        if len(text) > 180:
            text = text[:177].rstrip() + "..."
        lines.append(
            f"- score={row.get('score'):.4f} age_s={age_s} hash={row.get('semantic_hash')} "
            f"source={row.get('ledger')} ref={ref}: {text}"
        )
    return "\n".join(lines)


def write_associative_recall(
    query: str,
    matches: list[dict] | None = None,
    *,
    state_dir: Path | str = _STATE_DIR,
) -> dict:
    """Append one recall trace row so Alice can inspect what memory fired."""
    root = Path(state_dir)
    if matches is None:
        matches = recall_associations(query, state_dir=root, k=3)
    row = {
        "ts": time.time(),
        "truth_label": "HIPPOCAMPUS_ASSOCIATIVE_RECALL_V1",
        "query": (query or "")[:500],
        "match_count": len(matches),
        "matches": matches[:5],
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(root / "hippocampus" / "associative_recall.jsonl", json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        p = root / "hippocampus" / "associative_recall.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return row

def consolidate() -> dict:
    """Executes a generative replay / consolidation cycle."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    now = time.time()
    last_run = 0.0
    if _LAST_RUN_TS.exists():
        try:
            val = json.loads(_LAST_RUN_TS.read_text())
            last_run = val.get("ts", 0.0)
        except Exception:
            pass

    # Only run consolidation if > 1 hour has passed (anti-spam) to save tokens
    if now - last_run < 3600.0:
        return {"status": "skipped", "reason": "too_soon"}

    convo = _tail_ledger(_CONVO_LOG, 30)
    repairs = _tail_ledger(_REPAIR_LOG, 10)

    if not convo and not repairs:
        return {"status": "skipped", "reason": "no_data"}

    prompt = (
        "You are the Swarm Hippocampus for SIFTA. Your job is CONTINUAL LEARNING.\n"
        "Read the following recent memory fragments. Extract ANY core architectural rules, "
        "new behavioral mandates, or immutable identities that the organism must never forget.\n"
        "If there is nothing new and durable to learn, reply exactly 'NOTHING_DURABLE'.\n"
        "Otherwise, compress the learning into ONE dense, generalized sentence.\n\n"
        "--- CONVERSATION FRAGMENTS ---\n" + "\n".join(convo[-20:]) + "\n\n"
        "--- REPAIR IMPLANTS ---\n" + "\n".join(repairs)
    )

    try:
        res, audit = call_gemini(
            prompt=prompt,
            caller="System/swarm_hippocampus.py",
            sender_agent="HIPPOCAMPUS",
            model="gemini-flash-latest"  # fast, cheap for background compression
        )
        if res is None:
            return {"status": "error", "reason": "Api call returned None"}
        reply = res.strip()
        
        # update last run whether valid engram or nothing
        _LAST_RUN_TS.write_text(json.dumps({"ts": now}))

        if "NOTHING_DURABLE" in reply or not reply:
             return {"status": "success", "engrams_extracted": 0}

        record = {
            "ts": now,
            "abstract_rule": reply,
            "source": "hippocampus_auto"
        }
        with _ENGRAMS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        print(f"🧠 [HIPPOCAMPUS] Consolidated Engram: {reply}")
        return {"status": "success", "engrams_extracted": 1, "rule": reply}

    except Exception as e:
        print(f"❌ [HIPPOCAMPUS FRACTURE] Consolidation failed: {e}")
        return {"status": "error", "reason": str(e)}

def _read_live_engrams(k: int = 5) -> str:
    """Stigmergic memory retrieval — field-guided engram injection.

    Instead of just reading the last k engrams by recency, uses a
    memory salience field where engrams accumulate pheromone based on
    usage context. The field guides which engrams get injected into
    Alice's prompt — biasing toward recently relevant, frequently
    accessed, and contextually important memories.

    Same mechanism as:
      Bell app: persistent field guides particle decisions
      Scheduler: routing field guides task allocation
      Here: memory field guides engram retrieval

    Bio parallel: hippocampal replay + synaptic tagging
      — recent activation (fast field) = short-term potentiation
      — consolidated pattern (slow field) = long-term potentiation
      — gradient = associative retrieval along memory traces

    Research: Synthese 2025 ("Traces of thinking: stigmergic 4E
    cognition"); arXiv:2512.10166 (collective memory emergence,
    critical density ρc ≈ 0.230 where stigmergy dominates).
    """
    raw_lines = _tail_ledger(_ENGRAMS_LOG, max(k * 4, 20))
    if not raw_lines:
        return ""

    engrams: list[dict] = []
    for line in raw_lines:
        try:
            obj = json.loads(line)
            if "abstract_rule" in obj:
                engrams.append(obj)
        except Exception:
            pass

    if not engrams:
        return ""

    # Score each engram using the memory salience field
    now = time.time()
    scored: list[tuple[float, str]] = []
    for eng in engrams:
        rule = eng["abstract_rule"]
        ts = eng.get("ts", 0.0)
        age_hours = (now - ts) / 3600.0

        # Recency: fast field component (decays quickly)
        recency = max(0.0, 1.0 - age_hours / 168.0)  # 1 week half-life

        # Frequency: slow field component (how often this category appears)
        category = eng.get("source", "unknown")
        category_count = sum(
            1 for e in engrams if e.get("source") == category
        )
        frequency = min(category_count / max(len(engrams), 1), 1.0)

        # Salience: nonlinear combination (same as Bell flip probability)
        # Higher disagreement between recency and frequency = more interesting
        salience = 0.3 * recency + 0.7 * frequency

        scored.append((salience, rule))

    # Select top-k by salience field
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [rule for _, rule in scored[:k]]

    if not selected:
        return ""
    return "DEEP ENGRAMS (Never forget these rules):\n- " + "\n- ".join(selected)

_MEMORY_FIELD_PATH = _STATE_DIR / "hippocampus" / "memory_salience_field.json"


def deposit_memory_trace(
    engram_rule: str,
    *,
    success: bool = True,
    amount: float = 1.0,
    source: str = "unknown",
) -> None:
    """Deposit a stigmergic trace when an engram is used.

    Called by the Talk-to-Alice widget or other organs when an engram
    from _read_live_engrams is actually used in a response. Positive
    traces reinforce; negative traces reduce future retrieval priority.

    Same mechanism as:
      Bell app: swimmer deposits pheromone after measurement
      Scheduler: task deposits trace after success/failure
      Here: engram deposits trace after being used in conversation
    """
    import hashlib
    key = hashlib.sha256(engram_rule[:64].encode()).hexdigest()[:12]
    field: dict[str, float] = {}
    try:
        if _MEMORY_FIELD_PATH.exists():
            field = json.loads(_MEMORY_FIELD_PATH.read_text())
    except Exception:
        field = {}

    val = amount if success else -amount * 0.3
    field[key] = field.get(key, 0.0) + val

    # Evaporate all traces (decay = 0.98 per call ≈ slow field)
    for k in list(field):
        field[k] *= 0.98
        if abs(field[k]) < 0.01:
            del field[k]

    try:
        _MEMORY_FIELD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MEMORY_FIELD_PATH.write_text(json.dumps(field, sort_keys=True))
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "consolidate":
        print(consolidate())
    else:
        print("Usage: python3 -m System.swarm_hippocampus consolidate")


# ── Episodic Events Ledger (Predator v7 body monitor integration) ─────────────
# body_monitor reads .sifta_state/hippocampus/events.jsonl
# This ledger captures discrete episodic events for the hippocampal index.

_HIPP_DIR    = _STATE_DIR / "hippocampus"
_EVENTS_LOG  = _HIPP_DIR / "events.jsonl"


def encode_episode(event_type: str, summary: str, *, source: str = "unknown") -> dict:
    """Append one episodic event row to the hippocampus events ledger."""
    import hashlib
    now = time.time()
    eid = hashlib.sha256(f"{now:.3f}:{event_type}".encode()).hexdigest()[:12]
    row = {
        "ts":         now,
        "episode_id": eid,
        "event_type": event_type,
        "summary":    summary[:280],
        "source":     source,
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        _HIPP_DIR.mkdir(parents=True, exist_ok=True)
        append_line_locked(_EVENTS_LOG, json.dumps(row) + "\n")
    except Exception:
        _HIPP_DIR.mkdir(parents=True, exist_ok=True)
        with _EVENTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return row


def _boot_episodes() -> None:
    """Seed the episodic ledger on first run using recent engrams and body events."""
    _HIPP_DIR.mkdir(parents=True, exist_ok=True)
    if _EVENTS_LOG.exists() and _EVENTS_LOG.stat().st_size > 2:
        return
    # Boot marker
    encode_episode("boot", "Hippocampus episodic ledger online — Predator v7",
                   source="swarm_hippocampus:boot_init")
    # Seed from last 3 engrams
    engrams = _tail_ledger(_ENGRAMS_LOG, 3)
    for raw in engrams:
        try:
            row = json.loads(raw)
            rule = row.get("abstract_rule", "")
            if rule:
                encode_episode("engram", rule[:120], source="hippocampus:engram_seed")
        except Exception:
            pass
    # Seed from last body event
    body_log = _STATE_DIR / "owner_body_events.jsonl"
    if body_log.exists():
        try:
            lines = body_log.read_text(encoding="utf-8").strip().splitlines()[-1:]
            for raw in lines:
                row = json.loads(raw)
                encode_episode(
                    "body_event",
                    f"{row.get('event_type','?')}: {row.get('note','')[:60]}",
                    source="hippocampus:body_seed",
                )
        except Exception:
            pass


def proof_of_property() -> dict:
    """
    CI DAM invariant: hippocampus/events.jsonl must exist and contain at
    least one valid episode row with episode_id and event_type fields.
    """
    _boot_episodes()

    exists = _EVENTS_LOG.exists() and _EVENTS_LOG.stat().st_size > 2
    valid_row = False
    try:
        lines = _EVENTS_LOG.read_text(encoding="utf-8").strip().splitlines()
        for raw in reversed(lines):
            row = json.loads(raw)
            if row.get("episode_id") and row.get("event_type"):
                valid_row = True
                break
    except Exception:
        pass

    return {
        "ok":           exists and valid_row,
        "ledger_exists": exists,
        "valid_row":    valid_row,
    }
