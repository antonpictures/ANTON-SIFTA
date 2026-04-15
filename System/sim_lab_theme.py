#!/usr/bin/env python3
"""
sim_lab_theme.py — Shared “mad scientist lab” matplotlib look for SIFTA simulations
==================================================================================

Coherent dark UI + neon accents (Tokyo-Night–adjacent). Use for any Swarm OS sim
so demos read as one instrument panel, not random plots.
"""
from __future__ import annotations

import sys
from typing import Any, Optional, Sequence, Union


def ensure_matplotlib(feature: str = "visual mode") -> None:
    """
    Exit with a clear message if matplotlib is not installed (common on minimal venvs).
    Headless / --batch paths should not call this.
    """
    import importlib.util

    if importlib.util.find_spec("matplotlib") is None:
        print(
            "\n[SIFTA] Graphics need matplotlib, which is not installed in this Python.\n"
            "        Fix:  pip install matplotlib\n"
            "        Or:   pip install -r requirements.txt\n"
            f"        ({feature})\n",
            file=sys.stderr,
        )
        raise SystemExit(2)

# ── Palette: readable on dark, distinct series ─────────────────────────────
LAB_BG = "#070a12"
LAB_PANEL = "#0d111d"
LAB_GRID = "#1a2040"
LAB_TEXT = "#c0caf5"
LAB_MUTED = "#565f89"
LAB_ACCENT = "#bb9af7"
LAB_OK = "#9ece6a"
LAB_WARN = "#e0af68"
LAB_BAD = "#f7768e"
LAB_CYAN = "#7dcfff"
LAB_MAGENTA = "#ff7edb"
LAB_GOLD = "#ffc777"

SERIES = ("#7aa2f7", "#bb9af7", "#7dcfff", "#9ece6a", "#e0af68", "#f7768e", "#ff9e64")


def apply_matplotlib_lab_style() -> None:
    """Call once before building figures (imports matplotlib)."""
    import matplotlib as mpl

    try:
        mpl.use("MacOSX")
    except Exception:
        pass
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": LAB_BG,
            "axes.facecolor": LAB_PANEL,
            "axes.edgecolor": LAB_GRID,
            "axes.labelcolor": LAB_TEXT,
            "axes.titlecolor": LAB_ACCENT,
            "text.color": LAB_TEXT,
            "xtick.color": LAB_MUTED,
            "ytick.color": LAB_MUTED,
            "grid.color": LAB_GRID,
            "grid.alpha": 0.45,
            "font.family": "monospace",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "figure.titlesize": 13,
        }
    )


def neon_suptitle(
    fig: Any,
    title: str,
    subtitle: str = "",
    color: str = LAB_ACCENT,
) -> None:
    fig.suptitle(title, color=color, fontweight="bold", y=0.98)
    if subtitle:
        fig.text(0.5, 0.94, subtitle, ha="center", fontsize=8, color=LAB_MUTED, family="monospace")


def style_axis_lab(ax: Any, title: Optional[str] = None) -> None:
    ax.set_facecolor(LAB_PANEL)
    for spine in ax.spines.values():
        spine.set_color(LAB_GRID)
    ax.tick_params(colors=LAB_MUTED)
    if title:
        ax.set_title(title, color=LAB_TEXT, fontsize=10)


def legend_lab(ax: Any, **kwargs: Any) -> Any:
    import matplotlib.pyplot as plt

    leg = ax.legend(
        facecolor="#121620",
        edgecolor=LAB_GRID,
        labelcolor=LAB_TEXT,
        framealpha=0.92,
        **kwargs,
    )
    return leg


def cmap_pheromone() -> Any:
    """Magma-style but anchored to lab void."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "sifta_lab_pher",
        [(0.0, LAB_BG), (0.25, "#1a0f2e"), (0.5, "#5c2d7a"), (0.75, "#c94c4c"), (1.0, LAB_GOLD)],
    )


def cmap_terrain_lab() -> Any:
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "sifta_lab_terrain",
        [(0.0, "#0b1020"), (0.3, "#1c3d4a"), (0.55, "#3d6b5c"), (0.8, "#8b7355"), (1.0, LAB_GOLD)],
    )


def sparkline_update(
    ax: Any,
    values: Sequence[float],
    color: str = LAB_CYAN,
    ylabel: str = "",
) -> None:
    ax.clear()
    style_axis_lab(ax)
    if not values:
        return
    n = len(values)
    ax.plot(range(n), values, color=color, linewidth=1.2)
    ax.fill_between(range(n), values, alpha=0.15, color=color)
    ax.set_xlim(0, max(1, n - 1))
    if ylabel:
        ax.set_ylabel(ylabel, color=LAB_MUTED, fontsize=8)
    ax.set_xticks([])
