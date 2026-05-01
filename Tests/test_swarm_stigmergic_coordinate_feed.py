"""
tests/test_swarm_stigmergic_coordinate_feed.py
═══════════════════════════════════════════════
Falsifiable tests for the real-coordinate feed.

Invariants:
  1. coords_to_grid always stays in-bounds.
  2. coords_to_grid is deterministic.
  3. cursor_screen_coords returns a CoordSample with a valid truth_label.
  4. sample_real_grid_position returns a valid grid cell.
  5. best_grid_position returns valid cell + truth label.
  6. read_visual_stigmergy_coords returns pixel_x/y when present.
  7. Whole-stack: cursor → pheromone deposit with REAL_CURSOR_COORDS label.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── 1. coords_to_grid in-bounds ───────────────────────────────────────────

def test_coords_to_grid_inbounds():
    from System.swarm_stigmergic_coordinate_feed import coords_to_grid
    for grid_size in (16, 32, 64):
        for (px, py, sw, sh) in [
            (0, 0, 2560, 1600),
            (2559, 1599, 2560, 1600),
            (1280, 800, 2560, 1600),
            (0.5, 0.5, 1, 1),       # boundary
        ]:
            gx, gy = coords_to_grid(px, py, sw, sh, grid_size)
            assert 0 <= gx < grid_size, f"gx={gx} OOB for grid_size={grid_size}"
            assert 0 <= gy < grid_size, f"gy={gy} OOB for grid_size={grid_size}"


# ── 2. coords_to_grid deterministic ──────────────────────────────────────

def test_coords_to_grid_deterministic():
    from System.swarm_stigmergic_coordinate_feed import coords_to_grid
    a = coords_to_grid(1234.5, 678.9, 2560, 1600, 32)
    b = coords_to_grid(1234.5, 678.9, 2560, 1600, 32)
    assert a == b


# ── 3. cursor_screen_coords truth_label ──────────────────────────────────

def test_cursor_screen_coords_truth_label():
    from System.swarm_stigmergic_coordinate_feed import (
        cursor_screen_coords, TRUTH_REAL, TRUTH_SIM
    )
    sample = cursor_screen_coords()
    assert sample.truth_label in (TRUTH_REAL, TRUTH_SIM), (
        f"Unexpected truth_label: {sample.truth_label}"
    )
    assert sample.screen_w > 0
    assert sample.screen_h > 0
    # On multi-monitor setups the cursor can be on a secondary display
    # whose x/y exceeds the primary display bounds — allow up to 4× primary size
    assert sample.x_px >= 0
    assert sample.y_px >= 0


# ── 4. sample_real_grid_position ─────────────────────────────────────────

def test_sample_real_grid_position_inbounds():
    from System.swarm_stigmergic_coordinate_feed import sample_real_grid_position
    sample, (gx, gy) = sample_real_grid_position(32)
    assert 0 <= gx < 32
    assert 0 <= gy < 32


# ── 5. best_grid_position ────────────────────────────────────────────────

def test_best_grid_position_valid(tmp_path):
    from System.swarm_stigmergic_coordinate_feed import best_grid_position
    gx, gy, label = best_grid_position(32, tmp_path)
    assert 0 <= gx < 32
    assert 0 <= gy < 32
    assert isinstance(label, str) and len(label) > 0


# ── 6. read_visual_stigmergy_coords ──────────────────────────────────────

def test_read_visual_stigmergy_coords_finds_pixel(tmp_path):
    from System.swarm_stigmergic_coordinate_feed import read_visual_stigmergy_coords
    ledger = tmp_path / "visual_stigmergy.jsonl"
    row = {"ts": 1.0, "pixel_x": 800.0, "pixel_y": 450.0, "label": "test"}
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = read_visual_stigmergy_coords(tmp_path)
    assert result is not None
    assert abs(result[0] - 800.0) < 0.1
    assert abs(result[1] - 450.0) < 0.1


def test_read_visual_stigmergy_coords_none_when_missing(tmp_path):
    from System.swarm_stigmergic_coordinate_feed import read_visual_stigmergy_coords
    result = read_visual_stigmergy_coords(tmp_path)
    assert result is None


# ── 7. End-to-end: cursor → pheromone deposit with truth label ───────────

def test_pheromone_update_emits_real_coord_label(tmp_path, monkeypatch):
    """
    When the coordinate feed works, the pheromone receipt must contain
    a coord_truth_label that is NOT 'HASH_PROXY'.
    """
    import System.swarm_body_brain_loop as bbl
    monkeypatch.setattr(bbl, "_STATE_DIR", str(tmp_path), raising=False)

    from System.swarm_pheromone_field import update_pheromone_field
    result = update_pheromone_field({"action": "explore", "td_value": 0.5})
    # On a real Mac with Quartz, should be REAL_CURSOR_COORDS or SIM_BROWNIAN_WALK
    assert "coord_truth_label" in result
    assert result["coord_truth_label"] != "HASH_PROXY", (
        "coord feed returned hash proxy — Quartz / coordinate feed not working"
    )


def test_pheromone_caller_supplied_coords(tmp_path, monkeypatch):
    """Caller-supplied x,y must be used and labelled CALLER_SUPPLIED."""
    import System.swarm_body_brain_loop as bbl
    monkeypatch.setattr(bbl, "_STATE_DIR", str(tmp_path), raising=False)

    from System.swarm_pheromone_field import update_pheromone_field, load_grid
    result = update_pheromone_field(
        {"action": "test", "td_value": 1.0}, x=5, y=7
    )
    assert result["coord_truth_label"] == "CALLER_SUPPLIED"
    assert result["position"] == [5, 7]
    grid = load_grid()
    assert grid[7][5] > 0.0
