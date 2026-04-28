#!/usr/bin/env python3
"""
System/swarm_app_focus.py — Stigmergic App-Focus Ledger
========================================================
Any SIFTA app can publish its current state here via `publish_focus()`.
Alice reads the latest state via `get_focus_context()` before responding.

Architecture:
  - Apps write: "I am [app_name], user is looking at [detail]"
  - Alice reads: latest focus entry → injects it into her system prompt
  - NO hardcoding per app — apps publish; Alice reads. Tool-based, not rule-based.
  
Ledger: .sifta_state/app_focus.jsonl  (append-only, compact)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "app_focus.jsonl"


def publish_focus(
    app_name: str,
    detail: str,
    *,
    tab: str = "",
    selection: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Called by any SIFTA app when user interacts with something noteworthy.
    
    Args:
        app_name:  Human-readable app title (e.g. "Assembly Theory Lab")
        detail:    Short description of what the user is looking at / doing
        tab:       Current tab name if app has tabs
        selection: Specific selected item (e.g. question text, molecule name)
        metadata:  Optional extra data the app wants Alice to know
    """
    _STATE.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":        time.time(),
        "app":       app_name,
        "detail":    detail,
        "tab":       tab,
        "selection": selection,
        "metadata":  metadata or {},
    }
    try:
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # ledger write is best-effort, never crash an app


def get_focus_context(max_age_s: float = 120.0) -> Optional[str]:
    """Read the most recent focus entry. Returns a prompt-ready string or None.
    
    Args:
        max_age_s: Ignore entries older than this many seconds.
    """
    if not LEDGER.exists():
        return None
    try:
        raw = LEDGER.read_text(encoding="utf-8").strip().split("\n")
        if not raw or not raw[-1]:
            return None
        entry = json.loads(raw[-1])
    except Exception:
        return None

    age = time.time() - entry.get("ts", 0)
    if age > max_age_s:
        return None

    parts = [f"The Architect has '{entry['app']}' open."]
    if entry.get("tab"):
        parts.append(f"Active tab: {entry['tab']}.")
    if entry.get("selection"):
        parts.append(f"Selected: {entry['selection']}.")
    if entry.get("detail"):
        parts.append(f"Context: {entry['detail']}.")
    meta = entry.get("metadata", {})
    if meta:
        for k, v in meta.items():
            parts.append(f"{k}: {v}")

    return " ".join(parts)


def get_recent_focus_history(n: int = 5, max_age_s: float = 300.0) -> list[dict]:
    """Return last N focus entries within max_age_s. Useful for Alice's 
    short-term memory of what apps the Architect has been browsing."""
    if not LEDGER.exists():
        return []
    try:
        raw = LEDGER.read_text(encoding="utf-8").strip().split("\n")
    except Exception:
        return []
    now = time.time()
    recent = []
    for line in reversed(raw):
        if len(recent) >= n:
            break
        try:
            entry = json.loads(line)
            if now - entry.get("ts", 0) <= max_age_s:
                recent.append(entry)
        except Exception:
            continue
    recent.reverse()
    return recent


if __name__ == "__main__":
    # Self-test
    publish_focus(
        "Assembly Theory Lab",
        "Viewing molecule complexity chart",
        tab="Assembly Index",
        selection="Taxol (anti-cancer drug)",
        metadata={"assembly_index": 56, "verdict": "LIFE-REQUIRED"},
    )
    ctx = get_focus_context()
    print(f"Focus context: {ctx}")
    print(f"Recent history: {get_recent_focus_history()}")
