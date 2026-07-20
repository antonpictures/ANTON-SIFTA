import time

from System import swarm_camera_target
from System.swarm_eye_registry import (
    AUX_ROLE,
    OWNER_ROLE,
    WORLD_ROLE,
    build_eye_registry,
    classify_eye_role,
    live_owner_eye_device,
    live_world_eye_device,
    plug_play_sensor_registry,
)
from System.swarm_sensor_attention_director import default_sensor_registry


def test_plug_play_registry_uses_live_topology_not_hardcoded_vid(monkeypatch):
    monkeypatch.setattr(
        swarm_camera_target,
        "_live_devices",
        lambda: [
            ("mac-live", "MacBook Pro Camera"),
            ("usb-live", "Generic USB Webcam"),
        ],
    )

    owner = live_owner_eye_device()
    world = live_world_eye_device()
    reg = plug_play_sensor_registry()
    senses = default_sensor_registry()

    assert owner["name"] == "MacBook Pro Camera"
    assert owner["index"] == 0
    assert world["name"] == "Generic USB Webcam"
    assert world["index"] == 1
    assert reg["close_owner_eye"]["name"] == "MacBook Pro Camera"
    assert reg["room_patrol_eye"]["name"] == "Generic USB Webcam"
    assert senses["close_owner_eye"].name == "MacBook Pro Camera"
    assert senses["room_patrol_eye"].name == "Generic USB Webcam"


def test_unplugged_world_eye_has_no_live_name(monkeypatch):
    monkeypatch.setattr(
        swarm_camera_target,
        "_live_devices",
        lambda: [("mac-live", "MacBook Pro Camera")],
    )

    world = live_world_eye_device()
    assert world["name"] == ""
    assert world["live"] is False


def test_eye_role_classifier_never_treats_continuity_as_owner_eye():
    assert classify_eye_role({"name": "MacBook Pro Camera"}) == OWNER_ROLE
    assert classify_eye_role({"name": "USB Camera VID:1133 PID:2081"}) == WORLD_ROLE
    assert classify_eye_role({"name": "iPhone Camera"}) == AUX_ROLE
    assert classify_eye_role({"name": "MacBook Pro Desk View Camera"}) == AUX_ROLE


def test_eye_registry_refresh_repairs_stale_iphone_owner_role():
    previous = {
        "eyes": [
            {
                "eye_id": "owner_eye",
                "role": OWNER_ROLE,
                "connection_state": "LIVE",
                "device_name": "iPhone Camera",
                "device_identity": {
                    "key": "iphone-uid",
                    "unique_id": "iphone-uid",
                    "name_key": "iphone camera",
                },
            }
        ]
    }

    snapshot = build_eye_registry(
        devices=[{"index": 0, "unique_id": "iphone-uid", "name": "iPhone Camera"}],
        previous=previous,
        now=123.0,
        frame_age_by_eye={},
    )

    eye = snapshot["eyes"][0]
    assert eye["role"] == AUX_ROLE
    assert eye["eye_id"] != "owner_eye"
