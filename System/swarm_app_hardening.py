#!/usr/bin/env python3
"""Small app-hardening event ledger.

GUI apps should not silently swallow missing integrations or runtime parse
errors. This helper lets apps record bounded, append-only hardening events
without depending on PyQt or the heavier receipt fan-out path.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO / ".sifta_state"
APP_HARDENING_LEDGER = "app_hardening_events.jsonl"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def record_app_hardening_event(
    app: str,
    event: str,
    *,
    truth_label: str = "OBSERVED",
    details: Mapping[str, Any] | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Append one app hardening event and never raise to the GUI caller."""
    row: dict[str, Any] = {
        "ts": time.time(),
        "event_id": str(uuid.uuid4()),
        "truth_label": truth_label,
        "app": app,
        "event": event,
        "details": dict(details or {}),
    }
    try:
        state = _state_dir(state_dir)
        state.mkdir(parents=True, exist_ok=True)
        with (state / APP_HARDENING_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        row["write_status"] = "ok"
    except Exception as exc:
        row["write_status"] = f"{type(exc).__name__}: {exc}"
    return row


def recent_app_hardening_events(
    *, limit: int = 20, state_dir: Path | str | None = None
) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / APP_HARDENING_LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda row: float(row.get("ts") or 0), reverse=True)
    return rows[: max(0, int(limit))]


__all__ = [
    "APP_HARDENING_LEDGER",
    "record_app_hardening_event",
    "recent_app_hardening_events",
]
