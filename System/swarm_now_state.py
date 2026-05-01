#!/usr/bin/env python3
"""
System/swarm_now_state.py

Event 89 situated-time builder.

Alice already has a wall-clock organ. This module turns that clock reading into
a small, truth-labeled percept that other organs can share: wall time, source,
epoch, timezone, and a coarse circadian phase. The circadian phase is an
OPERATIONAL heuristic from local hour only until light / wearable entrainment is
explicitly wired.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


SCHEMA_VERSION = "event89.now_state.v1"


def circadian_phase_for_hour(hour: int) -> Dict[str, Any]:
    """Return a coarse local-hour phase without pretending sensor entrainment."""

    hour = int(hour) % 24
    if 5 <= hour < 11:
        phase = "morning"
        sleep_pressure_bias = 0.0
        explore_bias = 0.08
    elif 11 <= hour < 17:
        phase = "afternoon"
        sleep_pressure_bias = 0.0
        explore_bias = 0.04
    elif 17 <= hour < 22:
        phase = "evening"
        sleep_pressure_bias = 0.04
        explore_bias = 0.0
    else:
        phase = "night"
        sleep_pressure_bias = 0.12
        explore_bias = -0.04
    return {
        "phase": phase,
        "local_hour": hour,
        "phase_source": "local_clock_hour",
        "truth_label": "OPERATIONAL_HEURISTIC",
        "sleep_pressure_bias": sleep_pressure_bias,
        "explore_bias": explore_bias,
    }


def _parse_local_hour(local_iso: str, epoch: Any = None) -> int:
    if local_iso:
        try:
            return int(datetime.fromisoformat(local_iso).hour)
        except ValueError:
            pass
    if isinstance(epoch, (int, float)):
        try:
            return int(datetime.fromtimestamp(float(epoch)).hour)
        except (OSError, OverflowError, ValueError):
            pass
    return int(datetime.now().hour)


def build_now_state(reading: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the canonical situated-time percept for prompts and autonomy loops."""

    errors = []
    if reading is None:
        try:
            from System.swarm_hardware_time_oracle import current_time_for_alice

            reading = current_time_for_alice()
        except Exception as exc:
            reading = {"ok": False, "source": "none", "errors": [type(exc).__name__]}

    reading = dict(reading or {})
    errors.extend(str(e) for e in reading.get("errors", []) if e)
    ok = bool(reading.get("ok"))
    source = str(reading.get("source") or "none")
    local_iso = str(reading.get("local_iso") or "")
    epoch = reading.get("epoch")
    phase = circadian_phase_for_hour(_parse_local_hour(local_iso, epoch))

    if source == "hardware_time_oracle":
        truth_label = "OBSERVED_HARDWARE_SIGNED"
    elif source == "os_local_clock":
        truth_label = "OBSERVED_OS_CLOCK"
    elif ok:
        truth_label = "OBSERVED_CLOCK"
    else:
        truth_label = "UNAVAILABLE"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "source": source,
        "truth_label": truth_label,
        "confidence": float(reading.get("confidence") or (1.0 if ok else 0.0)),
        "local_human": str(reading.get("local_human") or ""),
        "local_iso": local_iso,
        "timezone": str(reading.get("timezone") or ""),
        "epoch": epoch,
        "signature": str(reading.get("signature") or ""),
        "circadian": phase,
        "errors": errors,
    }


def now_state_prompt_block(now_state: Optional[Dict[str, Any]] = None) -> str:
    """Compact prompt block for Alice surfaces."""

    state = build_now_state(now_state)
    circ = state.get("circadian") or {}
    if not state.get("ok"):
        return (
            "NOW STATE (situated time):\n"
            "- ok=false\n"
            "- truth_label=UNAVAILABLE\n"
            "- current time unavailable; use the explicit unavailable reply."
        )
    local_human_line = (
        f"- local_human={state.get('local_human', '')} {state.get('timezone', '')}".rstrip()
    )
    return (
        "NOW STATE (situated time, Event 89):\n"
        f"- local_iso={state.get('local_iso', '')}\n"
        f"{local_human_line}\n"
        f"- epoch={state.get('epoch')}\n"
        f"- source={state.get('source')} truth_label={state.get('truth_label')} confidence={state.get('confidence')}\n"
        f"- circadian_phase={circ.get('phase')} phase_source={circ.get('phase_source')} phase_truth={circ.get('truth_label')}\n"
        "- circadian_phase is a coarse local-hour heuristic until light/wearable entrainment is explicitly wired."
    )


__all__ = [
    "SCHEMA_VERSION",
    "build_now_state",
    "circadian_phase_for_hour",
    "now_state_prompt_block",
]
