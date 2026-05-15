#!/usr/bin/env python3
"""swarm_phone_call_tracker.py — Phone Call Detection Organ (AG46, 2026-05-06)

Detects when the Architect is on a phone call and logs start/end times
to owner_body_events.jsonl and stigmergic_schedule.jsonl.

Detection heuristics:
  - Explicit declaration: "I'm on the phone", "I was on a call", "phone call"
  - Retroactive: "that was a phone conversation", "I forgot to mention the phone"
  - Pattern signals: phone-side speech fragments (short, non-directed, one-sided)

Covenant §7.10.1 compliance: all writes are append-only, timestamped,
truth-labeled OBSERVED. No inference about call content beyond duration.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:
    def append_line_locked(path: Path, line: str) -> None:
        with open(path, "a") as f:
            f.write(line)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_BODY_EVENTS = _STATE / "owner_body_events.jsonl"
_SCHEDULE = _STATE / "stigmergic_schedule.jsonl"

# ── Detection patterns ──────────────────────────────────────────────────────

# Explicit declaration: owner says they are/were on the phone
_PHONE_EXPLICIT_RE = re.compile(
    r"(?:"
    r"\bi(?:'m|\s+am|\s+was|\s+were)\s+on\s+(?:a\s+)?(?:the\s+)?phone\b"
    r"|\bthat\s+was\s+a\s+phone\s+(?:call|conversation)\b"
    r"|\bphone\s+(?:call|conversation)\b"
    r"|\bi\s+forgot\s+to\s+mention\s+(?:it\s+)?(?:that\s+)?i(?:'m|\s+am|\s+was)\s+on\s+(?:the\s+)?phone\b"
    r"|\bi\s+was\s+on\s+a\s+call\b"
    r"|\bjust\s+got\s+off\s+(?:a\s+)?(?:the\s+)?phone\b"
    r"|\bjust\s+finished\s+(?:a\s+)?(?:the\s+)?(?:phone\s+)?call\b"
    r"|\bi\s+(?:just\s+)?had\s+(?:a\s+)?[^.!?\n]{0,80}\b(?:meeting|conversation|call)\b[^.!?\n]{0,80}\bon\s+(?:a\s+)?(?:the\s+)?phone\b"
    r"|\bi\s+(?:just\s+)?found\s+out[^.!?\n]{0,80}\bon\s+(?:a\s+)?(?:the\s+)?phone\b"
    r"|\bended\s+the\s+call\b"
    r"|\bgot\s+(?:a\s+)?call\b"
    r"|\banswered\s+(?:a\s+)?(?:the\s+)?call\b"
    r")",
    re.IGNORECASE,
)

# Request to log/track phone calls
_PHONE_LOG_REQUEST_RE = re.compile(
    r"(?:"
    r"\bwrite\s+(?:it\s+)?(?:on|to|in)\s+(?:a\s+)?(?:the\s+)?schedule\b"
    r"|\bdetect\s+(?:the\s+)?phone\s+(?:call|conversation)\b"
    r"|\btrack\s+(?:my\s+)?phone\s+(?:calls?|conversations?)\b"
    r"|\blog\s+(?:the\s+)?(?:phone\s+)?call\b"
    r"|\bkeep\s+(?:a\s+)?track\b"
    r"|\brecord\s+(?:the\s+)?(?:phone\s+)?call\b"
    r")",
    re.IGNORECASE,
)

_CALL_END_RE = re.compile(
    r"(?:"
    r"\bjust\s+got\s+off\s+(?:a\s+)?(?:the\s+)?phone\b"
    r"|\b(?:phone\s+call|call|phone)\s+ended\b"
    r"|\boff\s+(?:the\s+)?phone\s+now\b"
    r"|\bjust\s+finished\s+(?:a\s+)?(?:the\s+)?(?:phone\s+)?call\b"
    r"|\bfinished\s+(?:the\s+)?(?:call|phone\s+call)\b"
    r"|\bended\s+the\s+call\b"
    r"|\b(?:hung|hang|hanged)\s+up\b"
    r")",
    re.IGNORECASE,
)


def _append_jsonl(path: Path, row: dict) -> None:
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")


def _mark_phone_call_as_ambient_audio() -> None:
    """Tell the media ingress gate that room STT is phone background now."""
    try:
        from System.swarm_media_ingress_gate import record_ambient_media_context

        record_ambient_media_context(
            source="phone_call_background",
            note=(
                "Phone call is active. Phone-side or speakerphone speech is "
                "background audio unless Alice is directly addressed, George's "
                "voice is confirmed, or an explicit owner request is present."
            ),
            ttl_s=3 * 3600.0,
        )
    except Exception:
        pass


def _clear_phone_call_ambient_audio() -> None:
    """Clear phone ambient context when the call ends."""
    try:
        from System.swarm_media_ingress_gate import clear_ambient_media_context

        clear_ambient_media_context(
            source_prefix="phone_call",
            reason="phone_call_end",
        )
    except Exception:
        pass


def is_phone_declaration(text: str) -> bool:
    """True if the turn explicitly declares a phone call."""
    return bool(_PHONE_EXPLICIT_RE.search(text or ""))


def is_phone_log_request(text: str) -> bool:
    """True if the turn requests phone call logging."""
    return bool(_PHONE_LOG_REQUEST_RE.search(text or ""))


def _local_time_str() -> str:
    """Return local time as human-readable string."""
    try:
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(time.time())


def _write_phone_event(
    *,
    event_type: str,  # "phone_call_start" | "phone_call_end" | "phone_call_retroactive"
    note: str,
    ts: Optional[float] = None,
    call_id: Optional[str] = None,
    source: str = "talk_to_alice:phone_tracker",
) -> str:
    """Append a phone call event to owner_body_events.jsonl. Returns event_id."""
    ts = ts or time.time()
    event_id = call_id or str(uuid.uuid4())[:12]
    row = {
        "ts": ts,
        "event_id": event_id,
        "kind": "OWNER_BODY_EVENT",
        "event_type": event_type,
        "note": note,
        "status": "DONE",
        "source": source,
        "truth_label": "OBSERVED",
    }
    try:
        _append_jsonl(_BODY_EVENTS, row)
    except Exception as e:
        import sys
        print(f"[phone_tracker] write failed: {e}", file=sys.stderr)
    return event_id


def _write_schedule_entry(note: str, ts: Optional[float] = None) -> None:
    """Append a human-readable phone call note to the stigmergic schedule."""
    ts = ts or time.time()
    row = {
        "ts": ts,
        "text": note,
        "source": "alice:phone_call_tracker",
        "truth_label": "OBSERVED",
        "kind": "phone_call_log",
    }
    try:
        _append_jsonl(_SCHEDULE, row)
    except Exception:
        pass


def handle_phone_declaration(
    text: str,
    *,
    stt_conf: float = 0.0,
    prior_media_turns: int = 0,
) -> Tuple[Optional[str], Optional[str]]:
    """Main entry point for the talk widget.

    Returns (event_type, alice_reply) or (None, None) if not a phone event.
    
    Call this BEFORE the main LLM inference if a phone event is detected.
    """
    if not is_phone_declaration(text):
        return None, None
    if _CALL_END_RE.search(text or ""):
        return None, None

    ts = time.time()
    local_time = _local_time_str()

    # Was there recent media gate suppression? Those were phone-side audio.
    retroactive = bool(
        re.search(
            r"forgot\s+to\s+mention|just\s+heard|that\s+was\s+a|"
            r"\bi\s+(?:just\s+)?had\s+(?:a\s+)?[^.!?\n]{0,80}\b(?:meeting|conversation|call)\b[^.!?\n]{0,80}\bon\s+(?:a\s+)?(?:the\s+)?phone\b|"
            r"\bi\s+(?:just\s+)?found\s+out[^.!?\n]{0,80}\bon\s+(?:a\s+)?(?:the\s+)?phone\b",
            text,
            re.IGNORECASE,
        )
    )

    wants_log = is_phone_log_request(text)

    if retroactive:
        # Owner just told Alice that earlier audio was phone call
        note = f"{local_time} — George was on a phone call (retroactively confirmed). Prior STT fragments were phone audio, not George speaking to Alice."
        event_type = "phone_call_retroactive"
        _write_phone_event(event_type=event_type, note=note, ts=ts)
        _write_schedule_entry(note, ts=ts)
        alice_reply = f"Logged: phone call ended around {local_time[:16]}."
    else:
        # Active declaration
        note = f"{local_time} — George is on a phone call."
        event_type = "phone_call_active"
        _write_phone_event(event_type=event_type, note=note, ts=ts)
        _write_schedule_entry(note, ts=ts)
        _mark_phone_call_as_ambient_audio()
        if wants_log:
            alice_reply = f"Phone call logged at {local_time[:16]}. I will keep listening and log when it ends — just say 'call ended' or 'I'm off the phone.'"
        else:
            alice_reply = None  # Let the main LLM handle it

    return event_type, alice_reply


def handle_call_end(text: str, *, call_start_ts: Optional[float] = None) -> Optional[str]:
    """Detect and log call end. Returns alice_reply or None."""
    if not _CALL_END_RE.search(text or ""):
        return None

    ts = time.time()
    local_time = _local_time_str()
    duration_note = ""
    if call_start_ts:
        mins = int((ts - call_start_ts) / 60)
        duration_note = f" (~{mins} min)"

    note = f"{local_time} — Phone call ended{duration_note}."
    _write_phone_event(event_type="phone_call_end", note=note, ts=ts)
    _write_schedule_entry(note, ts=ts)
    _clear_phone_call_ambient_audio()
    return f"Call ended. Logged at {local_time[:16]}{duration_note}."


def format_phone_log_for_prompt(max_rows: int = 5) -> str:
    """Return recent phone call events for Alice's system prompt context."""
    try:
        rows = []
        if _BODY_EVENTS.exists():
            for line in _BODY_EVENTS.read_text().strip().splitlines():
                try:
                    r = json.loads(line)
                    if r.get("event_type", "").startswith("phone_call"):
                        rows.append(r)
                except Exception:
                    pass
        if not rows:
            return ""
        recent = rows[-max_rows:]
        parts = ["PHONE CALL LOG (owner body events, append-only):"]
        for r in recent:
            parts.append(f"  {r.get('note', '')[:120]}")
        return "\n".join(parts)
    except Exception:
        return ""


__all__ = [
    "is_phone_declaration",
    "is_phone_log_request",
    "handle_phone_declaration",
    "handle_call_end",
    "format_phone_log_for_prompt",
]
