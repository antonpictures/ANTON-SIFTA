#!/usr/bin/env python3
"""
System/swarm_visual_acuity_budget.py

Event 115: Alice eye acuity / visual swimmer budget.

This module keeps the resolution math in one place so the UI, ledgers, and
downstream organs agree about how many stigmergic cells and visual swimmers a
given eye setting represents. It is deliberately pure Python: no Qt, no numpy,
no camera access.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from typing import Any, Dict, Optional


MIN_ACUITY = 4
DEFAULT_ACUITY = 32
DEFAULT_MAX_ACUITY = 64
HARD_MAX_ACUITY = 96
SOURCE_PIXELS_PER_CELL = 8

BASE_SWIMMER_GRID = 32
BASE_SWIMMER_COUNT = 1800
DEFAULT_SWIMMER_FLOOR = 3600


@dataclass(frozen=True)
class VisualAcuityBudget:
    grid_size: int
    total_cells: int
    source_thumb_px: int
    source_pixels_per_cell: int
    swimmer_budget: int
    swimmer_scale: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def configured_max_acuity() -> int:
    """Runtime max, bounded so one bad env var cannot melt the UI."""

    return max(MIN_ACUITY, min(HARD_MAX_ACUITY, _env_int("SIFTA_ALICE_EYE_MAX_ACUITY", DEFAULT_MAX_ACUITY)))


def configured_default_acuity() -> int:
    return clamp_acuity(_env_int("SIFTA_ALICE_EYE_DEFAULT_ACUITY", DEFAULT_ACUITY))


def clamp_acuity(value: Any, *, max_acuity: Optional[int] = None) -> int:
    try:
        grid_size = int(value)
    except (TypeError, ValueError):
        grid_size = DEFAULT_ACUITY
    ceiling = configured_max_acuity() if max_acuity is None else int(max_acuity)
    ceiling = max(MIN_ACUITY, min(HARD_MAX_ACUITY, ceiling))
    return max(MIN_ACUITY, min(ceiling, grid_size))


def visual_swimmer_floor() -> int:
    return max(1, _env_int("SIFTA_VISION_SWIMMERS", DEFAULT_SWIMMER_FLOOR))


def swimmer_budget_for_acuity(grid_size: Any, *, floor: Optional[int] = None) -> int:
    """Scale visual swimmers by cell count, with a conservative floor.

    32x32 is the old high-acuity setting. 64x64 has 4x more cells, so it gets
    4x the base visual swarm unless the user explicitly sets a higher floor.
    """

    acuity = clamp_acuity(grid_size)
    scale = (acuity / float(BASE_SWIMMER_GRID)) ** 2
    scaled = int(round(BASE_SWIMMER_COUNT * scale))
    return max(int(floor if floor is not None else visual_swimmer_floor()), scaled)


def build_visual_acuity_budget(grid_size: Any, *, max_acuity: Optional[int] = None) -> VisualAcuityBudget:
    acuity = clamp_acuity(grid_size, max_acuity=max_acuity)
    total_cells = acuity * acuity
    source_thumb = acuity * SOURCE_PIXELS_PER_CELL
    budget = swimmer_budget_for_acuity(acuity)
    return VisualAcuityBudget(
        grid_size=acuity,
        total_cells=total_cells,
        source_thumb_px=source_thumb,
        source_pixels_per_cell=SOURCE_PIXELS_PER_CELL,
        swimmer_budget=budget,
        swimmer_scale=round(budget / float(BASE_SWIMMER_COUNT), 6),
    )


def infer_square_grid_side(serialized: Any) -> Optional[int]:
    """Return side length for square hex grids such as saliency_q/motion_q."""

    if not isinstance(serialized, str):
        return None
    text = serialized.strip()
    if not text:
        return None
    side = math.isqrt(len(text))
    if side * side != len(text):
        return None
    return side
