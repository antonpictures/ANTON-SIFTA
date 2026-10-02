#!/usr/bin/env python3
"""
world_awareness.py — hash-chained ledger for Alice's sense loop (camera/audio/web).

Append-only JSONL under .sifta_state. Each row includes prev_hash so receipts are
tamper-evident. Used by the coin-site sense loop (Test A "did the room change?").
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:
    append_line_locked = None  # fallback only

TRUTH_LABEL = "WORLD_AWARENESS_LEDGER_V1"
_STATE = Path(__file__).resolve().parents[1] / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

LEDGER_PATH = _STATE / "world_awareness.jsonl"
_last_hash = None


def _read_last_hash() -> Optional[str]:
    if not LEDGER_PATH.exists():
        return None
    try:
        with open(LEDGER_PATH, "r") as f:
            line = f.readlines()[-1].strip()
            entry = json.loads(line)
            return entry.get("hash")
    except (IOError, json.JSONDecodeError, IndexError):
        return None


def append_trace(
    source: str,
    kind: str,
    text: str,
    image_id: Optional[str] = None,
    confidence: float = 1.0,
    receipt_url: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a new sense trace to the ledger; return the written row."""
    global _last_hash
    _last_hash = _read_last_hash()

    row: Dict[str, Any] = {
        "ts": time.time(),
        "source": source,
        "kind": kind,
        "text": text,
        "image_id": image_id,
        "confidence": confidence,
        "receipt_url": receipt_url,
        "extra": extra or {},
        "truth_label": TRUTH_LABEL,
        "prev_hash": _last_hash,
    }

    # Compute hash over the canonical fields (not the hash itself)
    canonical = json.dumps({k: row[k] for k in ["ts", "source", "kind", "text", "image_id", "confidence"]}, sort_keys=True)
    row["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    _last_hash = row["hash"]

    if append_line_locked:
        # append_line_locked does NOT add the trailing newline (caller supplies it)
        append_line_locked(LEDGER_PATH, json.dumps(row) + "\n")
    else:
        with open(LEDGER_PATH, "a") as f:
            f.write(json.dumps(row) + "\n")

    return row


def read_traces(since_ts: Optional[float] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent traces, newest first."""
    rows = []
    if not LEDGER_PATH.exists():
        return rows
    with open(LEDGER_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rows.reverse()
    if since_ts:
        rows = [r for r in rows if r.get("ts", 0) >= since_ts]
    return rows[:limit]


def detect_room_change(now: Dict[str, Any], prev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compare two consecutive vision descriptions. If they differ substantially,
    return a new 'room_change' trace. (Simple diff for the first pass; later
    versions can use semantic similarity.)
    """
    if not now or not prev:
        return None
    now_text = now.get("text", "")
    prev_text = prev.get("text", "")
    if now_text == prev_text:
        return None
    # Simple heuristic: length change or key words
    if abs(len(now_text) - len(prev_text)) > 5 or set(now_text) != set(prev_text):
        return append_trace(
            source="camera",
            kind="room_change",
            text=f"Delta from: {prev_text} → {now_text}",
            extra={"previous": prev_text, "current": now_text},
        )
    return None


def get_recent_room_changes(limit: int = 10) -> List[Dict[str, Any]]:
    return [r for r in read_traces(limit=200) if r.get("kind") == "room_change"][:limit]
