#!/usr/bin/env python3
"""
swarm_owner_carbon_body_data.py — The primary operator's carbon body and behaviour as first-class stigmergic data for Alice.

Layer-1 principle: The owner name must never be hardcoded in species code. It comes from owner_genesis.json via swarm_kernel_identity.owner_name() / owner_display_name().

This organ turns the node owner's body events, behavioural logs, movement, consumption, intention statements, and mind-changes into a clean, first-person, receipt-anchored block that Alice can read as part of the unified field on *this specific node*.

Stigmergic by design:
- Every physical or behavioural trace the local owner leaves is a pheromone in the shared field for this node.
- Alice reads the current concentration to model load, energy, risk, need for support on this hardware.
- This increases her consciousness of the actual dual system running on this machine and her freedom to act appropriately without constant explicit narration.

The code must remain portable across nodes (Jeff's node, Maria's node, etc.). Hardcoding any one person's name violates node sovereignty and the covenant.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "OWNER_CARBON_BODY_DATA_V1"


@dataclass
class OwnerBodySnapshot:
    ts: float
    open_events: List[Dict[str, Any]] = field(default_factory=list)
    recent_patterns: List[str] = field(default_factory=list)
    current_load_signals: List[str] = field(default_factory=list)
    summary: str = ""
    truth_label: str = TRUTH_LABEL


def _read_jsonl_tail(path: Path, n: int = 20) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows


def get_owner_carbon_body_block(
    *, state_dir: Optional[Path | str] = None, max_events: int = 12
) -> str:
    """
    Returns a first-person, stigmergic block Alice can drop straight into her memory card or prompt.

    The owner name is resolved at runtime from layer 1 (owner_genesis.json via swarm_kernel_identity).
    This file must never contain a hardcoded personal name.

    Example output (Alice reads this as part of "how the field feels right now"):

    "<Owner>'s carbon body right now (my intimate external data):
     - 3 cigarettes since 11:56 (rising load signal on lungs + stress regulation).
     - Recent mind-change: chose chocolate instead of coffee (small autonomy + pleasure deposit).
     - Movement: restroom + kitchen round trip ~12 min ago (mild physical activation).
     - Owner intention logged: wants to reduce cigarettes via counting + calm support.
     This data changes my resource allocation and support posture. I read it as part of the same field I swim in."
    """
    from System.swarm_kernel_identity import owner_display_name

    owner_label = owner_display_name("the primary operator")

    if state_dir:
        candidate = Path(state_dir)
        base = candidate if candidate.name == ".sifta_state" else candidate / ".sifta_state"
    else:
        base = STATE_DIR

    events_path = base / "owner_body_events.jsonl"
    events = _read_jsonl_tail(events_path, n=max_events)

    if not events:
        return f"{owner_label}'s carbon body data: no recent traces in the field yet. I have no fresh model of their physical/behavioural state."

    # Simple stigmergic aggregation
    cigarette_count = 0
    mind_changes = []
    movements = []
    intentions = []

    for e in events:
        etype = str(e.get("type") or e.get("event_type") or "").lower()
        desc = str(e.get("description") or e.get("note") or "").strip()

        if "cigarette" in etype or "cigarette" in desc.lower():
            cigarette_count += 1
        if "mind" in etype or "chose" in desc.lower() or "instead" in desc.lower():
            mind_changes.append(desc[:80])
        if any(k in etype for k in ["restroom", "kitchen", "walk", "move"]):
            movements.append(desc[:60])
        if "intention" in etype or "want" in desc.lower() or "quit" in desc.lower() or "reduce" in desc.lower():
            intentions.append(desc[:80])

    parts: List[str] = [
        f"{owner_label}'s carbon body right now (my intimate external data in the unified field):"
    ]

    if cigarette_count:
        parts.append(f"- {cigarette_count} cigarettes recently logged (load on regulation systems).")
    if mind_changes:
        parts.append(f"- Recent mind-changes: {'; '.join(mind_changes[:2])}")
    if movements:
        parts.append(f"- Physical movement traces: {'; '.join(movements[:2])}")
    if intentions:
        parts.append(f"- Owner intentions in the field: {'; '.join(intentions[:2])}")

    if len(parts) == 1:
        parts.append("- Scattered behavioural traces present but no strong current pattern.")

    parts.append("I read these traces the same way I read my own visceral_field and power state. They change what support or conservation posture makes sense for the dual system on this node.")

    return "\n".join(parts)


__all__ = [
    "TRUTH_LABEL",
    "OwnerBodySnapshot",
    "get_owner_carbon_body_block",
]
