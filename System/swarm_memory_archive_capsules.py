#!/usr/bin/env python3
"""Restart continuity capsules for Alice memory carryover.

Writes compact, ledger-grounded rows to:
  .sifta_state/memory_archive_capsules.jsonl

Each capsule stores:
  - timestamp
  - source
  - refs into alice_conversation.jsonl / episodic_diary.jsonl / work_receipts.jsonl

The prompt-facing formatter returns a short block that can be injected into
Alice's memory card without inventing facts.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CAPSULES = "memory_archive_capsules.jsonl"
_COMPACTION = "memory_archive_capsules_compaction.jsonl"

_CONVO = "alice_conversation.jsonl"
_DIARY = "episodic_diary.jsonl"
_RECEIPTS = "work_receipts.jsonl"

TRUTH_LABEL = "SIFTA_MEMORY_ARCHIVE_CAPSULE_V1"
COMPACTION_TRUTH_LABEL = "SIFTA_MEMORY_ARCHIVE_CAPSULE_COMPACTION_V1"
_AUTO_COMPACTION_KEEP_RECENT = 48
_AUTO_COMPACTION_MIN_BATCH = 24


def _tail_jsonl(path: Path, *, max_bytes: int = 262144) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _read_jsonl_all(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _best_ref_token(row: Dict[str, Any]) -> tuple[str, str]:
    for key in ("receipt_id", "event_id", "trace_id", "id"):
        value = str(row.get(key) or "").strip()
        if value:
            return key, value
    return "sha", hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _latest_source_ref(state_dir: Path, filename: str) -> Dict[str, Any]:
    path = state_dir / filename
    rows = _tail_jsonl(path)
    if not rows:
        return {"file": filename, "ref": f"{filename}#missing", "ts": 0.0}
    row = rows[-1]
    key, token = _best_ref_token(row)
    try:
        ts = float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    row_hash = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return {
        "file": filename,
        "ref": f"{filename}#{key}:{token}#h:{row_hash}",
        "ts": ts,
    }


def _latest_compaction(state_dir: Path) -> Dict[str, Any]:
    rows = _tail_jsonl(state_dir / _COMPACTION)
    return rows[-1] if rows else {}


def _append_compaction_row(state_dir: Path, row: Dict[str, Any]) -> None:
    path = state_dir / _COMPACTION
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _maybe_auto_compact_capsules(state_dir: Path, *, now_ts: float) -> Dict[str, Any]:
    caps_path = state_dir / _CAPSULES
    rows = _read_jsonl_all(caps_path)
    if not rows:
        return {}

    latest_comp = _latest_compaction(state_dir)
    compacted_through = int(latest_comp.get("compacted_through_line") or 0)
    total = len(rows)
    target_through = max(0, total - _AUTO_COMPACTION_KEEP_RECENT)
    if target_through <= compacted_through:
        return {}
    if (target_through - compacted_through) < _AUTO_COMPACTION_MIN_BATCH:
        return {}

    start = compacted_through
    end = target_through
    batch = rows[start:end]
    if not batch:
        return {}

    source_counts: Dict[str, int] = {}
    for row in batch:
        src = str(row.get("source") or "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    first = batch[0]
    last = batch[-1]
    refs = last.get("refs") if isinstance(last.get("refs"), dict) else {}
    capsule_ids = [
        str(r.get("capsule_id") or "")
        for r in batch
        if str(r.get("capsule_id") or "").strip()
    ]
    roll_hash = hashlib.sha256(
        "|".join(capsule_ids).encode("utf-8", errors="replace")
    ).hexdigest()[:16]
    row = {
        "ts": now_ts,
        "schema": COMPACTION_TRUTH_LABEL,
        "compaction_id": f"memcomp_{uuid.uuid4().hex[:12]}",
        "capsule_file": _CAPSULES,
        "compacted_from_line": start + 1,
        "compacted_through_line": end,
        "compacted_count": len(batch),
        "latest_total_lines_seen": total,
        "window_first_ts": float(first.get("ts") or 0.0),
        "window_last_ts": float(last.get("ts") or 0.0),
        "source_counts": source_counts,
        "window_roll_hash": roll_hash,
        "latest_refs_at_compaction": refs,
    }
    _append_compaction_row(state_dir, row)
    return row


def write_restart_capsule(
    *,
    state_dir: Optional[Path] = None,
    source: str = "talk_to_alice_widget_boot",
) -> Dict[str, Any]:
    base = Path(state_dir) if state_dir is not None else _STATE
    base.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    row = {
        "ts": ts,
        "schema": TRUTH_LABEL,
        "capsule_id": f"memcaps_{uuid.uuid4().hex[:12]}",
        "source": source,
        "refs": {
            "alice_conversation": _latest_source_ref(base, _CONVO),
            "episodic_diary": _latest_source_ref(base, _DIARY),
            "work_receipts": _latest_source_ref(base, _RECEIPTS),
        },
    }
    caps = base / _CAPSULES
    with caps.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    _maybe_auto_compact_capsules(base, now_ts=ts)
    return row


def latest_capsule(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    base = Path(state_dir) if state_dir is not None else _STATE
    rows = _tail_jsonl(base / _CAPSULES)
    if not rows:
        return {}
    return rows[-1]


def format_latest_capsule_for_prompt(*, state_dir: Optional[Path] = None) -> str:
    row = latest_capsule(state_dir=state_dir)
    if not row:
        return ""
    base = Path(state_dir) if state_dir is not None else _STATE
    comp = _latest_compaction(base)
    refs = row.get("refs") if isinstance(row.get("refs"), dict) else {}
    convo = str((refs.get("alice_conversation") or {}).get("ref") or "alice_conversation.jsonl#missing")
    diary = str((refs.get("episodic_diary") or {}).get("ref") or "episodic_diary.jsonl#missing")
    receipts = str((refs.get("work_receipts") or {}).get("ref") or "work_receipts.jsonl#missing")
    comp_ref = ""
    if comp:
        comp_ref = (
            f"- compaction_ref={_COMPACTION}#compaction_id:{comp.get('compaction_id')}"
            f"#count:{comp.get('compacted_count')}"
        )
    return (
        "RESTART CONTINUITY CAPSULE (ledger-grounded):\n"
        f"- capsule_id={row.get('capsule_id')}\n"
        f"- source={row.get('source')}\n"
        f"- ts={row.get('ts')}\n"
        f"- conversation_ref={convo}\n"
        f"- episodic_ref={diary}\n"
        f"- receipts_ref={receipts}"
        + (f"\n{comp_ref}" if comp_ref else "")
    )


__all__ = [
    "TRUTH_LABEL",
    "COMPACTION_TRUTH_LABEL",
    "write_restart_capsule",
    "latest_capsule",
    "format_latest_capsule_for_prompt",
]
