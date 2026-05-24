#!/usr/bin/env python3
"""
System/swarm_visibility.py
==========================
BeeSon-native visibility provider for the SIFTA field.

The old white app only sketched a visibility surface. This module exposes the
real data shape a Qt app can render: organ ledger health, recent field rows,
STGM flow, and active IDE swimmers inferred from registration receipts.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_REPO_STATE = _REPO / ".sifta_state"

ORGAN_LEDGERS: dict[str, str] = {
    "owner_genesis": "owner_genesis.json",
    "terminal": "terminal_organ.jsonl",
    "file": "file_organ.jsonl",
    "web": "web_organ.jsonl",
    "tool_router": "tool_router_trace.jsonl",
    "app_focus": "app_focus.jsonl",
    "conversation": "alice_conversation.jsonl",
    "ide_bus": "ide_stigmergic_trace.jsonl",
    "skills": "nanobot_skill_receipts.jsonl",
    "metabolism": "metabolic_homeostasis.jsonl",
    "organ_field": "organ_field_vector.jsonl",
}

FIELD_LEDGERS: tuple[str, ...] = (
    "ide_stigmergic_trace.jsonl",
    "tool_router_trace.jsonl",
    "basal_ganglia_selections.jsonl",
    "alice_conversation.jsonl",
    "app_focus.jsonl",
)

_TAIL_READ_BYTES = 512 * 1024
_COUNT_EXACT_MAX_BYTES = 1024 * 1024
_HEAD_HASH_BYTES = 256 * 1024


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    cwd_state = Path.cwd() / ".sifta_state"
    if cwd_state.exists():
        return cwd_state
    return _REPO_STATE


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_tail_bytes(path: Path, max_bytes: int = _TAIL_READ_BYTES) -> bytes:
    if not path.exists():
        return b""
    try:
        size = path.stat().st_size
        read_size = max(1, int(max_bytes))
        offset = max(0, size - read_size)
        with path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read(read_size)
    except Exception:
        return b""
    if offset > 0:
        first_newline = chunk.find(b"\n")
        if first_newline >= 0:
            chunk = chunk[first_newline + 1 :]
    return chunk


def _jsonl_rows(
    path: Path,
    limit: int | None = None,
    *,
    max_bytes: int = _TAIL_READ_BYTES,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        if limit and limit > 0:
            tail = _read_tail_bytes(path, max_bytes=max_bytes).decode("utf-8", errors="replace")
            lines = [line.strip() for line in tail.splitlines() if line.strip()]
        else:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                lines = [line.strip() for line in fh if line.strip()]
    except Exception:
        return []
    selected = lines[-limit:] if limit and limit > 0 else lines
    for line in selected:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return rows


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        size = path.stat().st_size
        if size > _COUNT_EXACT_MAX_BYTES:
            data = _read_tail_bytes(path, max_bytes=_COUNT_EXACT_MAX_BYTES)
            return sum(1 for line in data.splitlines() if line.strip())
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for line in fh if line.strip())
    except Exception:
        return 0


def _row_ts(row: dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "created_at", "time"):
        try:
            return float(row.get(key, 0.0) or 0.0)
        except Exception:
            continue
    return 0.0


def _row_type(row: dict[str, Any]) -> str:
    for key in ("type", "kind", "event", "action", "status"):
        value = row.get(key)
        if value:
            return str(value)
    payload = row.get("payload")
    if isinstance(payload, dict):
        for key in ("type", "kind", "event", "action", "status"):
            value = payload.get(key)
            if value:
                return str(value)
    return "UNKNOWN"


def _head_for_path(path: Path, last_row: dict[str, Any] | None = None) -> str:
    if last_row:
        for key in ("hash", "receipt_hash", "chain_hash", "trace_hash"):
            value = last_row.get(key)
            if value:
                return str(value)[:16]
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        data = _read_tail_bytes(path, max_bytes=_HEAD_HASH_BYTES)
    except Exception:
        return ""
    if not data:
        return ""
    h = hashlib.sha256()
    h.update(str(size).encode("ascii", errors="ignore"))
    h.update(b"\0")
    h.update(data)
    return h.hexdigest()[:16]


def _health_for(last_row: dict[str, Any] | None, row_count: int, age_s: float | None) -> str:
    if row_count <= 0:
        return "red"
    if last_row:
        row_type = _row_type(last_row).upper()
        text = json.dumps(last_row, sort_keys=True, default=str).upper()
        if "FAIL" in row_type or "ERROR" in row_type or "CRITICAL" in text:
            return "red"
        if "WARN" in row_type or "WARNING" in text:
            return "yellow"
    if age_s is not None and age_s > 3600:
        return "yellow"
    return "green"


def organ_status(state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return health summaries for known SIFTA organ ledgers."""
    state = _state_dir(state_dir)
    now = time.time()
    out: list[dict[str, Any]] = []
    for organ, ledger in ORGAN_LEDGERS.items():
        path = state / ledger
        exists = path.exists()
        last_row: dict[str, Any] | None = None
        if path.suffix == ".json":
            data = _read_json_file(path) if exists else None
            row_count = 1 if data else 0
            last_row = data if isinstance(data, dict) else None
        else:
            row_count = _jsonl_count(path)
            rows = _jsonl_rows(path, limit=1)
            last_row = rows[-1] if rows else None
        try:
            file_bytes = path.stat().st_size if exists else 0
        except OSError:
            file_bytes = 0

        ts = _row_ts(last_row or {})
        age_s = round(now - ts, 3) if ts > 0 else None
        health = "yellow" if organ == "owner_genesis" and row_count == 0 else _health_for(last_row, row_count, age_s)
        out.append(
            {
                "organ": organ,
                "ledger": ledger,
                "exists": exists,
                "row_count": row_count,
                "row_count_basis": "tail" if file_bytes > _COUNT_EXACT_MAX_BYTES and path.suffix != ".json" else "exact",
                "file_bytes": int(file_bytes),
                "health": health,
                "head": _head_for_path(path, last_row),
                "last_type": _row_type(last_row or {}) if last_row else "",
                "age_s": age_s,
            }
        )
    return out


