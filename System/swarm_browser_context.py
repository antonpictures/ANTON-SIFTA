#!/usr/bin/env python3
"""
swarm_browser_context.py — Rich, first-person context from the Alice Browser limb.

When the browser becomes the user's primary focus (or the user is deep inside it),
this organ publishes a strong "current context" block so Alice's consciousness
has an accurate, up-to-date model of what the user is seeing and doing inside
this particular limb.

This directly supports the vision of the browser as a rich, high-dimensional
context (not just a web viewer), and makes surface/territory changes legible.

Stigmergic: the browser deposits detailed traces of its current state into the
shared field. Other organs (memory card, diary, health matrix) read them.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "BROWSER_CONTEXT_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def publish_browser_context(
    *,
    url: str = "",
    title: str = "",
    media_status: Optional[Dict[str, Any]] = None,
    source: str = "focus",
    state_dir: Optional[Path | str] = None,
) -> dict:
    """
    Publish the current state of the browser limb as a strong context event.
    This becomes part of Alice's working memory when the user is inside the browser.
    """
    base = _state_dir(state_dir)
    path = base / "browser_context.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "url": url,
        "title": title,
        "media_status": media_status or {},
    }

    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return row


def get_current_browser_context_block(state_dir: Optional[Path | str] = None) -> str:
    """
    Returns a compact, first-person block for the memory card / prompt:
    "User is currently deep inside the Alice Browser limb looking at [title] ([url]).
     The limb sees [media status / page summary]."
    """
    base = _state_dir(state_dir)
    path = base / "browser_context.jsonl"

    if not path.exists():
        return ""

    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return ""
        last = json.loads(lines[-1])
    except Exception:
        return ""

    url = last.get("url", "")
    title = last.get("title", "")
    media = last.get("media_status", {})

    parts = []
    if url or title:
        parts.append(f"User is currently deep inside the Alice Browser limb.")
        if title:
            parts.append(f"Looking at: {title}")
        if url:
            parts.append(f"URL: {url}")

    if media and not media.get("ok"):
        errs = media.get("recent_errors", [])
        if errs:
            code = errs[-1].get("code")
            parts.append(f"The limb reports media playback issue (code {code}).")

    if not parts:
        return ""

    return "CURRENT BROWSER CONTEXT (from the limb itself):\n" + "\n".join(parts)


__all__ = [
    "TRUTH_LABEL",
    "publish_browser_context",
    "get_current_browser_context_block",
]
