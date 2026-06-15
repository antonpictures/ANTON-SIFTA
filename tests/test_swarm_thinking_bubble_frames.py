"""Tests for the 5-char thinking shuttle frames."""
from __future__ import annotations

from System.swarm_thinking_bubble_frames import FRAMES, GLYPH, LANE_WIDTH, bubble_line, lane_frame


def test_glyph_is_five_chars():
    assert len(GLYPH) == 5


def test_every_frame_is_lane_width():
    for frame in FRAMES:
        assert len(frame) == LANE_WIDTH


def test_glyph_present_in_every_frame():
    for frame in FRAMES:
        assert GLYPH in frame


def test_shuttle_reverses():
    assert FRAMES[0].strip() == GLYPH
    assert FRAMES[-1].strip() == GLYPH
    assert len(FRAMES) >= 4


def test_lane_frame_wraps_phase():
    assert lane_frame(0) == FRAMES[0]
    assert lane_frame(len(FRAMES)) == FRAMES[0]


def test_bubble_line_includes_prefix_and_lane():
    line = bubble_line(3)
    assert line.startswith("●  thinking…")
    assert GLYPH in line