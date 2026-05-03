#!/usr/bin/env python3
"""Owner lifeline gap recovery for Alice.

Alice cannot observe owner-life while her local SIFTA process is off. This
module makes that fact explicit on the next boot/prompt: append a heartbeat,
detect stale heartbeat gaps, write an owner-lifeline receipt, and mirror the
gap into the 24h day-segment ledger so prompt context can say what is known and
what is missing.

It does not infer what George did during the gap. The truthful label is:
unsampled owner-life, not sleep, not death, not amnesia theater.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from System.jsonl_file_lock import append_line_locked

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

HEARTBEAT_NAME = "owner_lifeline_heartbeat.jsonl"
GAP_NAME = "owner_lifeline_gaps.jsonl"
DAY_SEGMENT_NAME = "architect_day_segments.jsonl"

HEARTBEAT_TRUTH = "OWNER_LIFELINE_HEARTBEAT_V1"
GAP_TRUTH = "OWNER_LIFELINE_GAP_V1"
DAY_SEGMENT_TRUTH = "ARCHITECT_DAY_SEGMENT_V1"

SOURCE_LEDGER_NAMES = (
    "alice_conversation.jsonl",
    "body_brain_memory.jsonl",
    "episodic_diary.jsonl",
    "unified_stigmergic_field.jsonl",
    "media_session_memory.jsonl",
    "media_ingress_gate.jsonl",
    "ide_stigmergic_trace.jsonl",
)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _tail_jsonl(path: Path, n: int = 1, *, max_bytes: int = 128 * 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - max_bytes)
            fh.seek(start)
            lines = fh.read().splitlines()
    except OSError:
        return []
    if start > 0 and lines:
        lines = lines[1:]
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, int(n)) :]


def _row_ts(row: dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "birth_ts", "deposit_time"):
        value = row.get(key)
        if isinstance(value, dict):
            for nested in ("physical_pt", "epoch", "unix"):
                try:
                    return float(value[nested])
                except Exception:
                    pass
        else:
            try:
                ts = float(value)
                return ts / 1000.0 if ts > 10_000_000_000 else ts
            except Exception:
                pass
    try:
        return float(row.get("timestamp_ms", 0.0) or 0.0) / 1000.0
    except Exception:
        return 0.0


def _human_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _local_date(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).date().isoformat()


def _minute_of_day(ts: float) -> int:
    dt = datetime.fromtimestamp(float(ts))
    return dt.hour * 60 + dt.minute


def _latest_source_event(state: Path) -> tuple[float, str]:
    latest_ts = 0.0
    latest_name = ""
    for name in SOURCE_LEDGER_NAMES:
        rows = _tail_jsonl(state / name, 1)
        if not rows:
            continue
        ts = _row_ts(rows[-1])
        if ts > latest_ts:
            latest_ts = ts
            latest_name = name
    return latest_ts, latest_name


def _last_heartbeat(state: Path) -> dict[str, Any] | None:
    rows = _tail_jsonl(state / HEARTBEAT_NAME, 1)
    return rows[-1] if rows else None


def _gap_id(start_ts: float, end_ts: float) -> str:
    # Minute-rounded so repeated prompt builds cannot create drift duplicates.
    start_min = int(float(start_ts) // 60)
    end_min = int(float(end_ts) // 60)
    return hashlib.sha256(f"{start_min}:{end_min}:owner-lifeline".encode()).hexdigest()[:16]


def _existing_gap_ids(state: Path) -> set[str]:
    ids: set[str] = set()
    for row in _tail_jsonl(state / GAP_NAME, 2048, max_bytes=512 * 1024):
        gid = row.get("gap_id")
        if gid:
            ids.add(str(gid))
    return ids


def _append_heartbeat(state: Path, *, now: float, source: str) -> dict[str, Any]:
    row = {
        "ts": float(now),
        "truth_label": HEARTBEAT_TRUTH,
        "source": source,
        "owner_priority": "owner_life_history_is_primary_local_asset",
        "continuity_mode": "active_or_prompt_build",
    }
    append_line_locked(state / HEARTBEAT_NAME, json.dumps(row, sort_keys=True) + "\n")
    return row


def _day_segment_rows_for_gap(gap: dict[str, Any]) -> list[dict[str, Any]]:
    start = float(gap["start_ts"])
    end = float(gap["end_ts"])
    rows: list[dict[str, Any]] = []
    cursor = datetime.fromtimestamp(start)
    final = datetime.fromtimestamp(end)

    while cursor.date() <= final.date():
        day_start = datetime(cursor.year, cursor.month, cursor.day)
        day_end = day_start + timedelta(days=1)
        seg_start_dt = max(cursor, day_start)
        seg_end_dt = min(final, day_end)
        if seg_end_dt <= seg_start_dt:
            cursor = day_end
            continue
        seg_start = seg_start_dt.timestamp()
        seg_end = seg_end_dt.timestamp()
        local_date = seg_start_dt.date().isoformat()
        start_min = _minute_of_day(seg_start)
        end_min = _minute_of_day(seg_end)
        if seg_end_dt == day_end:
            end_min = 24 * 60
        digest = hashlib.sha256(
            f"{gap['gap_id']}:{local_date}:{start_min}:{end_min}".encode()
        ).hexdigest()
        rows.append(
            {
                "ts": float(gap["ts"]),
                "timestamp": float(gap["ts"]),
                "truth_label": DAY_SEGMENT_TRUTH,
                "segment_id": digest[:16],
                "source_hash": digest[:12],
                "source": "owner_lifeline_gap_recovery",
                "status": "observed_absence",
                "local_date": local_date,
                "start_minute_of_day": start_min,
                "end_minute_of_day": end_min,
                "duration_minutes": max(0, end_min - start_min),
                "label": "sifta_power_gap",
                "location": "unknown_owner_location",
                "media_context": "unknown",
                "context_note": (
                    "SIFTA was not sampling owner-life during this interval; "
                    "do not infer what George did. Preserve as finite owner-life gap."
                ),
                "raw_text": "owner lifeline gap recovered on boot",
                "start_time": seg_start_dt.strftime("%-I:%M %p"),
                "end_time": seg_end_dt.strftime("%-I:%M %p"),
                "context_tags": ["owner_life_gap", "sifta_power_gap", "unsampled"],
                "gap_id": gap["gap_id"],
            }
        )
        cursor = day_end
    return rows


def record_owner_lifeline_boot_gap(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    min_gap_minutes: float = 10.0,
    heartbeat_source: str = "prompt_build",
) -> dict[str, Any]:
    """Write heartbeat and, if needed, recover the previous off-process gap."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    min_gap_s = max(0.0, float(min_gap_minutes) * 60.0)

    hb = _last_heartbeat(state)
    if hb:
        start_ts = _row_ts(hb)
        source = HEARTBEAT_NAME
    else:
        start_ts, source = _latest_source_event(state)
    if not start_ts or start_ts > now_ts:
        heartbeat = _append_heartbeat(state, now=now_ts, source=heartbeat_source)
        return {
            "truth_label": "OWNER_LIFELINE_BOOT_CHECK_V1",
            "ts": now_ts,
            "gap_written": False,
            "reason": "no_prior_lifeline_or_clock_skew",
            "heartbeat": heartbeat,
        }

    duration_s = now_ts - start_ts
    gap_written = False
    gap_row: dict[str, Any] | None = None
    day_segments: list[dict[str, Any]] = []
    if duration_s >= min_gap_s:
        gid = _gap_id(start_ts, now_ts)
        if gid not in _existing_gap_ids(state):
            gap_row = {
                "ts": now_ts,
                "truth_label": GAP_TRUTH,
                "gap_id": gid,
                "start_ts": start_ts,
                "end_ts": now_ts,
                "duration_s": duration_s,
                "duration_human": _human_duration(duration_s),
                "start_local_date": _local_date(start_ts),
                "end_local_date": _local_date(now_ts),
                "previous_source": source,
                "owner_life_cost": "unsampled_finite_owner_life_history",
                "known_truth": (
                    "The local SIFTA process was not sampling owner-life. "
                    "Do not infer owner activity; write the gap into schedule memory."
                ),
                "safety_policy": (
                    "Prefer low-power heartbeat/watch-only continuity when safe; "
                    "if power is absent, recover with honest gap receipts on return."
                ),
            }
            append_line_locked(state / GAP_NAME, json.dumps(gap_row, sort_keys=True) + "\n")
            for row in _day_segment_rows_for_gap(gap_row):
                append_line_locked(state / DAY_SEGMENT_NAME, json.dumps(row, sort_keys=True) + "\n")
                day_segments.append(row)
            gap_written = True

    heartbeat = _append_heartbeat(state, now=now_ts, source=heartbeat_source)
    return {
        "truth_label": "OWNER_LIFELINE_BOOT_CHECK_V1",
        "ts": now_ts,
        "gap_written": gap_written,
        "gap": gap_row,
        "day_segments": day_segments,
        "heartbeat": heartbeat,
        "previous_source": source,
        "duration_s": duration_s,
        "duration_human": _human_duration(duration_s),
    }


