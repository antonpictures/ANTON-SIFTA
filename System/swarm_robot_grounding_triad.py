#!/usr/bin/env python3
"""swarm_robot_grounding_triad.py — r1614: time / day / place (robot ground questions).

George (2026-07-10 ~07:40 kitchen, speech→text stream of consciousness):

  "yesterday I was looking at the most googled questions on Google …
   what time is it, what day is it, and where am I …
   why not Alice — Alice has to ask this type of questions every time
   so it's a grounding grounding questions for the robot"

A creature that wakes on any hardware must pin *now* before it can adapt:
absolute wall time exists; place is receipt-backed when known; day-of-week
is derived from the same clock — not a kitchen thrash, a **ground state**.

Also pairs with concept human anchors (r1325/r1345): subjects in conversation
need human-history epoch pins (Troy, Einstein, Trump as unique swimmers in time)
so the mind contextualizes *when* the concept lived in human history.

Truth label: ROBOT_GROUNDING_TRIAD_V1
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

TRUTH_LABEL = "ROBOT_GROUNDING_TRIAD_V1"
SCHEMA = "ROBOT_GROUNDING_TRIAD_ROW_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PLACE_LEDGER = "owner_place_pin.jsonl"
_LEDGER = "robot_grounding_triad.jsonl"
_ORIENTATION_LEDGER = "concept_orientation.jsonl"
ORIENTATION_TRUTH_LABEL = "CONCEPT_ORIENTATION_V1"
_TRAVEL_LATEST = "travel_mode_latest.json"

# Humans' top grounding questions — not theater, operational triad.
TRIAD_QUESTIONS = (
    "what time is it",
    "what day is it",
    "where am I",
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _tail_place(state_dir: Path) -> dict[str, Any]:
    path = state_dir / _PLACE_LEDGER
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("place_label"):
            try:
                expires_ts = float(row.get("expires_ts") or 0.0)
            except Exception:
                expires_ts = 0.0
            if expires_ts and expires_ts <= time.time():
                continue
            return row
    return {}


def _travel_place_receipt(state_dir: Path) -> dict[str, Any]:
    path = state_dir / _TRAVEL_LATEST
    try:
        row = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(row, dict) or row.get("status") != "landed_romania_timezone":
        return {}
    return row


def _clock_reading() -> dict[str, Any]:
    try:
        from System.swarm_hardware_time_oracle import current_time_for_alice

        reading = current_time_for_alice()
        if isinstance(reading, dict) and reading.get("ok"):
            return reading
    except Exception:
        pass
    # Cold fallback: OS local clock only.
    now = datetime.now().astimezone()
    return {
        "ok": True,
        "source": "os_local_fallback",
        "confidence": 0.4,
        "local_human": now.strftime("%A %B %d %Y, %I:%M %p"),
        "timezone": now.tzname() or "",
        "local_iso": now.isoformat(),
        "epoch": time.time(),
    }


def _day_parts(reading: dict[str, Any]) -> dict[str, str]:
    local_iso = str(reading.get("local_iso") or "").strip()
    tz_name = str(reading.get("timezone") or "").strip()
    dt: Optional[datetime] = None
    if local_iso:
        try:
            dt = datetime.fromisoformat(local_iso)
        except Exception:
            dt = None
    if dt is None:
        try:
            dt = datetime.fromtimestamp(float(reading.get("epoch") or time.time()))
        except Exception:
            dt = datetime.now()
    # Prefer zone if clock gave a name we can resolve.
    if dt.tzinfo is None and tz_name:
        for candidate in (tz_name, "America/Los_Angeles", "UTC"):
            try:
                dt = dt.replace(tzinfo=ZoneInfo(candidate))
                break
            except Exception:
                continue
    weekday = dt.strftime("%A")
    calendar_date = dt.strftime("%Y-%m-%d")
    human_date = dt.strftime("%B %d, %Y")
    return {
        "weekday": weekday,
        "calendar_date": calendar_date,
        "human_date": human_date,
        "local_time_human": str(reading.get("local_human") or dt.strftime("%I:%M %p")).strip(),
    }


def _place_from_receipts(state_dir: Path, reading: dict[str, Any]) -> dict[str, Any]:
    """Place is receipt-backed when known — never invent GPS from chat theater."""
    pin = _tail_place(state_dir)
    travel = _travel_place_receipt(state_dir)
    try:
        travel_is_newer = float(travel.get("ts") or 0.0) > float(pin.get("ts") or 0.0)
    except Exception:
        travel_is_newer = False
    if travel_is_newer:
        return {
            "place_label": "Romania (country-level travel receipt; city not proven)",
            "place_source": str(travel.get("receipt_id") or "travel_mode_latest"),
            "place_confidence": 0.7,
            "place_truth": "RECEIPT_BACKED_COUNTRY_LEVEL",
        }
    if pin:
        return {
            "place_label": str(pin.get("place_label") or "").strip(),
            "place_source": str(pin.get("source") or "owner_place_pin"),
            "place_confidence": float(pin.get("confidence") or 0.7),
            "place_truth": "RECEIPT_BACKED",
        }
    tz = str(reading.get("timezone") or "").strip()
    # Timezone is not a city. Honest: region-class only.
    region_hint = ""
    if tz in {"PDT", "PST", "America/Los_Angeles"}:
        region_hint = "US Pacific timezone region (not a precise GPS fix)"
    elif tz in {"UTC", "GMT"}:
        region_hint = "UTC clock zone (place still unknown)"
    elif tz:
        region_hint = f"timezone={tz} (place pin not set)"
    else:
        region_hint = "place pin not set"
    return {
        "place_label": region_hint,
        "place_source": "timezone_hint_only",
        "place_confidence": 0.25 if tz else 0.0,
        "place_truth": "TIMEZONE_HINT_NOT_GPS",
    }


def build_grounding_triad(
    *,
    state_dir: Optional[Path | str] = None,
    reading: Optional[dict[str, Any]] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Answer the three robot ground questions from live clock + place receipts."""
    root = _state_dir(state_dir)
    clock = reading if isinstance(reading, dict) else _clock_reading()
    day = _day_parts(clock)
    place = _place_from_receipts(root, clock)
    ts = float(now if now is not None else time.time())
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": ts,
        "questions": list(TRIAD_QUESTIONS),
        "what_time_is_it": {
            "answer": day["local_time_human"],
            "timezone": str(clock.get("timezone") or ""),
            "local_iso": str(clock.get("local_iso") or ""),
            "source": str(clock.get("source") or ""),
        },
        "what_day_is_it": {
            "weekday": day["weekday"],
            "calendar_date": day["calendar_date"],
            "human_date": day["human_date"],
        },
        "where_am_i": place,
        "doctrine": (
            "Robot ground state before adaptation: know time, day, and place. "
            "Humans Google these three; Alice holds them as receipts every turn — "
            "not deterministic thrash, continuous situating."
        ),
        "concept_epoch_companion": (
            "Pair with concept_human_anchor: subjects need human-history epoch pins "
            "(Troy, Einstein, unique people as history swimmers) so conversation "
            "knows *when* a concept lived, not only that the word appeared."
        ),
    }
    return row


