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

# ── Cowork 2026-05-20 — Phase 1 extension: dedicated phone-call ledger ──
# Reason: AG46's tracker writes to owner_body_events.jsonl (one row per
# event_type) and stigmergic_schedule.jsonl (one row per event). Neither
# ledger LINKS the start row to its end row, so duration is not auditable
# without scanning the whole tail. The new phone_call_events.jsonl
# ledger writes one row per CLOSED call with call_id / start_ts / end_ts /
# duration / other_party. Plus _active_call.json keeps the live call_id
# between turns so handle_call_end can look up the start.
_CALL_EVENTS = _STATE / "phone_call_events.jsonl"
_ACTIVE_CALL = _STATE / "_active_phone_call.json"

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

    # ── Cowork 2026-05-20 — Phase 1: extract other party from this turn ──
    party = extract_other_party(text)
    party_suffix = f" with {party['party_name']}" if party.get("party_name") else ""

    if retroactive:
        # Owner just told Alice that earlier audio was phone call
        note = (
            f"{local_time} — George was on a phone call{party_suffix} "
            "(retroactively confirmed). Prior STT fragments were phone audio, "
            "not George speaking to Alice."
        )
        event_type = "phone_call_retroactive"
        event_id = _write_phone_event(event_type=event_type, note=note, ts=ts)
        _write_schedule_entry(note, ts=ts)
        # No active state needed for retroactive — call is already over.
        _append_call_event_row({
            "ts": ts,
            "call_id": event_id,
            "kind": "PHONE_CALL_EVENT",
            "phase": "retroactive_close",
            "started_ts": None,
            "ended_ts": ts,
            "duration_min": None,
            "other_party": party.get("party_name", ""),
            "other_party_confidence": party.get("confidence", 0.0),
            "owner": "George",
            "node_serial": "GTH4921YP3",
            "source": "swarm_phone_call_tracker.handle_phone_declaration(retroactive)",
            "truth_label": "OBSERVED",
        })
        alice_reply = f"Logged: phone call{party_suffix} ended around {local_time[:16]}."
    else:
        # Active declaration — start a new call session
        note = f"{local_time} — George is on a phone call{party_suffix}."
        event_type = "phone_call_active"
        event_id = _write_phone_event(event_type=event_type, note=note, ts=ts)
        _write_schedule_entry(note, ts=ts)
        _mark_phone_call_as_ambient_audio()
        # Phase 1: write the live call_id to _active_phone_call.json so
        # handle_call_end can link to this start row.
        _write_active_call({
            "call_id": event_id,
            "started_ts": ts,
            "started_local": local_time,
            "other_party": party.get("party_name", ""),
            "other_party_confidence": party.get("confidence", 0.0),
            "other_party_raw_match": party.get("raw_match", ""),
            "declaration_text_excerpt": (text or "")[:200],
        })
        if wants_log:
            alice_reply = (
                f"Phone call{party_suffix} logged at {local_time[:16]}. "
                "I will stay quiet during the call and log when it ends — "
                "just say 'call ended' or 'I'm off the phone.'"
            )
        else:
            alice_reply = None  # Let the main LLM handle it

    return event_type, alice_reply


