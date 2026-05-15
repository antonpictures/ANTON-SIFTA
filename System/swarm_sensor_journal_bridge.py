#!/usr/bin/env python3
"""Sensor-to-journal bridge.

This background-friendly organ converts noisy sensor ledgers into clean,
timestamped journal and schedule receipts. It is deterministic and conservative:
no LLM inference, no raw media copy, and no low-confidence spam.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from datetime import datetime
from typing import Any

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

SOURCE_LEDGERS = (
    "visual_stigmergy.jsonl",
    "app_focus.jsonl",
    "owner_body_events.jsonl",
    "alice_ble_radar.jsonl",
    "audio_ingress_log.jsonl",
)
JOURNAL_LEDGER = "alice_life_journal.jsonl"
SCHEDULE_LEDGER = "stigmergic_schedule_receipts.jsonl"
BRIDGE_LEDGER = "sensor_journal_bridge_receipts.jsonl"
SCHEMA = "SIFTA_SENSOR_JOURNAL_BRIDGE_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _local_journal_label(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).strftime("%m-%d-%y_%H:%M")


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _tail_jsonl(path: Path, n: int = 20) -> list[dict[str, Any]]:
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows = []
    for line in text.splitlines()[-n:]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _short(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def _event_ts(row: dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "ts_captured"):
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            continue
    return time.time()


def _confidence(source: str, row: dict[str, Any], *, now: float) -> float:
    age = max(0.0, now - _event_ts(row))
    freshness = 1.0 if age <= 120 else max(0.0, 1.0 - (age / 3600.0))
    if source == "visual_stigmergy.jsonl":
        has_frame = bool(row.get("sha8") or row.get("frame_sha256") or (row.get("w") and row.get("h")))
        return 0.8 * freshness if has_frame else 0.35 * freshness
    if source == "app_focus.jsonl":
        return 0.9 * freshness if row.get("app") or row.get("detail") else 0.3 * freshness
    if source == "owner_body_events.jsonl":
        return 0.85 * freshness if row.get("event") or row.get("kind") or row.get("body_event") else 0.4 * freshness
    if source == "alice_ble_radar.jsonl":
        return 0.7 * freshness if row else 0.0
    if source == "audio_ingress_log.jsonl":
        try:
            rms = float(row.get("rms_amplitude") or 0.0)
        except (TypeError, ValueError):
            rms = 0.0
        return min(0.75, 0.35 + rms * 8.0) * freshness
    return 0.0


def _journal_text(source: str, row: dict[str, Any]) -> str:
    if source == "app_focus.jsonl":
        return f"Owner focus: {_short(row.get('app'))} {_short(row.get('detail'))}".strip()
    if source == "visual_stigmergy.jsonl":
        frame = f"{row.get('w', '?')}x{row.get('h', '?')}"
        proof = row.get("sha8") or row.get("frame_sha256") or row.get("source_sha8") or "unhashed"
        return f"Visual stigmergy frame observed: {frame} proof={_short(proof, 32)}"
    if source == "owner_body_events.jsonl":
        return f"Owner body event: {_short(row.get('event') or row.get('kind') or row.get('body_event') or row)}"
    if source == "alice_ble_radar.jsonl":
        return f"BLE proximity/radar receipt: {_short(row)}"
    if source == "audio_ingress_log.jsonl":
        return f"Audio ingress energy receipt: rms={row.get('rms_amplitude')} device={_short(row.get('device_name'), 80)}"
    return _short(row)


def _schedule_kind(source: str, row: dict[str, Any]) -> str:
    text = json.dumps(row, ensure_ascii=False, default=str).casefold()
    if source == "app_focus.jsonl":
        return "owner_activity_context"
    if "call" in text or "meeting" in text or "schedule" in text or "appointment" in text:
        return "schedule_relevant"
    if source == "owner_body_events.jsonl":
        return "owner_body_context"
    return "ambient_context"


def _seen_hashes(state: Path) -> set[str]:
    seen = set()
    for path_name in (JOURNAL_LEDGER, BRIDGE_LEDGER):
        for row in _tail_jsonl(state / path_name, n=1000):
            if row.get("source_hash"):
                seen.add(str(row["source_hash"]))
    return seen


def collect_sensor_journal_events(
    *,
    state_dir: Path | str | None = None,
    max_per_source: int = 5,
    min_confidence: float = 0.6,
    now: float | None = None,
) -> list[dict[str, Any]]:
    state = _state_dir(state_dir)
    ts_now = time.time() if now is None else float(now)
    events = []
    seen = _seen_hashes(state)
    for source in SOURCE_LEDGERS:
        for row in _tail_jsonl(state / source, n=max_per_source):
            source_hash = _sha({"source": source, "row": row})
            if source_hash in seen:
                continue
            conf = _confidence(source, row, now=ts_now)
            if conf < min_confidence:
                continue
            events.append(
                {
                    "ts": ts_now,
                    "schema": SCHEMA,
                    "truth_label": "SENSOR_JOURNAL_EVENT",
                    "source_ledger": source,
                    "source_hash": source_hash,
                    "event_ts": _event_ts(row),
                    "confidence": round(conf, 4),
                    "journal_text": _journal_text(source, row),
                    "schedule_kind": _schedule_kind(source, row),
                }
            )
    events.sort(key=lambda e: (e["event_ts"], e["source_ledger"]))
    return events


def run_sensor_journal_bridge(
    *,
    state_dir: Path | str | None = None,
    max_per_source: int = 5,
    min_confidence: float = 0.6,
    now: float | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    events = collect_sensor_journal_events(
        state_dir=state,
        max_per_source=max_per_source,
        min_confidence=min_confidence,
        now=now,
    )
    for event in events:
        journal = {
            **event,
            "local_journal_label": _local_journal_label(float(event["ts"])),
            "truth_label": "ALICE_LIFE_JOURNAL_ENTRY",
            "writer": "swarm_sensor_journal_bridge",
        }
        schedule = {
            "ts": event["ts"],
            "schema": SCHEMA,
            "truth_label": "STIGMERGIC_SCHEDULE_RECEIPT",
            "source_hash": event["source_hash"],
            "source_ledger": event["source_ledger"],
            "kind": event["schedule_kind"],
            "summary": event["journal_text"],
            "confidence": event["confidence"],
        }
        append_line_locked(state / JOURNAL_LEDGER, json.dumps(journal, ensure_ascii=False, sort_keys=True) + "\n")
        append_line_locked(state / SCHEDULE_LEDGER, json.dumps(schedule, ensure_ascii=False, sort_keys=True) + "\n")
    receipt = {
        "ts": time.time() if now is None else float(now),
        "schema": SCHEMA,
        "truth_label": "SENSOR_JOURNAL_BRIDGE_RUN",
        "events_written": len(events),
        "source_ledgers": list(SOURCE_LEDGERS),
        "journal_ledger": JOURNAL_LEDGER,
        "schedule_ledger": SCHEDULE_LEDGER,
    }
    append_line_locked(state / BRIDGE_LEDGER, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    return {"receipt": receipt, "events": events}


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    state = _state_dir(state_dir)
    rows = _tail_jsonl(state / BRIDGE_LEDGER, n=1)
    if not rows:
        return ""
    row = rows[-1]
    return (
        "SENSOR JOURNAL BRIDGE:\n"
        f"- last_run_events={row.get('events_written')} journal={row.get('journal_ledger')} "
        f"schedule={row.get('schedule_ledger')}"
    )


__all__ = [
    "SCHEMA",
    "collect_sensor_journal_events",
    "run_sensor_journal_bridge",
    "summary_for_prompt",
]