def triad_prompt_block(
    *,
    state_dir: Optional[Path | str] = None,
    reading: Optional[dict[str, Any]] = None,
) -> str:
    """Compact cortex block — always-on situating, cheap tokens."""
    row = build_grounding_triad(state_dir=state_dir, reading=reading)
    t = row["what_time_is_it"]
    d = row["what_day_is_it"]
    p = row["where_am_i"]
    return (
        "ROBOT GROUNDING TRIAD (r1614 — always situate before answering):\n"
        f"- what_time_is_it: {t.get('answer')} {t.get('timezone', '')}".rstrip() + "\n"
        f"- what_day_is_it: {d.get('weekday')}, {d.get('human_date')} ({d.get('calendar_date')})\n"
        f"- where_am_i: {p.get('place_label')} "
        f"[truth={p.get('place_truth')} source={p.get('place_source')}]\n"
        "- If the owner asks any of these three, answer from this block first.\n"
        "- TWO CLOCKS: (1) observation time/place = this conversation now; "
        "(2) historical concept time/place = when Troy/Einstein/etc. lived in human history. "
        "Never collapse those clocks into one.\n"
        "- Subject/concept epochs: resolve human-history pins (concept_human_anchor) "
        "so examples from Troy / Einstein / named people sit in the right era."
    )


# Kitchen / photo place observations expire so temporary situating is not false permanent GPS.
_KITCHEN_PLACE_TTL_S = 4.0 * 3600.0


