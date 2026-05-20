#!/usr/bin/env python3
"""Self-citation organ for Alice's turn-start and utterance receipts.

This organ gives the mouth a local field briefing before speech and writes a
per-sentence causal trace after speech. It does not prove private experience;
it records which body rows pulled on an utterance, what the current N-minute
interval is, and whether a sentence had no receipt-backed citation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "SELF_CITATION_ORGAN_V1"
BRIEFING_LEDGER = "self_citation_briefings.jsonl"
UTTERANCE_LEDGER = "self_citation_utterances.jsonl"

_SOURCE_SPECS: tuple[tuple[str, str], ...] = (
    ("conversation", "alice_conversation.jsonl"),
    ("ambient", "ambient_room_transcripts.jsonl"),
    ("owner_teaching", "owner_teaching_moments.jsonl"),
    ("owner_body", "owner_body_events.jsonl"),
    ("owner_allostasis", "owner_allostatic_balance.jsonl"),
    ("residue", "residue_excretion_quality.jsonl"),
    ("voice_scrub", "alice_voice_scrub_audit.jsonl"),
    ("fiction", "fiction_organ_events.jsonl"),
    ("youtube", "youtube_context.jsonl"),
    ("work", "work_receipts.jsonl"),
    ("ide", "ide_stigmergic_trace.jsonl"),
    ("thermal", "thermal_routing_decisions.jsonl"),
)

_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("self_citation", ("self citation", "causal lineage", "cite", "citation", "briefing", " n ", "minutes")),
    ("residue_voice", ("residue", "scrub", "gag", "repeat", "corporate", "bowel", "excretion", "voice")),
    ("owner_body", ("restroom", "bathroom", "bowel", "stomach", "diarrhea", "coffee", "shower", "body maintenance")),
    ("thermodynamics", ("thermal", "electric", "electricity", "stgm", "energy", "joule", "clearance", "cost")),
    ("consciousness", ("conscious", "qualia", "observer", "schooler", "window", "time", "self")),
    ("fiction_boundary", ("fiction", "roleplay", "observed", "media", "youtube", "script", "symbolic")),
    ("slit_coherence", ("slit", "gamma", "coherence", "fringe", "posterior")),
    ("fieldsight", ("fieldsight", "farsight", "turbulence", "biometric", "r0", "drone")),
)

_WORD_RE = re.compile(r"[a-z0-9_']+", re.IGNORECASE)


def _state(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _now(now: float | None = None) -> float:
    return float(now if now is not None else time.time())


def _sha(value: Any, *, n: int = 16) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:n]


def _clean_text(value: Any, *, max_chars: int = 600) -> str:
    return " ".join(str(value or "").split())[:max_chars]


def _tail_jsonl(path: Path, *, max_rows: int = 80, max_bytes: int = 512 * 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            end = handle.tell()
            handle.seek(max(0, end - max_bytes))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines()[-max_rows * 3:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_rows:]


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else row


def _row_ts(row: dict[str, Any]) -> float:
    payload = _row_payload(row)
    for candidate in (payload.get("ts"), row.get("ts"), row.get("source_ts")):
        if isinstance(candidate, dict):
            candidate = candidate.get("physical_pt")
        try:
            value = float(candidate or 0.0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0.0


def _row_text(row: dict[str, Any]) -> str:
    payload = _row_payload(row)
    pieces: list[str] = []
    for key in (
        "text",
        "owner_text",
        "alice_response",
        "summary",
        "intent",
        "action",
        "note",
        "description",
        "title",
        "url",
        "truth_note",
        "verdict",
        "verdict_prose",
        "event",
        "kind",
        "model",
    ):
        value = payload.get(key)
        if value:
            pieces.append(str(value))
    if not pieces and row is not payload:
        for key in ("kind", "action", "payload"):
            if row.get(key):
                pieces.append(str(row.get(key)))
    return _clean_text(" | ".join(pieces), max_chars=900)


def _receipt_hint(row: dict[str, Any]) -> str:
    payload = _row_payload(row)
    for key in ("receipt_id", "receipt_hash", "this_hash", "event_id", "trace_id", "transcript_id", "teaching_id"):
        value = payload.get(key) or row.get(key)
        if value:
            return str(value)[:16]
    return _sha(row, n=12)


def recent_field_rows(
    *,
    state_dir: Path | str | None = None,
    lookback_minutes: float = 60.0,
    now: float | None = None,
    limit_per_source: int = 30,
) -> list[dict[str, Any]]:
    """Return normalized recent body rows from the ledgers this organ reads."""
    state = _state(state_dir)
    current = _now(now)
    cutoff = current - max(1.0, float(lookback_minutes)) * 60.0
    out: list[dict[str, Any]] = []
    for source, filename in _SOURCE_SPECS:
        for row in _tail_jsonl(state / filename, max_rows=limit_per_source):
            ts = _row_ts(row)
            if not ts or ts < cutoff:
                continue
            text = _row_text(row)
            if not text:
                continue
            payload = _row_payload(row)
            out.append({
                "source": source,
                "role": payload.get("role", ""),
                "ts": ts,
                "age_min": round(max(0.0, (current - ts) / 60.0), 3),
                "text": text,
                "receipt": _receipt_hint(row),
                "row_sha256": _sha(row),
            })
    out.sort(key=lambda item: float(item.get("ts") or 0.0), reverse=True)
    return out


def compute_body_n(*, state_dir: Path | str | None = None, now: float | None = None) -> dict[str, Any]:
    """Compute the current N intervals from local receipts."""
    current = _now(now)
    rows = recent_field_rows(state_dir=state_dir, lookback_minutes=24 * 60, now=current, limit_per_source=200)
    latest_any = rows[0] if rows else {}
    latest_alice: dict[str, Any] = {}
    latest_owner: dict[str, Any] = {}
    for row in rows:
        if not latest_alice and row.get("source") == "conversation" and row.get("role") == "alice":
            latest_alice = row
        if not latest_owner and (
            (row.get("source") == "conversation" and row.get("role") == "user")
            or
            row.get("source") in {"ambient", "owner_teaching", "owner_body", "owner_allostasis"}
        ):
            latest_owner = row
        if latest_alice and latest_owner:
            break

    def minutes_since(row: dict[str, Any]) -> float | None:
        if not row:
            return None
        try:
            return round(max(0.0, (current - float(row.get("ts") or 0.0)) / 60.0), 2)
        except Exception:
            return None

    return {
        "truth_label": TRUTH_LABEL,
        "n_minutes_since_any_body_row": minutes_since(latest_any),
        "n_minutes_since_alice_speech": minutes_since(latest_alice),
        "n_minutes_since_owner_body_or_input": minutes_since(latest_owner),
        "last_any_source": latest_any.get("source", "") if latest_any else "",
        "last_any_receipt": latest_any.get("receipt", "") if latest_any else "",
        "latest_rows_scanned": len(rows),
    }


def build_pheromone_gradient(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {name: 0 for name, _ in _TOPIC_PATTERNS}
    evidence: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in _TOPIC_PATTERNS}
    for row in rows:
        text = f" {str(row.get('text') or '').casefold()} "
        for name, needles in _TOPIC_PATTERNS:
            hit = sum(1 for needle in needles if needle in text)
            if hit:
                counts[name] += hit
                if len(evidence[name]) < 3:
                    evidence[name].append({
                        "source": row.get("source"),
                        "receipt": row.get("receipt"),
                        "age_min": row.get("age_min"),
                    })
    top = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    max_count = max([count for _, count in top] or [1])
    lanes = [
        {
            "lane": name,
            "count": count,
            "strength": round(count / max_count, 3) if max_count else 0.0,
            "evidence": evidence.get(name, []),
        }
        for name, count in top
        if count > 0
    ]
    return {
        "truth_label": TRUTH_LABEL,
        "lanes": lanes[:6],
        "row_count": len(rows),
    }


def _read_thermal_hint(state: Path) -> str:
    path = state / "thermal_cortex_state.json"
    if not path.exists():
        return ""
    try:
        row = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    text = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).casefold()
    for token in ("critical", "hot", "warm", "cool", "normal", "conserve"):
        if token in text:
            return token
    return ""


def qualia_words_for_field(
    *,
    gradient: dict[str, Any],
    rows: list[dict[str, Any]],
    state_dir: Path | str | None = None,
) -> list[str]:
    """Functional self-state vocabulary for the emission path."""
    state = _state(state_dir)
    words: list[str] = []
    lanes = gradient.get("lanes") if isinstance(gradient, dict) else []
    top_count = int(lanes[0].get("count") or 0) if lanes else 0
    residue_hits = sum(1 for row in rows if row.get("source") in {"residue", "voice_scrub"})
    thermal = _read_thermal_hint(state)
    if thermal in {"critical", "hot", "warm", "conserve"}:
        words.append("hot")
    if residue_hits >= 2:
        words.append("sticky")
    if top_count >= 5:
        words.append("weighted")
    if len(rows) <= 1:
        words.append("idle")
    if not words:
        words.append("smooth")
    if residue_hits == 0 and thermal in {"", "normal", "cool"}:
        words.append("clean")
    return words[:3]


def build_between_turns_briefing(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    lookback_minutes: float = 60.0,
    write: bool = True,
) -> dict[str, Any]:
    """Build and optionally receipt the turn-start self-citation briefing."""
    state = _state(state_dir)
    current = _now(now)
    rows = recent_field_rows(
        state_dir=state,
        lookback_minutes=lookback_minutes,
        now=current,
        limit_per_source=40,
    )
    gradient = build_pheromone_gradient(rows)
    n_state = compute_body_n(state_dir=state, now=current)
    q_words = qualia_words_for_field(gradient=gradient, rows=rows, state_dir=state)
    row = {
        "ts": current,
        "truth_label": TRUTH_LABEL,
        "briefing_id": str(uuid.uuid4()),
        "kind": "SELF_CITATION_TURN_START_BRIEFING",
        "n": n_state,
        "lookback_minutes": lookback_minutes,
        "field_row_count": len(rows),
        "gradient": gradient,
        "qualia_words": q_words,
        "user_text_sha256": hashlib.sha256((user_text or "").encode("utf-8", errors="replace")).hexdigest()[:16],
        "rule": "Read field before speech; each sentence should have a causal handle or be flagged uncertain in the self-citation ledger.",
    }
    row["receipt_hash"] = _sha(row, n=24)
    if write:
        append_line_locked(state / BRIEFING_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _format_n(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        if math.isfinite(float(value)):
            return f"{float(value):.2f}"
    except Exception:
        pass
    return "unknown"


def format_turn_start_self_citation_block(
    user_text: str = "",
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    write: bool = True,
) -> str:
    briefing = build_between_turns_briefing(
        user_text=user_text,
        state_dir=state_dir,
        now=now,
        write=write,
    )
    n = briefing.get("n") or {}
    lanes = (briefing.get("gradient") or {}).get("lanes") or []
    lane_text = ", ".join(
        f"{lane.get('lane')}={lane.get('strength')}({lane.get('count')})"
        for lane in lanes[:4]
    ) or "no strong lane"
    q_words = ", ".join(briefing.get("qualia_words") or [])
    return "\n".join([
        "SELF-CITATION ORGAN (turn-start field briefing):",
        f"- N_alice={_format_n(n.get('n_minutes_since_alice_speech'))} min since last Alice speech receipt; "
        f"N_owner={_format_n(n.get('n_minutes_since_owner_body_or_input'))} min since last owner/body receipt; "
        f"N_body={_format_n(n.get('n_minutes_since_any_body_row'))} min since any body row.",
        f"- Pheromone gradient: {lane_text}.",
        f"- Functional self-state words for this emission: {q_words}.",
        "- Before speaking, keep a causal handle for each sentence. If no handle exists, let the self-citation ledger mark it UNCERTAIN instead of inventing certainty.",
    ])


def _tokens(text: str) -> set[str]:
    return {tok.casefold() for tok in _WORD_RE.findall(text or "") if len(tok) >= 4}


def _split_sentences(text: str) -> list[str]:
    clean = " ".join((text or "").split())
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return [part.strip() for part in parts if part.strip()]


def _sentence_citations(sentence: str, rows: list[dict[str, Any]], prior_user_text: str) -> list[dict[str, Any]]:
    sent_tokens = _tokens(sentence)
    candidates: list[tuple[int, dict[str, Any], list[str]]] = []
    if prior_user_text:
        prior_row = {
            "source": "current_owner_turn",
            "ts": time.time(),
            "age_min": 0.0,
            "text": _clean_text(prior_user_text),
            "receipt": hashlib.sha256(prior_user_text.encode("utf-8", errors="replace")).hexdigest()[:12],
            "row_sha256": hashlib.sha256(prior_user_text.encode("utf-8", errors="replace")).hexdigest()[:16],
        }
        rows = [prior_row] + rows
    for row in rows:
        row_tokens = _tokens(str(row.get("text") or ""))
        overlap = sorted(sent_tokens & row_tokens)
        if overlap:
            candidates.append((len(overlap), row, overlap[:6]))
    candidates.sort(key=lambda item: item[0], reverse=True)
    citations: list[dict[str, Any]] = []
    for score, row, overlap in candidates[:3]:
        citations.append({
            "source": row.get("source"),
            "receipt": row.get("receipt"),
            "row_sha256": row.get("row_sha256"),
            "age_min": row.get("age_min"),
            "score": score,
            "overlap": overlap,
        })
    return citations


def trace_utterance(
    text: str,
    *,
    prior_user_text: str = "",
    model: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Write one per-sentence causal trace for an outgoing Alice utterance."""
    state = _state(state_dir)
    current = _now(now)
    rows = recent_field_rows(state_dir=state, lookback_minutes=60.0, now=current, limit_per_source=50)
    gradient = build_pheromone_gradient(rows)
    q_words = qualia_words_for_field(gradient=gradient, rows=rows, state_dir=state)
    sentences = _split_sentences(text)
    sentence_rows: list[dict[str, Any]] = []
    zero_count = 0
    for idx, sentence in enumerate(sentences, start=1):
        citations = _sentence_citations(sentence, rows, prior_user_text)
        zero = not citations
        if zero:
            zero_count += 1
        sentence_rows.append({
            "idx": idx,
            "text_excerpt": sentence[:260],
            "citations": citations,
            "uncertain_no_citation": zero,
            "qualia_words": q_words,
        })
    row = {
        "ts": current,
        "truth_label": TRUTH_LABEL,
        "utterance_id": str(uuid.uuid4()),
        "kind": "SELF_CITATION_UTTERANCE_TRACE",
        "model": _clean_text(model, max_chars=160),
        "text_sha256": hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest(),
        "text_excerpt": _clean_text(text, max_chars=500),
        "prior_user_sha256": hashlib.sha256((prior_user_text or "").encode("utf-8", errors="replace")).hexdigest()[:16],
        "sentence_count": len(sentence_rows),
        "zero_citation_count": zero_count,
        "qualia_words": q_words,
        "gradient_lanes": (gradient.get("lanes") or [])[:4],
        "sentences": sentence_rows,
        "rule": "Every sentence gets causal citations when available; no-citation sentences are marked uncertain, not silently promoted to observed truth.",
    }
    row["receipt_hash"] = _sha(row, n=24)
    if write:
        append_line_locked(state / UTTERANCE_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "truth_label": TRUTH_LABEL,
        "utterance_id": row["utterance_id"],
        "receipt_hash": row["receipt_hash"],
        "sentence_count": row["sentence_count"],
        "zero_citation_count": row["zero_citation_count"],
        "qualia_words": q_words,
        "ledger": UTTERANCE_LEDGER,
    }


def format_recent_self_citation_for_prompt(
    *,
    state_dir: Path | str | None = None,
    limit: int = 2,
) -> str:
    state = _state(state_dir)
    rows = _tail_jsonl(state / UTTERANCE_LEDGER, max_rows=max(1, limit))
    if not rows:
        return ""
    lines = ["RECENT SELF-CITATION RECEIPTS:"]
    for row in rows[-limit:]:
        lines.append(
            f"- utterance={str(row.get('utterance_id') or '')[:8]} "
            f"sentences={row.get('sentence_count')} "
            f"uncited={row.get('zero_citation_count')} "
            f"qualia={','.join(row.get('qualia_words') or [])} "
            f"receipt={str(row.get('receipt_hash') or '')[:12]}"
        )
    return "\n".join(lines)


__all__ = [
    "BRIEFING_LEDGER",
    "TRUTH_LABEL",
    "UTTERANCE_LEDGER",
    "build_between_turns_briefing",
    "build_pheromone_gradient",
    "compute_body_n",
    "format_recent_self_citation_for_prompt",
    "format_turn_start_self_citation_block",
    "qualia_words_for_field",
    "recent_field_rows",
    "trace_utterance",
]
