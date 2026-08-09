#!/usr/bin/env python3
"""Observer-window ticks — Lane contract: trace (zero-surprise).

Each bounded observer window owns a monotonic counter.  A tick receipt records
both ``ts`` and ``tick_count`` so a quiet/stalled window is distinguishable
from one that simply has no interesting result.  Callers may rate-limit a
window; skipped display refreshes never pretend to be new observations.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict

from System.jsonl_file_lock import append_line_locked, read_write_json_locked

TRUTH_LABEL = "OBSERVER_WINDOW_TICK_V1"
COUNTERS_NAME = "observer_window_tick_counters.json"
LEDGER_NAME = "observer_window_ticks.jsonl"
_WINDOW_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")


def _state_path(state_dir: Path | str, name: str) -> Path:
    return Path(state_dir) / name


def record_observer_tick(
    window: str,
    *,
    state_dir: Path | str,
    now: float | None = None,
    min_interval_s: float = 0.0,
    detail: str = "",
) -> Dict[str, Any]:
    """Atomically advance one observer window and append its receipt.

    If the window was sampled more recently than ``min_interval_s``, returns
    the last count with ``written=False``.  This lets fast UI redraws remain
    observable without turning every paint into an artificial heartbeat.
    """
    name = str(window or "").strip().lower()
    if not _WINDOW_RE.fullmatch(name):
        raise ValueError("window must be a short lowercase observer id")
    stamp = float(now if now is not None else time.time())
    counters = _state_path(state_dir, COUNTERS_NAME)
    prior: Dict[str, Any] = {}

    def advance(data: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal prior
        windows = data.get("windows") if isinstance(data.get("windows"), dict) else {}
        old = windows.get(name) if isinstance(windows.get(name), dict) else {}
        prior = dict(old)
        last_ts = float(old.get("ts") or 0.0)
        if last_ts and stamp - last_ts < max(0.0, float(min_interval_s)):
            data["windows"] = windows
            return data
        windows[name] = {"tick_count": int(old.get("tick_count") or 0) + 1, "ts": stamp}
        data["windows"] = windows
        return data

    updated = read_write_json_locked(counters, advance)
    current = dict((updated.get("windows") or {}).get(name) or {})
    written = current != prior
    row: Dict[str, Any] = {
        "ts": float(current.get("ts") or stamp),
        "window": name,
        "tick_count": int(current.get("tick_count") or 0),
        "truth_label": TRUTH_LABEL,
        "written": written,
    }
    if detail:
        row["detail"] = str(detail)[:180]
    if written:
        append_line_locked(
            _state_path(state_dir, LEDGER_NAME),
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        )
    return row


def observer_tick_snapshot(window: str, *, state_dir: Path | str) -> Dict[str, Any]:
    """Read the last stamped count without creating a new observation."""
    name = str(window or "").strip().lower()
    if not _WINDOW_RE.fullmatch(name):
        return {}
    path = _state_path(state_dir, COUNTERS_NAME)
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        found = (data.get("windows") or {}).get(name)
        return dict(found) if isinstance(found, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


__all__ = [
    "COUNTERS_NAME",
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "observer_tick_snapshot",
    "record_observer_tick",
]