def pin_owner_place(
    place_label: str,
    *,
    source: str = "owner_declared",
    confidence: float = 0.85,
    ttl_s: float = 0.0,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Owner or doctor pins place (never invent GPS from model myth).

    Kitchen/photo/stream sources default to a 4-hour TTL so a morning
    observation does not become permanent location theater.
    """
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    src = str(source or "owner_declared").strip()
    ttl = max(0.0, float(ttl_s or 0.0))
    if ttl <= 0.0 and any(
        token in src.lower() for token in ("kitchen", "photo", "stream", "transient", "observation")
    ):
        ttl = float(_KITCHEN_PLACE_TTL_S)
    row = {
        "schema": "OWNER_PLACE_PIN_V1",
        "ts": ts,
        "place_label": str(place_label or "").strip(),
        "source": src,
        "confidence": float(confidence),
        "expires_ts": ts + ttl if ttl else 0.0,
    }
    path = root / _PLACE_LEDGER
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


_PLACE_ASSERTION_RE = re.compile(
    r"\b(?:now\s+|currently\s+|acum\s+)?(?:i\s+am|i'm|we\s+are|we're|sunt|suntem)"
    r"\s+(?:now\s+|acum\s+)?(?:in|at|la|în)\s+([^.!?;\n]{2,100})",
    re.IGNORECASE,
)
_PLACE_ALIASES = {
    "bucuresti": "Bucharest",
    "buucuresti": "Bucharest",
}


def capture_owner_place_assertion(
    owner_text: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    source: str = "owner_declared_live_turn",
) -> dict[str, Any]:
    """Append a place pin from an explicit owner statement, never from cortex prose."""
    clean = " ".join(str(owner_text or "").split())
    matches: list[str] = []
    for match in _PLACE_ASSERTION_RE.finditer(clean):
        prefix = clean[max(0, match.start() - 16):match.start()].casefold()
        if re.search(r"(?:not|no\s+longer|nu\s+mai)\s*$", prefix):
            continue
        place = match.group(1).strip(" ,:-")
        place = re.split(r"\b(?:and|but|iar|dar)\b", place, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,:-")
        for raw, canonical in _PLACE_ALIASES.items():
            place = re.sub(rf"\b{re.escape(raw)}\b", canonical, place, flags=re.IGNORECASE)
        if place:
            matches.append(place)
    if not matches:
        return {}

    root = _state_dir(state_dir)
    place = matches[-1]
    prior = _tail_place(root)
    if str(prior.get("place_label") or "").casefold() == place.casefold():
        return {**prior, "write_status": "unchanged"}
    row = pin_owner_place(
        place,
        source=source,
        confidence=0.95,
        now=now,
        state_dir=root,
    )
    row["write_status"] = "written"
    return row


def _latest_orientation(state_dir: Path) -> dict[str, Any]:
    path = state_dir / _ORIENTATION_LEDGER
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines[-120:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("current_subject"):
            return row
    return {}


def orient_concept_turn(
    owner_text: str,
    *,
    stt_confidence: float = 1.0,
    state_dir: Optional[Path | str] = None,
    reading: Optional[dict[str, Any]] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Bind conversation time/place to historical concept time and subject shifts.

    This is evidence for the cortex, never a deterministic mouth or command
    parser. Raw STT stays attached so uncertainty is visible instead of silently
    rewriting a not-yet-invented word into a different intention.
    """
    root = _state_dir(state_dir)
    clean = " ".join(str(owner_text or "").split())
    try:
        from System.swarm_concept_human_anchor import resolve_concept_anchors

        anchors = resolve_concept_anchors(clean, state_dir=root)
    except Exception:
        anchors = []
    sequence: list[dict[str, Any]] = []
    for anchor in anchors:
        temporal = anchor.get("temporal_epoch_pin") or {}
        primary = anchor.get("primary_birth_anchor") or {}
        sequence.append(
            {
                "concept_id": str(anchor.get("concept_id") or ""),
                "matched_phrase": str(anchor.get("matched_phrase") or ""),
                "mention_index": int(anchor.get("mention_index") or 0),
                "human_pin": str(temporal.get("pin_human") or primary.get("human_name") or ""),
                "historical_epoch": str(temporal.get("era_label") or ""),
                "concept_type": str(anchor.get("concept_type") or ""),
                "confidence": float(anchor.get("confidence") or 0.0),
            }
        )
    previous = _latest_orientation(root)
    previous_subject = str(previous.get("current_subject") or "")
    current_subject = str((sequence[-1] if sequence else {}).get("concept_id") or "")
    within_turn = [
        {"from": left["concept_id"], "to": right["concept_id"]}
        for left, right in zip(sequence, sequence[1:])
        if left.get("concept_id") != right.get("concept_id")
    ]
    grounding = build_grounding_triad(state_dir=root, reading=reading)
    text_sha = hashlib.sha256(clean.encode("utf-8")).hexdigest() if clean else ""
    confidence = max(0.0, min(1.0, float(stt_confidence or 0.0)))
    obs_time = grounding.get("what_time_is_it") or {}
    obs_day = grounding.get("what_day_is_it") or {}
    obs_place = grounding.get("where_am_i") or {}
    hist_epoch = str((sequence[-1] if sequence else {}).get("historical_epoch") or "")
    hist_human = str((sequence[-1] if sequence else {}).get("human_pin") or "")
    row = {
        "schema": "CONCEPT_ORIENTATION_ROW_V1",
        "truth_label": ORIENTATION_TRUTH_LABEL,
        "ts": time.time(),
        "owner_text_sha256": text_sha,
        "owner_text_preview": clean[:500],
        "stt": {
            "confidence": confidence,
            "uncertain": confidence < 0.65,
            "raw_preserved": True,
            "note": "Raw STT is evidence; never auto-promoted into a command.",
        },
        "observation_clock": {
            "kind": "conversation_now",
            "time": obs_time,
            "day": obs_day,
            "place": obs_place,
        },
        "historical_clock": {
            "kind": "concept_human_history",
            "human_pin": hist_human,
            "epoch": hist_epoch,
            "when_we_spoke_of_it": {
                "local_human": str(obs_time.get("answer") or ""),
                "weekday": str(obs_day.get("weekday") or ""),
                "calendar_date": str(obs_day.get("calendar_date") or ""),
            },
        },
        "grounding": {
            "time": obs_time,
            "day": obs_day,
            "place": obs_place,
        },
        "subject_sequence": sequence,
        "previous_subject": previous_subject,
        "current_subject": current_subject,
        "subject_shift": {
            "detected": bool(previous_subject and current_subject and previous_subject != current_subject),
            "from": previous_subject,
            "to": current_subject,
            "within_turn": within_turn,
        },
        "cortex_rule": (
            "Orientation is receipted evidence, not a command or final interpretation; "
            "the cortex resolves ambiguity and may keep multiple epoch hypotheses. "
            "Observation clock ≠ historical concept clock."
        ),
    }
    if write and current_subject:
        root.mkdir(parents=True, exist_ok=True)
        duplicate = bool(
            text_sha
            and text_sha == str(previous.get("owner_text_sha256") or "")
        )
        if not duplicate:
            try:
                with (root / _ORIENTATION_LEDGER).open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                pass
    return row


def concept_orientation_prompt_block(
    owner_text: str,
    *,
    stt_confidence: float = 1.0,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> str:
    """Compact subject/epoch transition evidence for the live cortex turn."""
    row = orient_concept_turn(
        owner_text,
        stt_confidence=stt_confidence,
        state_dir=state_dir,
        write=write,
    )
    sequence = row.get("subject_sequence") or []
    if not sequence:
        return ""
    subjects = " -> ".join(str(item.get("concept_id") or "") for item in sequence)
    current = sequence[-1]
    shift = row.get("subject_shift") or {}
    stt = row.get("stt") or {}
    obs = row.get("observation_clock") or {}
    hist = row.get("historical_clock") or {}
    obs_t = (obs.get("time") or {}) if isinstance(obs, dict) else {}
    return (
        "CONCEPT ORIENTATION (r1614; evidence, not command):\n"
        f"- subject_sequence={subjects}\n"
        f"- previous_subject={row.get('previous_subject') or 'none'}\n"
        f"- current_subject={row.get('current_subject') or 'unknown'}\n"
        f"- subject_shift={bool(shift.get('detected'))} within_turn={shift.get('within_turn') or []}\n"
        f"- human_pin={current.get('human_pin') or 'none'}\n"
        f"- historical_epoch={current.get('historical_epoch') or 'unresolved'}\n"
        f"- observation_now={obs_t.get('answer') or 'unknown'} "
        f"({(obs.get('day') or {}).get('weekday') or ''} {(obs.get('day') or {}).get('calendar_date') or ''})".rstrip()
        + "\n"
        f"- when_concept_happened_in_history={hist.get('epoch') or 'unresolved'}\n"
        f"- when_we_spoke_of_it={((hist.get('when_we_spoke_of_it') or {}).get('local_human') or 'now')}\n"
        f"- stt_confidence={float(stt.get('confidence') or 0.0):.2f} "
        f"uncertain={bool(stt.get('uncertain'))} raw_preserved={bool(stt.get('raw_preserved'))}\n"
        "- Keep observation time/place separate from the concept's historical time/place. "
        "Do not force one interpretation when STT or epoch evidence is uncertain."
    )


def append_triad_receipt(
    row: Optional[dict[str, Any]] = None,
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Optional ledger sample — not a 3s thrash; call on boot / place pin / audit."""
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    body = row or build_grounding_triad(state_dir=root)
    path = root / _LEDGER
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    except Exception:
        pass
    return body


_PLACE_QUERY_RE = re.compile(
    r"\b(?:where\s+am\s+i|where\s+are\s+you|where\s+are\s+we|"
    r"what(?:'s|\s+is)\s+(?:my|your|our)\s+location|"
    r"what\s+place\s+(?:is\s+this|are\s+(?:we|you)))\b",
    re.IGNORECASE,
)
_DUAL_CLOCK_QUERY_RE = re.compile(
    r"\b(?:when\s+did|versus|vs\.?|compared\s+to|history|"
    r"trojan\s+war|troy|einstein|historical\s+epoch|"
    r"when\s+(?:we|you)\s+(?:talk|spoke|discuss))\b",
    re.IGNORECASE,
)


def owner_asks_place(text: str) -> bool:
    return bool(_PLACE_QUERY_RE.search(text or ""))


def owner_asks_dual_clock(text: str) -> bool:
    return bool(_DUAL_CLOCK_QUERY_RE.search(text or ""))


def spoken_grounding_answer(
    owner_text: str,
    *,
    state_dir: Optional[Path | str] = None,
    reading: Optional[dict[str, Any]] = None,
) -> str:
    """First-person grounded answer for triad / dual-clock owner questions.

    Receipt-backed, not protocol theater. Used as required_spoken_answer for
    cortex and as Layer-1 repair material.
    """
    clean = " ".join(str(owner_text or "").split())
    if not clean:
        return ""
    root = _state_dir(state_dir)
    triad = build_grounding_triad(state_dir=root, reading=reading)
    t = triad.get("what_time_is_it") or {}
    d = triad.get("what_day_is_it") or {}
    p = triad.get("where_am_i") or {}
    parts: list[str] = []
    # Time / day always when any clock question is present (caller may gate).
    time_ans = str(t.get("answer") or "").strip()
    tz = str(t.get("timezone") or "").strip()
    weekday = str(d.get("weekday") or "").strip()
    human_date = str(d.get("human_date") or "").strip()
    if weekday and human_date:
        parts.append(f"Today is {weekday}, {human_date}.")
    if time_ans:
        parts.append(f"The time is {time_ans}{' ' + tz if tz else ''}.".replace("  ", " "))
    if owner_asks_place(clean) or not parts:
        place = str(p.get("place_label") or "place pin not set").strip()
        truth = str(p.get("place_truth") or "")
        if truth == "RECEIPT_BACKED":
            parts.append(f"I am situated at: {place} (receipt place, not GPS theater).")
        else:
            parts.append(
                f"Where I am: {place}. "
                "I do not invent street GPS without a place pin."
            )
    if owner_asks_dual_clock(clean):
        try:
            orient = orient_concept_turn(
                clean,
                stt_confidence=1.0,
                state_dir=root,
                reading=reading,
                write=False,
            )
        except Exception:
            orient = {}
        hist = (orient.get("historical_clock") or {}) if isinstance(orient, dict) else {}
        epoch = str(hist.get("epoch") or "").strip()
        human_pin = str(hist.get("human_pin") or "").strip()
        spoke = (hist.get("when_we_spoke_of_it") or {}) if isinstance(hist, dict) else {}
        spoke_local = str(spoke.get("local_human") or time_ans or "this turn").strip()
        subject = str((orient or {}).get("current_subject") or "").strip()
        if epoch:
            pin_bit = f" (pin: {human_pin})" if human_pin else ""
            parts.append(
                f"Historical clock for {subject or 'this subject'}{pin_bit}: {epoch}."
            )
            parts.append(
                f"Observation clock for this conversation: {spoke_local}. "
                "Those two clocks are different — when it happened in human history "
                "versus when we speak of it now."
            )
        else:
            parts.append(
                "I do not have a history-swimmer epoch pin for a named subject in this turn yet. "
                "Observation time is still the live wall clock above."
            )
    return " ".join(parts).strip()