def handle_call_end(text: str, *, call_start_ts: Optional[float] = None) -> Optional[str]:
    """Detect and log call end. Returns alice_reply or None.

    Cowork 2026-05-20 Phase 1: look up the live call from _active_phone_call.json
    if no call_start_ts is passed. Write a closed-call row to phone_call_events.jsonl
    with full metadata (call_id, started_ts, ended_ts, duration_min, other_party).
    """
    if not _CALL_END_RE.search(text or ""):
        return None

    ts = time.time()
    local_time = _local_time_str()

    # Phase 1 — pull active call state if it exists
    active = _read_active_call()
    if not call_start_ts and active.get("started_ts"):
        try:
            call_start_ts = float(active["started_ts"])
        except (TypeError, ValueError):
            call_start_ts = None

    duration_min = None
    duration_note = ""
    if call_start_ts:
        duration_min = round((ts - call_start_ts) / 60.0, 2)
        duration_note = f" (~{int(duration_min)} min)"

    other_party = active.get("other_party", "") if active else ""
    party_suffix = f" with {other_party}" if other_party else ""

    note = f"{local_time} — Phone call{party_suffix} ended{duration_note}."
    _write_phone_event(event_type="phone_call_end", note=note, ts=ts)
    _write_schedule_entry(note, ts=ts)
    _clear_phone_call_ambient_audio()

    # Phase 1 — write the closed-call event row with full linkage
    _append_call_event_row({
        "ts": ts,
        "call_id": active.get("call_id") if active else None,
        "kind": "PHONE_CALL_EVENT",
        "phase": "closed",
        "started_ts": call_start_ts,
        "started_local": active.get("started_local") if active else None,
        "ended_ts": ts,
        "ended_local": local_time,
        "duration_min": duration_min,
        "other_party": other_party,
        "other_party_confidence": active.get("other_party_confidence", 0.0) if active else 0.0,
        "other_party_raw_match": active.get("other_party_raw_match", "") if active else "",
        "declaration_text_excerpt": active.get("declaration_text_excerpt", "") if active else "",
        "end_text_excerpt": (text or "")[:200],
        "owner": "George",
        "node_serial": "GTH4921YP3",
        "source": "swarm_phone_call_tracker.handle_call_end",
        "truth_label": "OBSERVED",
    })

    # Phase 1 — clear the active call state so the next call starts fresh
    _clear_active_call()

    return f"Call ended{party_suffix}. Logged at {local_time[:16]}{duration_note}."


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


# ── Cowork 2026-05-20 — Phase 1 extension: other-party extraction ────────
# Pull "Mr. Versace", "Vitaliy", "my friend Vitaliy", "Mr. Vitaliy Versace"
# out of the owner's declaration so the call event names who was on the
# other end. Regex-only — no NLP, no LLM. Falls back to "unknown" if nothing
# clean matches.

# Capture group is the party name.
# NOTE: We do NOT use re.IGNORECASE on the patterns because the name itself
# must START with an actual capital letter (otherwise "on", "me", "you" get
# captured). Trigger words (with / talking / called) are spelled in two
# cases or wrapped in [Tt] groups to keep the trigger flexible while
# keeping the name part case-strict.
_OTHER_PARTY_PATTERNS: list[re.Pattern[str]] = [
    # "on a phone with Mr. Vitaliy Versace" / "on the phone with my friend Vitaliy"
    re.compile(
        r"\b[Oo]n\s+(?:a|the)\s+phone\s+with\s+"
        r"(?:my\s+(?:friend|cousin|brother|sister|dad|mom|wife|husband|boss|partner)\s+)?"
        r"((?:(?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+)?"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})",
    ),
    # "talking to Mr. Versace" / "speaking with my friend Vitaliy"
    re.compile(
        r"\b(?:[Tt]alking|[Ss]peaking|[Cc]hatting)\s+(?:to|with)\s+"
        r"(?:my\s+(?:friend|cousin|brother|sister|dad|mom|wife|husband|boss|partner)\s+)?"
        r"((?:(?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+)?"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})",
    ),
    # "called <Name>" — must be a capitalized name, no pronouns
    re.compile(
        r"\b(?:[Cc]alled|[Pp]honed|[Rr]ang)\s+"
        r"((?:(?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+)?"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})",
    ),
    # "That was Mr. Versace on a phone"
    re.compile(
        r"\b[Tt]hat\s+was\s+"
        r"((?:(?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+)?"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})"
        r"\s+on\s+(?:a|the)\s+phone\b",
    ),
    # "got off the phone with X" / "off the phone with my friend Vitaliy"
    re.compile(
        r"\boff\s+(?:a|the)\s+phone\s+with\s+"
        r"(?:my\s+(?:friend|cousin|brother|sister|dad|mom|wife|husband|boss|partner)\s+)?"
        r"((?:(?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+)?"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})",
    ),
    # Standalone "Mr. <Name>" / "Mrs. <Name>" near phone context
    re.compile(
        r"\b((?:[Mm]r|[Mm]rs|[Mm]s|[Dd]r|[Mm]iss|[Ss]ir|[Mm]adam)\.?\s+"
        r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})",
    ),
]

