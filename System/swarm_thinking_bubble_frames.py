#!/usr/bin/env python3
"""System/swarm_thinking_bubble_frames.py — Earth shuttle + blinking star field.

Architect 2026-06-14: Grok-style thinking strip. Fixed star slots blink
(· ∙ ˙ cycle); planet Earth moves left→right→left across the lane.

Truth label: ``THINKING_BUBBLE_FRAMES_V3``.
"""
from __future__ import annotations

_TRUTH_LABEL = "THINKING_BUBBLE_FRAMES_V3"

EARTH = "🌍"
# Moving shuttle glyph — Earth replaces the old UFO (UFO kept as alias for imports).
UFO = EARTH
GLYPH = EARTH
LANE_WIDTH = 16

STAR_PHASES = ("·", "∙", "˙")
LEFT_STAR_SLOTS = (1, 2, 3, 4, 5)
GAP_SLOTS = (6, 7, 8, 9)
RIGHT_STAR_SLOTS = (10, 11, 12, 13, 14, 15)

_SHUTTLE_PATH = tuple(range(0, 12)) + tuple(range(11, -1, -1))


def _star_char(phase: int, slot_index: int) -> str:
    return STAR_PHASES[(int(phase) + int(slot_index)) % len(STAR_PHASES)]


def _render_lane(phase: int, shuttle_slot: int) -> str:
    cells = [" "] * LANE_WIDTH
    for i, idx in enumerate(LEFT_STAR_SLOTS):
        if idx != shuttle_slot:
            cells[idx] = _star_char(phase, i)
    for i, idx in enumerate(RIGHT_STAR_SLOTS):
        if idx != shuttle_slot:
            cells[idx] = _star_char(phase, i + len(LEFT_STAR_SLOTS))
    if 0 <= shuttle_slot < LANE_WIDTH:
        cells[shuttle_slot] = EARTH
    return "".join(cells)


def _build_frames() -> tuple[str, ...]:
    return tuple(
        _render_lane(phase, _SHUTTLE_PATH[phase % len(_SHUTTLE_PATH)]) for phase in range(48)
    )


FRAMES: tuple[str, ...] = _build_frames()


def lane_frame(phase: int) -> str:
    """Return one lane frame: blinking stars + Earth at shuttle position."""
    if not FRAMES:
        return EARTH
    return FRAMES[int(phase) % len(FRAMES)]


def bubble_line(phase: int, *, prefix: str = "●  thinking…") -> str:
    """Full single-line text for the Talk thinking bubble."""
    return f"{prefix}  {lane_frame(phase)}"


__all__ = [
    "EARTH",
    "FRAMES",
    "GLYPH",
    "LANE_WIDTH",
    "UFO",
    "_TRUTH_LABEL",
    "bubble_line",
    "lane_frame",
]