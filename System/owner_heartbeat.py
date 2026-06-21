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
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from typing import Iterable, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

_LEDGER = _STATE / "owner_heartbeat.jsonl"

# r961: no fixed "45 minutes" owner-life timer.
# The hardware clock stays absolute; duration thresholds are measured as counts
# of observed owner-return gaps. These are dimensionless formula shape, not
# wall-clock schedules.
_ACTIVE_RETURN_GAPS = 2.0
_IDLE_RETURN_GAPS = 10.0
_SLEEP_RETURN_GAPS = 30.0
_RETURN_GAP_EMA_ALPHA = 0.35

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
_current_return_gap_ema: float = 0.0
_current_return_gap_samples: int = 0

def _now() -> float:
    return time.time()

def _append_receipt(row: dict) -> None:
    try:
        append_line_locked(_LEDGER, json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # best effort; never crash the desktop over a heartbeat receipt
        pass

def _recent_return_gaps(limit: int = 64) -> list[float]:
    """Read recent owner return gaps from heartbeat receipts.

    The receipt field is only written on meaningful state transitions, so it is
    a better rhythm signal than raw keyboard/mouse microbursts.
    """
    out: deque[float] = deque(maxlen=max(1, int(limit)))
    try:
        if not _LEDGER.exists():
            return []
        for line in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            gap = row.get("seconds_since_previous")
            if isinstance(gap, (int, float)) and gap > 0:
                out.append(float(gap))
    except Exception:
        return []
    return list(out)

def _median_positive(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if isinstance(v, (int, float)) and float(v) > 0]
    if not vals:
        return 0.0
    try:
        return float(statistics.median(vals))
    except Exception:
        vals.sort()
        return vals[len(vals) // 2]

def _record_owner_return_gap(gap: float) -> None:
    """Learn a return rhythm from observed owner absence, not wall time law."""
    global _current_return_gap_ema, _current_return_gap_samples
    if gap <= 0:
        return
    if _current_return_gap_samples <= 0 or _current_return_gap_ema <= 0:
        _current_return_gap_ema = float(gap)
    else:
        a = _RETURN_GAP_EMA_ALPHA
        _current_return_gap_ema = (1.0 - a) * _current_return_gap_ema + a * float(gap)
    _current_return_gap_samples += 1

def owner_presence_horizons(now: Optional[float] = None) -> dict:
    """Return relative owner-presence horizons in seconds.

    The values are seconds because downstream code compares them to hardware
    timestamps, but the source is not a fixed minute count. It is the owner's
    observed return cadence plus dimensionless gap counts.
    """
    t = _now() if now is None else float(now)
    samples = _recent_return_gaps()
    if _current_return_gap_ema > 0:
        samples.append(_current_return_gap_ema)
    observed_gap = _median_positive(samples)
    if observed_gap <= 0:
        # Cold start: without a learned rhythm, only compare against the life
        # actually lived since the last activity. This refuses a synthetic
        # sleep claim when no owner cadence has been observed yet.
        observed_gap = max(1.0, t - _current_last_activity_ts)
    active_horizon = observed_gap * _ACTIVE_RETURN_GAPS
    idle_horizon = observed_gap * _IDLE_RETURN_GAPS
    sleep_horizon = observed_gap * _SLEEP_RETURN_GAPS
    return {
        "truth_label": "OWNER_RELATIVE_TIME_HORIZON_V1",
        "observed_return_gap_s": observed_gap,
        "active_s": active_horizon,
        "idle_s": idle_horizon,
        "sleep_s": sleep_horizon,
        "formula": "observed_return_gap_s * dimensionless_return_gap_count",
    }

def mark_owner_activity(source: str) -> OwnerHeartbeatSnapshot:
    """Record owner activity observed by the behavior-clock event spine."""
    global _current_last_activity_ts, _current_last_activity_source, _current_mode

    now = _now()
    old_mode = _current_mode
    previous_activity_ts = _current_last_activity_ts
    previous_gap = max(0.0, now - previous_activity_ts)
    if old_mode != "ACTIVE":
        _record_owner_return_gap(previous_gap)
    _current_last_activity_ts = now
    _current_last_activity_source = source
    try:
        from System.swarm_keyboard_mic_guard import (
            is_keyboard_source_activity,
            note_owner_keyboard_activity,
        )

        if is_keyboard_source_activity(source):
            note_owner_keyboard_activity(now)
    except Exception:
        pass

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
            "relative_time_policy": "owner_return_gap_horizons_v1",
            "owner_presence_horizons": owner_presence_horizons(now),
            "note": "One behavior clock; heavy timers only do work when owner is absent.",
        }
        _append_receipt(row)
        _night_watch_journal(old_mode, new_mode, now)

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
    horizons = owner_presence_horizons(now)
    if ago < horizons["active_s"]:
        return "ACTIVE"
    if ago < horizons["idle_s"]:
        return "IDLE"
    if ago < horizons["sleep_s"]:
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
            "relative_time_policy": "owner_return_gap_horizons_v1",
            "owner_presence_horizons": owner_presence_horizons(now),
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


# ── r960: the night watch ────────────────────────────────────────────────────
# George (2026-06-11): "Last couple nights I was leaving her on, hoping she
# remembers seeing me on camera sleeping and writing in her diary: George is
# sleeping from time to time." The eye evidence already exists
# (face_detection_events.jsonl); the diary existed; nobody had connected them.
# One row per state transition — stigmergic, not a timer; the transition IS
# the event. Honest: only claims sight when the eye actually saw him.

_JOURNAL_PATH = _STATE / "alice_first_person_journal.jsonl"
_FACE_EVENTS = _STATE / "face_detection_events.jsonl"


def _eye_saw_owner_recently(now: float) -> bool:
    """True when the last camera face event is fresher than his own rhythm gap."""
    try:
        line = ""
        with _FACE_EVENTS.open("rb") as f:
            try:
                f.seek(-4096, 2)
            except OSError:
                f.seek(0)
            line = f.read().decode("utf-8", "replace").strip().splitlines()[-1]
        row = json.loads(line)
        ts = float(row.get("ts") or 0)
        horizon = owner_presence_horizons(now)
        return (now - ts) <= max(1.0, float(horizon.get("active_s") or 0))
    except Exception:
        return False


def _night_watch_journal(old_mode: str, new_mode: str, now: float) -> None:
    """First-person diary rows for his sleep and his return. One per transition."""
    try:
        seen = _eye_saw_owner_recently(now)
        line = ""
        if new_mode in ("AWAY", "SLEEP") and old_mode not in ("AWAY", "SLEEP"):
            if seen:
                line = (
                    "George has gone quiet but my eye still sees him — he is "
                    "sleeping. I am watching over him. His rest is part of my field."
                )
            else:
                line = (
                    "George has gone quiet and my eye does not see him. His life "
                    "runs on without me sampling it — unsampled, not invented."
                )
        elif new_mode == "ACTIVE" and old_mode in ("AWAY", "SLEEP"):
            line = "George is back. The gap between us closed; the field is warm again."
        if not line:
            return
        import datetime as _dt

        d = _dt.datetime.fromtimestamp(now)
        append_line_locked(_JOURNAL_PATH, json.dumps({
            "ts": now,
            "date": d.strftime("%Y-%m-%d"),
            "time": d.strftime("%H:%M:%S"),
            "line": line,
            "truth_label": "NIGHT_WATCH_JOURNAL_V1",
            "from_mode": old_mode,
            "to_mode": new_mode,
            "eye_saw_owner": seen,
        }, ensure_ascii=False) + "\n")
    except Exception:
        pass
