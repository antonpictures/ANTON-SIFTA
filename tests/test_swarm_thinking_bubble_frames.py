"""Tests for Earth shuttle + blinking star thinking frames."""
from __future__ import annotations

from System.swarm_thinking_bubble_frames import (
    EARTH,
    FRAMES,
    LANE_WIDTH,
    UFO,
    bubble_line,
    lane_frame,
)


def test_earth_present_in_every_frame():
    for frame in FRAMES:
        assert EARTH in frame
        assert UFO == EARTH


def test_lane_width_constant():
    for frame in FRAMES:
        assert len(frame) == LANE_WIDTH


def test_earth_moves_across_frames():
    positions = [f.index(EARTH) for f in FRAMES[:24]]
    assert min(positions) < max(positions)


def test_stars_blink_while_earth_moves():
    """Fixed star slots change glyph across phases (not only Earth motion)."""
    left_slot = 1
    glyphs = {FRAMES[p][left_slot] for p in range(0, 12, 2) if FRAMES[p][left_slot] != EARTH}
    assert len(glyphs) >= 2


def test_lane_frame_wraps_phase():
    assert lane_frame(0) == FRAMES[0]
    assert lane_frame(len(FRAMES)) == FRAMES[0]


def test_bubble_line_prefix_and_earth():
    line = bubble_line(4)
    assert line.startswith("●  thinking…")
    assert EARTH in line


def test_first_frame_matches_owner_pattern_shape():
    """Earth left, star cluster, gap, right cluster — like 🌍·∙˙·∙     ˙∙·˙∙"""
    frame = FRAMES[0]
    assert frame[0] == EARTH
    assert frame[1] in "·∙˙"
    assert frame[10] in "·∙˙"