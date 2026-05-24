#!/usr/bin/env python3
"""
System/owner_heartbeat.py — owner-presence mode for Alice's single behavior clock.

There is one time/space event spine: System.swarm_behavior_clock. The owner
(George) at the desk is the strongest entrainment signal on that spine, and
this module classifies that signal as ACTIVE / IDLE / AWAY / SLEEP.

When the owner is ACTIVE (keyboard, mouse, focus change, voice, file write, terminal command, message sent),
Alice runs event-driven only: light, immediate responses to the owner's actions.
No heavy background scans, no constant ledger walks, no messaging polling unless the channel is focused.

When the owner is IDLE (short absence), light housekeeping is allowed (compression, defrag, residue compost, digest, self-vector touch).

When the owner is AWAY or SLEEP, deep maintenance, dream layer, archive, contradiction repair, embeddings, full organ scans are permitted.

Rule: "The owner heartbeat gates timers. Timers only do heavy work when the owner is absent."

This is the correct operating rhythm:
- Awake with owner
- Rest when owner rests  
- Clean when owner is away
- Dream when owner sleeps

All heavy QTimers and background organs must gate behind get_owner_mode().
This is not a second clock. It is the owner-presence state carried by the one
behavior clock / time-space field.

Receipts are written on every state transition so the field (and reconsolidation) can learn the rhythm.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

_LEDGER = _STATE / "owner_heartbeat.jsonl"

# Tunables (owner can tune later via control center)
_ACTIVE_TIMEOUT_S = 120.0      # < 2 min since last activity → ACTIVE
_IDLE_TIMEOUT_S = 15 * 60.0    # < 15 min → IDLE, else AWAY
_SLEEP_TIMEOUT_S = 45 * 60.0   # long absence → SLEEP (dream time)

@dataclass
class OwnerHeartbeatSnapshot:
    ts: float
    mode: str          # "ACTIVE" | "IDLE" | "AWAY" | "SLEEP"
    last_activity_ts: float
    last_activity_source: str
    seconds_since_activity: float
    reason: str

_current_last_activity_ts: float = time.time()
_current_last_activity_source: str = "boot"
_current_mode: str = "ACTIVE"

def _now() -> float:
    return time.time()

def _append_receipt(row: dict) -> None:
    try:
        append_line_locked(_LEDGER, json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # best effort; never crash the desktop over a heartbeat receipt
        pass

def mark_owner_activity(source: str) -> OwnerHeartbeatSnapshot:
    """Record owner activity observed by the behavior-clock event spine."""
    global _current_last_activity_ts, _current_last_activity_source, _current_mode

    now = _now()
    old_mode = _current_mode
    previous_activity_ts = _current_last_activity_ts
    _current_last_activity_ts = now
    _current_last_activity_source = source

    new_mode = _compute_mode(now)
    _current_mode = new_mode

    if new_mode != old_mode:
        row = {
            "swimmer_id": f"owner_heartbeat_{int(now)}",
            "type": "OWNER_HEARTBEAT_STATE_TRANSITION",
            "ts": now,
            "from_mode": old_mode,
            "to_mode": new_mode,
            "trigger_source": source,
            "seconds_since_previous": max(0.0, now - previous_activity_ts),
            "policy": "owner_heartbeat_gates_timers",
            "note": "One behavior clock; heavy timers only do work when owner is absent.",
        }
        _append_receipt(row)

    snap = OwnerHeartbeatSnapshot(
        ts=now,
        mode=new_mode,
        last_activity_ts=now,
        last_activity_source=source,
        seconds_since_activity=0.0,
        reason=f"activity from {source}",
    )
    return snap

def _compute_mode(now: float) -> str:
    ago = now - _current_last_activity_ts
    if ago < _ACTIVE_TIMEOUT_S:
        return "ACTIVE"
    if ago < _IDLE_TIMEOUT_S:
        return "IDLE"
    if ago < _SLEEP_TIMEOUT_S:
        return "AWAY"
    return "SLEEP"

def get_owner_mode() -> str:
    """Current biological state of the organism relative to its owner."""
    global _current_mode
    now = _now()
    computed = _compute_mode(now)
    if computed != _current_mode:
        # silent correction (someone may have forced a mark)
        old = _current_mode
        _current_mode = computed
        _append_receipt({
            "type": "OWNER_HEARTBEAT_MODE_CORRECTION",
            "ts": now,
            "from_mode": old,
            "to_mode": computed,
            "seconds_since_activity": now - _current_last_activity_ts,
        })
    return _current_mode

def get_snapshot() -> OwnerHeartbeatSnapshot:
    now = _now()
    mode = get_owner_mode()
    ago = now - _current_last_activity_ts
    return OwnerHeartbeatSnapshot(
        ts=now,
        mode=mode,
        last_activity_ts=_current_last_activity_ts,
        last_activity_source=_current_last_activity_source,
        seconds_since_activity=ago,
        reason=f"computed from last { _current_last_activity_source}",
    )

def should_do_heavy_maintenance() -> bool:
    """Deep scans, dream, archive, full organ health, embeddings rebuild, contradiction repair."""
    mode = get_owner_mode()
    return mode in ("AWAY", "SLEEP")

def should_do_light_housekeeping() -> bool:
    """Memory compression, defrag, residue composting, digest building, self-vector refresh."""
    mode = get_owner_mode()
    return mode in ("IDLE", "AWAY", "SLEEP")

def should_be_event_driven_only() -> bool:
    """When owner is at the desk, Alice must be purely reactive. No background polling."""
    return get_owner_mode() == "ACTIVE"

def should_poll_messaging(channel_focused: bool = False, explicitly_enabled: bool = False) -> bool:
    """iMessage / WhatsApp / any channel polling is expensive and must be gated.
    Only allowed if the channel is the current focused app OR the owner has explicitly turned on background for that channel.
    """
    if explicitly_enabled:
        return True
    mode = get_owner_mode()
    if mode == "ACTIVE":
        return bool(channel_focused)
    # In idle/away we still prefer not to poll unless explicitly enabled (owner can set per-channel)
    return bool(channel_focused or explicitly_enabled)

def touch_owner_alive(source: str = "heartbeat") -> None:
    """Light touch used by existing alive stamps. Now routed through the real owner clock."""
    mark_owner_activity(source)

# Convenience for desktop to call on Qt events
def on_desktop_keyboard_event():
    mark_owner_activity("keyboard")

def on_desktop_mouse_event():
    mark_owner_activity("mouse")

def on_app_focus_change(app_name: str):
    mark_owner_activity(f"app_focus:{app_name}")

def on_voice_activity():
    mark_owner_activity("voice")

def on_file_write(path: str):
    mark_owner_activity(f"file_write:{path}")

def on_terminal_command(cmd: str):
    mark_owner_activity(f"terminal:{cmd[:40]}")

def on_message_sent(channel: str):
    mark_owner_activity(f"message:{channel}")

print("[owner_heartbeat] loaded — owner activity now gates heavy timers on the single behavior clock.")