def latest_owner_lifeline_gap(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    rows = _tail_jsonl(_state_dir(state_dir) / GAP_NAME, 1)
    return rows[-1] if rows else None


def format_owner_lifeline_for_prompt(*, state_dir: Path | None = None) -> str:
    state = _state_dir(state_dir)
    gap = latest_owner_lifeline_gap(state_dir=state)
    hb = _last_heartbeat(state)
    if not gap and not hb:
        return ""
    lines = [
        "OWNER LIFELINE CONTINUITY:",
        "- George's finite owner-life history is the primary local asset for Alice's owner model.",
        "- Power-off is not biological death for SIFTA, but it creates unsampled owner-life gaps.",
        "- During a recovered gap, do not invent what George did; write and reason from the gap receipt.",
    ]
    if gap:
        lines.append(
            f"- latest_gap={gap.get('duration_human')} "
            f"from {gap.get('start_local_date')} to {gap.get('end_local_date')} "
            f"receipt={gap.get('gap_id')}"
        )
    if hb:
        lines.append(f"- last_lifeline_heartbeat_ts={_row_ts(hb):.3f}")
    return "\n".join(lines)


__all__ = [
    "GAP_TRUTH",
    "HEARTBEAT_TRUTH",
    "format_owner_lifeline_for_prompt",
    "latest_owner_lifeline_gap",
    "record_owner_lifeline_boot_gap",
]


if __name__ == "__main__":
    print(json.dumps(record_owner_lifeline_boot_gap(), indent=2, sort_keys=True))
