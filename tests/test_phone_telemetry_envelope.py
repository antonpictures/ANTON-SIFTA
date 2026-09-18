from __future__ import annotations

import math

from System.swarm_web_global_chat_gate import _capture_envelope


def test_phone_telemetry_is_bounded_and_finite():
    result = _capture_envelope(
        {
            "capture_id": "capture-1",
            "telemetry": {
                "schema_version": "sifta.iphone.telemetry.v1",
                "device_id": "browser-device",
                "captured_at": "2026-09-11T10:00:00Z",
                "consent": {"motion": True, "location": True, "battery": True},
                "signals": {
                    "motion": {"acceleration_x": 1.5, "rotation_z": -0.2},
                    "location": {"latitude": 44.4, "longitude": 26.1, "accuracy": 30},
                    "battery": {"level": 4.0, "charging": True},
                },
            },
        }
    )
    telemetry = result["telemetry"]
    assert telemetry["consent"] == {"motion": True, "location": True, "battery": True}
    assert telemetry["signals"]["motion"]["acceleration_x"] == 1.5
    assert telemetry["signals"]["battery"]["level"] == 1.0
    assert all(math.isfinite(value) for value in telemetry["signals"]["location"].values())


def test_phone_telemetry_drops_nonfinite_values_and_unknown_fields():
    result = _capture_envelope(
        {
            "telemetry": {
                "consent": {"motion": "yes", "unknown": True},
                "signals": {
                    "motion": {"acceleration_x": float("nan"), "secret": 123},
                    "location": {"latitude": float("inf")},
                },
            }
        }
    )
    telemetry = result["telemetry"]
    assert telemetry["consent"] == {"motion": True}
    assert telemetry["signals"] == {}


def test_phone_capture_keeps_bounded_camera_and_face_provenance():
    result = _capture_envelope({
        "capture_id": "capture-2",
        "camera_facing": "user",
        "face_signal": "absent",
        "owner_presence": "unverified",
        "likely_black": False,
        "pose": {"untrusted": "client data remains bounded"},
    })
    assert result["camera_facing"] == "user"
    assert result["face_signal"] == "absent"
    assert result["owner_presence"] == "unverified"
    assert result["likely_black"] is False
    assert result["pose"] == {"untrusted": "client data remains bounded"}


def test_phone_capture_rejects_fabricated_identity_or_camera_values():
    result = _capture_envelope({
        "camera_facing": "owner-face",
        "face_signal": "owner_verified",
        "owner_presence": "present",
        "likely_black": "no",
    })
    assert "camera_facing" not in result
    assert "face_signal" not in result
    assert "owner_presence" not in result
    assert "likely_black" not in result
