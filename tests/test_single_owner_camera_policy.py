from __future__ import annotations

from dataclasses import dataclass
import json
import pytest


@dataclass
class _FakeCamera:
    name: str

    def description(self) -> str:
        return self.name


def test_default_camera_rank_has_one_embedded_owner_eye(monkeypatch):
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    from Applications.sifta_what_alice_sees_widget import _rank_cameras

    ranked = _rank_cameras([
        _FakeCamera("USB Camera VID:1133 PID:2081"),
        _FakeCamera("Model ID: MacBook Pro Camera"),
        _FakeCamera("MacBook Pro Camera"),
        _FakeCamera("iPhone Camera"),
    ])

    assert [camera.description() for camera in ranked] == ["MacBook Pro Camera"]


def test_stale_non_owner_target_resolves_to_embedded_eye(monkeypatch):
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    from System import swarm_camera_target as target

    monkeypatch.setattr(
        target,
        "_raw_live_devices",
        lambda: [
            ("mac-live", "MacBook Pro Camera"),
            ("usb-live", "USB Camera VID:1133 PID:2081"),
        ],
    )

    assert target.resolve_index({
        "name": "USB Camera VID:1133 PID:2081",
        "index": 1,
        "unique_id": "usb-live",
        "writer": "swarm_oculomotor_saccades",
    }) == 0


def test_camera_snapshot_reports_no_secondary_capture(monkeypatch, tmp_path):
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    from System.swarm_camera_policy import camera_eye_snapshot

    (tmp_path / "active_saccade_target.json").write_text(
        '{"name":"MacBook Pro Camera"}\n', encoding="utf-8"
    )
    _live_receipts(tmp_path)

    snapshot = camera_eye_snapshot(tmp_path, now=1000.0)
    assert snapshot["active_target_allowed"] is True
    assert snapshot["secondary_capture_allowed"] is False
    assert snapshot["connection_state"] == "LIVE_CAPTURE_VERIFIED"
    assert snapshot["capture_gate_pass"] is True


def _live_receipts(state):
    for name, row in {
        "active_eye_identity_frames.jsonl": {"ts": 999.0, "device": "MacBook Pro Camera", "w": 640, "h": 480, "sha8": "frame123"},
        "visual_stigmergy.jsonl": {"ts": 999.0, "camera_name": "MacBook Pro Camera", "w": 640, "h": 480, "sha8": "frame123"},
        "camera_capture_policy.jsonl": {"ts": 999.0, "device": "MacBook Pro Camera", "single_owner_eye": True, "secondary_capture": False, "capture_winks": False},
    }.items():
        (state / name).write_text(json.dumps(row) + "\n")
    (state / "kernel_process_table.json").write_text(json.dumps({"processes": {"vision": {"health": 1.0, "last_heartbeat_ts": 999.0}}}))


@pytest.mark.parametrize("record", [
    {"index": 0}, {"unique_id": "phone"}, {"name": "MacBook Pro Camera", "index": 0},
    {"name": "USB Camera VID:1133 PID:2081", "index": 1},
])
def test_raw_indices_include_excluded_devices(monkeypatch, record):
    from System import swarm_camera_target as target
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    monkeypatch.setattr(target, "_raw_live_devices", lambda: [("phone", "iPhone Camera"), ("usb", "USB Camera"), ("mac", "MacBook Pro Camera")])
    assert target.resolve_index(record) == 2
    assert target.preferred_live_index() == 2


def test_missing_embedded_camera_does_not_fall_back(monkeypatch):
    from System import swarm_camera_target as target
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    monkeypatch.setattr(target, "_raw_live_devices", lambda: [("usb", "USB Camera VID:1133 PID:2081")])
    assert target.resolve_index({"index": 0}) == -1
    assert target.preferred_live_index() == -1
    assert target.index_for_owner_selection(name="USB Camera VID:1133 PID:2081") is None
    with pytest.raises(ValueError, match="SINGLE_OWNER_EYE"):
        target.write_target(name="USB Camera VID:1133 PID:2081")


def test_off_does_not_reopen_the_camera(monkeypatch):
    from System import swarm_camera_target as target
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    monkeypatch.setattr(target, "_raw_live_devices", lambda: [("mac", "MacBook Pro Camera")])
    assert target.resolve_index({"unique_id": "OFF", "index": 0}) == -1


@pytest.mark.parametrize("name", ["iPhone FaceTime Camera", "MacBook Pro Camera Desk View", "OBS Built-in Camera", "Model ID: MacBook Pro Camera"])
def test_misleading_device_names_are_excluded(monkeypatch, name):
    from System.swarm_camera_policy import capture_allowed
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    assert capture_allowed(name) is False


def test_health_expires_even_if_cached_proof_was_green(tmp_path):
    from System.swarm_camera_policy import camera_eye_snapshot
    _live_receipts(tmp_path)
    (tmp_path / "camera_unified_field_proof.jsonl").write_text('{"camera_healthy":true,"connection_state":"LIVE_CAPTURE_VERIFIED"}\n')
    result = camera_eye_snapshot(tmp_path, now=1100.0)
    assert result["camera_healthy"] is False
    assert result["runtime_policy_verified"] is False
    assert result["capture_gate_pass"] is False


def test_future_receipts_do_not_prove_live_capture(tmp_path):
    from System.swarm_camera_policy import camera_eye_snapshot
    _live_receipts(tmp_path)
    assert camera_eye_snapshot(tmp_path, now=900.0)["capture_gate_pass"] is False


def test_winking_cannot_interrupt_single_camera(monkeypatch):
    from types import SimpleNamespace
    from Applications.sifta_what_alice_sees_widget import WhatAliceSeesWidget
    monkeypatch.delenv("SIFTA_SINGLE_OWNER_EYE", raising=False)
    def forbidden():
        pytest.fail("Camera.stop called for decorative wink")
    surface = SimpleNamespace(_camera=SimpleNamespace(stop=forbidden), _led_blinking=False)
    WhatAliceSeesWidget._wink_led(surface, 200)
