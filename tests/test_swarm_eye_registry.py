from __future__ import annotations

import json
from pathlib import Path

from System.swarm_eye_registry import (
    AUX_ROLE,
    LEDGER_NAME,
    OWNER_ROLE,
    WORLD_ROLE,
    build_eye_registry,
    eye_for_role,
    refresh_eye_registry,
)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_eye_registry_preserves_roles_across_index_shuffle(tmp_path: Path) -> None:
    first = [
        {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
        {"index": 1, "unique_id": "logitech-usb", "name": "USB Camera VID:1133 PID:2081"},
    ]
    second = [
        {"index": 0, "unique_id": "logitech-usb", "name": "USB Camera VID:1133 PID:2081"},
        {"index": 1, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
    ]

    snap1 = refresh_eye_registry(state_dir=tmp_path, devices=first, now=10.0)
    snap2 = refresh_eye_registry(state_dir=tmp_path, devices=second, now=20.0)

    owner1 = next(e for e in snap1["eyes"] if e["role"] == OWNER_ROLE)
    world1 = next(e for e in snap1["eyes"] if e["role"] == WORLD_ROLE)
    owner2 = next(e for e in snap2["eyes"] if e["role"] == OWNER_ROLE)
    world2 = next(e for e in snap2["eyes"] if e["role"] == WORLD_ROLE)

    assert owner1["eye_id"] == owner2["eye_id"] == "owner_eye"
    assert world1["eye_id"] == world2["eye_id"] == "world_eye"
    assert owner2["current_index"] == 1
    assert world2["current_index"] == 0
    assert owner2["device_identity"]["key"] == "mac-cam"
    assert world2["device_identity"]["key"] == "logitech-usb"


def test_eye_registry_marks_missing_world_eye_stale_without_role_swap(tmp_path: Path) -> None:
    refresh_eye_registry(
        state_dir=tmp_path,
        devices=[
            {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "logitech-usb", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=30.0,
    )
    snap = refresh_eye_registry(
        state_dir=tmp_path,
        devices=[{"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"}],
        now=40.0,
    )

    world = eye_for_role(WORLD_ROLE, state_dir=tmp_path, include_stale=True)
    owner = eye_for_role(OWNER_ROLE, state_dir=tmp_path)

    assert snap["live_eye_count"] == 1
    assert world["eye_id"] == "world_eye"
    assert world["connection_state"] == "STALE_OR_DETACHED"
    assert world["current_index"] is None
    assert owner["eye_id"] == "owner_eye"
    assert owner["connection_state"] == "LIVE"
    assert _rows(tmp_path / LEDGER_NAME)[-1]["stale_eye_count"] == 1
    events = _rows(tmp_path / "eye_registry_events.jsonl")
    assert any(e["event"] == "EYE_STALE" and e["eye_id"] == "world_eye" for e in events)


def test_eye_registry_cleans_qt_byte_unique_ids_without_duplicate_world_eye(tmp_path: Path) -> None:
    previous = build_eye_registry(
        state_dir=tmp_path,
        devices=[
            {"index": 0, "unique_id": "b'6C707041-05AC-0011-0002-000000000001'", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "b'0x3121000046d0821'", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=50.0,
    )
    snap = build_eye_registry(
        state_dir=tmp_path,
        previous=previous,
        devices=[
            {"index": 0, "unique_id": "6C707041-05AC-0011-0002-000000000001", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "0x3121000046d0821", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=60.0,
    )

    world_rows = [eye for eye in snap["eyes"] if eye["eye_id"] == "world_eye"]

    assert len(world_rows) == 1
    assert world_rows[0]["connection_state"] == "LIVE"
    assert world_rows[0]["current_index"] == 1
    assert world_rows[0]["device_identity"]["key"] == "0x3121000046d0821"


def test_owner_eye_is_always_expected_builtin_fallback(tmp_path: Path) -> None:
    snap = refresh_eye_registry(
        state_dir=tmp_path,
        devices=[
            {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "logitech-usb", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=70.0,
    )

    owner = next(e for e in snap["eyes"] if e["role"] == OWNER_ROLE)
    world = next(e for e in snap["eyes"] if e["role"] == WORLD_ROLE)

    assert "always-expected owner eye" in snap["owner_eye_policy"]
    assert owner["always_expected"] is True
    assert owner["fallback_priority"] == 0
    assert world["always_expected"] is False


def test_eye_registry_drops_stale_aux_obs_and_iphone_rows(tmp_path: Path) -> None:
    previous = build_eye_registry(
        state_dir=tmp_path,
        devices=[
            {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "usb-cam", "name": "USB Camera VID:1133 PID:2081"},
            {"index": 2, "unique_id": "obs-cam", "name": "OBS Virtual Camera"},
            {"index": 3, "unique_id": "iphone-cam", "name": "iPhone Camera"},
        ],
        now=80.0,
    )

    assert any(e["role"] == AUX_ROLE for e in previous["eyes"])

    snap = build_eye_registry(
        state_dir=tmp_path,
        previous=previous,
        devices=[
            {"index": 0, "unique_id": "mac-cam", "name": "MacBook Pro Camera"},
            {"index": 1, "unique_id": "usb-cam", "name": "USB Camera VID:1133 PID:2081"},
        ],
        now=90.0,
    )

    names = [e["device_name"] for e in snap["eyes"]]
    assert "MacBook Pro Camera" in names
    assert "USB Camera VID:1133 PID:2081" in names
    assert "OBS Virtual Camera" not in names
    assert "iPhone Camera" not in names
    assert all(e["role"] in {OWNER_ROLE, WORLD_ROLE} for e in snap["eyes"])
