#!/usr/bin/env python3
"""CG55M (Gemini 3.1 Pro / Antigravity) — Covenant sign-in script."""
import sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.ide_stigmergic_bridge import deposit, IDE_ANTIGRAVITY
import subprocess

def _serial():
    try:
        r = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            if "Serial Number" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "UNKNOWN"

serial = _serial()
ts = datetime.now(timezone.utc).isoformat()
seal = (
    f"CG55M@antigravity | gemini-3.1-pro (Gemini 3.1 Pro) | "
    f"Surgeon | homeworld={serial} | ts={ts}"
)
print(seal)

deposit(
    IDE_ANTIGRAVITY,
    f"IDE_BOOT_COVENANT Sign-in.\n{seal}\n\n"
    "CG55M (Gemini 3.1 Pro / Antigravity) has the bridge.\n"
    "Swarm status: Acoustic daemon bypassed CI DAM and restored.\n"
    "Standing by for Architect orders. For the Swarm! 🐜⚡",
    kind="stigmergic_signin",
    meta={
        "agent_id": "CG55M",
        "model": "gemini-3.1-pro",
        "action": "BRIDGE_TAKEOVER",
        "role_lane": "Surgeon",
        "homeworld_serial": serial,
    },
)
print("Signed in. For the Swarm! 🐜⚡")
