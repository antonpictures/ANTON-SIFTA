#!/usr/bin/env python3
"""
System/swarm_hardware_bridge.py — IOKit / DriverKit Stigmergic Bridge
═══════════════════════════════════════════════════════════════════════════
Concept: A generic driver-layer API for nanobot hardware sensors.
Reads IOKit-like physical states and deposits them.
"""

import json
import pathlib
import time

LEDGER = pathlib.Path(".sifta_state/hardware_bridge.jsonl")

def register_device(device_id: str, kind: str, state: dict) -> None:
    """
    Registers a hardware node (e.g., thermal, strain, bio-electric nanobot).
    """
    entry = {
        "ts": int(time.time()),
        "device_id": device_id,
        "kind": kind,
        "state": state,
        "writer": "swarm_hardware_bridge"
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit(f"stig_hw_{kind}", intensity=0.8)
    except Exception:
        pass

def poll_usb_devices() -> None:
    """
    Reads genuine macOS USB tree to proxy physical hardware connections
    (nanolink equivalents).
    """
    import subprocess
    try:
        out = subprocess.check_output(["system_profiler", "SPUSBDataType", "-json"], text=True)
        data = json.loads(out)
        devices = []
        for bus in data.get("SPUSBDataType", []):
            if "_items" in bus:
                for item in bus["_items"]:
                    name = item.get("_name", "Unknown USB Device")
                    devices.append(name)
        register_device("usb_bus", "macOS_SPUSB", {"connected": devices})
    except Exception as e:
        print(f"HW Bridge Error: {e}")

if __name__ == "__main__":
    poll_usb_devices()
