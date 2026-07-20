#!/usr/bin/env python3
"""Body metabolism governor — throttle timers under beach-ball pressure.

George r1338: keep Talk, Alice Browser, receipts, body_screen_eye, cortex alive;
stretch decorative poll timers when CPU/WindowServer pressure rises.

Truth label: BODY_METABOLISM_GOVERNOR_V1
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "BODY_METABOLISM_GOVERNOR_V1"
SCHEMA = "BODY_METABOLISM_GOVERNOR_V1"
_LEDGER = "body_metabolism_governor.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Base intervals (ms) for organs the governor may stretch.
_ORGAN_BASE_MS: dict[str, int] = {
    "alice_browser_spa_snap": 900,
    "what_alice_sees_poll": 800,
    "matrix_demo_loop": 150,
    "matrix_terminal_status": 1000,
    "matrix_terminal_blink": 500,
    "matrix_cursor_blink": 530,
    "matrix_rabbit_anim": 600,
    "matrix_type_anim": 100,
    "matrix_grok_queue_poll": 900,
    "cowatch_urge_poll": 4500,
    "desktop_heartbeat": 1000,
}

_PRESSURE_THRESHOLDS = (
    (85.0, 4.0),  # cpu% -> multiplier
    (70.0, 2.5),
    (55.0, 1.75),
    (40.0, 1.25),
)

_WINDOWSERVER_COMM = "WindowServer"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _sample_pressure() -> dict[str, Any]:
    try:
        from System.swarm_body_metabolism_audit import _run_ps_sample

        processes = _run_ps_sample()
    except Exception:
        processes = []
    top_cpu = 0.0
    window_server_cpu = 0.0
    hot_processes: list[dict[str, Any]] = []
    for proc in processes[:8]:
        try:
            cpu = float(proc.get("cpu") or 0.0)
        except (TypeError, ValueError):
            cpu = 0.0
        top_cpu = max(top_cpu, cpu)
        comm = str(proc.get("comm") or "")
        if _WINDOWSERVER_COMM in comm:
            window_server_cpu = max(window_server_cpu, cpu)
        if cpu >= 25.0:
            hot_processes.append(proc)
    composite = max(top_cpu, window_server_cpu * 1.15)
    multiplier = 1.0
    band = "normal"
    for threshold, mult in _PRESSURE_THRESHOLDS:
        if composite >= threshold:
            multiplier = mult
            band = f"pressure_{int(threshold)}"
            break
    return {
        "top_cpu": round(top_cpu, 2),
        "window_server_cpu": round(window_server_cpu, 2),
        "composite_cpu": round(composite, 2),
        "multiplier": multiplier,
        "band": band,
        "hot_processes": hot_processes[:5],
    }


def current_pressure(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sample = _sample_pressure()
    sample.update(
        {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "ts": time.time(),
        }
    )
    return sample


def governed_interval_ms(
    base_ms: int,
    *,
    organ_id: str = "",
    state_dir: Optional[Path | str] = None,
    pressure: Optional[dict[str, Any]] = None,
) -> int:
    """Return stretched timer interval under pressure; vital organs keep base when cool."""
    base = max(50, int(base_ms or 0))
    sample = pressure if pressure is not None else _sample_pressure()
    mult = float(sample.get("multiplier") or 1.0)
    if mult <= 1.0:
        return base
    stretched = int(base * mult)
    cap = 60_000 if organ_id in {"alice_browser_spa_snap", "what_alice_sees_poll"} else 30_000
    return min(max(base, stretched), cap)


def should_throttle_giant_jsonl_scan(*, state_dir: Optional[Path | str] = None) -> bool:
    sample = _sample_pressure()
    return float(sample.get("composite_cpu") or 0.0) >= 55.0


def append_governor_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def tick_metabolism_governor(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Sample pressure and write one governor receipt row."""
    row = current_pressure(state_dir=state_dir)
    organs = {
        organ: governed_interval_ms(base, organ_id=organ, pressure=row)
        for organ, base in _ORGAN_BASE_MS.items()
    }
    row["governed_intervals_ms"] = organs
    append_governor_row(row, state_dir=state_dir)
    return row


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "current_pressure",
    "governed_interval_ms",
    "should_throttle_giant_jsonl_scan",
    "tick_metabolism_governor",
    "append_governor_row",
]