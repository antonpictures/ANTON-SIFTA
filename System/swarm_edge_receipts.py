#!/usr/bin/env python3
"""
System/swarm_edge_receipts.py
=============================

Small hash-chain helper for SIFTA edge-species ledgers.

Every fast-layer row is append-only and SHA-256 chained. The helper is kept
stdlib-only so it can run on a Jetson without pulling desktop dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from System.jsonl_file_lock import read_text_locked

try:
    import fcntl

    _HAVE_FLOCK = True
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False

try:
    from System.swarm_kernel_identity import owner_silicon
except Exception:  # pragma: no cover - Jetson bootstrap fallback
    def owner_silicon() -> str:  # type: ignore
        return "UNKNOWN"


GENESIS_HASH = "GENESIS"
HEAD_SCHEMA = "SIFTA_EDGE_CHAIN_HEAD_V1"


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_hash(data: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def chain_head_path(path: Path) -> Path:
    return path.with_name(path.name + ".head.json")


def _scan_chain_head_from_text(text: str) -> Tuple[str, int]:
    last = GENESIS_HASH
    count = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        candidate = row.get("receipt_hash") or row.get("this_hash") or row.get("hash")
        if candidate:
            last = str(candidate)
            count += 1
    return last, count


def _read_cached_head(path: Path) -> Optional[Dict[str, Any]]:
    head = chain_head_path(path)
    if not path.exists() or not head.exists():
        return None
    try:
        data = json.loads(head.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("schema") != HEAD_SCHEMA:
        return None
    if data.get("ledger_name") != path.name:
        return None
    try:
        if int(data.get("ledger_size", -1)) != path.stat().st_size:
            return None
    except Exception:
        return None
    last_hash = data.get("last_hash")
    if not last_hash:
        return None
    return data


def _write_cached_head(path: Path, row: Dict[str, Any], row_count: Optional[int] = None) -> None:
    head = chain_head_path(path)
    payload: Dict[str, Any] = {
        "schema": HEAD_SCHEMA,
        "ledger_name": path.name,
        "ledger_path": str(path),
        "last_hash": str(row.get("receipt_hash") or row.get("this_hash") or row.get("hash") or GENESIS_HASH),
        "last_trace_id": str(row.get("trace_id") or ""),
        "last_event_type": str(row.get("event_type") or row.get("type") or ""),
        "updated_ts": time.time(),
    }
    if row_count is not None:
        payload["row_count"] = int(row_count)
    try:
        payload["ledger_size"] = path.stat().st_size
    except Exception:
        payload["ledger_size"] = 0

    tmp = head.with_name(head.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, head)


def cached_receipt_hash(path: Path) -> str:
    cached = _read_cached_head(path)
    if cached:
        return str(cached["last_hash"])
    return last_receipt_hash(path)


def last_receipt_hash(path: Path) -> str:
    last = GENESIS_HASH
    for row in iter_jsonl(path):
        candidate = row.get("receipt_hash") or row.get("this_hash") or row.get("hash")
        if candidate:
            last = str(candidate)
    return last


def build_chained_row(
    *,
    source: str,
    event_type: str,
    payload: Dict[str, Any],
    state_dir: Optional[Path] = None,
    ledger_name: str,
    status: str = "ok",
    ok: bool = True,
    truth_label: str = "OPERATIONAL",
    trace_id: Optional[str] = None,
    ts: Optional[float] = None,
    previous_hash: Optional[str] = None,
) -> Dict[str, Any]:
    state_root = Path(state_dir) if state_dir is not None else Path(__file__).resolve().parent.parent / ".sifta_state"
    ledger_path = state_root / ledger_name
    row: Dict[str, Any] = {
        "schema": "SIFTA_EDGE_CHAINED_RECEIPT_V1",
        "ts": float(time.time() if ts is None else ts),
        "trace_id": trace_id or str(uuid.uuid4()),
        "source": source,
        "event_type": event_type,
        "type": event_type,
        "ok": bool(ok),
        "status": str(status),
        "truth_label": truth_label,
        "node_serial": owner_silicon(),
        "ledger_name": ledger_name,
        "previous_hash": previous_hash if previous_hash is not None else cached_receipt_hash(ledger_path),
        "payload": dict(payload or {}),
    }
    row["receipt_hash"] = stable_hash(row)
    return row


def append_chained_receipt(
    *,
    state_dir: Optional[Path] = None,
    ledger_name: str,
    source: str,
    event_type: str,
    payload: Dict[str, Any],
    status: str = "ok",
    ok: bool = True,
    truth_label: str = "OPERATIONAL",
    trace_id: Optional[str] = None,
    ts: Optional[float] = None,
) -> Dict[str, Any]:
    state_root = Path(state_dir) if state_dir is not None else Path(__file__).resolve().parent.parent / ".sifta_state"
    state_root.mkdir(parents=True, exist_ok=True)
    ledger_path = state_root / ledger_name
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    if not _HAVE_FLOCK:
        cached = _read_cached_head(ledger_path)
        if cached:
            previous_hash = str(cached["last_hash"])
            row_count = int(cached.get("row_count", 0)) + 1 if cached.get("row_count") is not None else None
        else:
            previous_hash, existing_count = _scan_chain_head_from_text(
                ledger_path.read_text(encoding="utf-8", errors="replace") if ledger_path.exists() else ""
            )
            row_count = existing_count + 1
        row = build_chained_row(
            source=source,
            event_type=event_type,
            payload=payload,
            state_dir=state_root,
            ledger_name=ledger_name,
            status=status,
            ok=ok,
            truth_label=truth_label,
            trace_id=trace_id,
            ts=ts,
            previous_hash=previous_hash,
        )
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(canonical_json(row) + "\n")
            f.flush()
        _write_cached_head(ledger_path, row, row_count=row_count)
        return row

    with ledger_path.open("a+", encoding="utf-8") as f:
        fd = f.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            cached = _read_cached_head(ledger_path)
            if cached:
                previous_hash = str(cached["last_hash"])
                row_count = int(cached.get("row_count", 0)) + 1 if cached.get("row_count") is not None else None
            else:
                f.seek(0)
                previous_hash, existing_count = _scan_chain_head_from_text(f.read())
                row_count = existing_count + 1
            row = build_chained_row(
                source=source,
                event_type=event_type,
                payload=payload,
                state_dir=state_root,
                ledger_name=ledger_name,
                status=status,
                ok=ok,
                truth_label=truth_label,
                trace_id=trace_id,
                ts=ts,
                previous_hash=previous_hash,
            )
            f.seek(0, os.SEEK_END)
            f.write(canonical_json(row) + "\n")
            f.flush()
            _write_cached_head(ledger_path, row, row_count=row_count)
            return row
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    return row


def verify_chained_ledger(path: Path) -> Dict[str, Any]:
    previous = GENESIS_HASH
    count = 0
    errors = []
    for index, row in enumerate(iter_jsonl(path), start=1):
        if "receipt_hash" not in row:
            continue
        count += 1
        if row.get("previous_hash") != previous:
            errors.append({"line": index, "error": "previous_hash_mismatch"})
        observed = str(row.get("receipt_hash") or "")
        body = dict(row)
        body.pop("receipt_hash", None)
        expected = stable_hash(body)
        if observed != expected:
            errors.append({"line": index, "error": "receipt_hash_mismatch"})
        previous = observed
    return {
        "ledger": str(path),
        "row_count": count,
        "ok": not errors,
        "errors": errors,
        "last_hash": previous,
    }


__all__ = [
    "GENESIS_HASH",
    "append_chained_receipt",
    "build_chained_row",
    "cached_receipt_hash",
    "canonical_json",
    "chain_head_path",
    "iter_jsonl",
    "last_receipt_hash",
    "stable_hash",
    "verify_chained_ledger",
]
