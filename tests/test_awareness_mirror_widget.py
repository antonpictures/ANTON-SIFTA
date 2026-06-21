"""Tests for the Awareness Mirror widget (task #58).

Architect 2026-05-14: "If I see my mirror image on the screen I know
Alice is watching me right now. That's the truth — it's just for the
awareness for the person."

These tests verify the data contract — the widget reads from the
canonical camera-worker frame file on disk and never opens a second
QCamera handle (which would conflict with the existing reader).
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_SRC = (Path(__file__).resolve().parent.parent
        / "Applications" / "sifta_awareness_mirror_widget.py"
        ).read_text(encoding="utf-8")


# ── Source-code shape (no PyQt6 import — sandbox has no Qt) ─────

def test_module_has_required_classes():
    """Public surface includes the three classes the host expects."""
    assert "class AwarenessMirrorApp" in _SRC
    assert "class AwarenessMirrorWidget" in _SRC
    assert "class DualAwarenessMirrorWidget" in _SRC
    assert "class _MirrorCanvas" in _SRC


def test_frame_file_path_points_at_canonical_worker_output():
    """The widget MUST read from the file the canonical camera worker
    writes — NOT open its own QCamera."""
    assert "active_eye_latest.png" in _SRC
    assert "owner_body_vision_frames" in _SRC
    assert "by_device" in _SRC


def test_truth_label_is_v1():
    assert 'TRUTH_LABEL = "AWARENESS_MIRROR_V1"' in _SRC


def test_truth_boundary_states_no_camera_open():
    """The boundary text must make explicit that this widget does NOT
    open the camera — only reads the on-disk frame."""
    boundary_lower = _SRC.lower()
    assert "does not open the camera" in boundary_lower or \
           "not open the camera" in boundary_lower
    assert "mirror" in boundary_lower or "reads" in boundary_lower


def test_truth_boundary_mentions_stigmergic_camera():
    """The boundary must say Alice already reads the camera
    stigmergically — this widget exists for the HUMAN, not for her."""
    assert "stigmergically" in _SRC.lower()


# ── Source code shape — no QCamera instantiation ────────────────

def test_widget_does_not_instantiate_qcamera():
    """Critical: opening a second QCamera handle would conflict with
    the existing WhatAliceSeesWidget camera worker on macOS."""
    src = (Path(__file__).resolve().parent.parent
           / "Applications" / "sifta_awareness_mirror_widget.py"
           ).read_text(encoding="utf-8")
    # Must NOT use cv2.VideoCapture or QCamera() to open the camera
    assert "cv2.VideoCapture" not in src
    assert "QCamera()" not in src
    assert "QMediaCaptureSession" not in src
    # MUST read the file from disk
    assert "active_eye_latest.png" in src
    assert "device_eye_frame_path" in src


def test_single_active_eye_mirror_reads_active_saccade_target():
    """Talk embed shows one panel bound to active_saccade_target.json (r1286)."""
    assert "ActiveAwarenessMirrorWidget" in _SRC
    assert "_active_eye_display_bundle" in _SRC
    assert "active_saccade_target.json" in _SRC
    assert "hide_when_stale=True" in (Path(__file__).resolve().parent.parent
        / "Applications" / "sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")


def test_dual_widget_reads_registry_and_topology_for_two_camera_display():
    """Legacy dual strip still exists for older embeds; Talk no longer uses it."""
    assert "DualAwarenessMirrorWidget" in _SRC
    assert "deprecated in Talk" in _SRC.lower() or "legacy" in _SRC.lower()


def test_frame_source_prefers_freshest_owner_eye_path():
    """Owner tile must not go black when active-eye PNG is newer than per-device."""
    assert "def _frame_mtime" in _SRC
    assert "max(candidates, key=_frame_mtime)" in _SRC


def test_dual_widget_filters_aux_cameras_and_labels_logitech_usb():
    """The chat strip should be MacBook owner eye + Logitech/USB world eye, not OBS/iPhone."""
    assert "def _is_excluded_aux_camera" in _SRC
    assert '"obs"' in _SRC
    assert '"iphone"' in _SRC
    assert '"continuity"' in _SRC
    assert "role not in {\"owner_eye\", \"world_eye\"}" in _SRC
    assert "Logitech USB" in _SRC
    assert "vid:1133" in _SRC
    assert "pid:2081" in _SRC


def test_widget_polls_at_two_hz():
    """The architect said 'doesn't need much resolution, 480p is enough'
    — for awareness purposes 2 Hz refresh is plenty."""
    src = (Path(__file__).resolve().parent.parent
           / "Applications" / "sifta_awareness_mirror_widget.py"
           ).read_text(encoding="utf-8")
    # The timer is started at 500ms (2 Hz)
    assert "start(500)" in src or "refresh_ms: int = 500" in src


def test_widget_has_rec_indicator_when_fresh():
    """Eye badge with red pupil dot signals the camera is live (no REC label)."""
    assert "_draw_eye_live_badge" in _SRC
    assert "👁" in _SRC
    assert 'drawText(22, 17, "REC")' not in _SRC
    assert "ff3030" in _SRC.lower() or "#ff3" in _SRC.lower()


def test_widget_has_stale_indicator_when_old():
    """Stale frame uses muted eye badge without STALE label text."""
    assert "_draw_eye_live_badge" in _SRC
    assert 'drawText(22, 17, "STALE")' not in _SRC


def test_caption_carries_awareness_message():
    """The architect's framing: 'You are aware of yourself.'"""
    src = (Path(__file__).resolve().parent.parent
           / "Applications" / "sifta_awareness_mirror_widget.py"
           ).read_text(encoding="utf-8")
    assert "aware of yourself" in src.lower()
    assert "watching" in src.lower()


# ── Default sizes are small (architect: '480p is enough, even smaller') ─

def test_default_preview_size_is_small():
    """Architect's spec: '480p is enough, even smaller'. Defaults must
    be small enough that the widget doesn't dominate the desktop."""
    # Pull PREVIEW_W / PREVIEW_H literal values from the source
    import re
    m_w = re.search(r"^PREVIEW_W\s*=\s*(\d+)", _SRC, re.MULTILINE)
    m_h = re.search(r"^PREVIEW_H\s*=\s*(\d+)", _SRC, re.MULTILINE)
    assert m_w is not None
    assert m_h is not None
    w = int(m_w.group(1))
    h = int(m_h.group(1))
    assert w <= 480, f"PREVIEW_W={w} too large for awareness widget"
    assert h <= 360, f"PREVIEW_H={h} too large for awareness widget"
    ratio = w / h
    assert 1.7 < ratio < 1.85, f"aspect ratio {ratio} is not ~16:9"


def test_embeddable_widget_has_size_param():
    """The corner-of-desktop overlay version takes a size tuple so
    hosts can place it as small as they want."""
    assert "size: tuple[int, int]" in _SRC or "size=" in _SRC
    # The __init__ signature contains the size kwarg
    assert "def __init__(\n        self,\n        parent" in _SRC


def test_embeddable_widget_hides_when_frame_stale():
    """The Talk/desktop embed must not keep a stale camera tile visible."""
    assert "hide_when_stale: bool = True" in _SRC
    assert "def _sync_visibility(self, fresh: bool)" in _SRC
    assert "self.setVisible(bool(fresh))" in _SRC


# ── App name + class ─────────────────────────────────────────────

def test_app_name_is_awareness_mirror():
    assert 'APP_NAME = "Awareness Mirror"' in _SRC
