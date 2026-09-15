#!/usr/bin/env python3
"""David-side bridge: SIFTA command queue -> local RVR1 safety-gated rover.

This process is intentionally boring. It never invents commands, never uses
Alice's owner credential, and never sends a nonzero velocity without a fresh
front-LiDAR scan accepted by ``RoverClient.safe_velocity``. Run it on David's
LAN, not on the public web server.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import time

# Make ``python3 scripts/david_rover_gateway.py`` work from any directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from System.stigmerobotics_remote_link import RemoteRoverGateway
from System.stigmerobotics_rvr1 import RoverClient


def dispatch_command(rover, command):
    """Apply one validated server command and return an ack-safe result."""
    required = {"command_id", "linear_mm_s", "angular_mrad_s", "timeout_ms"}
    if not isinstance(command, dict) or set(command) != required:
        raise ValueError("invalid queued rover command")
    command_id = command["command_id"]
    try:
        result = rover.safe_velocity(command["linear_mm_s"], command["angular_mrad_s"],
                                     timeout_ms=command["timeout_ms"])
    except (RuntimeError, ValueError) as exc:
        return {"command_id": command_id, "state": "rejected",
                "result": {"error": str(exc)}}
    return {"command_id": command_id, "state": "accepted", "result": result}


def run_once(gateway, rover, *, limit=8):
    """Claim and acknowledge a bounded batch. Claimed commands are never retried."""
    batch = gateway.poll_commands(limit=limit)
    outcomes = []
    for command in batch.get("commands", []):
        outcome = dispatch_command(rover, command)
        gateway.ack_command(command_id=outcome["command_id"], state=outcome["state"],
                             result=outcome["result"])
        outcomes.append(outcome)
    return outcomes


def _required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def main():
    base_url = os.environ.get("SIFTA_BASE_URL", "https://stigmergicoin.com")
    gateway = RemoteRoverGateway(
        base_url,
        token=_required("SIFTA_ROVER_TOKEN"),
        control_token=_required("SIFTA_ROVER_CONTROL_TOKEN"),
        robot_id=_required("SIFTA_ROBOT_ID"),
        connection_id=_required("SIFTA_CONNECTION_ID"),
    )
    key = _required("RVR1_PSK").encode("utf-8")
    rover = RoverClient(_required("RVR1_HOST"), key,
                        port=int(os.environ.get("RVR1_PORT", "4210")))
    try:
        rover.open()
        while True:
            run_once(gateway, rover)
            time.sleep(float(os.environ.get("COMMAND_POLL_SECONDS", "1")))
    finally:
        rover.close()


if __name__ == "__main__":
    main()
