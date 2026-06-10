#!/usr/bin/env python3
"""Infer owner life-event reminders from natural speech — zero schedule setup (r873 P1-E)."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "OWNER_LIFE_EVENT_INFERENCE_V1"

# minutes — editable priors; field learns via correction receipts
DEFAULT_PRIORS_MIN: Dict[str, float] = {
    "pizza": 13.0,
    "oven": 13.0,
    "tea": 4.0,
    "eggs": 10.0,
    "laundry": 50.0,
    "microwave": 3.0,
}

_DURATION_RE = re.compile(
    r"\b(?P<n>\d{1,3})\s*(?:-|–)?\s*(?:min(?:ute)?s?|mins?)\b",
    re.IGNORECASE,
)
_DURATION_RANGE_RE = re.compile(
    r"\b(?P<lo>\d{1,3})\s*(?:-|–|to)\s*(?P<hi>\d{1,3})\s*(?:min(?:ute)?s?|mins?)\b",
    re.IGNORECASE,
)

_EVENT_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:putting|put|placed|stick(?:ing)?)\s+.+\b(?:in|into)\s+(?:the\s+)?(?:oven|owen)\b", re.I), "oven_food"),
    (re.compile(r"\bpizza\b.+\b(?:in|into)\s+(?:the\s+)?(?:oven|owen)\b", re.I), "pizza"),
    (re.compile(r"\b(?:pizza|food)\s+in\s+(?:the\s+)?(?:oven|owen)\b", re.I), "pizza"),
    (re.compile(r"\btea\s+steep(?:ing)?\b", re.I), "tea"),
    (re.compile(r"\beggs?\s+boil(?:ing)?\b", re.I), "eggs"),
    (re.compile(r"\blaundry\s+in\b", re.I), "laundry"),
    (re.compile(r"\bmicrowave\b", re.I), "microwave"),
)

_CLOSE_RE = re.compile(
    r"\b(?:already\s+)?(?:took|take|got|pulled)\s+(?:it\s+)?out\b|"
    r"\bate\s+it\b|"
    r"\bdone\s+(?:with\s+)?(?:the\s+)?(?:pizza|food|oven)\b",
    re.IGNORECASE,
)

_TOO_EARLY_RE = re.compile(
    r"\b(?:too\s+early|not\s+ready|still\s+raw|came\s+too\s+soon)\b",
    re.IGNORECASE,
)

_MIN_CONFIDENCE = 0.55


def _write_bridget_diary(
    line: str,
    *,
    state_dir: Path,
    ts: Optional[float] = None,
    kind: str = "owner_life",
) -> None:
    """Schedule witness line in Alice's diary (Bridget Jones *style*, not Alice's name)."""
    try:
        from System.swarm_alice_witness import witness

        witness(
            line,
            source="bridget",
            ts=ts,
            state_dir=state_dir,
            importance={"kind": kind, "lane": "owner_schedule_unified"},
        )
    except Exception:
        pass


def _bridget_scheduled_line(clean: str, *, minutes: float, due_ts: float) -> str:
    try:
        due_clock = time.strftime("%H:%M", time.localtime(due_ts))
    except Exception:
        due_clock = f"~{int(minutes)} min"
    snippet = clean[:120].strip()
    return (
        f"Dear diary — Alice here. George just told me: {snippet}. "
        f"I owe him a reminder around {due_clock}. I must not forget."
    )


def _bridget_fired_line(speech: str) -> str:
    return f"Dear diary — I just reminded George: {speech.strip()}"


def _bridget_closed_line(clean: str) -> str:
    return f"Dear diary — George closed the kitchen loop: {clean[:120].strip()}."


def _state_dir(state_dir: str | Path | None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_schedule(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_schedule_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _infer_event_class(text: str) -> Tuple[str, float]:
    clean = " ".join((text or "").strip().split())
    for pattern, label in _EVENT_PATTERNS:
        if pattern.search(clean):
            return label, 0.82
    return "", 0.0


def _duration_minutes(text: str, event_class: str, *, state_dir: Path) -> float:
    r = _DURATION_RANGE_RE.search(text or "")
    if r:
        try:
            return max(1.0, float(r.group("lo")), float(r.group("hi")))
        except Exception:
            pass
    m = _DURATION_RE.search(text or "")
    if m:
        try:
            return max(1.0, float(m.group("n")))
        except Exception:
            pass
    priors_path = state_dir / "owner_life_event_priors.json"
    priors = dict(DEFAULT_PRIORS_MIN)
    if priors_path.exists():
        try:
            loaded = json.loads(priors_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    try:
                        priors[str(k)] = float(v)
                    except Exception:
                        pass
        except Exception:
            pass
    for key, minutes in priors.items():
        if key in event_class or key in (text or "").lower():
            return minutes
    return priors.get("oven", 13.0)


def _reminder_speech(event_class: str, item_text: str) -> str:
    if "pizza" in event_class or "pizza" in item_text.lower():
        return "George, your pizza should be ready about now."
    if "tea" in event_class:
        return "George, your tea should be ready."
    if "eggs" in event_class:
        return "George, your eggs should be done."
    if "laundry" in event_class:
        return "George, the laundry cycle should be about done."
    return f"George, {item_text} should be ready about now."


def process_owner_turn(
    text: str,
    *,
    typed_turn: bool = False,
    media_lane: bool = False,
    state_dir: str | Path | None = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Listen on owner lane only. Returns action summary for receipts."""
    base = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    clean = " ".join((text or "").strip().split())
    result: Dict[str, Any] = {"action": "none", "truth_label": TRUTH_LABEL}

    if not clean or media_lane:
        result["action"] = "skipped_media_or_empty"
        return result

    schedule_path = base / "stigmergic_schedule.jsonl"

    if _CLOSE_RE.search(clean):
        from System.stigmergic_schedule import mark_schedule_done_by_source

        closed = mark_schedule_done_by_source("stigmergic_inference", path=schedule_path)
        if closed:
            _append_jsonl(
                base / "owner_body_events.jsonl",
                {
                    "ts": now_ts,
                    "type": "kitchen",
                    "event_type": "life_event_closed",
                    "description": clean[:240],
                    "source": "swarm_owner_life_event_inference",
                },
            )
            _write_bridget_diary(
                _bridget_closed_line(clean),
                state_dir=base,
                ts=now_ts,
                kind="life_event_closed",
            )
            result.update({"action": "closed", "closed": closed})
        return result

    if _TOO_EARLY_RE.search(clean):
        _adjust_prior(base, "pizza", delta_min=3.0, evidence=clean)
        result.update({"action": "prior_adjusted", "delta_min": 3.0})
        return result

    event_class, confidence = _infer_event_class(clean)
    if not event_class or confidence < _MIN_CONFIDENCE:
        result["action"] = "no_event_detected"
        return result

    minutes = _duration_minutes(clean, event_class, state_dir=base)
    due_ts = now_ts + minutes * 60.0
    item = clean[:200]
    if "pizza" in event_class:
        item = "pizza in the oven"

    from System.stigmergic_schedule import add_task

    row = add_task(
        item,
        due_ts=due_ts,
        due=f"in ~{int(minutes)} min (inferred)",
        priority=2,
        source="stigmergic_inference",
        path=schedule_path,
    )
    row["event_class"] = event_class
    row["confidence"] = confidence
    row["evidence_turn"] = clean[:280]
    row["inferred_minutes"] = minutes

    _append_jsonl(
        base / "owner_body_events.jsonl",
        {
            "ts": now_ts,
            "type": "kitchen",
            "event_type": "life_event_inferred",
            "description": clean[:240],
            "event_class": event_class,
            "due_ts": due_ts,
            "source": "swarm_owner_life_event_inference",
        },
    )
    _write_bridget_diary(
        _bridget_scheduled_line(clean, minutes=minutes, due_ts=due_ts),
        state_dir=base,
        ts=now_ts,
        kind="life_event_scheduled",
    )
    result.update({"action": "scheduled", "row": row, "due_ts": due_ts, "minutes": minutes})
    return result


