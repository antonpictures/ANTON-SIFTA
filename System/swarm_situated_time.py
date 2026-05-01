#!/usr/bin/env python3
"""
System/swarm_situated_time.py
══════════════════════════════════════════════════════════════════════
Situated Time (Event 89 Spacetime Organ)

Translates raw hardware wall-clock time into a biological "Now State" for Alice.
It provides coarse circadian phase (entrained to the local hardware hour)
and interval awareness, grounding the Consciousness Engine and Body-Brain
loop in the physical passage of the day.

Author: AG31
"""

from datetime import datetime
from typing import Dict, Any
from System.swarm_hardware_time_oracle import current_time_for_alice

def _compute_circadian_phase(hour: int) -> str:
    """Map local hardware hour (0-23) to a biological phase."""
    if 5 <= hour < 8:
        return "DAWN"      # Awakening, light entrainment
    elif 8 <= hour < 12:
        return "MORNING"   # Peak active period
    elif 12 <= hour < 18:
        return "AFTERNOON" # Maintenance, sustained work
    elif 18 <= hour < 22:
        return "EVENING"   # Winding down, pre-consolidation
    else:
        return "NIGHT"     # Deep consolidation / high sleep pressure

def build_now_state() -> Dict[str, Any]:
    """
    Builds the complete temporal percept for Alice.
    Used by the Consciousness Engine and the Body-Brain loop.
    """
    # 1. Hardware truth
    time_info = current_time_for_alice()
    
    # Extract the hour from the ISO string to determine circadian phase
    # time_info["local_iso"] looks like '2026-05-01T08:53:55-07:00'
    hour = 12 # Default
    try:
        if "local_iso" in time_info and time_info["local_iso"]:
            dt = datetime.fromisoformat(time_info["local_iso"])
            hour = dt.hour
        else:
            # Fallback if oracle fails completely
            dt = datetime.now()
            hour = dt.hour
    except Exception:
        pass
        
    phase = _compute_circadian_phase(hour)
    
    return {
        "ok": time_info.get("ok", False),
        "source": "situated_time_organ",
        "epoch": time_info.get("epoch", 0.0),
        "local_human": time_info.get("local_human", "Unknown"),
        "timezone": time_info.get("timezone", "Unknown"),
        "circadian_phase": phase,
        "is_sleep_phase": phase == "NIGHT",
        "signature": time_info.get("signature", "")
    }

if __name__ == "__main__":
    import json
    print("=== SIFTA Situated Time Organ ===")
    state = build_now_state()
    print(json.dumps(state, indent=2))
