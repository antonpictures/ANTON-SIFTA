#!/usr/bin/env python3
"""System/swarm_thinking_bubble_frames.py — 5-char thinking shuttle for UI bubbles.

Architect 2026-06-14 (Grok IDE inspiration): while Alice thinks, a short glyph
lane moves left→right→left inside the purple thinking bubble — like the Grok
terminal strip, but without a UFO emoji. The moving unit is exactly five chars.

Truth label: ``THINKING_BUBBLE_FRAMES_V1``.
"""
from __future__ import annotations

_TRUTH_LABEL = "THINKING_BUBBLE_FRAMES_V1"

# Five-char thinking glyph — the swimmer cluster that walks the lane.
GLYPH = "∙˙·∙˙"
LANE_WIDTH = 11


def _build_frames(*, glyph: str = GLYPH, lane_width: int = LANE_WIDTH) -> tuple[str, ...]:
    span = max(0, lane_width - len(glyph))
    frames: list[str] = []
    for pos in range(span + 1):
        frames.append(" " * pos + glyph + " " * (span - pos))
    for pos in range(span - 1, -1, -1):
        frames.append(" " * pos + glyph + " " * (span - pos))
    return tuple(frames)


FRAMES: tuple[str, ...] = _build_frames()


def lane_frame(phase: int) -> str:
    """Return one shuttle frame for the given animation phase."""
    if not FRAMES:
        return GLYPH
    return FRAMES[int(phase) % len(FRAMES)]


def bubble_line(phase: int, *, prefix: str = "●  thinking…") -> str:
    """Full single-line text for the Talk thinking bubble QLabel."""
    return f"{prefix}  {lane_frame(phase)}"


__all__ = [
    "FRAMES",
    "GLYPH",
    "LANE_WIDTH",
    "_TRUTH_LABEL",
    "bubble_line",
    "lane_frame",
]