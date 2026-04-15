#!/usr/bin/env python3
"""
app_fitness.py — Natural Selection for the Programs Menu
=========================================================

Every app carries a fitness score that evolves daily:
  +1.0  per launch
  -5.0  per crash / error exit
  ×0.92 daily decay toward neutral (prevents stale leaders)

The Programs menu reorders by fitness: apps the Architect uses
constantly rise; apps that segfault sink.  Over weeks the menu
becomes a living reflection of what actually matters.

Persistence: .sifta_state/app_fitness.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_FITNESS_FILE = _STATE_DIR / "app_fitness.json"

LAUNCH_REWARD = 1.0
CRASH_PENALTY = -5.0
DAILY_DECAY = 0.92
EPOCH_KEY = "last_decay_epoch"
LEGACY_NAME_MAP = {
    "SIFTA NLE (Video Editor)": "SIFTA NLE",
    "Sebastian Batch Editor": "Silence Remover & Stitcher",
}


def _normalize_app_name(app_name: str) -> str:
    return LEGACY_NAME_MAP.get(app_name, app_name)


def _migrate_legacy_names(state: dict[str, Any]) -> dict[str, Any]:
    scores = state.setdefault("scores", {})
    migrated: dict[str, float] = {}
    changed = False
    for name, score in scores.items():
        normalized = _normalize_app_name(name)
        if normalized != name:
            changed = True
        migrated[normalized] = round(migrated.get(normalized, 0.0) + float(score), 4)
    if changed:
        state["scores"] = migrated
    return state


def _load() -> dict[str, Any]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if _FITNESS_FILE.exists():
        try:
            state = json.loads(_FITNESS_FILE.read_text())
            return _migrate_legacy_names(state)
        except Exception:
            pass
    return {EPOCH_KEY: _today(), "scores": {}}


def _save(state: dict[str, Any]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _FITNESS_FILE.write_text(json.dumps(state, indent=2) + "\n")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _apply_decay(state: dict[str, Any]) -> dict[str, Any]:
    """Decay all scores once per calendar day."""
    last = state.get(EPOCH_KEY, "")
    today = _today()
    if last == today:
        return state
    days_missed = max(1, (int(time.time()) - int(time.mktime(time.strptime(last, "%Y-%m-%d")))) // 86400) if last else 1
    factor = DAILY_DECAY ** days_missed
    for app in state.get("scores", {}):
        state["scores"][app] = round(state["scores"][app] * factor, 4)
    state[EPOCH_KEY] = today
    return state


def record_launch(app_name: str) -> float:
    """Called when the Architect opens an app. Returns new fitness."""
    state = _apply_decay(_load())
    app_name = _normalize_app_name(app_name)
    scores = state.setdefault("scores", {})
    scores[app_name] = round(scores.get(app_name, 0.0) + LAUNCH_REWARD, 4)
    _save(state)
    return scores[app_name]


def record_crash(app_name: str) -> float:
    """Called when an app exits with error. Returns new fitness."""
    state = _apply_decay(_load())
    app_name = _normalize_app_name(app_name)
    scores = state.setdefault("scores", {})
    scores[app_name] = round(scores.get(app_name, 0.0) + CRASH_PENALTY, 4)
    _save(state)
    return scores[app_name]


def get_scores() -> dict[str, float]:
    """Return {app_name: fitness} dict, decayed to today."""
    state = _migrate_legacy_names(_apply_decay(_load()))
    _save(state)
    return dict(state.get("scores", {}))


def ranked_apps(app_names: list[str]) -> list[str]:
    """Return app_names sorted by fitness (highest first).
    Apps not yet scored sort after scored apps, alphabetically."""
    scores = get_scores()
    def key(name: str) -> tuple[int, float, str]:
        if name in scores:
            return (0, -scores[name], name)
        return (1, 0.0, name)
    return sorted(app_names, key=key)


if __name__ == "__main__":
    record_launch("Colloid Simulator")
    record_launch("Colloid Simulator")
    record_launch("Swarm Arena")
    record_crash("Warehouse Logistics Test")
    for name, score in sorted(get_scores().items(), key=lambda x: -x[1]):
        print(f"  {score:+.2f}  {name}")
