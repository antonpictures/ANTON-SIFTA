from __future__ import annotations


class _FakeCamera:
    def __init__(self, description: str) -> None:
        self._description = description

    def description(self) -> str:
        return self._description


def test_rank_cameras_keeps_macbook_owner_eye_before_usb(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_IPHONE_CAMERA", raising=False)
    monkeypatch.delenv("SIFTA_ALLOW_VIRTUAL_CAMERA", raising=False)
    from Applications.sifta_what_alice_sees_widget import _rank_cameras

    ranked = _rank_cameras(
        [
            _FakeCamera("USB Camera VID:1133 PID:2081"),
            _FakeCamera("MacBook Pro Camera"),
        ]
    )

    assert [cam.description() for cam in ranked] == [
        "MacBook Pro Camera",
        "USB Camera VID:1133 PID:2081",
    ]


def test_rank_cameras_keeps_usb_as_secondary_body_eye(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_IPHONE_CAMERA", raising=False)
    monkeypatch.delenv("SIFTA_ALLOW_VIRTUAL_CAMERA", raising=False)
    from Applications.sifta_what_alice_sees_widget import _rank_cameras

    ranked = _rank_cameras(
        [
            _FakeCamera("Other Webcam"),
            _FakeCamera("USB Camera VID:1133 PID:2081"),
            _FakeCamera("MacBook Pro Camera"),
            _FakeCamera("iPhone Camera"),
            _FakeCamera("Model ID: MacBook Pro Camera"),
            _FakeCamera("UVC Camera VendorID_1133 ProductID_2081"),
            _FakeCamera("OBS Virtual Camera"),
        ]
    )

    assert [cam.description() for cam in ranked] == [
        "MacBook Pro Camera",
        "USB Camera VID:1133 PID:2081",
    ]


def test_secondary_world_eye_is_usb_only_not_aux():
    from Applications.sifta_what_alice_sees_widget import _is_secondary_world_eye

    assert _is_secondary_world_eye("USB Camera VID:1133 PID:2081")
    assert not _is_secondary_world_eye("Logitech Brio")
    assert not _is_secondary_world_eye("MacBook Pro Camera")
    assert not _is_secondary_world_eye("OBS Virtual Camera")
    assert not _is_secondary_world_eye("iPhone Camera")
    assert not _is_secondary_world_eye("MacBook Pro Desk View Camera")


def test_secondary_world_eye_has_pulse_fallback_when_qt_second_session_is_silent():
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "Applications" / "sifta_what_alice_sees_widget.py").read_text(encoding="utf-8")

    assert "SECONDARY_WORLD_EYE_NO_FRAMES" in src
    assert "fallback\": \"pulse_single_camera_session\"" in src
    assert "SECONDARY_WORLD_EYE_PULSE_STARTED" in src
    assert "SECONDARY_WORLD_EYE_PULSE_FINISHED" in src
    assert "self._session.setCamera(None)" in src
    assert "self._session.setCamera(self._camera)" in src
