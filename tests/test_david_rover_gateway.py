import threading
import time
from types import SimpleNamespace

import pytest

from scripts.david_rover_gateway import LocalRover, dispatch_command, run_once
from System.stigmerobotics_rvr1 import RoverClient


def command(**changes):
    return dict(command_id="move1", linear_mm_s=100, angular_mrad_s=0,
                timeout_ms=250, valid_for_ms=2250, **changes)


def test_transport_delay_expires_command_before_motor_send():
    sent = []
    rover = SimpleNamespace(safe_velocity=lambda *a, **k: sent.append(a))
    result = dispatch_command(rover, command(), request_started=10, clock=lambda: 12.1)
    assert result["state"] == "rejected"
    assert not sent


def test_lifetime_is_not_renewed_by_prior_ack_delay():
    now = [10.0]
    sent = []
    rover = SimpleNamespace(safe_velocity=lambda *a, **k: sent.append(a) or {"status": "sent"})
    class Gateway:
        robot_id, connection_id = "car", "connection"
        def poll_commands(self, limit):
            return {"robot_id": self.robot_id, "connection_id": self.connection_id,
                    "commands": [command(), {**command(), "command_id": "move2"}]}
        def ack_command(self, **kwargs):
            now[0] += 3
    outcomes = run_once(Gateway(), rover, clock=lambda: now[0])
    assert [o["state"] for o in outcomes] == ["accepted", "rejected"]
    assert len(sent) == 1


def test_turn_only_cannot_bypass_sensor_checks():
    rover = RoverClient("127.0.0.1", b"offline-test")
    try:
        with pytest.raises(RuntimeError, match="turn clearance"):
            rover.safe_velocity(0, 200)
    finally:
        rover.close()


def test_local_monitor_stops_during_web_inactivity():
    class Rover:
        opened_at = None
        blocked = False
        def __init__(self):
            self.stopped = threading.Event()
            self.sent = threading.Event()
            self.closed = False
            self.observations = SimpleNamespace(obstacle_clear=lambda *a, **k: not self.blocked)
        def open(self):
            self.opened_at = time.monotonic()
        def poll(self, timeout):
            time.sleep(0.005)
            return {"modality": "lidar"}
        def safe_velocity(self, *args, **kwargs):
            self.sent.set()
            return {"status": "sent", "physical_motion_verified": False}
        def stop(self):
            self.stopped.set()
        def close(self):
            self.closed = True
    rover = Rover()
    local = LocalRover(rover)
    try:
        local.start()
        result = local.execute(command(), time.monotonic())
        assert result["state"] == "accepted" and rover.sent.is_set()
        # No HTTPS polling or acknowledgement happens while the hazard appears.
        rover.blocked = True
        assert rover.stopped.wait(0.5)
        assert local.latest[1]["modality"] == "lidar"
    finally:
        local.close()
    assert rover.closed and not local.thread.is_alive()


def test_rearm_discards_old_pending_goals(tmp_path):
    from System.stigmerobotics_remote_link import RemoteRoverLink
    link = RemoteRoverLink(tmp_path)
    pair = link.pair(link.invite("car")["ticket"])
    arm = link.arm("car")
    payload = {k: v for k, v in command().items() if k != "valid_for_ms"}
    payload.update(robot_id="car", connection_id=pair["connection_id"])
    link.enqueue_command(arm["control_token"], payload)
    new_arm = link.arm("car")
    assert link.poll_commands(new_arm["control_token"])["commands"] == []
    with pytest.raises(PermissionError):
        link.poll_commands(arm["control_token"])