# Common phone-call words that should NOT be captured as a party name.
# Includes vague-reference words like "someone" / "this guy" — those mean
# George didn't actually name the party in that utterance.
_PARTY_BLACKLIST = {
    "phone", "call", "phone call", "alice", "george", "ioan",
    "george anton", "ioan george", "ioan george anton",
    "the phone", "a phone", "speaker phone", "cell phone",
    "mobile", "the call", "a call", "voice mail", "voicemail",
    "someone", "somebody", "anyone", "anybody", "no one", "nobody",
    "this guy", "that guy", "the guy", "this person", "that person",
    "my friend", "my cousin", "my dad", "my mom", "my wife", "my husband",
}


# Words that signal the captured name has spilled into surrounding context.
# If a captured name ENDS with any of these, trim them off.
_NAME_TAIL_NOISE = (
    " on speaker phone", " on speaker", " on the phone", " on phone",
    " on a phone", " on cell", " on cellphone", " on call",
    " in the room", " at the door", " at home", " at work",
    " from work", " from home",
    " on", " in", " at", " from", " with", " for", " to", " by",
    " is", " was", " are", " and", " but", " or",
)

# Words that, if appearing as the LAST word of a captured name, indicate
# the regex spilled into a verb/preposition. Strip them.
_LAST_WORD_NOISE = {
    "on", "in", "at", "from", "with", "for", "to", "by",
    "is", "was", "are", "and", "but", "or", "the", "a", "an",
    "speaker", "phone", "cell", "call", "now", "today",
    "calling", "called", "said", "told", "asked",
    "right", "just", "still", "yet", "already", "soon", "later",
    "yesterday", "tomorrow", "tonight", "earlier",
    "about", "around", "regarding",
    "me", "him", "her", "us", "them",  # pronouns shouldn't end a name
}


def _clean_party_name(name: str) -> str:
    """Strip trailing prepositions / phone-context words from a captured name."""
    if not name:
        return name
    s = name.strip().rstrip(".,;:!?'\" ")
    # First: strip multi-word noise tails (case-insensitive)
    low = s.lower()
    for tail in _NAME_TAIL_NOISE:
        if low.endswith(tail):
            s = s[: -len(tail)].rstrip(".,;:!?'\" ")
            low = s.lower()
    # Second: strip single trailing noise words, possibly multiple
    parts = s.split()
    while parts and parts[-1].lower().rstrip(".,;:!?'\" ") in _LAST_WORD_NOISE:
        parts.pop()
    return " ".join(parts).strip()


def extract_other_party(text: str) -> dict:
    """Return {party_name, confidence, raw_match, pattern_idx} for the other party.

    Confidence:
      0.9  — explicit "with X" pattern matched
      0.7  — "talking to X" / "speaking with X" pattern
      0.6  — "called X" / "X called me"
      0.5  — "That was X on a phone"
      0.4  — standalone "Mr. X" found in context
      0.0  — nothing matched
    """
    if not text:
        return {"party_name": "", "confidence": 0.0, "raw_match": "", "pattern_idx": -1}
    confidences = [0.9, 0.7, 0.6, 0.5, 0.4]
    for idx, pat in enumerate(_OTHER_PARTY_PATTERNS):
        m = pat.search(text)
        if not m:
            continue
        candidate_raw = m.group(1).strip().rstrip(".,;:!?")
        candidate = _clean_party_name(candidate_raw)
        if not candidate:
            continue
        # Reject blacklisted phrases
        if candidate.lower() in _PARTY_BLACKLIST:
            continue
        # Reject pure noise like "I I" or single common pronouns
        if candidate.lower() in {"i", "me", "you", "he", "she", "we", "they", "him", "her", "us", "them"}:
            continue
        return {
            "party_name": candidate,
            "confidence": confidences[idx] if idx < len(confidences) else 0.3,
            "raw_match": m.group(0),
            "pattern_idx": idx,
        }
    return {"party_name": "", "confidence": 0.0, "raw_match": "", "pattern_idx": -1}


# ── Cowork 2026-05-20 — Phase 1 extension: active call state file ────────
# Stash the live call's call_id + started_ts + other_party so handle_call_end
# can compute duration and write the closed-call row to phone_call_events.

