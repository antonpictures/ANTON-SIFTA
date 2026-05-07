#!/usr/bin/env python3
"""Stigmergic schedule prediction from local owner-life ledgers.

This is a deterministic prior, not a claim of certainty. It looks at observed
day segments, body events, and explicit schedule rows, then writes the next
likely owner segment into the SIFTA state ledger.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - import fallback for standalone probes
    def append_line_locked(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)


STATE_DIR = Path(__file__).resolve().parents[1] / ".sifta_state"
TRUTH_LABEL = "OBSERVED_SCHEDULE_PRIOR"
SCHEMA = "SIFTA_STIGMERGIC_PREDICTION_V1"
LATEST_NAME = "stigmergic_prediction.json"
LEDGER_NAME = "stigmergic_prediction.jsonl"
PROMPT_WRITE_INTERVAL_S = 15 * 60.0

DAY_SEGMENT_LEDGER_NAMES = (
    "architect_day_segments.jsonl",
    "day_segments_diary.jsonl",
)
OWNER_BODY_LEDGER_NAME = "owner_body_events.jsonl"
SCHEDULE_LEDGER_NAME = "stigmergic_schedule.jsonl"

_LABEL_ALIASES = {
    "food": "meal",
    "eating": "meal",
    "dinner": "meal",
    "lunch": "meal",
    "breakfast": "meal",
    "phone_call_retroactive": "phone_call",
    "phone": "phone_call",
    "co_watch": "co_watch",
    "cowatch": "co_watch",
    "youtube": "co_watch",
    "desk": "desk_work",
    "work": "desk_work",
    "typing": "desk_work",
    "store": "shopping",
    "shop": "shopping",
    "shopping": "shopping",
    "sleep": "sleep",
    "rest": "rest",
    "hydration": "care",
    "care_appointment": "appointment",
    "body_check": "care",
    "vision": "presence",
    "visual_recognition": "presence",
}

_SCHEDULE_LABEL_RE = re.compile(
    r"\b("
    r"meal|eat|dinner|lunch|breakfast|sleep|rest|phone|call|store|shop|"
    r"shopping|desk|work|coding|youtube|video|co-?watch|appointment|care"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EventSample:
    label: str
    minute: int
    ts: float | None
    source: str
    receipt: str
    text: str = ""
    explicit_future: bool = False


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _read_jsonl(path: Path, *, max_rows: int = 4096) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(max_rows)) :]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _minute_from_ts(ts: float) -> int:
    lt = time.localtime(float(ts))
    return int(lt.tm_hour) * 60 + int(lt.tm_min)


def _minute_label(minute: int) -> str:
    minute = int(minute) % 1440
    hour24, mm = divmod(minute, 60)
    period = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12 or 12
    return f"{hour12}:{mm:02d} {period}"


def _local_datetime_label(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S %Z")


def _normalize_label(raw: Any, text: str = "") -> str:
    label = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if label in _LABEL_ALIASES:
        return _LABEL_ALIASES[label]
    if label and label not in {"unknown", "none", "owner_body_event", "activity"}:
        return label[:40]

    haystack = f"{raw or ''} {text or ''}".lower()
    match = _SCHEDULE_LABEL_RE.search(haystack)
    if match:
        token = match.group(1).lower().replace("-", "_")
        return _LABEL_ALIASES.get(token, token)
    return "activity"


def _row_receipt(row: Mapping[str, Any]) -> str:
    for key in ("segment_id", "schedule_id", "event_id", "trace_id", "source_hash"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:48]
    seed = json.dumps(dict(row), sort_keys=True, default=str)[:240]
    return uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]


def _row_text(row: Mapping[str, Any]) -> str:
    for key in ("context_note", "raw_text", "note", "text", "summary", "topic"):
        value = str(row.get(key) or "").strip()
        if value:
            return " ".join(value.split())[:240]
    return ""


def _row_ts(row: Mapping[str, Any]) -> float | None:
    for key in ("ts", "timestamp", "created", "start_ts", "end_ts", "due_ts", "due"):
        value = _safe_float(row.get(key))
        if value and value > 1_000_000_000:
            return value
    return None


def _segment_samples(root: Path, now_ts: float, window_days: int) -> list[EventSample]:
    cutoff = now_ts - max(1, int(window_days)) * 86400
    samples: list[EventSample] = []
    for ledger_name in DAY_SEGMENT_LEDGER_NAMES:
        path = root / ledger_name
        for row in _read_jsonl(path):
            ts = _row_ts(row)
            if ts is not None and ts < cutoff:
                continue
            minute = _safe_int(row.get("start_minute_of_day"))
            if minute is None:
                minute = _safe_int(row.get("start_minute"))
            if minute is None and ts is not None:
                minute = _minute_from_ts(ts)
            if minute is None:
                continue
            text = _row_text(row)
            label = _normalize_label(row.get("label") or row.get("segment"), text)
            samples.append(
                EventSample(
                    label=label,
                    minute=minute % 1440,
                    ts=ts,
                    source=ledger_name,
                    receipt=_row_receipt(row),
                    text=text,
                )
            )
    return samples


def _owner_body_samples(root: Path, now_ts: float, window_days: int) -> list[EventSample]:
    cutoff = now_ts - max(1, int(window_days)) * 86400
    samples: list[EventSample] = []
    for row in _read_jsonl(root / OWNER_BODY_LEDGER_NAME):
        ts = _row_ts(row)
        if ts is None or ts < cutoff:
            continue
        text = _row_text(row)
        label = _normalize_label(row.get("event_type") or row.get("kind"), text)
        samples.append(
            EventSample(
                label=label,
                minute=_minute_from_ts(ts),
                ts=ts,
                source=OWNER_BODY_LEDGER_NAME,
                receipt=_row_receipt(row),
                text=text,
            )
        )
    return samples


def _schedule_samples(root: Path, now_ts: float, window_days: int) -> list[EventSample]:
    cutoff = now_ts - max(1, int(window_days)) * 86400
    samples: list[EventSample] = []
    for row in _read_jsonl(root / SCHEDULE_LEDGER_NAME):
        if row.get("done") is True:
            continue
        text = _row_text(row)
        due = None
        for key in ("due_ts", "due", "when_ts", "scheduled_ts"):
            due = _safe_float(row.get(key))
            if due and due > 1_000_000_000:
                break
            due = None
        created = _safe_float(row.get("created"))
        if due:
            if due < now_ts - 3600:
                continue
            minute = _minute_from_ts(due)
            label = _normalize_label(row.get("label"), text)
            samples.append(
                EventSample(
                    label="scheduled_task" if label == "activity" else label,
                    minute=minute,
                    ts=due,
                    source=SCHEDULE_LEDGER_NAME,
                    receipt=_row_receipt(row),
                    text=text,
                    explicit_future=due >= now_ts,
                )
            )
    return samples


def _collect_samples(root: Path, now_ts: float, window_days: int) -> list[EventSample]:
    samples: list[EventSample] = []
    samples.extend(_segment_samples(root, now_ts, window_days))
    samples.extend(_owner_body_samples(root, now_ts, window_days))
    samples.extend(_schedule_samples(root, now_ts, window_days))
    return samples


def _source_ledgers(root: Path) -> list[str]:
    names = [*DAY_SEGMENT_LEDGER_NAMES, OWNER_BODY_LEDGER_NAME, SCHEDULE_LEDGER_NAME]
    return [name for name in names if (root / name).exists()]


def _basis_days(samples: Iterable[EventSample], now_ts: float) -> int:
    days: set[str] = set()
    for sample in samples:
        if sample.ts:
            days.add(datetime.fromtimestamp(sample.ts).strftime("%Y-%m-%d"))
    return len(days)


def _confidence(best_score: float, total_score: float, support: int, basis_count: int) -> float:
    if total_score <= 0.0 or best_score <= 0.0:
        return 0.0
    share = best_score / total_score
    support_factor = min(1.0, math.log1p(max(0, support)) / math.log(6))
    volume_factor = min(1.0, math.log1p(max(0, basis_count)) / math.log(24))
    return round(max(0.05, min(0.95, 0.72 * share + 0.18 * support_factor + 0.10 * volume_factor)), 3)


def build_prediction(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    window_days: int = 7,
    write: bool = False,
) -> dict[str, Any]:
    """Build a forward-looking owner schedule prior from local ledgers."""
    root = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    now_minute = _minute_from_ts(now_ts)
    samples = _collect_samples(root, now_ts, window_days)

    label_scores: dict[str, float] = defaultdict(float)
    label_minutes: dict[str, list[int]] = defaultdict(list)
    label_support: Counter[str] = Counter()
    label_receipts: dict[str, list[str]] = defaultdict(list)
    label_sources: dict[str, set[str]] = defaultdict(set)
    candidate_details: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for sample in samples:
        distance = (sample.minute - now_minute) % 1440
        if distance > 720 and not sample.explicit_future:
            continue
        age_days = 0.0
        if sample.ts:
            age_days = max(0.0, (now_ts - sample.ts) / 86400)
        recency = 1.0 / (1.0 + min(age_days, max(1, window_days)))
        proximity = math.exp(-distance / (90.0 if sample.explicit_future else 260.0))
        explicit_boost = 2.8 if sample.explicit_future else 1.0
        source_weight = 0.55 if sample.source == SCHEDULE_LEDGER_NAME and not sample.explicit_future else 1.0
        score = explicit_boost * source_weight * recency * proximity
        if score <= 0.0001:
            continue

        label_scores[sample.label] += score
        label_minutes[sample.label].append(distance)
        label_support[sample.label] += 1
        label_sources[sample.label].add(sample.source)
        if len(label_receipts[sample.label]) < 5:
            label_receipts[sample.label].append(sample.receipt)
        if len(candidate_details[sample.label]) < 5:
            candidate_details[sample.label].append(
                {
                    "source": sample.source,
                    "receipt": sample.receipt,
                    "minute": sample.minute,
                    "minute_label": _minute_label(sample.minute),
                    "expected_in_min": int(distance),
                    "text": sample.text[:140],
                }
            )

    candidates: list[dict[str, Any]] = []
    total_score = sum(label_scores.values())
    for label, score in sorted(label_scores.items(), key=lambda item: item[1], reverse=True):
        distances = sorted(label_minutes[label])
        expected = int(round(sum(distances) / len(distances))) if distances else 0
        candidates.append(
            {
                "segment": label,
                "expected_start_min": expected,
                "expected_start_time": _minute_label(now_minute + expected),
                "score": round(score, 5),
                "support_count": int(label_support[label]),
                "sources": sorted(label_sources[label]),
                "receipts": label_receipts[label],
                "evidence": candidate_details[label],
            }
        )

    best = candidates[0] if candidates else {}
    best_score = float(best.get("score", 0.0) or 0.0)
    confidence = _confidence(best_score, total_score, int(best.get("support_count", 0) or 0), len(samples))
    segment = str(best.get("segment") or "unknown")
    expected_start_min = int(best.get("expected_start_min", 0) or 0)

    row: dict[str, Any] = {
        "schema": SCHEMA,
        "kind": "STIGMERGIC_PREDICTION",
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": now_ts,
        "local_time": _local_datetime_label(now_ts),
        "now_minute_of_day": now_minute,
        "now_time": _minute_label(now_minute),
        "window_days": int(window_days),
        "basis_days": _basis_days(samples, now_ts),
        "basis_event_count": len(samples),
        "next_likely_segment": segment,
        "confidence": confidence,
        "expected_start_min": expected_start_min,
        "expected_start_time": best.get("expected_start_time") or _minute_label(now_minute),
        "candidate_segments": candidates[:6],
        "source_ledgers": _source_ledgers(root),
        "explanation": (
            "Deterministic schedule prior from observed day segments, owner body events, "
            "and explicit schedule rows. This is an anticipatory hint, not a certainty."
        ),
    }

    if write:
        write_prediction_row(row, state_dir=root)
    return row


def write_prediction_row(row: Mapping[str, Any], *, state_dir: Path | str = STATE_DIR) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(row), ensure_ascii=False, sort_keys=True)
    append_line_locked(root / LEDGER_NAME, payload + "\n")
    try:
        (root / LATEST_NAME).write_text(
            json.dumps(dict(row), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def write_prediction(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    return build_prediction(state_dir=state_dir, now=now, window_days=window_days, write=True)


def latest_prediction(*, state_dir: Path | str = STATE_DIR) -> dict[str, Any]:
    root = _state_dir(state_dir)
    path = root / LATEST_NAME
    if path.exists():
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(row, dict):
                return row
        except Exception:
            pass
    rows = _read_jsonl(root / LEDGER_NAME, max_rows=1)
    return rows[-1] if rows else {}


def format_prediction_for_alice(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    window_days: int = 7,
    write: bool = True,
) -> str:
    now_ts = float(now if now is not None else time.time())
    row: dict[str, Any]
    if write:
        row = latest_prediction(state_dir=state_dir)
        try:
            fresh = (
                row.get("schema") == SCHEMA
                and now_ts - float(row.get("ts", 0.0) or 0.0) <= PROMPT_WRITE_INTERVAL_S
            )
        except Exception:
            fresh = False
        if not fresh:
            row = build_prediction(state_dir=state_dir, now=now_ts, window_days=window_days, write=True)
    else:
        row = build_prediction(state_dir=state_dir, now=now_ts, window_days=window_days, write=False)
    if row.get("next_likely_segment") == "unknown" or row.get("basis_event_count", 0) <= 0:
        return ""
    segment = str(row.get("next_likely_segment") or "unknown").replace("_", " ")
    confidence = float(row.get("confidence", 0.0) or 0.0)
    expected = int(row.get("expected_start_min", 0) or 0)
    expected_time = str(row.get("expected_start_time") or "--")
    basis_days = int(row.get("basis_days", 0) or 0)
    basis_count = int(row.get("basis_event_count", 0) or 0)
    candidates = row.get("candidate_segments") or []

    lines = [
        "### STIGMERGIC PREDICTION (owner schedule prior)",
        f"- truth_label={TRUTH_LABEL}; confidence={confidence:.2f}; basis={basis_count} events across {basis_days} day(s)",
        f"- Next likely segment: {segment}; expected in ~{expected} min ({expected_time})",
        "- Use as anticipatory context only. If George says otherwise, his live voice overrides the prior.",
    ]
    if candidates:
        compact = []
        for cand in candidates[:3]:
            compact.append(
                f"{str(cand.get('segment') or 'unknown').replace('_', ' ')}"
                f"@~{int(cand.get('expected_start_min') or 0)}m"
            )
        lines.append("- Candidate field: " + "; ".join(compact))
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(write_prediction(), ensure_ascii=False, indent=2, sort_keys=True))
