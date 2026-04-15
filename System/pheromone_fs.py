#!/usr/bin/env python3
"""
pheromone_fs.py — Stigmergic file co-access trails
====================================================

Files accessed together leave trace on each other.  Open crypto_keychain.py
then inference_economy.py ten times? They form a "trail."

`sifta_fs_trails` shows clusters of related files — not by directory,
but by behavioral co-access.  It's how ants find shortest paths,
applied to codebase navigation.

Persistence: .sifta_state/fs_pheromone.json
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_TRAIL_FILE = _STATE_DIR / "fs_pheromone.json"

DEPOSIT = 1.0
EVAPORATION = 0.90  # daily decay
MIN_PHER = 0.05
SESSION_WINDOW = 120  # seconds — files opened within this window are "co-accessed"


def _pair_key(a: str, b: str) -> str:
    return "::".join(sorted([a, b]))


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load() -> dict[str, Any]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if _TRAIL_FILE.exists():
        try:
            return json.loads(_TRAIL_FILE.read_text())
        except Exception:
            pass
    return {"trails": {}, "session": [], "last_decay": _today()}


def _save(state: dict[str, Any]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _TRAIL_FILE.write_text(json.dumps(state, indent=2) + "\n")


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


def record_access(filepath: str) -> None:
    """Record that a file was accessed. Deposits pheromone between
    this file and any file accessed within the SESSION_WINDOW."""
    state = _evaporate(_load())
    now = time.time()

    # Normalize path to relative
    rel = filepath.replace(str(Path(__file__).resolve().parent.parent) + "/", "")

    session: list[dict[str, Any]] = state.get("session", [])
    # Prune stale session entries
    session = [e for e in session if now - e.get("t", 0) < SESSION_WINDOW]

    for entry in session:
        other = entry["f"]
        if other == rel:
            continue
        k = _pair_key(rel, other)
        state["trails"][k] = round(state["trails"].get(k, 0.0) + DEPOSIT, 4)

    session.append({"f": rel, "t": now})
    state["session"] = session
    _save(state)


def neighbors(filepath: str, top_n: int = 8) -> list[tuple[str, float]]:
    """Return the top-N files most co-accessed with *filepath*."""
    state = _evaporate(_load())
    _save(state)
    rel = filepath.replace(str(Path(__file__).resolve().parent.parent) + "/", "")
    pairs: list[tuple[str, float]] = []
    for k, v in state.get("trails", {}).items():
        parts = k.split("::")
        if rel in parts:
            other = parts[0] if parts[1] == rel else parts[1]
            pairs.append((other, v))
    pairs.sort(key=lambda x: -x[1])
    return pairs[:top_n]


def clusters(min_strength: float = 1.0) -> list[list[str]]:
    """Return clusters of files connected by trails above min_strength.
    Uses simple union-find on the trail graph."""
    state = _evaporate(_load())
    _save(state)

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for k, v in state.get("trails", {}).items():
        if v < min_strength:
            continue
        parts = k.split("::")
        if len(parts) == 2:
            parent.setdefault(parts[0], parts[0])
            parent.setdefault(parts[1], parts[1])
            union(parts[0], parts[1])

    groups: dict[str, list[str]] = defaultdict(list)
    for node in parent:
        groups[find(node)].append(node)

    return [sorted(g) for g in groups.values() if len(g) > 1]


def trail_map() -> dict[str, float]:
    """Return full trail map {pairkey: strength} for visualization."""
    state = _evaporate(_load())
    _save(state)
    return dict(state.get("trails", {}))


if __name__ == "__main__":
    record_access("System/crypto_keychain.py")
    record_access("inference_economy.py")
    record_access("System/crypto_keychain.py")
    record_access("System/immune_memory.py")
    time.sleep(0.1)
    record_access("sifta_os_desktop.py")
    record_access("Applications/apps_manifest.json")

    print("Neighbors of crypto_keychain:")
    for f, s in neighbors("System/crypto_keychain.py"):
        print(f"  {s:.2f}  {f}")

    print("\nClusters:")
    for c in clusters(0.5):
        print(f"  {c}")
