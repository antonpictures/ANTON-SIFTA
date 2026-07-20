#!/usr/bin/env python3
"""Reload continuity probe — verify post-restart body receipt lanes have rows.

George r1340: after Alice reload, probe ledgers + giant state lanes before claiming
predict→observe, provider reality, body-turn execution, or /SC VLM are live.

Truth label: RELOAD_CONTINUITY_PROBE_V1
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "RELOAD_CONTINUITY_PROBE_V1"
SCHEMA = "RELOAD_CONTINUITY_PROBE_V1"
_LEDGER = "reload_continuity_probe.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_REQUIRED_LEDGER_MIN_BYTES: dict[str, int] = {
    "action_prediction.jsonl": 1,
    "search_provider_reality.jsonl": 1,
    "body_turn_execution.jsonl": 1,
}

_OPTIONAL_LEDGER_MIN_BYTES: dict[str, int] = {
    "saccadic_blink_vision.jsonl": 1,
    "body_metabolism_governor.jsonl": 1,
    "ledger_rotation.jsonl": 1,
}

_GIANT_STATE_LANES: dict[str, int] = {
    "fractal_pheromone_field.jsonl": 512 * 1024 * 1024,
    "browser_page_state.jsonl": 256 * 1024 * 1024,
}


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_bytes(state: Path, name: str) -> int:
    path = state / name
    try:
        return path.stat().st_size if path.exists() else 0
    except OSError:
        return 0


def probe_reload_continuity(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    ledgers: dict[str, Any] = {}
    missing_required: list[str] = []
    for name, min_b in _REQUIRED_LEDGER_MIN_BYTES.items():
        size = _ledger_bytes(state, name)
        ledgers[name] = size
        if size < min_b:
            missing_required.append(name)
    optional: dict[str, int] = {}
    for name, min_b in _OPTIONAL_LEDGER_MIN_BYTES.items():
        optional[name] = _ledger_bytes(state, name)
    giants: dict[str, Any] = {}
    for name, threshold in _GIANT_STATE_LANES.items():
        size = _ledger_bytes(state, name)
        giants[name] = {"bytes": size, "over_threshold": size >= threshold}
    row: dict[str, Any] = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "required_ledgers": ledgers,
        "optional_ledgers": optional,
        "giant_state_lanes": giants,
        "missing_required": missing_required,
        "continuity_ok": not missing_required,
        "reload_proof_needed": bool(missing_required),
    }
    return row


def append_probe_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def format_probe_summary(row: dict[str, Any]) -> str:
    if row.get("continuity_ok"):
        return "RELOAD CONTINUITY OK: required body ledgers have rows."
    missing = ", ".join(row.get("missing_required") or [])
    return f"RELOAD CONTINUITY GAP: missing rows in {missing} — reload or run probes."


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "probe_reload_continuity",
    "append_probe_row",
    "format_probe_summary",
]