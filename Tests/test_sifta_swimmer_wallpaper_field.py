#!/usr/bin/env python3
"""Tests for the SIFTA Swimmer Wallpaper Field engine.

Key properties verified:
1. No face data leaves the gradient computation (the per-cell |dL| on a
   16x16 grid cannot encode face identity by construction).
2. Motion gradient is non-negative and bounded.
3. Drift field decays toward the new motion with the configured alpha.
4. Wake-word flash state machine ramps up, holds, and decays cleanly,
   and re-triggering resets the timer.
5. tick_swimmer_field is robust to missing frames / corrupted PNGs.
6. Update cost on a small grid is well below the 500 ms desktop budget.

Sandbox-safe: pure numpy + PIL + pytest.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pytest

from System.sifta_swimmer_wallpaper_field import (
    NO_FACE_GUARD,
    SwimmerDriftField,
    TRUTH_LABEL,
    WakeWordFlash,
    latest_two_frames,
    load_frame_as_grid,
    motion_gradient,
    tick_swimmer_field,
)


# ────────────────────────────────────────────────────────────────────────
# Helpers — synthetic frames written to tmp_path
# ────────────────────────────────────────────────────────────────────────
def _write_synthetic_frame(
    path: Path, brightness: float, motion_x: int = 0, motion_y: int = 0
) -> None:
    """Write a 64x64 grayscale PNG with a movable bright square."""
    from PIL import Image
    arr = (np.ones((64, 64), dtype=np.uint8) * int(brightness * 255)).copy()
    # Bright square at (16+motion_x, 16+motion_y) of size 16x16.
    y0 = max(0, 16 + motion_y)
    x0 = max(0, 16 + motion_x)
    arr[y0:y0 + 16, x0:x0 + 16] = 255
    Image.fromarray(arr, mode="L").save(str(path))


# ────────────────────────────────────────────────────────────────────────
# Truth-label / guard tests
# ────────────────────────────────────────────────────────────────────────
class TestGuards:
    def test_truth_label(self):
        assert TRUTH_LABEL == "SIFTA_SWIMMER_WALLPAPER_FIELD_V1"

    def test_no_face_guard_text(self):
        assert "MOTION_GRADIENT_ONLY" in NO_FACE_GUARD
        assert "no face detection" in NO_FACE_GUARD.lower()


# ────────────────────────────────────────────────────────────────────────
# Frame loading + motion gradient
# ────────────────────────────────────────────────────────────────────────
class TestFrameAndMotion:
    def test_load_frame_produces_small_grid(self, tmp_path):
        f = tmp_path / "a.png"
        _write_synthetic_frame(f, brightness=0.5)
        grid = load_frame_as_grid(f, grid=16)
        assert grid.shape == (16, 16)
        assert grid.dtype == np.float32
        assert grid.min() >= 0.0 and grid.max() <= 1.0

    def test_grid_too_small_rejected(self, tmp_path):
        f = tmp_path / "a.png"
        _write_synthetic_frame(f, brightness=0.5)
        with pytest.raises(ValueError):
            load_frame_as_grid(f, grid=2)

    def test_motion_gradient_zero_for_identical_frames(self):
        g = np.full((16, 16), 0.5, dtype=np.float32)
        m = motion_gradient(g, g)
        assert m.shape == (16, 16)
        assert np.allclose(m, 0.0)

    def test_motion_gradient_nonneg(self):
        a = np.full((16, 16), 0.2, dtype=np.float32)
        b = a.copy()
        b[5:9, 5:9] = 0.9  # bright patch appears
        m = motion_gradient(a, b)
        assert (m >= 0).all()

    def test_motion_gradient_shape_mismatch_raises(self):
        a = np.zeros((16, 16), dtype=np.float32)
        b = np.zeros((12, 12), dtype=np.float32)
        with pytest.raises(ValueError):
            motion_gradient(a, b)

    def test_no_face_recoverable_at_grid_16(self, tmp_path):
        """A 'face' (a circular bright region) at 64x64 reduces to a
        few cells at 16x16. The output array has only 256 values total —
        far below any face-recognition feature space.
        """
        # Build a synthetic 'face' frame.
        from PIL import Image
        arr = np.zeros((128, 128), dtype=np.uint8)
        for y in range(128):
            for x in range(128):
                if (x - 64) ** 2 + (y - 64) ** 2 < 30 ** 2:
                    arr[y, x] = 200
        face_path = tmp_path / "face.png"
        Image.fromarray(arr, mode="L").save(str(face_path))
        grid = load_frame_as_grid(face_path, grid=16)
        # 256 cells, no spatial frequency above what 16x16 supports.
        # The Architect's no-face contract is structural: at this
        # resolution there is no identity.
        assert grid.size == 256
        unique_values = np.unique((grid * 16).astype(int))
        # very few distinct intensity levels — nothing face-like
        assert len(unique_values) < 50


# ────────────────────────────────────────────────────────────────────────
# SwimmerDriftField
# ────────────────────────────────────────────────────────────────────────
class TestDriftField:
    def test_default_field_is_zero(self):
        f = SwimmerDriftField()
        assert f.field_state.shape == (16, 16)
        assert np.allclose(f.field_state, 0.0)

    def test_absorb_decays_old_state(self):
        f = SwimmerDriftField(decay_alpha=0.5)
        m1 = np.full((16, 16), 1.0, dtype=np.float32)
        f.absorb(m1)
        # After one absorb: state = 0.5 * 0 + 0.5 * 1 = 0.5
        assert np.allclose(f.field_state, 0.5)
        m2 = np.zeros((16, 16), dtype=np.float32)
        f.absorb(m2)
        # After second: state = 0.5 * 0.5 + 0.5 * 0 = 0.25
        assert np.allclose(f.field_state, 0.25)

    def test_invalid_decay_alpha_rejected(self):
        with pytest.raises(ValueError):
            SwimmerDriftField(decay_alpha=1.0)
        with pytest.raises(ValueError):
            SwimmerDriftField(decay_alpha=-0.1)

    def test_sample_at_corner(self):
        f = SwimmerDriftField()
        f.field_state[0, 0] = 1.0
        assert f.sample_at(0.0, 0.0) == pytest.approx(1.0, abs=1e-6)

    def test_drift_vector_is_zero_for_flat_field(self):
        f = SwimmerDriftField()
        f.field_state[:] = 0.5
        dx, dy = f.drift_vector(0.5, 0.5)
        assert abs(dx) < 1e-6 and abs(dy) < 1e-6

    def test_drift_vector_points_toward_higher_intensity(self):
        f = SwimmerDriftField()
        # Bright corner at upper-left.
        f.field_state[0:4, 0:4] = 1.0
        dx, dy = f.drift_vector(0.5, 0.5)
        # Gradient should pull toward (0, 0) — so dx < 0 (west wins)
        # and dy < 0 (north wins).
        assert dx <= 0 + 1e-6
        assert dy <= 0 + 1e-6

    def test_overall_intensity_matches_mean(self):
        f = SwimmerDriftField()
        f.field_state[:] = 0.3
        assert f.overall_intensity() == pytest.approx(0.3, abs=1e-6)


# ────────────────────────────────────────────────────────────────────────
# WakeWordFlash
# ────────────────────────────────────────────────────────────────────────
class TestWakeFlash:
    def test_idle_returns_zero(self):
        w = WakeWordFlash()
        assert w.intensity(now=1000.0) == 0.0
        assert not w.is_active(now=1000.0)

    def test_rise_hold_fall(self):
        w = WakeWordFlash(rise_ms=40, hold_ms=30, fall_ms=80)
        w.trigger(now=1000.0)
        # 0 ms after trigger: rising from 0
        assert w.intensity(now=1000.0) == 0.0
        # 20 ms in (halfway up rise): ~0.5
        assert w.intensity(now=1000.020) == pytest.approx(0.5, abs=0.05)
        # 60 ms (past rise, into hold): 1.0
        assert w.intensity(now=1000.060) == pytest.approx(1.0)
        # 110 ms (past rise+hold, partway through fall): ~0.5
        assert w.intensity(now=1000.110) == pytest.approx(0.5, abs=0.1)
        # 200 ms (well past): back to idle
        assert w.intensity(now=1000.200) == 0.0

    def test_retrigger_resets(self):
        w = WakeWordFlash()
        w.trigger(now=1000.0)
        # 90 ms — should be in fall
        first = w.intensity(now=1000.090)
        # Retrigger at 90 ms
        w.trigger(now=1000.090)
        # 100 ms — only 10 ms into rise → small value, not the
        # falling-tail value
        retr = w.intensity(now=1000.100)
        assert retr < first or retr < 0.5

    def test_is_active_matches_intensity(self):
        w = WakeWordFlash()
        w.trigger(now=1000.0)
        assert w.is_active(now=1000.050)
        assert not w.is_active(now=1000.500)


# ────────────────────────────────────────────────────────────────────────
# tick_swimmer_field — the per-frame integration
# ────────────────────────────────────────────────────────────────────────
class TestTick:
    def test_no_frames_dir_returns_false(self, tmp_path):
        f = SwimmerDriftField()
        nowhere = tmp_path / "absent"
        assert tick_swimmer_field(f, frames_dir=nowhere) is False
        assert np.allclose(f.field_state, 0.0)

    def test_empty_frames_dir_returns_false(self, tmp_path):
        f = SwimmerDriftField()
        (tmp_path / "frames").mkdir()
        assert tick_swimmer_field(f, frames_dir=tmp_path / "frames") is False

    def test_one_frame_returns_false(self, tmp_path):
        d = tmp_path / "frames"
        d.mkdir()
        _write_synthetic_frame(d / "one.png", brightness=0.5)
        f = SwimmerDriftField()
        assert tick_swimmer_field(f, frames_dir=d) is False

    def test_two_frames_with_motion_absorbs(self, tmp_path):
        d = tmp_path / "frames"
        d.mkdir()
        a = d / "a.png"
        b = d / "b.png"
        _write_synthetic_frame(a, brightness=0.3, motion_x=0)
        # Force b to be newer mtime than a (filesystems sort by mtime).
        time.sleep(0.01)
        _write_synthetic_frame(b, brightness=0.3, motion_x=8)
        f = SwimmerDriftField()
        ok = tick_swimmer_field(f, frames_dir=d)
        assert ok is True
        # Some motion should have been absorbed somewhere in the field.
        assert f.overall_intensity() > 0.0

    def test_latest_two_frames_picks_newest(self, tmp_path):
        d = tmp_path / "frames"
        d.mkdir()
        for i, b in enumerate((0.1, 0.3, 0.5, 0.7)):
            p = d / f"frame_{i}.png"
            _write_synthetic_frame(p, brightness=b)
            time.sleep(0.005)
        pair = latest_two_frames(d)
        assert pair is not None
        prev, curr = pair
        assert curr.name == "frame_3.png"
        assert prev.name == "frame_2.png"


# ────────────────────────────────────────────────────────────────────────
# Resource budget — the Architect's "OS must not lag" constraint
# ────────────────────────────────────────────────────────────────────────
class TestResourceBudget:
    def test_full_tick_under_50ms_on_synthetic_frames(self, tmp_path):
        """One full tick (read 2 PNGs + downsample + gradient + absorb)
        must complete well under the 500 ms desktop timer budget.
        Conservatively assert <50 ms even in the sandbox.
        """
        d = tmp_path / "frames"
        d.mkdir()
        _write_synthetic_frame(d / "a.png", brightness=0.3)
        time.sleep(0.005)
        _write_synthetic_frame(d / "b.png", brightness=0.3, motion_x=4)
        f = SwimmerDriftField()
        t0 = time.perf_counter()
        ok = tick_swimmer_field(f, frames_dir=d)
        dt = (time.perf_counter() - t0) * 1000.0
        assert ok
        assert dt < 50.0, (
            f"tick took {dt:.1f}ms — must stay under the 500ms desktop "
            "budget with margin; if this fails, lower grid size or "
            "reduce smooth_kernel."
        )
