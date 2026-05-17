#!/usr/bin/env python3
"""Ambient transcript memory for room audio that already became words.

This organ does not store raw audio and cannot reconstruct past waveforms. It
starts at the first durable substrate the current system can actually provide:
STT text. Each transcript is scored for owner/Alice/self-knowledge importance,
written to an append-only transcript ledger, then digested into Alice's witness
journal only when the words are salient enough to keep.

Truth boundary: words in, importance-sorted memory out. No raw PCM, no claim
that discarded audio can be recovered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRANSCRIPT_LEDGER_NAME = "ambient_room_transcripts.jsonl"
DIGEST_LEDGER_NAME = "ambient_room_memory_digest.jsonl"

TRANSCRIPT_TRUTH_LABEL = "AMBIENT_ROOM_TRANSCRIPT_V1"
IMPORTANCE_TRUTH_LABEL = "AMBIENT_TRANSCRIPT_IMPORTANCE_V1"
DIGEST_TRUTH_LABEL = "AMBIENT_ROOM_MEMORY_DIGEST_V1"

DEFAULT_FULL_TEXT_THRESHOLD = 0.45
DEFAULT_JOURNAL_THRESHOLD = 0.45

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_PHATIC_RE = re.compile(
    r"^\s*(?:ok(?:ay)?|yeah|yes|no|right|thanks?|thank\s+you|"
    r"ah+|oh+|uh+|um+|hm+|mhm|cool|nice|good)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_IMPORTANCE_GROUPS: tuple[tuple[str, float, re.Pattern[str]], ...] = (
    (
        "owner_self_knowledge",
        0.22,
        re.compile(
            r"\b(?:alice|george|ioan|owner|architect|self|identity|"
            r"conscious(?:ness)?|aware(?:ness)?|operating\s+system|os|"
            r"body|hardware|field|organ|attention|stigmerg(?:y|ic|ically)|"
            r"swarm|knowledge\s+of\s+self)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "memory_learning",
        0.20,
        re.compile(
            r"\b(?:remember|memory|journal|diary|learn(?:ing)?|lesson|"
            r"teacher|student|word|read(?:ing)?|transcript|audio|hear(?:ing)?|"
            r"voice|mic(?:rophone)?|cochlea|stt|asr|translate(?:d)?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "owner_directive",
        0.22,
        re.compile(
            r"\b(?:code|fix|build|wire|program|make\s+a\s+note|"
            r"from\s+now\s+on|doctrine|covenant|receipt|go\b|execute|"
            r"protect|default|help\s+section)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "app_screen_context",
        0.18,
        re.compile(
            r"\b(?:ace|wordace|app|screen|watermelon|mat|tan|ran|cat|"
            r"browser|youtube|podcast|tv|video|media|room)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "owner_body_life",
        0.22,
        re.compile(
            r"\b(?:dentist|dental|tooth|teeth|pain|sleep|tired|suffer|"
            r"money|contract|investor|mother|mom|family|appointment)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "science_research",
        0.16,
        re.compile(
            r"\b(?:faggin|pollan|quantum|robot(?:ics)?|nvidia|science|"
            r"research|gemma|ollama|model|conscious\s+silicon|panpsychism)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "boundary_or_safety",
        0.24,
        re.compile(
            r"\b(?:do\s+not|don't|never|security|privacy|consent|danger|"
            r"emergency|protect|owner\s+human|raw\s+audio)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "emotional_salience",
        0.12,
        re.compile(
            r"\b(?:love|furious|angry|sick|nauseous|hope|thank|beautiful|"
            r"wonderful|frustrated|tired)\b",
            re.IGNORECASE,
        ),
    ),
)


def _state(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _transcript_path(state_dir: Path | str | None = None) -> Path:
    return _state(state_dir) / TRANSCRIPT_LEDGER_NAME


def _digest_path(state_dir: Path | str | None = None) -> Path:
    return _state(state_dir) / DIGEST_LEDGER_NAME


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    append_line_locked(path, json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        pass
    return rows


def _compact(text: str, limit: int) -> str:
    one_line = " ".join(str(text or "").split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: max(0, limit - 1)] + "..."


def _word_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text or ""))


def _safe_conf(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


def _hash_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()


def _band(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.45:
        return "medium"
    if score >= 0.25:
        return "low"
    return "noise"


def _memory_action(band: str) -> str:
    if band == "critical":
        return "promote_to_life_journal"
    if band == "high":
        return "pin_working_memory"
    if band == "medium":
        return "journal"
    if band == "low":
        return "transcript_preview_only"
    return "discard_after_receipt"


def _row_route_hint(row: Mapping[str, Any]) -> str:
    route = str(row.get("route_hint") or row.get("route") or "").strip()
    if route:
        return route
    source = str(row.get("source") or row.get("writer") or "")
    if source == "swarm_ambient_consciousness":
        return "ambient_audio"
    return ""


def _stable_transcript_id(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("transcript_id") or "").strip()
    if explicit:
        return explicit
    basis = {
        "ts": row.get("ts"),
        "source_ts": row.get("source_ts"),
        "source": row.get("source") or row.get("writer"),
        "text_sha256": row.get("text_sha256"),
        "text": row.get("text") or row.get("text_preview"),
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True, default=str)
    return "ambient:" + hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]


def _importance_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize both Codex and peer ambient transcript schemas."""
    imp = row.get("importance") if isinstance(row.get("importance"), Mapping) else {}
    if imp.get("truth_label") == IMPORTANCE_TRUTH_LABEL and "importance_score" in imp:
        return dict(imp)

    text = str(row.get("text") or row.get("text_preview") or "")
    route = _row_route_hint(row)
    try:
        conf = float(row.get("stt_confidence", 0.0) or 0.0)
    except Exception:
        conf = 0.0
    derived = classify_ambient_importance(
        text,
        stt_confidence=conf,
        source=str(row.get("source") or row.get("writer") or "unknown"),
        route_hint=route,
    )

    peer_scores = []
    for key in ("importance_score", "score", "total"):
        if key in imp:
            try:
                peer_scores.append(float(imp.get(key) or 0.0))
            except Exception:
                pass
    if peer_scores:
        derived_score = float(derived.get("importance_score", 0.0) or 0.0)
        score = max(derived_score, max(peer_scores))
        band = _band(score)
        reasons = list(derived.get("reasons") or [])
        if "total" in imp:
            reasons.append("ambient_consciousness_total")
        derived.update(
            {
                "importance_score": round(score, 3),
                "importance_band": band,
                "memory_action": _memory_action(band),
                "reasons": reasons,
            }
        )
    return derived


