#!/usr/bin/env python3
"""
System/swarm_window_manager.py — WindowServer adapter (real bridge)
═══════════════════════════════════════════════════════════════════════════
Originally a stub created by AG31 in the Code-Everything Tournament. The
.py was deleted but a stale `.pyc` lingered, so `launchd/swarm_sense_loop.py`
was nominally polling `poll_active_window()` while actually firing into a
ghost. Reborn 2026-04-23 by C47H as a *real* adapter that delegates to
`System.swarm_active_window` (osascript-backed NSWorkspace cortex).

The sense_loop contract is preserved:
    poll_active_window()  -> None  (writes ledger + pheromone)
    record_focus(app_name, window_title) -> None
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

LEDGER = Path(".sifta_state/window_manager.jsonl")
PHEROMONE = "stig_ui_focus"


def _write_legacy_ledger(row: Dict[str, Any]) -> None:
    """Keep the legacy `.sifta_state/window_manager.jsonl` ledger alive
    so anything reading the old AG31 contract still gets data."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def record_focus(app_name: Optional[str], window_title: Optional[str]) -> None:
    """Original AG31 verb — record a focus change with explicit values."""
    row = {
        "ts": time.time(),
        "app_name": app_name,
        "window_title": window_title,
        "writer": "swarm_window_manager",
    }
    _write_legacy_ledger(row)
    try:
        from System.swarm_pheromone import deposit_pheromone
        deposit_pheromone(PHEROMONE, 1.5)
    except Exception:
        pass


def poll_active_window() -> Dict[str, Any]:
    """Sense-loop entrypoint. Delegates to the *real* active-window cortex
    so this module emits truthful focus events instead of nothing."""
    try:
        from System import swarm_active_window as aw
        snap = aw.write_snapshot()
        row = {
            "ts": snap.get("ts", time.time()),
            "app_name": snap.get("app"),
            "window_title": snap.get("window"),
            "bundle_id": snap.get("bundle_id"),
            "writer": "swarm_window_manager_via_active_window",
        }
        _write_legacy_ledger(row)
        try:
            from System.swarm_pheromone import deposit_pheromone
            deposit_pheromone(PHEROMONE, 0.5)
        except Exception:
            pass
        return row
    except Exception as exc:
        row = {
            "ts": time.time(),
            "error": f"{type(exc).__name__}: {exc}",
            "writer": "swarm_window_manager",
        }
        _write_legacy_ledger(row)
        return row


if __name__ == "__main__":
    print(json.dumps(poll_active_window(), indent=2))
