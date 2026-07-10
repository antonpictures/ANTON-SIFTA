#!/usr/bin/env python3
"""r1603 — DimOS-inspired body pipes DB1–DB6."""
from __future__ import annotations

import json
from pathlib import Path

from sifta.core.stream import StreamBus, wrap_camera_frame, wrap_cmd_vel, wrap_hardware_body_power
from sifta.core.blueprint import (
    autoconnect,
    camera_eye_blueprint,
    hardware_body_blueprint,
    motor_cortex_blueprint,
    mcp_server_blueprint,
)
from sifta.core.replay import ReplayMode, SimulationMode, assert_sim_before_real, write_fixture
from sifta.core.transport import InProcessTransport, make_transport
from sifta.core.maturity import EMBODIMENT_MATURITY, maturity_lines, status_for
from sifta.core.spy import StreamSpy
from sifta.core.mcp_stream_skills import get_color_image, relative_move, explore_room


def test_db1_typed_stream_pub_sub() -> None:
    bus = StreamBus()
    seen = []
    bus.subscribe("camera", "Image", lambda m: seen.append(m.payload))
    wrap_camera_frame(bus, {"w": 160, "h": 120, "rgb": True}, source="camera_eye")
    wrap_hardware_body_power(bus, {"percent": 88, "source": "AC"}, source="alice_hardware_body")
    wrap_cmd_vel(bus, {"linear": 0.1, "angular": 0.0}, source="motor")
    assert len(seen) == 1
    assert bus.latest("battery", "PowerState").payload["percent"] == 88
    assert bus.latest("cmd_vel", "Twist").payload["linear"] == 0.1


def test_db2_autoconnect_blueprint() -> None:
    graph = autoconnect(
        hardware_body_blueprint(),
        camera_eye_blueprint(),
        motor_cortex_blueprint(),
        mcp_server_blueprint(),
    ).build()
    wired = [c for c in graph.connections if c["wired"]]
    names = {(c["channel"], c["type"]) for c in wired}
    assert ("camera", "Image") in names
    assert ("battery", "PowerState") in names
    # publish through bus reaches subscriber ports
    got = []
    motor = graph.module("motor_cortex")
    assert motor is not None
    motor.ins[("camera", "Image")].subscribe(lambda m: got.append(m.payload))
    graph.bus.publish("camera", "Image", {"frame": 1}, source="camera_eye")
    assert got == [{"frame": 1}]


def test_db3_replay_and_sim_before_real(tmp_path: Path) -> None:
    fixture = tmp_path / "trace.jsonl"
    write_fixture(
        fixture,
        [
            {"sensor": {"frame": 0}, "action": {"linear": 0.1, "angular": 0.0}},
            {"sensor": {"frame": 1, "obstacle_ahead": True}, "action": {"linear": 0.0, "angular": 0.3}},
        ],
    )
    bus = StreamBus()
    rep = ReplayMode.from_jsonl(fixture)
    msgs = rep.play(bus)
    assert len(msgs) >= 4

    receipts = []
    sim = SimulationMode(steps=4)
    recs = sim.run_camera_to_effector(bus, write_receipt=receipts.append)
    assert len(recs) == 4
    assert all(r["claim"] == "SIMULATED_NOT_REAL_HARDWARE" for r in recs)

    blocked = assert_sim_before_real(claimed_mode="real", simulation_ok=False, real_hardware_receipt=False)
    assert blocked["allowed"] is False
    assert blocked["label"] == "HYPOTHESIS"
    allowed = assert_sim_before_real(claimed_mode="real", simulation_ok=True, real_hardware_receipt=True)
    assert allowed["allowed"] is True


def test_db4_mcp_stream_skills(tmp_path: Path) -> None:
    bus = StreamBus()
    wrap_camera_frame(bus, {"w": 64, "h": 48}, source="eye")
    img = get_color_image(bus, state_dir=tmp_path)
    assert img["skill"] == "get_color_image"
    assert img["scar"].startswith("SCAR_")
    mv = relative_move(0.2, 0.0, bus=bus, mode="simulation", state_dir=tmp_path)
    assert mv["ok"] is True
    assert mv["claim"] == "SIMULATED_NOT_REAL_HARDWARE"
    blocked = relative_move(0.2, 0.0, bus=bus, mode="real", state_dir=tmp_path)
    assert blocked["ok"] is False
    exp = explore_room(bus=bus, note="kitchen", state_dir=tmp_path)
    assert exp["ok"] is True
    ledger = tmp_path / "mcp_stream_skill_receipts.jsonl"
    assert ledger.exists()
    assert sum(1 for _ in ledger.open()) >= 3


def test_db5_inprocess_transport() -> None:
    t = make_transport("inprocess")
    assert isinstance(t, InProcessTransport)
    got = []
    t.subscribe("cmd_vel", lambda e: got.append(e["payload"]))
    mid = t.publish("cmd_vel", {"linear": 0.05})
    assert mid
    assert got[0]["linear"] == 0.05


def test_db6_maturity_and_spy() -> None:
    lines = maturity_lines()
    assert any("EMBODIMENT" in ln for ln in lines)
    assert status_for("alice_hardware_body") == "green"
    assert status_for("real robot") == "red"
    assert any(r["status"] == "red" for r in EMBODIMENT_MATURITY)

    bus = StreamBus()
    spy = StreamSpy(bus).arm()
    wrap_camera_frame(bus, {"x": 1}, source="eye")
    wrap_cmd_vel(bus, {"linear": 0.0, "angular": 0.1}, source="motor")
    assert len(spy.events) == 2
    cam = spy.filter(name="camera")
    assert len(cam) == 1
    assert "STREAM SPY" in spy.summary_lines()[0]
