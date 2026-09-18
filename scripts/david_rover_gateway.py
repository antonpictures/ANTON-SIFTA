#!/usr/bin/env python3
"""David-side bridge: SIFTA command queue -> local RVR1 safety-gated rover.

This process is intentionally boring. It never invents commands, never uses
Alice's owner credential, and never sends a nonzero velocity without a fresh
front-LiDAR scan accepted by ``RoverClient.safe_velocity``. Run it on David's
LAN, not on the public web server.
"""
from __future__ import annotations

import os
import math
from pathlib import Path
import queue
import sys
import threading
import time

# Make ``python3 scripts/david_rover_gateway.py`` work from any directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from System.stigmerobotics_remote_link import RemoteRoverGateway
from System.stigmerobotics_rvr1 import RoverClient


def dispatch_command(rover, command, *, request_started=None, clock=time.monotonic):
    """Apply one validated server command and return an ack-safe result."""
    required = {"command_id", "linear_mm_s", "angular_mrad_s", "timeout_ms", "valid_for_ms"}
    if not isinstance(command, dict) or set(command) != required:
        raise ValueError("invalid queued rover command")
    command_id = command["command_id"]
    try:
        ttl = command["valid_for_ms"]
        if type(ttl) is not int or not 0 < ttl <= 3000 or request_started is None:
            raise ValueError("missing or invalid command lifetime")
        remaining = int(ttl - 1000 * (clock() - request_started))
        duration = command["timeout_ms"]
        if type(duration) is not int or not 1 <= duration <= 1000:
            raise ValueError("invalid finite command duration")
        if remaining < duration:
            raise RuntimeError("command expired in transport or local queue")
        result = rover.safe_velocity(command["linear_mm_s"], command["angular_mrad_s"],
                                     timeout_ms=duration)
    except (RuntimeError, ValueError) as exc:
        return {"command_id": command_id, "state": "rejected",
                "result": {"error": str(exc)}}
    return {"command_id": command_id, "state": "accepted", "result": result}


def run_once(gateway, rover, *, limit=1, clock=time.monotonic):
    """Claim and acknowledge a bounded batch. Claimed commands are never retried."""
    started = clock()
    batch = gateway.poll_commands(limit=limit)
    if (batch.get("robot_id") != gateway.robot_id or
            batch.get("connection_id") != gateway.connection_id):
        raise ValueError("wrong command connection")
    outcomes = []
    for command in batch.get("commands", []):
        if isinstance(rover, LocalRover):
            outcome = rover.execute(command, started)
        else:
            outcome = dispatch_command(rover, command, request_started=started, clock=clock)
        gateway.ack_command(command_id=outcome["command_id"], state=outcome["state"],
                             result=outcome["result"])
        outcomes.append(outcome)
    return outcomes


class LocalRover:
    """Own the UDP socket on one thread, independent of slow HTTPS calls."""

    def __init__(self, rover):
        self.rover = rover
        self.pending = queue.Queue(maxsize=1)
        self.finished = threading.Event()
        self.ready = threading.Event()
        self.failure = None
        self.latest = None
        self.thread = threading.Thread(target=self._run, name="rover-lan", daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(3) or self.failure:
            self.close()
            raise RuntimeError("local rover handshake failed") from self.failure

    def execute(self, command, started):
        result = queue.Queue(maxsize=1)
        self.pending.put_nowait((dict(command), started, result))
        try:
            return result.get(timeout=3)
        except queue.Empty:
            self.finished.set()
            raise RuntimeError("local command result unavailable; do not retry")

    def _run(self):
        active = None
        try:
            self.rover.open()
            self.ready.set()
            while not self.finished.is_set():
                try:
                    row = self.rover.poll(timeout=0.05)
                    self.latest = (time.time(), row)
                except TimeoutError:
                    pass
                except ValueError:
                    self.rover.stop()
                    active = None
                now = time.monotonic()
                if active and (now >= active[1] or not self.rover.observations.obstacle_clear(
                        active[0], now=now,
                        stop_distance_mm=300 + max(0, active[0]) * max(0, active[1] - now))):
                    self.rover.stop()
                    active = None
                if active is None and now - self.rover.opened_at > 15:
                    self.rover.open()
                if active is None:
                    try:
                        command, started, result = self.pending.get_nowait()
                    except queue.Empty:
                        continue
                    outcome = dispatch_command(self.rover, command, request_started=started)
                    if outcome["state"] == "accepted":
                        active = (command["linear_mm_s"], time.monotonic() + command["timeout_ms"] / 1000)
                    result.put_nowait(outcome)
        except Exception as exc:
            self.failure = exc
            self.finished.set()
        finally:
            self.ready.set()
            try:
                self.rover.stop()
            except OSError:
                pass
            self.rover.close()

    def close(self):
        self.finished.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=3)


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
    local = LocalRover(rover)
    interval = float(os.environ.get("COMMAND_POLL_SECONDS", "0.2"))
    if not math.isfinite(interval) or not 0.05 <= interval <= 2:
        rover.close()
        raise SystemExit("COMMAND_POLL_SECONDS must be between 0.05 and 2")
    try:
        sequence = gateway.status()["sequence"] + 1
        last_upload = 0.0
        uploaded = None
        local.start()
        while True:
            if local.failure:
                raise RuntimeError("local rover connection failed") from local.failure
            run_once(gateway, local)
            observation = local.latest
            if observation is not None and observation is not uploaded and time.monotonic() - last_upload >= 1:
                gateway.send_telemetry(sequence=sequence, captured_at=observation[0],
                                       readings={"received_observation": observation[1],
                                                 "timestamp_kind": "gateway_received"})
                sequence += 1
                uploaded = observation
                last_upload = time.monotonic()
            time.sleep(interval)
    finally:
        local.close()


if __name__ == "__main__":
    main()
