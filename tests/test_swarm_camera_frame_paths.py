from __future__ import annotations

from pathlib import Path

from System.swarm_camera_frame_paths import (
    active_eye_frame_path,
    camera_device_frame_index_path,
    device_eye_frame_path,
    safe_camera_key,
)


def test_active_eye_frame_path_preserves_existing_contract(tmp_path: Path):
    assert active_eye_frame_path(tmp_path) == (
        tmp_path / "owner_body_vision_frames" / "active_eye_latest.png"
    )


def test_device_eye_frame_path_is_stable_and_identity_bound(tmp_path: Path):
    mac = device_eye_frame_path(
        "MacBook Pro Camera",
        "6C707041-05AC-0011-0002-000000000001",
        state_dir=tmp_path,
    )
    usb = device_eye_frame_path(
        "USB Camera VID:1133 PID:2081",
        "0x3121000046d0821",
        state_dir=tmp_path,
    )

    assert mac != usb
    assert mac.parent == tmp_path / "owner_body_vision_frames" / "by_device"
    assert usb.parent == tmp_path / "owner_body_vision_frames" / "by_device"
    assert mac.name == device_eye_frame_path(
        "MacBook Pro Camera",
        "6C707041-05AC-0011-0002-000000000001",
        state_dir=tmp_path,
    ).name


def test_camera_key_uses_unique_id_not_name_only():
    assert safe_camera_key("USB Camera", "uid-a") != safe_camera_key("USB Camera", "uid-b")


def test_camera_device_frame_index_path_lives_in_state(tmp_path: Path):
    assert camera_device_frame_index_path(tmp_path) == tmp_path / "camera_device_frames.jsonl"