def _adjust_prior(base: Path, key: str, *, delta_min: float, evidence: str) -> None:
    priors_path = base / "owner_life_event_priors.json"
    priors = dict(DEFAULT_PRIORS_MIN)
    if priors_path.exists():
        try:
            loaded = json.loads(priors_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                priors.update({str(k): float(v) for k, v in loaded.items() if v is not None})
        except Exception:
            pass
    priors[key] = float(priors.get(key, 13.0)) + float(delta_min)
    priors_path.write_text(json.dumps(priors, indent=2), encoding="utf-8")
    _append_jsonl(
        base / "stigmergic_schedule_receipts.jsonl",
        {
            "ts": time.time(),
            "operation": "PRIOR_ADJUST",
            "key": key,
            "new_minutes": priors[key],
            "evidence": evidence[:220],
            "source": "swarm_owner_life_event_inference",
        },
    )


def due_life_reminders(
    *,
    state_dir: str | Path | None = None,
    now: Optional[float] = None,
    grace_s: float = 5.0,
) -> List[Dict[str, Any]]:
    """Return inferred schedule rows that are due and not yet fired."""
    base = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    due: List[Dict[str, Any]] = []
    for row in _read_schedule(base / "stigmergic_schedule.jsonl"):
        if row.get("done"):
            continue
        if str(row.get("source") or "") != "stigmergic_inference":
            continue
        if row.get("fired"):
            continue
        try:
            due_ts = float(row.get("due_ts") or 0.0)
        except Exception:
            continue
        if due_ts and due_ts <= now_ts + grace_s:
            due.append(row)
    return due


def mark_reminder_fired(
    schedule_id: str,
    *,
    speech: str = "",
    state_dir: str | Path | None = None,
) -> Optional[Dict[str, Any]]:
    base = _state_dir(state_dir)
    path = base / "stigmergic_schedule.jsonl"
    rows = _read_schedule(path)
    fired_row: Optional[Dict[str, Any]] = None
    # r875 (Fable verifier fix): mutate rows[idx] in place. The r874 version
    # set fired=True on a dict COPY and then wrote the ORIGINAL rows back,
    # so the flag never reached disk and the 30s poll re-fired the same
    # reminder forever. Receipts decide reality — the flag must land.
    for idx, row in enumerate(rows):
        if str(row.get("schedule_id") or "") == schedule_id:
            updated = dict(row)
            updated["fired"] = True
            updated["fired_ts"] = time.time()
            updated["fired_speech"] = speech[:280]
            rows[idx] = updated
            fired_row = updated
            break
    if fired_row is None:
        return None
    _write_schedule_rows(path, rows)
    receipt = {
        "ts": time.time(),
        "receipt_id": str(uuid.uuid4()),
        "operation": "LIFE_REMINDER_FIRED",
        "schedule_id": schedule_id,
        "speech": speech[:280],
        "truth_label": TRUTH_LABEL,
        "source": "swarm_owner_life_event_inference",
    }
    _append_jsonl(base / "stigmergic_schedule_receipts.jsonl", receipt)
    try:
        from System.swarm_app_command_effect_verification import record_schedule_fire_command

        record_schedule_fire_command(
            schedule_id=schedule_id,
            speech=speech,
            ok=True,
            state_dir=base,
        )
    except Exception:
        pass
    if speech:
        _write_bridget_diary(
            _bridget_fired_line(speech),
            state_dir=base,
            kind="life_reminder_fired",
        )
    return receipt


def reminder_speech_for_row(row: Mapping[str, Any]) -> str:
    event_class = str(row.get("event_class") or "")
    item = str(row.get("text") or "your task")
    return _reminder_speech(event_class, item)


__all__ = [
    "TRUTH_LABEL",
    "process_owner_turn",
    "due_life_reminders",
    "mark_reminder_fired",
    "reminder_speech_for_row",
    "DEFAULT_PRIORS_MIN",
]
