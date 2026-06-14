"""CUR-V4 — owner-eye safety: never auto-open the iPhone / Continuity camera,
and never open a live camera under tests/coding. George 2026-06-13."""
from __future__ import annotations

from System import swarm_camera_target as ct


def test_iphone_and_continuity_detected():
    assert ct.is_iphone_or_continuity("Ioan's iPhone Camera")
    assert ct.is_iphone_or_continuity("iPhone Camera")
    assert ct.is_iphone_or_continuity("iPhone Desk View Camera")
    # macOS 'Desk View' is a Continuity feature → also excluded from auto-pick
    assert ct.is_iphone_or_continuity("MacBook Pro Desk View Camera")
    assert not ct.is_iphone_or_continuity("MacBook Pro Camera")
    assert not ct.is_iphone_or_continuity("USB Camera VID:1133 PID:2081")
    assert not ct.is_iphone_or_continuity(None)


def test_builtin_owner_camera():
    assert ct.is_builtin_owner_camera("MacBook Pro Camera")
    assert ct.is_builtin_owner_camera("FaceTime HD Camera")
    assert not ct.is_builtin_owner_camera("Ioan's iPhone Camera")
    assert not ct.is_builtin_owner_camera("USB Camera VID:1133 PID:2081")


def test_prefer_builtin_over_iphone():
    # iPhone listed first, built-in present → built-in wins (the bug George hit)
    pick = ct.prefer_builtin_owner_eye(["Ioan's iPhone Camera", "MacBook Pro Camera"])
    assert pick == "MacBook Pro Camera"


def test_iphone_refused_unless_explicitly_allowed():
    # Only the iPhone available → refuse (None) by default
    assert ct.prefer_builtin_owner_eye(["iPhone Camera"]) is None
    # …unless George explicitly opts in
    assert ct.prefer_builtin_owner_eye(["iPhone Camera"], allow_iphone=True) == "iPhone Camera"


def test_usb_eye_when_no_builtin():
    # No built-in; USB world-eye is fine, iPhone still skipped
    pick = ct.prefer_builtin_owner_eye(["iPhone Desk View Camera", "USB Camera VID:1133 PID:2081"])
    assert pick == "USB Camera VID:1133 PID:2081"


def test_live_camera_blocked_under_pytest():
    # PYTEST_CURRENT_TEST is set by pytest during this run → no live camera open,
    # so a coding/test run can never wake the owner's iPhone.
    assert ct.live_camera_allowed() is False


def test_physical_capture_daemon_does_not_open_camera_under_pytest(monkeypatch):
    from System import swarm_physical_capture_daemon as daemon

    opened = []

    def fake_video_capture(index):
        opened.append(index)
        raise AssertionError("VideoCapture must not be called under pytest")

    monkeypatch.setattr(daemon.cv2, "VideoCapture", fake_video_capture)

    cap, idx = daemon._open_capture()

    assert cap is None
    assert idx == -1
    assert opened == []
