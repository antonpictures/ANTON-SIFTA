"""
System/swarm_global_chat_view_model.py
══════════════════════════════════════
Round 56 (2026-05-27) — Pure view-model for Alice's global chat.

This module is the swarm consensus from §ROUND 55 / §55.1 / §55.GROK /
§ROUND 58 (peer Claude + Grok subsections). All four doctors converged
on: land a PURE-Python view-model first, with no Qt, that takes ledger
rows in and produces normalized chat rows out. The Qt renderer is the
next round; this is the foundation that makes it testable.

Inputs (read-only from the append-only ledgers):
  - .sifta_state/alice_conversation.jsonl
      Row shape (current production):
        {
          "event_id": "<8-hex>",
          "ts": {"physical_pt": <float>, "logical": <int>, "agent_id": "ALICE_M5"},
          "payload": {"ts": <float>, "role": "user"|"alice"|"system"|"owner",
                       "text": "<str>", ...optional...},
          "prev_hash": "<sha>",
          "this_hash": "<sha>",
        }

  - .sifta_state/agent_arm_receipts.jsonl (optional, for receipt chip enrichment)

Outputs (a list of ChatRow records, newest-last for display order):

    ChatRow(
        message_id: str,            # stable hash, safe to use as a Qt object name
        ts: float,                  # unix timestamp from payload (real time)
        speaker: str,               # "owner" | "alice" | "system" | "arm:<arm_id>"
        modality: str,              # "typed" | "spoken" | "system" | "unknown"
        kind: str,                  # "owner_turn" | "alice_turn" | "system_note"
                                    # | "arm_output" | "silence" | "field_failure"
        text_preview: str,          # first ~200 chars, single-line
        full_text: str,             # whole body
        text_lines: int,            # line count of full_text
        collapse_default: bool,     # True when text is long enough to warrant
                                    # a "show more" affordance
        dedupe_key: str,            # speaker | rounded-ts | text-hash[:12]
        receipt_refs: tuple[str, ...],   # receipt ids referenced inside text
        severity: str,              # "info" | "ok" | "warn" | "error"
    )

Pure stdlib. No PyQt. Never raises out. Tested by
tests/test_swarm_global_chat_view_model.py.

Doctrine touchpoints:
  - Covenant §6 (effector immunity): receipts are first-class metadata,
    not loose text. The view-model surfaces receipt_refs explicitly so
    the renderer can show them as chips.
  - Covenant §7.6 / §7.10.1 (one Alice, direct mode): the speaker field
    is the truth of who composed the row. Arm outputs render as
    speaker="arm:<id>", never as "alice".
  - Round 50 (silence narration): silence rows are classified with
    kind="silence" so the renderer can style them distinctly.
  - Round 47/51 (no robot gates): FIELD_FAILURE strings get
    kind="field_failure" + severity="error" but are never hidden.
  - §ROUND 58 (peer Claude): dedupe_key + message_id + collapse_default
    + receipts-as-metadata are all here.
  - §ROUND 58 (Grok): receipt-driven duplicate suppression (hash of text
    + speaker + ts bucket, exact match collapsed).

Public surface
══════════════
    @dataclass ChatRow
    load_recent_view(state_dir, *, max_n=200, dedupe_window_s=2.0,
                     collapse_lines_threshold=8,
                     collapse_chars_threshold=600) -> list[ChatRow]
    classify_modality(payload) -> str
    extract_receipt_refs(text) -> tuple[str, ...]
    dedupe_key_for(speaker, ts, text) -> str
    message_id_for(event_id, payload_ts, text) -> str

Constants
═════════
    PREVIEW_CHAR_LIMIT = 200
    DEFAULT_DEDUPE_WINDOW_S = 2.0
    DEFAULT_COLLAPSE_LINES = 8
    DEFAULT_COLLAPSE_CHARS = 600
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


TRUTH_LABEL = "GLOBAL_CHAT_VIEW_V1"

PREVIEW_CHAR_LIMIT = 200
DEFAULT_DEDUPE_WINDOW_S = 2.0
DEFAULT_COLLAPSE_LINES = 8
DEFAULT_COLLAPSE_CHARS = 600
DEFAULT_VISIBLE_PARAGRAPHS = 4


# ─── Data class ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChatRow:
    message_id: str
    ts: float
    speaker: str
    modality: str
    kind: str
    text_preview: str
    full_text: str
    text_lines: int
    collapse_default: bool
    dedupe_key: str
    receipt_refs: tuple[str, ...] = ()
    severity: str = "info"


@dataclass(frozen=True)
class CollapsedTextPreview:
    visible_text: str
    hidden_text: str
    hidden_paragraph_count: int
    is_collapsed: bool


# ─── Helpers ────────────────────────────────────────────────────────────────


_SILENT_TEXT_RE = re.compile(r"^\(silent(?::\s*[^)]+)?\)\s*$", re.IGNORECASE)
_FIELD_FAILURE_RE = re.compile(r"^FIELD_FAILURE\s*:", re.IGNORECASE)
_RECEIPT_REF_RES = (
    re.compile(r"\br\d+(?:-[a-z0-9]+){1,4}\b", re.IGNORECASE),  # peer Claude style (r58-src-e04...)
    re.compile(r"\bcortex_pre_exec_[0-9a-f]{8,}\b"),     # cortex pre-exec receipts
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),  # uuid
    re.compile(r"\barm-[a-z0-9-]{4,}\b", re.IGNORECASE),
    re.compile(r"\breceipt[_\s:=]+([0-9a-f]{6,})\b", re.IGNORECASE),
)


def _hash12(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def classify_modality(payload: dict[str, Any]) -> str:
    """Best-effort modality classification from a conversation payload.

    Reads any of the existing modality markers SIFTA's widget writes:
      - payload.modality   ("TYPED" / "SPOKEN" / "SYSTEM")
      - payload.source     ("typed" / "voice")
      - payload.typed_turn (bool)
      - presence of payload.stt_conf (low conf → spoken)
    """
    explicit = str(payload.get("modality") or "").strip().lower()
    if explicit in ("typed", "spoken", "system"):
        return explicit
    source = str(payload.get("source") or "").strip().lower()
    if source in ("typed", "type", "keyboard"):
        return "typed"
    if source in ("voice", "spoken", "stt", "mic"):
        return "spoken"
    if source in ("system", "auto", "boot"):
        return "system"
    if "typed_turn" in payload:
        return "typed" if bool(payload["typed_turn"]) else "spoken"
    if "stt_conf" in payload and payload["stt_conf"] is not None:
        return "spoken"
    role = str(payload.get("role") or "").lower()
    if role in ("system",):
        return "system"
    return "unknown"


def extract_receipt_refs(text: str) -> tuple[str, ...]:
    """Find receipt id references inside a chat text body. Returns a stable,
    deduplicated tuple of unique ids in first-seen order."""
    if not text:
        return ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for pat in _RECEIPT_REF_RES:
        for m in pat.findall(text):
            # findall returns a string for non-grouped patterns and the
            # group for grouped patterns; normalize.
            ref = m if isinstance(m, str) else "".join(p for p in m if p)
            if ref and ref not in seen_set:
                seen_set.add(ref)
                seen.append(ref)
    return tuple(seen)


def dedupe_key_for(speaker: str, ts: float, text: str,
                   *, window_s: float = DEFAULT_DEDUPE_WINDOW_S) -> str:
    """Stable dedupe key: speaker | bucketed-ts | text-hash[:12]."""
    try:
        bucket = int(float(ts) // max(0.001, float(window_s)))
    except (TypeError, ValueError):
        bucket = 0
    text_hash = _hash12((text or "").strip())
    return f"{speaker}|{bucket}|{text_hash}"


def message_id_for(event_id: str, payload_ts: Any, text: str) -> str:
    """Stable per-row id usable as a Qt object name.

    Priority:
      1. event_id from the conversation row (production rows have these)
      2. hash(payload_ts + first 80 chars of text)  (for legacy rows)
    """
    ev = (event_id or "").strip()
    if ev:
        return f"msg_{ev}"
    digest = _hash12(f"{payload_ts}|{(text or '')[:80]}")
    return f"msg_{digest}"


def _normalize_speaker(role: str, payload: dict[str, Any]) -> str:
    r = (role or "").strip().lower()
    arm = str(payload.get("arm_id") or payload.get("arm") or "").strip().lower()
    if r in ("alice", "assistant"):
        return "alice"
    if r in ("user", "owner", "george", "ioan", "architect"):
        return "owner"
    if r in ("system",):
        return "system"
    if r in ("arm",) or arm:
        return f"arm:{arm}" if arm else "arm:unknown"
    if r:
        return r
    return "unknown"


def _classify_kind_and_severity(speaker: str, text: str) -> tuple[str, str]:
    """Return (kind, severity) from speaker + text shape."""
    body = (text or "").strip()
    if speaker == "alice" and _SILENT_TEXT_RE.match(body):
        return "silence", "warn"
    if _FIELD_FAILURE_RE.match(body):
        return "field_failure", "error"
    if speaker == "owner":
        return "owner_turn", "info"
    if speaker == "alice":
        return "alice_turn", "info"
    if speaker == "system":
        return "system_note", "info"
    if speaker.startswith("arm:"):
        return "arm_output", "info"
    return "system_note", "info"


def _preview_of(text: str, *, limit: int = PREVIEW_CHAR_LIMIT) -> str:
    """Single-line preview for the message header."""
    if not text:
        return ""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: max(1, limit - 1)] + "…"


def collapse_text_after_paragraphs(
    text: str,
    *,
    max_paragraphs: int = DEFAULT_VISIBLE_PARAGRAPHS,
) -> CollapsedTextPreview:
    """Split a long Alice answer into preview + hidden continuation.

    Paragraphs are blank-line separated. The full text remains in the ledger;
    this only gives the Qt renderer a bounded visible preview so a long answer
    cannot visually swallow the chat surface.
    """
    body = str(text or "").strip()
    if not body:
        return CollapsedTextPreview("", "", 0, False)
    try:
        max_p = max(1, int(max_paragraphs))
    except (TypeError, ValueError):
        max_p = DEFAULT_VISIBLE_PARAGRAPHS
    paragraphs = [
        p.strip()
        for p in re.split(r"(?:\r?\n\s*){2,}", body)
        if p.strip()
    ]
    if len(paragraphs) <= max_p:
        return CollapsedTextPreview(body, "", 0, False)
    visible = "\n\n".join(paragraphs[:max_p])
    hidden = "\n\n".join(paragraphs[max_p:])
    return CollapsedTextPreview(
        visible_text=visible,
        hidden_text=hidden,
        hidden_paragraph_count=len(paragraphs) - max_p,
        is_collapsed=True,
    )


def _iter_jsonl_tail(path: Path, *, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_lines:]


def _unwrap_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The current production rows are wrapped:
       {event_id, ts: {...}, payload: {role, text, ts, ...}, prev_hash, this_hash}.
    Legacy rows are flat:
       {role, text, ts, ...}.
    Return a normalized dict carrying event_id (or '') + payload fields.
    """
    if not isinstance(row, dict):
        return None
    payload = row.get("payload")
    event_id = str(row.get("event_id") or "")
    if isinstance(payload, dict):
        merged = dict(payload)
        merged.setdefault("event_id", event_id)
        return merged
    if "role" in row or "text" in row:
        flat = dict(row)
        flat.setdefault("event_id", event_id)
        return flat
    return None


