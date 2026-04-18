#!/usr/bin/env python3
"""Qt QSplitter helpers — avoid zero-width side panes on first show (common Qt default)."""
from __future__ import annotations

from PyQt6.QtWidgets import QSplitter, QWidget


def balance_horizontal_splitter(
    splitter: QSplitter,
    host: QWidget,
    *,
    left_ratio: float = 0.72,
    min_right: int = 260,
    min_left: int = 240,
    max_right: int | None = None,
) -> None:
    """
    Set splitter handle positions from host width. Call after layout (e.g. QTimer.singleShot(0, ...)).
    Use max_right when the right widget has setMaximumWidth (e.g. GCI chat cap).
    """
    w = max(host.width(), 500)
    right = max(min_right, int(w * (1.0 - left_ratio)))
    if max_right is not None:
        right = min(right, max_right)
    left = max(min_left, w - right - 8)
    splitter.setSizes([left, right])