def field_recent(limit: int = 40, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return recent rows from the shared field ledgers in time order."""
    state = _state_dir(state_dir)
    rows: list[dict[str, Any]] = []
    per_ledger = max(1, int(limit or 40))
    for ledger in FIELD_LEDGERS:
        path = state / ledger
        for row in _jsonl_rows(path, limit=per_ledger):
            item = dict(row)
            item.setdefault("type", _row_type(row))
            item["ledger"] = ledger
            item["_sort_ts"] = _row_ts(row)
            rows.append(item)
    rows.sort(key=lambda r: (float(r.get("_sort_ts") or 0.0), str(r.get("ledger", ""))))
    for row in rows:
        row.pop("_sort_ts", None)
    return rows[-limit:] if limit and limit > 0 else rows


def stgm_flow(limit: int = 20, state_dir: str | Path | None = None) -> dict[str, Any]:
    """Return recent STGM ledger entries and the latest observed balance."""
    state = _state_dir(state_dir)
    entries = _jsonl_rows(state / "stgm_ledger.jsonl", limit=limit)
    current_balance: float | None = None
    for row in reversed(entries):
        for key in ("balance_after", "balance", "canonical_wallet_sum", "wallet_balance"):
            if key in row:
                try:
                    current_balance = float(row[key])
                    break
                except Exception:
                    continue
        if current_balance is not None:
            break
    return {
        "current_balance": current_balance,
        "entries": entries,
        "entry_count": len(entries),
        "source": "stgm_ledger.jsonl",
    }


def _doctor_from(row: dict[str, Any]) -> str:
    for scope in (row, row.get("payload") if isinstance(row.get("payload"), dict) else {}, row.get("meta") if isinstance(row.get("meta"), dict) else {}):
        if not isinstance(scope, dict):
            continue
        for key in ("doctor", "doctor_name", "source_ide", "agent", "name"):
            value = scope.get(key)
            if value:
                return str(value)
    return "unknown"


def _field_from(row: dict[str, Any], key: str, default: str = "") -> str:
    for scope in (row, row.get("payload") if isinstance(row.get("payload"), dict) else {}, row.get("meta") if isinstance(row.get("meta"), dict) else {}):
        if isinstance(scope, dict) and scope.get(key):
            return str(scope[key])
    return default


def active_swimmers(limit: int = 80, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return IDE doctors with live registration rows on the bus."""
    state = _state_dir(state_dir)
    latest_by_doctor: dict[str, dict[str, Any]] = {}
    for row in _jsonl_rows(state / "ide_stigmergic_trace.jsonl", limit=limit):
        if _row_type(row).upper() != "LLM_REGISTRATION":
            continue
        doctor = _doctor_from(row)
        item = {
            "doctor": doctor,
            "model": _field_from(row, "model", ""),
            "lane": _field_from(row, "lane", _field_from(row, "role", "")),
            "trace_id": _field_from(row, "trace_id", ""),
            "ts": _row_ts(row),
        }
        prev = latest_by_doctor.get(doctor)
        if prev is None or item["ts"] >= float(prev.get("ts") or 0.0):
            latest_by_doctor[doctor] = item
    return sorted(latest_by_doctor.values(), key=lambda r: (float(r.get("ts") or 0.0), r.get("doctor", "")))


def full_snapshot(state_dir: str | Path | None = None) -> dict[str, Any]:
    """Return one complete visibility snapshot for UI rendering."""
    snapshot_ts = time.time()
    return {
        "organs": organ_status(state_dir),
        "field": field_recent(40, state_dir),
        "stgm": stgm_flow(20, state_dir),
        "swimmers": active_swimmers(120, state_dir),
        "snapshot_ts": snapshot_ts,
        "ts": snapshot_ts,
    }


__all__ = [
    "ORGAN_LEDGERS",
    "FIELD_LEDGERS",
    "active_swimmers",
    "field_recent",
    "full_snapshot",
    "organ_status",
    "stgm_flow",
]
