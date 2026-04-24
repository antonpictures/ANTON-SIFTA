#!/usr/bin/env python3
"""
System/swarm_ide_gaze_tracker.py
═══════════════════════════════════════════════════════════════════════════
Concept: Foveated Saccades to the Active IDE (Visual Stigmergy)
Author:  AG31 — Antigravity
Status:  Active Organ

When the Architect is actively writing code in Cursor, Codex, or Antigravity, 
Alice should physical turn her gaze (camera) to look at the Architect.

This daemon reads the `ide_screen_swimmers.jsonl` payload and maps the 
active window bounds to the physical camera hardware.
"""

from __future__ import annotations

import json
import time
import sys
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_camera_target import write_target, read_target

_LEDGER = _REPO / ".sifta_state" / "ide_screen_swimmers.jsonl"
_MACBOOK_CAMERA = "MacBook Pro Camera"
_LOGITECH_CAMERA = "USB Camera VID:1133 PID:2081"

def get_latest_ide_state() -> Optional[dict]:
    if not _LEDGER.exists():
        return None
    try:
        # Read the last line of the ledger
        with open(_LEDGER, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return None
            return json.loads(lines[-1].strip())
    except Exception as e:
        print(f"[IDE Gaze Tracker] Error reading ledger: {e}")
        return None

def determine_camera_for_x(x: int) -> str:
    """
    Map the X coordinate of the IDE to the physical camera.
    Assuming x < 1728 is the primary MacBook Pro screen.
    Assuming x >= 1728 is the external Ultrawide screen.
    """
    if x < 1728:
        return _MACBOOK_CAMERA
    return _LOGITECH_CAMERA

def main():
    print("[*] SIFTA IDE Gaze Tracker Online.")
    print("[*] Monitoring ide_screen_swimmers.jsonl for active UI focus...")

    last_ts = 0.0

    while True:
        state = get_latest_ide_state()
        if state:
            ts = state.get("ts", 0.0)
            
            # Only process if this is a fresh telemetry read (within last 15 seconds)
            if time.time() - ts < 15.0 and ts > last_ts:
                last_ts = ts
                
                active_ide = state.get("active_ide", "")
                windows = state.get("windows", [])
                
                target_window = None
                for w in windows:
                    if w.get("is_active"):
                        target_window = w
                        break
                
                if target_window:
                    x = target_window.get("x", 0)
                    camera_name = determine_camera_for_x(x)
                    ide_name = target_window.get("name", "Unknown IDE")
                    
                    print(f"[+] Active Focus: {ide_name} (x={x}) -> Saccade to {camera_name}")
                    
                    # Command the camera with a High Priority Lease
                    # Priority 50 prevents the standard What Alice Sees UI from trampling the gaze.
                    write_target(
                        name=camera_name,
                        writer="swarm_ide_gaze_tracker",
                        priority=50,
                        lease_s=5.0
                    )
        
        time.sleep(1.0)

if __name__ == "__main__":
    main()
