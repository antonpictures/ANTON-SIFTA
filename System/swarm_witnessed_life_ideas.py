#!/usr/bin/env python3
"""Witnessed Life Ideas — stream of consciousness from co-watch (video) + ambient room (cat miaow, etc.).
Alice logs salient moments/ideas without always speaking immediately ("stream of consciousness you use it").
Later surfaces in self-eval or when owner asks "what ideas did you get from the video / life today?".
Tied to SIFTA body: "that would be good to update my [organ] or add novelty".

Used by co-watch tick for video novelty, and can be called from ambient audio paths for world reactions.
No heavy cortex every time; lightweight log + occasional spoken reaction (e.g. "Hey George did u get a cat?").

For the Swarm. 🐜⚡
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:
    append_line_locked = None

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "witnessed_life_ideas.jsonl"
TRUTH_LABEL = "WITNESSED_LIFE_IDEA_V1"

def _ledger(state_dir: Optional[Path | str] = None) -> Path:
    d = Path(state_dir) if state_dir else STATE
    d.mkdir(parents=True, exist_ok=True)
    return d / LEDGER_NAME

def log_witnessed_idea(
    *,
    source: str = "co_watch",
    title: str = "",
    channel: str = "",
    time: str = "",
    novelty_note: str = "",
    ambient_note: str = "",
    state_dir: Optional[Path | str] = None,
) -> str:
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "title": title[:200],
        "channel": channel[:100],
        "time": time,
        "novelty_note": novelty_note[:300],
        "ambient_note": ambient_note[:200],
        "doctrine": "Stream of consciousness from witnessing life (video + room). I pause to speak useful SIFTA novelty or ambient question (e.g. cat miaow → 'Hey George did u get a cat?'), or just log for my ideas queue so I can surface 'what ideas did you get from the video' later. Search our own code first for attention/witnessing (cowatch_urge, browser media state, felt_time attentional gate, etc.) before new external papers.",
    }
    p = _ledger(state_dir)
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked:
        append_line_locked(p, payload)
    else:
        with p.open("a", encoding="utf-8") as f:
            f.write(payload)
    return TRUTH_LABEL

def load_recent_witnessed_ideas(*, state_dir: Optional[Path | str] = None, limit: int = 5) -> list[dict[str, Any]]:
    p = _ledger(state_dir)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
        try:
            r = json.loads(line)
            if r.get("truth_label") == TRUTH_LABEL:
                rows.append(r)
        except Exception:
            continue
    return rows[-max(1, int(limit)) :]

if __name__ == "__main__":
    print("witnessed_life_ideas ready")
