"""r1744 — with the ear off, the eye must not lie about being blind.

George 2026-08-09: "hai sa reparam camera sa fim sigur ca daca nu aude, VEDE."

For three days the What Alice Sees surface wrote `no_cameras_detected` — 199 of
its last 200 receipts — while the canonical camera worker was writing fresh
frames to disk the whole time. Two lanes, one body. These tests pin the rule:
a display surface may only claim blindness when the body has no fresh sight.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtGui")

from PyQt6.QtGui import QImage  # noqa: E402


def _write_frame(path: Path, *, age_s: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(0x203040)
    assert img.save(str(path), "PNG")
    if age_s:
        stamp = time.time() - age_s
        import os

        os.utime(path, (stamp, stamp))


class _FakeCanvas:
    def __init__(self) -> None:
        self.error = "was blind"
        self._image = None
        self.chyron = ""

    def set_error(self, text) -> None:
        self.error = text

    def set_chyron(self, text, _color) -> None:
        self.chyron = text

    def update(self) -> None:
        pass


class _Surface:
    """Only the fallback organ under test, grafted onto a bare object.

    Importing the full widget pulls a Qt app and the whole SIFTA body; the two
    methods carry the doctrine, so they are what gets pinned.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._canvas = _FakeCanvas()
        self._tmp = tmp_path
        self._canonical_fallback_timer = object()  # pretend a timer already runs

    CANONICAL_FRAME_MAX_AGE_S = 30.0

    def _canonical_eye_frame(self):
        from Applications import sifta_what_alice_sees_widget as w

        return w.WhatAliceSeesWidget._canonical_eye_frame(self)


@pytest.fixture()
def frames(tmp_path, monkeypatch):
    """Point the canonical frame paths at a temp dir — never the real ledgers."""
    from System import swarm_camera_frame_paths as paths

    root = tmp_path / "active_eye_latest.png"
    nested = tmp_path / "owner_body_vision_frames" / "active_eye_latest.png"
    monkeypatch.setattr(paths, "_STATE", tmp_path, raising=False)
    import Applications.sifta_what_alice_sees_widget as w

    monkeypatch.setattr(w, "root_active_eye_frame_path", lambda: root)
    monkeypatch.setattr(w, "active_eye_frame_path", lambda: nested)
    return root, nested


def test_fresh_canonical_frame_is_sight_not_blindness(tmp_path, frames):
    root, _nested = frames
    _write_frame(root, age_s=0.4)

    surface = _Surface(tmp_path)
    img, age, path = surface._canonical_eye_frame()

    assert img is not None, "a 0.4s-old frame is live sight"
    assert age < 1.0
    assert path.endswith("active_eye_latest.png")


def test_normal_worker_gap_still_counts_as_sight(tmp_path, frames):
    """Measured on this node: healthy frame gaps reach 19.5s. Do not flap."""
    root, _nested = frames
    _write_frame(root, age_s=19.5)

    surface = _Surface(tmp_path)
    img, _age, _path = surface._canonical_eye_frame()

    assert img is not None, "a worst-case healthy gap must not read as blindness"


def test_stale_frame_is_a_memory_and_must_not_pass_as_sight(tmp_path, frames):
    root, _nested = frames
    _write_frame(root, age_s=90.0)

    surface = _Surface(tmp_path)
    img, age, _path = surface._canonical_eye_frame()

    assert img is None, "a 90s-old frame is a memory; painting it as live is a lie"
    assert age > surface.CANONICAL_FRAME_MAX_AGE_S


def test_no_frame_at_all_reports_no_sight(tmp_path, frames):
    surface = _Surface(tmp_path)
    img, _age, _path = surface._canonical_eye_frame()

    assert img is None, "nothing on disk means the body really has no sight here"


def test_newest_frame_wins_across_lanes(tmp_path, frames):
    root, nested = frames
    _write_frame(root, age_s=8.0)
    _write_frame(nested, age_s=0.2)

    surface = _Surface(tmp_path)
    img, age, path = surface._canonical_eye_frame()

    assert img is not None
    assert age < 1.0, "the freshest lane is the one the body is actually seeing"
    assert "owner_body_vision_frames" in path
