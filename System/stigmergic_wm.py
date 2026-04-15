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


def suggest_position(app_name: str, open_windows: dict[str, tuple[int, int]]) -> tuple[int, int] | None:
    """Given currently open windows {name: (x,y)}, suggest a position
    for *app_name* near its strongest neighbor.  Returns (x, y) or None."""
    nbrs = neighbors(app_name, top_n=3)
    for nbr_name, _strength in nbrs:
        if nbr_name in open_windows:
            ox, oy = open_windows[nbr_name]
            return (ox + 30, oy + 30)
    return None


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