def _read_active_call() -> dict:
    if not _ACTIVE_CALL.exists():
        return {}
    try:
        return json.loads(_ACTIVE_CALL.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_active_call(row: dict) -> None:
    try:
        _ACTIVE_CALL.parent.mkdir(parents=True, exist_ok=True)
        _ACTIVE_CALL.write_text(
            json.dumps(row, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def _clear_active_call() -> None:
    try:
        if _ACTIVE_CALL.exists():
            _ACTIVE_CALL.unlink()
    except OSError:
        pass


def _append_call_event_row(row: dict) -> None:
    """Append a closed-call event to phone_call_events.jsonl."""
    try:
        _CALL_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        _append_jsonl(_CALL_EVENTS, row)
    except Exception:
        pass


# ── Cowork 2026-05-20 — phone_call_active query for talk widget gating ──
# Reason: George's Versace call (May 20 ~09:55 PDT) hit the tracker's regex
# but the LLM kept generating florid help-desk responses through the call
# because nothing in the speech path checked "are we IN a call right now?"
# This query lets the talk widget read state from the most-recent
# unended phone_call_* row in owner_body_events.jsonl (with a TTL).
#
# Doctrine: stay quiet during owner phone calls unless directly addressed
# by name. Logged calls already live in the ledger; that's the receipt.

_DEFAULT_CALL_TTL_S = 3 * 3600.0  # 3 hours — matches media_ingress_gate TTL


def is_phone_call_active(
    *,
    state_dir: Optional[Path] = None,
    ttl_s: float = _DEFAULT_CALL_TTL_S,
    now: Optional[float] = None,
) -> bool:
    """Return True if the most-recent phone_call_* row says we're still on a call.

    Rules:
      - Walk owner_body_events.jsonl from the END backwards.
      - First phone_call_* row wins.
      - If it's phone_call_active or phone_call_retroactive AND fresh (<ttl_s old),
        return True.
      - If it's phone_call_end, return False.
      - If no phone_call_* row found within the file's tail, return False.
      - Audit/correction rows are skipped entirely.
    """
    path = (state_dir or _STATE) / "owner_body_events.jsonl"
    if not path.exists():
        return False
    now = float(now or time.time())
    try:
        # Read only the tail — phone events are sparse, no need to scan all.
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 256 * 1024))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        et = str(row.get("event_type") or "")
        if not et.startswith("phone_call_"):
            continue
        # Skip audit / correction rows — they are not real owner events
        if "correction" in et or "audit" in et or "dry_run" in et:
            continue
        if et in ("phone_call_end",):
            return False
        if et in ("phone_call_active", "phone_call_retroactive"):
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            if ts <= 0:
                continue
            if (now - ts) > ttl_s:
                return False  # stale, assume ended
            return True
    return False


def phone_call_active_state(
    *,
    state_dir: Optional[Path] = None,
    ttl_s: float = _DEFAULT_CALL_TTL_S,
    now: Optional[float] = None,
) -> dict:
    """Detailed query: returns the active row + age, or {} if not in a call."""
    path = (state_dir or _STATE) / "owner_body_events.jsonl"
    if not path.exists():
        return {}
    now = float(now or time.time())
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 256 * 1024))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return {}
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        et = str(row.get("event_type") or "")
        if not et.startswith("phone_call_"):
            continue
        if "correction" in et or "audit" in et or "dry_run" in et:
            continue
        if et == "phone_call_end":
            return {}
        if et in ("phone_call_active", "phone_call_retroactive"):
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            if ts <= 0 or (now - ts) > ttl_s:
                return {}
            return {
                "active": True,
                "event_id": row.get("event_id"),
                "event_type": et,
                "started_ts": ts,
                "age_s": round(now - ts, 1),
                "age_min": round((now - ts) / 60.0, 2),
                "note": row.get("note", "")[:200],
            }
    return {}


__all__ = [
    "is_phone_declaration",
    "is_phone_log_request",
    "is_phone_call_active",
    "phone_call_active_state",
    "extract_other_party",
    "handle_phone_declaration",
    "handle_call_end",
    "format_phone_log_for_prompt",
]
