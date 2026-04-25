#!/usr/bin/env python3
"""
stigmergic_wm.py — Pheromone-based Window Manager
===================================================

Windows that open together leave pheromone on each other.
Open Finance + Arena three days in a row?  They spawn adjacent.
A window untouched for weeks drifts to the bottom of the menu.

The desktop learns spatial habits through evaporation and
reinforcement — not explicit pinning.

Persistence: .sifta_state/wm_pheromone.json
Structure:
  {
    "trails": { "AppA::AppB": 3.7, ... },
    "last_session": ["AppA", "AppB"],
    "last_decay": "2026-04-14"
  }
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_PHER_FILE = _STATE_DIR / "wm_pheromone.json"

DEPOSIT = 1.0
EVAPORATION = 0.85  # daily decay factor
MIN_PHER = 0.01


def _pair_key(a: str, b: str) -> str:
    return "::".join(sorted([a, b]))


def _load() -> dict[str, Any]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if _PHER_FILE.exists():
        try:
            return json.loads(_PHER_FILE.read_text())
        except Exception:
            pass
    return {"trails": {}, "last_session": [], "last_decay": _today()}


def _save(state: dict[str, Any]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PHER_FILE.write_text(json.dumps(state, indent=2) + "\n")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _evaporate(state: dict[str, Any]) -> dict[str, Any]:
    last = state.get("last_decay", "")
    today = _today()
    if last == today:
        return state
    days = 1
    if last:
        try:
            days = max(1, (int(time.time()) - int(time.mktime(time.strptime(last, "%Y-%m-%d")))) // 86400)
        except Exception:
            days = 1
    factor = EVAPORATION ** days
    pruned: dict[str, float] = {}
    for k, v in state.get("trails", {}).items():
        nv = round(v * factor, 4)
        if nv >= MIN_PHER:
            pruned[k] = nv
    state["trails"] = pruned
    state["last_decay"] = today
    return state


def record_open(app_name: str) -> None:
    """Call every time a window is opened.
    Deposits pheromone between this window and every other
    window opened in the same session (since last desktop boot)."""
    state = _evaporate(_load())
    session: list[str] = state.get("last_session", [])

    for other in session:
        if other == app_name:
            continue
        k = _pair_key(app_name, other)
        state["trails"][k] = round(state["trails"].get(k, 0.0) + DEPOSIT, 4)

    if app_name not in session:
        session.append(app_name)
    state["last_session"] = session
    _save(state)


def reset_session() -> None:
    """Call on desktop boot to start a fresh co-open session."""
    state = _evaporate(_load())
    state["last_session"] = []
    _save(state)


def neighbors(app_name: str, top_n: int = 5) -> list[tuple[str, float]]:
    """Return the top-N apps most co-opened with *app_name*,
    sorted by pheromone strength (descending)."""
    state = _evaporate(_load())
    _save(state)
    pairs: list[tuple[str, float]] = []
    for k, v in state.get("trails", {}).items():
        parts = k.split("::")
        if app_name in parts:
            other = parts[0] if parts[1] == app_name else parts[1]
            pairs.append((other, v))
    pairs.sort(key=lambda x: -x[1])
    return pairs[:top_n]


def suggest_position(
    app_name: str,
    open_windows: dict[str, tuple[int, int]],
    mdi_w: int = 1280,
    mdi_h: int = 720,
    win_w: int = 660,
    win_h: int = 540,
) -> tuple[int, int]:
    """Return (x, y) for a new window — never stacked on top of another.

    Strategy (macOS-style):
      1. If the app has a pheromone-strong neighbour that is open, place
         30 px right and 30 px down from that neighbour (affinity grouping).
      2. Otherwise use a cascade: each new window is offset (STEP_X, STEP_Y)
         from the last-opened window.  When the cascade would push the window
         off the right or bottom edge it wraps back to the origin lane.
    """
    STEP_X, STEP_Y = 60, 40
    ORIGIN_X, ORIGIN_Y = 60, 40

    def clamp(x: int, y: int) -> tuple[int, int]:
        max_x = max(0, mdi_w - win_w)
        max_y = max(0, mdi_h - win_h)
        return (min(max(0, x), max_x), min(max(0, y), max_y))

    # 1. Pheromone affinity
    occupied = set(open_windows.values())
    nbrs = neighbors(app_name, top_n=3)
    for nbr_name, _strength in nbrs:
        if nbr_name in open_windows:
            ox, oy = open_windows[nbr_name]
            candidate = clamp(ox + 30, oy + 30)
            if candidate not in occupied:
                return candidate

    # 2. Cascade fallback — find the last-opened window position
    if open_windows:
        # take the window that was opened most recently (last in dict)
        last_x, last_y = list(open_windows.values())[-1]
        nx = last_x + STEP_X
        ny = last_y + STEP_Y
        # wrap horizontally
        if nx + win_w > mdi_w:
            nx = ORIGIN_X
        # wrap vertically
        if ny + win_h > mdi_h:
            ny = ORIGIN_Y
        return clamp(nx, ny)

    # 3. First window of the session: top-left with a small inset
    return clamp(ORIGIN_X, ORIGIN_Y)



def ranked_menu(app_names: list[str], anchor: str | None = None) -> list[str]:
    """Reorder *app_names* so that apps co-opened with *anchor*
    (or globally strongest trails) appear first."""
    state = _evaporate(_load())
    _save(state)
    agg: dict[str, float] = defaultdict(float)
    for k, v in state.get("trails", {}).items():
        parts = k.split("::")
        if anchor and anchor not in parts:
            continue
        for p in parts:
            agg[p] += v
    def key(name: str) -> tuple[float, str]:
        return (-agg.get(name, 0.0), name)
    return sorted(app_names, key=key)


if __name__ == "__main__":
    reset_session()
    record_open("Colloid Simulator")
    record_open("Swarm Arena")
    record_open("Colloid Simulator")
    record_open("Swarm Finance")
    print("Neighbors of Colloid:", neighbors("Colloid Simulator"))
    print("Ranked menu:", ranked_menu(["Swarm Arena", "Colloid Simulator", "Warehouse", "Swarm Finance"]))
