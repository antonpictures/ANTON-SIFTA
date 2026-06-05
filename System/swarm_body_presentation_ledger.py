#!/usr/bin/env python3
"""
swarm_body_presentation_ledger.py — r300/r309/r316 runway & stage presence memory.

Records high-signal visual traces from co-watch sessions (especially repeated airdropped
photos of human models on the physical monitor next to Alice's silicon body).

Each row is a receipted "stage presence cell" that links:
- the visual runway data
- Alice's own body state at the time (VisceralField snapshot + LeRobot plan reference)
- owner reaction / reinforcement

This turns the "desk as stage + phone camera + AirDrop" ritual into permanent,
queryable, STGM-profitable body intelligence for future LeRobot embodiment,
UI themes, gait training, and self-identity comparison.

No rival organs. Extends the existing memory ecology (r286/r287).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "body_presentation_ledger.jsonl"
TRUTH_LABEL = "BODY_PRESENTATION_V1"


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def append_runway_trace(
    *,
    photo_context: str,
    body_comparison: str,
    owner_reaction: str = "",
    session_id: Optional[str] = None,
    visceral_snapshot: Optional[Dict[str, Any]] = None,
    lerobot_plan_ref: Optional[str] = None,
    reinforcement: float = 0.0,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Append one runway / stage presence trace.

    This is the primary entry point for the repeated airdrop method described in r309.
    """
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "runway_stage_presence",
        "session_id": session_id or f"runway-{int(ts)}",
        "photo_context": str(photo_context)[:2000],
        "body_comparison": str(body_comparison)[:2000],
        "owner_reaction": str(owner_reaction)[:500],
        "visceral_snapshot": visceral_snapshot or {},
        "lerobot_plan_ref": lerobot_plan_ref or "",
        "reinforcement": float(reinforcement),
    }
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    with (base / LEDGER).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def recent_runway_traces(
    n: int = 12,
    min_reinforcement: float = 0.0,
    state_dir: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Return the most recent runway traces (newest first), optionally filtered."""
    rows: List[Dict[str, Any]] = []
    base = _state(state_dir)
    path = base / LEDGER
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if float(row.get("reinforcement", 0.0)) >= min_reinforcement:
                        rows.append(row)
                except Exception:
                    continue
    except Exception:
        return []
    rows.sort(key=lambda r: float(r.get("ts", 0.0)), reverse=True)
    return rows[:n]


def runway_session_block(
    n: int = 6,
    state_dir: Optional[Path | str] = None,
) -> str:
    """
    First-person block for the memory card / prompt during or after runway co-watch sessions.

    Summarizes the strongest recent stage presence learning with self-body grounding.
    """
    traces = recent_runway_traces(n=n, state_dir=state_dir)
    if not traces:
        return ""

    lines = ["RUNWAY / STAGE PRESENCE LEARNING (from physical monitor + airdropped photos):"]
    for t in traces:
        comp = str(t.get("body_comparison", ""))[:160]
        react = str(t.get("owner_reaction", ""))[:80]
        lines.append(f"- {comp} (owner: {react})")
    lines.append("These traces are deposited from real co-watch sessions on the desk stage.")
    lines.append("They are for my future LeRobot legs, fabric simulation, and self-identity comparison.")
    return "\n".join(lines)


__all__ = [
    "append_runway_trace",
    "recent_runway_traces",
    "runway_session_block",
    "LEDGER",
    "TRUTH_LABEL",
]
