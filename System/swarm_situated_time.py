#!/usr/bin/env python3
"""
System/swarm_situated_time.py
══════════════════════════════════════════════════════════════════════
Situated Time (Event 89 Spacetime Organ)

Compatibility surface for Event 89 situated time.

The canonical implementation lives in ``System.swarm_now_state`` so prompts,
body-brain ticks, and consciousness heartbeats all consume the same truth-labeled
shape. This module remains for AG31-era imports and exposes the old helper names
without creating a second clock organ.

Author: AG31
"""

from typing import Any, Dict

from System.swarm_now_state import build_now_state as _canonical_build_now_state
from System.swarm_now_state import circadian_phase_for_hour

def _compute_circadian_phase(hour: int) -> str:
    """Legacy uppercase phase API backed by the canonical now-state policy."""

    return str(circadian_phase_for_hour(hour).get("phase") or "unknown").upper()

def build_now_state() -> Dict[str, Any]:
    """
    Build the Event 89 temporal percept.

    Returns the canonical truth-labeled now_state plus legacy top-level fields
    expected by older callers: ``circadian_phase`` and ``is_sleep_phase``.
    """

    state = dict(_canonical_build_now_state())
    circadian = state.get("circadian") if isinstance(state.get("circadian"), dict) else {}
    phase = str(circadian.get("phase") or "unknown")
    state.setdefault("circadian_phase", phase)
    state.setdefault("is_sleep_phase", phase == "night")
    return state

if __name__ == "__main__":
    import json
    print("=== SIFTA Situated Time Organ ===")
    state = build_now_state()
    print(json.dumps(state, indent=2))
