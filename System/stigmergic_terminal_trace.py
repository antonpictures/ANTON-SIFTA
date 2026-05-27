#!/usr/bin/env python3
"""Append-only stigmergic terminal trace ledger.

This module is deliberately pure stdlib and PyQt-free so every SIFTA surface,
test runner, and agent arm can record terminal-state pheromones without pulling
in widget code. It is a small reusable organ for terminal-as-field work.
"""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any
from uuid import uuid4


REPO = Path(__file__).resolve().parent.parent
TRACE_PATH = REPO / ".sifta_state" / "stigmergic_terminal_trace.jsonl"
_FALLBACK_PATH = Path(tempfile.gettempdir()) / "sifta_stigmergic_terminal_trace_fallback.jsonl"


def _coerce_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    return {"value": payload}


def _row(
    kind: str,
    payload: dict[str, Any],
    *,
    ide: str,
    model: str,
    homeworld_serial: str,
    row_id: str | None = None,
    ts: float | None = None,
) -> dict[str, Any]:
    return {
        "id": row_id or str(uuid4()),
        "ts": float(time.time() if ts is None else ts),
        "kind": str(kind or "unknown"),
        "payload": _coerce_payload(payload),
        "ide": str(ide or "unknown"),
        "model": str(model or "unknown"),
        "homeworld_serial": str(homeworld_serial or "unknown"),
    }


def _append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_terminal_trace(
    kind: str,
    payload: dict[str, Any],
    *,
    ide: str,
    model: str,
    homeworld_serial: str = "GTH4921YP3",
) -> str:
    """Append one stigmergic terminal trace row. Returns the row id."""
    row = _row(
        kind,
        payload,
        ide=ide,
        model=model,
        homeworld_serial=homeworld_serial,
    )
    try:
        _append_row(Path(TRACE_PATH), row)
        return str(row["id"])
    except OSError as exc:
        failure = _row(
            "trace_write_failed",
            {
                "error": f"{type(exc).__name__}: {exc}",
                "original_kind": str(kind or "unknown"),
                "original_payload": _coerce_payload(payload),
                "target_path": str(TRACE_PATH),
            },
            ide=ide,
            model=model,
            homeworld_serial=homeworld_serial,
        )
        try:
            fallback = Path(os.environ.get("SIFTA_TERMINAL_TRACE_FALLBACK", str(_FALLBACK_PATH)))
            _append_row(fallback, failure)
        except OSError as fallback_exc:
            print(
                "stigmergic_terminal_trace fallback failed: "
                f"{type(fallback_exc).__name__}: {fallback_exc}",
                file=sys.stderr,
            )
        return str(failure["id"])


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def tail_recent_rows(n: int = 20) -> list[dict[str, Any]]:
    """Return the last n rows as parsed dicts. Empty list if file absent."""
    if n <= 0:
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=int(n))
    for row in _read_rows(Path(TRACE_PATH)):
        rows.append(row)
    return list(rows)


def find_by_kind(kind: str, *, since_ts: float | None = None) -> list[dict[str, Any]]:
    """Return rows matching kind and optionally newer than or equal to since_ts."""
    wanted = str(kind or "")
    found: list[dict[str, Any]] = []
    for row in _read_rows(Path(TRACE_PATH)):
        if str(row.get("kind") or "") != wanted:
            continue
        if since_ts is not None:
            try:
                if float(row.get("ts", 0.0)) < float(since_ts):
                    continue
            except (TypeError, ValueError):
                continue
        found.append(row)
    return found


__all__ = [
    "TRACE_PATH",
    "append_terminal_trace",
    "tail_recent_rows",
    "find_by_kind",
]