def _payload_ts(payload: dict[str, Any]) -> Optional[float]:
    """Resolve the real wall-clock ts from a payload.

    payload.ts can be a float (legacy + many current payloads)
    or sometimes the outer row's ts object {"physical_pt": float, ...};
    we accept either."""
    raw = payload.get("ts")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        for k in ("physical_pt", "wall", "unix"):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


# ─── Public ──────────────────────────────────────────────────────────────────


def load_recent_view(
    state_dir: Path | str,
    *,
    max_n: int = 200,
    dedupe_window_s: float = DEFAULT_DEDUPE_WINDOW_S,
    collapse_lines_threshold: int = DEFAULT_COLLAPSE_LINES,
    collapse_chars_threshold: int = DEFAULT_COLLAPSE_CHARS,
    conversation_filename: str = "alice_conversation.jsonl",
) -> list[ChatRow]:
    """
    Read the conversation ledger tail and return up to `max_n` normalized
    ChatRow records, oldest-first (display order — newest at bottom).

    Adjacent rows with the same `dedupe_key` are collapsed to one — the
    later row wins (so streaming partials get superseded by their final
    form when the widget writes both).
    """
    sd = Path(state_dir)
    raw_rows = _iter_jsonl_tail(
        sd / conversation_filename,
        max_lines=max(1, int(max_n)) * 4,  # over-read so dedupe shrinks
    )

    interim: list[ChatRow] = []
    for raw in raw_rows:
        payload = _unwrap_row(raw)
        if payload is None:
            continue

        text = str(payload.get("text") or "").strip()
        if not text:
            # silent boundary markers and empty rows — skip; the silence
            # row that matters is "(silent: <reason>)" which has text.
            continue

        ts = _payload_ts(payload) or 0.0
        role = str(payload.get("role") or "")
        speaker = _normalize_speaker(role, payload)
        modality = classify_modality(payload)
        kind, severity = _classify_kind_and_severity(speaker, text)
        text_lines = text.count("\n") + 1
        collapse_default = (
            text_lines > collapse_lines_threshold
            or len(text) > collapse_chars_threshold
        )
        dedupe_key = dedupe_key_for(speaker, ts, text, window_s=dedupe_window_s)
        msg_id = message_id_for(
            str(payload.get("event_id") or ""),
            ts,
            text,
        )
        receipt_refs = extract_receipt_refs(text)

        interim.append(ChatRow(
            message_id=msg_id,
            ts=ts,
            speaker=speaker,
            modality=modality,
            kind=kind,
            text_preview=_preview_of(text),
            full_text=text,
            text_lines=text_lines,
            collapse_default=collapse_default,
            dedupe_key=dedupe_key,
            receipt_refs=receipt_refs,
            severity=severity,
        ))

    # ── Dedupe: collapse adjacent rows that share the same dedupe_key.
    # We walk the list in original order and keep only the LAST row in
    # each consecutive same-key run. Non-adjacent same-key rows are NOT
    # collapsed (those are honest re-occurrences).
    deduped: list[ChatRow] = []
    for row in interim:
        if deduped and deduped[-1].dedupe_key == row.dedupe_key:
            deduped[-1] = row
            continue
        deduped.append(row)

    # ── Cap to max_n newest rows (interim list is already oldest-first).
    if len(deduped) > max_n:
        deduped = deduped[-max_n:]

    return deduped


__all__ = [
    "TRUTH_LABEL",
    "PREVIEW_CHAR_LIMIT",
    "DEFAULT_DEDUPE_WINDOW_S",
    "DEFAULT_COLLAPSE_LINES",
    "DEFAULT_COLLAPSE_CHARS",
    "DEFAULT_VISIBLE_PARAGRAPHS",
    "ChatRow",
    "CollapsedTextPreview",
    "collapse_text_after_paragraphs",
    "classify_modality",
    "extract_receipt_refs",
    "dedupe_key_for",
    "message_id_for",
    "load_recent_view",
]
