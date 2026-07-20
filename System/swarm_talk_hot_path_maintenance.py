#!/usr/bin/env python3
"""Talk heartbeat hot-path maintenance — metabolism audit + giant ledger rotation.

George r1349: hard-bind swarm_body_metabolism_audit into the Talk body-writer pulse
so beach-ball pressure and giant .sifta_state lanes get receipted without waiting
only on sifta_os_desktop heartbeat.

Truth label: TALK_HOT_PATH_MAINTENANCE_V1
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "TALK_HOT_PATH_MAINTENANCE_V1"
SCHEMA = "TALK_HOT_PATH_MAINTENANCE_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_AUDIT_INTERVAL_S = 180.0
_GOVERNOR_INTERVAL_S = 120.0
_ROTATION_INTERVAL_S = 300.0

_last_audit_ts = 0.0
_last_governor_ts = 0.0
_last_rotation_ts = 0.0


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def tick_talk_hot_path_maintenance(
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    force: bool = False,
) -> dict[str, Any]:
    """One maintenance pulse from Talk body_writer_tick — audit, governor, rotation."""
    global _last_audit_ts, _last_governor_ts, _last_rotation_ts

    t = time.time() if now is None else float(now)
    events: list[str] = []
    row: dict[str, Any] = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": t,
        "events": events,
    }

    if force or (t - _last_audit_ts) >= _AUDIT_INTERVAL_S:
        try:
            from System.swarm_body_metabolism_audit import audit_body_metabolism, append_audit_row

            audit = audit_body_metabolism(state_dir=state_dir)
            append_audit_row(audit, state_dir=state_dir)
            events.append("body_metabolism_audit")
            row["audit_state_human"] = audit.get("state_dir_human")
        except Exception as exc:
            events.append(f"audit_skip:{type(exc).__name__}")
        _last_audit_ts = t

    if force or (t - _last_governor_ts) >= _GOVERNOR_INTERVAL_S:
        try:
            from System.swarm_metabolism_governor import tick_metabolism_governor

            gov = tick_metabolism_governor(state_dir=state_dir)
            band = str(gov.get("band") or "normal")
            events.append(f"metabolism_governor:{band}")
            row["governor_band"] = band
        except Exception as exc:
            events.append(f"governor_skip:{type(exc).__name__}")
        _last_governor_ts = t

    if force or (t - _last_rotation_ts) >= _ROTATION_INTERVAL_S:
        rotated: list[str] = []
        try:
            from System.swarm_ledger_rotation import rotate_default_ledgers

            rows = rotate_default_ledgers(state_dir=state_dir)
            for rot in rows:
                name = str(rot.get("ledger_name") or "")
                if rot.get("archive_path") and int(rot.get("archive_bytes") or 0) > 0:
                    rotated.append(name)
            if rotated:
                events.append("ledger_rotation:" + ",".join(rotated[:6]))
            row["rotated_ledgers"] = rotated
        except Exception as exc:
            events.append(f"rotation_skip:{type(exc).__name__}")
        _last_rotation_ts = t

    return row


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "tick_talk_hot_path_maintenance",
]