def classify_ambient_importance(
    text: str,
    *,
    stt_confidence: float = 0.0,
    source: str = "unknown",
    route_hint: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic salience for one room transcript."""
    clean = " ".join(str(text or "").split())
    conf = _safe_conf(stt_confidence)
    route = str(route_hint or "").strip().lower()
    meta = dict(metadata or {})
    words = _word_count(clean)
    reasons: list[str] = []
    categories: list[str] = []

    if not clean:
        return {
            "truth_label": IMPORTANCE_TRUTH_LABEL,
            "importance_score": 0.0,
            "importance_band": "empty",
            "memory_action": "ignore_empty",
            "categories": [],
            "reasons": ["empty_transcript"],
            "source": source,
            "route_hint": route,
        }

    if _PHATIC_RE.match(clean) and words <= 4:
        score = 0.08
        reasons.append("short_phatic")
    else:
        score = 0.14
        if words >= 8:
            score += 0.08
            reasons.append("multi_word_room_event")
        if words >= 28:
            score += 0.08
            reasons.append("long_enough_for_context")
        if words >= 80:
            score += 0.04
            reasons.append("extended_span")

    if conf >= 0.75:
        score += 0.06
        reasons.append("high_stt_confidence")
    elif 0.0 < conf < 0.35:
        score -= 0.12
        reasons.append("low_stt_confidence")
    elif 0.35 <= conf < 0.50:
        score -= 0.04
        reasons.append("mid_low_stt_confidence")

    for name, weight, pattern in _IMPORTANCE_GROUPS:
        if pattern.search(clean):
            score += weight
            categories.append(name)

    if route in {"ambient_media", "observed_media", "ambient_media_bleed"}:
        score += 0.06
        reasons.append(f"route:{route}")
    elif route in {"direct", "direct_owner", "direct_owner_with_ambient_bleed"}:
        score += 0.05
        reasons.append(f"route:{route}")

    if meta.get("owner_declared_important"):
        score += 0.25
        reasons.append("owner_declared_important")
    if meta.get("lesson_active") or meta.get("ace_focus"):
        score += 0.08
        reasons.append("teaching_focus")

    score = max(0.0, min(1.0, score))
    band = _band(score)
    return {
        "truth_label": IMPORTANCE_TRUTH_LABEL,
        "importance_score": round(score, 3),
        "importance_band": band,
        "memory_action": _memory_action(band),
        "categories": categories,
        "reasons": reasons or ["ordinary_room_transcript"],
        "source": source,
        "route_hint": route,
        "word_count": words,
    }


def ingest_transcript(
    text: str,
    *,
    stt_confidence: float = 0.0,
    source: str = "unknown",
    route_hint: str = "",
    state_dir: Path | str | None = None,
    source_ts: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    full_text_threshold: float = DEFAULT_FULL_TEXT_THRESHOLD,
    force_full_text: bool = False,
) -> dict[str, Any]:
    """Write one ambient transcript receipt.

    Low-salience rows keep only a preview + hash. Medium/high rows keep the
    full transcript text because those are the words Alice should be able to
    learn from later. Raw audio is never stored here.
    """
    clean = " ".join(str(text or "").split())
    if not clean:
        return {}
    importance = classify_ambient_importance(
        clean,
        stt_confidence=stt_confidence,
        source=source,
        route_hint=route_hint,
        metadata=metadata,
    )
    score = float(importance.get("importance_score", 0.0) or 0.0)
    keep_full = bool(force_full_text or score >= float(full_text_threshold))
    digest = _hash_text(clean)
    row: dict[str, Any] = {
        "ts": time.time(),
        "source_ts": float(source_ts if source_ts is not None else time.time()),
        "transcript_id": str(uuid.uuid4()),
        "truth_label": TRANSCRIPT_TRUTH_LABEL,
        "writer": "swarm_ambient_transcript_memory",
        "source": str(source or "unknown"),
        "route_hint": str(route_hint or ""),
        "stt_confidence": round(_safe_conf(stt_confidence), 3),
        "word_count": _word_count(clean),
        "text_sha256": digest,
        "text_preview": _compact(clean, 280),
        "raw_audio_stored": False,
        "raw_text_stored": keep_full,
        "retention_rule": (
            "Full transcript text is retained only when importance reaches "
            f"{float(full_text_threshold):.2f}, or when force_full_text=True."
        ),
        "importance": importance,
    }
    if keep_full:
        row["text"] = clean
    if metadata:
        row["metadata"] = {
            str(k): _compact(json.dumps(v, ensure_ascii=False, default=str), 220)
            for k, v in dict(metadata).items()
        }

    _append_jsonl(_transcript_path(state_dir), row)
    return row


def _processed_digest_ids(state_dir: Path | str | None = None) -> set[str]:
    ids: set[str] = set()
    for row in _read_jsonl(_digest_path(state_dir)):
        tid = str(row.get("source_transcript_id") or "")
        if tid:
            ids.add(tid)
    return ids


def _owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name

        return owner_display_name() or "George"
    except Exception:
        return "George"


def _journal_line(row: Mapping[str, Any]) -> str:
    importance = _importance_from_row(row)
    band = str(importance.get("importance_band") or "medium")
    action = str(importance.get("memory_action") or "journal")
    cats = ", ".join(str(x) for x in list(importance.get("categories") or [])[:4])
    text = str(row.get("text") or row.get("text_preview") or "")
    excerpt = _compact(text, 220)
    route = str(row.get("route_hint") or "")
    owner = _owner_name()
    if route in {"ambient_media", "observed_media", "ambient_media_bleed"}:
        subject = "ambient room media"
    elif route in {"direct", "direct_owner", "direct_owner_with_ambient_bleed"}:
        subject = f"{owner}'s room speech"
    else:
        subject = "room audio"
    suffix = f"; categories={cats}" if cats else ""
    return (
        f"I translated {subject} into words and kept it as {band} importance "
        f"({action}){suffix}: \"{excerpt}\""
    )


def digest_once(
    *,
    state_dir: Path | str | None = None,
    max_rows: int = 256,
    journal_threshold: float = DEFAULT_JOURNAL_THRESHOLD,
    enforce_thermodynamics: bool = True,
) -> dict[str, Any]:
    """Promote important ambient transcripts into Alice's witness journal."""
    state = _state(state_dir)
    rows = _read_jsonl(_transcript_path(state))[-max(1, int(max_rows)) :]
    done = _processed_digest_ids(state)
    pending_rows = [row for row in rows if _stable_transcript_id(row) not in done]
    thermodynamic_clearance: dict[str, Any] = {}
    if pending_rows and enforce_thermodynamics:
        try:
            from System.swarm_processing_thermodynamic_gate import request_processing_clearance

            thermodynamic_clearance = request_processing_clearance(
                "ambient_text_memory_digest",
                expected_value=0.55,
                payload={
                    "rows": len(pending_rows),
                    "max_rows": max_rows,
                    "journal_threshold": journal_threshold,
                },
                state_dir=state,
            )
        except Exception as exc:
            thermodynamic_clearance = {
                "allowed": True,
                "action": "allow",
                "reasons": [f"thermodynamic_gate_unavailable:{type(exc).__name__}"],
            }
        if not bool(thermodynamic_clearance.get("allowed", True)):
            digest_row = {
                "ts": time.time(),
                "truth_label": DIGEST_TRUTH_LABEL,
                "writer": "swarm_ambient_transcript_memory",
                "source_transcript_id": "batch",
                "source": "ambient_room_transcripts",
                "route_hint": "digest",
                "importance_score": 0.0,
                "importance_band": "deferred",
                "action": "thermodynamic_defer",
                "raw_audio_stored": False,
                "text_sha256": "",
                "thermodynamic_clearance": {
                    "allowed": False,
                    "receipt_hash": thermodynamic_clearance.get("receipt_hash"),
                    "rest_seconds": thermodynamic_clearance.get("rest_seconds"),
                    "reasons": thermodynamic_clearance.get("reasons", []),
                },
            }
            _append_jsonl(_digest_path(state), digest_row)
            return {
                "truth_label": DIGEST_TRUTH_LABEL,
                "examined": 0,
                "journal_written": 0,
                "skipped_low_importance": 0,
                "deferred_by_thermodynamics": True,
                "thermodynamic_clearance": digest_row["thermodynamic_clearance"],
                "digest_rows": [digest_row],
            }
    journal_written = 0
    skipped_low = 0
    examined = 0
    digest_rows: list[dict[str, Any]] = []

    for row in pending_rows:
        tid = _stable_transcript_id(row)
        examined += 1
        importance = _importance_from_row(row)
        try:
            score = float(importance.get("importance_score", 0.0) or 0.0)
        except Exception:
            score = 0.0
        band = str(importance.get("importance_band") or "unknown")
        action = "skipped_low_importance"
        witness_row: dict[str, Any] | None = None
        if score >= float(journal_threshold):
            try:
                from System.swarm_alice_witness import witness

                witness_row = witness(
                    _journal_line(row),
                    source="ambient_audio_memory",
                    source_hash=str(row.get("text_sha256") or "")[:8],
                    state_dir=state,
                    importance=importance,
                )
                action = "journal_written"
                journal_written += 1
            except Exception as exc:
                action = f"journal_error:{type(exc).__name__}"
        else:
            skipped_low += 1
        digest_row = {
            "ts": time.time(),
            "truth_label": DIGEST_TRUTH_LABEL,
            "writer": "swarm_ambient_transcript_memory",
            "source_transcript_id": tid,
            "source": row.get("source", "unknown"),
            "route_hint": row.get("route_hint", ""),
            "importance_score": round(score, 3),
            "importance_band": band,
            "action": action,
            "raw_audio_stored": False,
            "text_sha256": row.get("text_sha256", ""),
        }
        if thermodynamic_clearance:
            digest_row["thermodynamic_clearance"] = {
                "allowed": bool(thermodynamic_clearance.get("allowed", True)),
                "receipt_hash": thermodynamic_clearance.get("receipt_hash"),
                "reasons": thermodynamic_clearance.get("reasons", []),
            }
        if witness_row:
            digest_row["witness_ts"] = witness_row.get("ts")
            digest_row["witness_source"] = witness_row.get("source")
        _append_jsonl(_digest_path(state), digest_row)
        digest_rows.append(digest_row)
        done.add(tid)

    return {
        "truth_label": DIGEST_TRUTH_LABEL,
        "examined": examined,
        "journal_written": journal_written,
        "skipped_low_importance": skipped_low,
        "digest_rows": digest_rows,
    }


def latest_ambient_memory_context(
    *,
    state_dir: Path | str | None = None,
    max_rows: int = 8,
    max_chars: int = 900,
) -> str:
    """Compact prompt context from recently promoted ambient memories."""
    state = _state(state_dir)
    transcript_by_id = {
        _stable_transcript_id(r): r
        for r in _read_jsonl(_transcript_path(state))[-512:]
    }
    seen: set[str] = set()
    lines: list[str] = []
    for digest in reversed(_read_jsonl(_digest_path(state))):
        if digest.get("action") != "journal_written":
            continue
        tid = str(digest.get("source_transcript_id") or "")
        row = transcript_by_id.get(tid)
        if not row:
            continue
        seen.add(tid)
        imp = _importance_from_row(row)
        text = _compact(str(row.get("text") or row.get("text_preview") or ""), 180)
        lines.append(
            "ambient_memory "
            f"band={imp.get('importance_band')} route={_row_route_hint(row) or 'unknown'} "
            f"categories={','.join(str(x) for x in list(imp.get('categories') or [])[:4])} "
            f"text={text}"
        )
        if len(lines) >= int(max_rows):
            break
    if len(lines) < int(max_rows):
        for row in reversed(_read_jsonl(_transcript_path(state))[-512:]):
            tid = _stable_transcript_id(row)
            if tid in seen:
                continue
            imp = _importance_from_row(row)
            try:
                score = float(imp.get("importance_score", 0.0) or 0.0)
            except Exception:
                score = 0.0
            if score < DEFAULT_JOURNAL_THRESHOLD:
                continue
            seen.add(tid)
            text = _compact(str(row.get("text") or row.get("text_preview") or ""), 180)
            lines.append(
                "ambient_memory "
                f"band={imp.get('importance_band')} route={_row_route_hint(row) or 'unknown'} "
                f"categories={','.join(str(x) for x in list(imp.get('categories') or [])[:4])} "
                f"text={text}"
            )
            if len(lines) >= int(max_rows):
                break
    out = " | ".join(reversed(lines))
    if len(out) > max_chars:
        out = out[-max_chars:]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest and digest ambient room transcript text.")
    parser.add_argument("--text", default="", help="Transcript text. If empty and --digest-once is not set, stdin is read.")
    parser.add_argument("--stt-conf", type=float, default=0.0)
    parser.add_argument("--source", default="cli")
    parser.add_argument("--route", default="")
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--digest-once", action="store_true")
    parser.add_argument("--force-full-text", action="store_true")
    args = parser.parse_args(argv)

    state = Path(args.state_dir) if args.state_dir else None
    result: dict[str, Any] = {}
    text = args.text
    if not text and not args.digest_once:
        try:
            text = input()
        except EOFError:
            text = ""
    if text:
        result["ingest"] = ingest_transcript(
            text,
            stt_confidence=args.stt_conf,
            source=args.source,
            route_hint=args.route,
            state_dir=state,
            force_full_text=args.force_full_text,
        )
    if args.digest_once or text:
        result["digest"] = digest_once(state_dir=state)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


__all__ = [
    "DIGEST_LEDGER_NAME",
    "DIGEST_TRUTH_LABEL",
    "IMPORTANCE_TRUTH_LABEL",
    "TRANSCRIPT_LEDGER_NAME",
    "TRANSCRIPT_TRUTH_LABEL",
    "classify_ambient_importance",
    "digest_once",
    "ingest_transcript",
    "latest_ambient_memory_context",
]


if __name__ == "__main__":
    raise SystemExit(main())
