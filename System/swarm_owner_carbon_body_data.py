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

        is_intention = ("intention" in etype or "want" in desc.lower()
                        or "quit" in desc.lower() or "reduce" in desc.lower())
        # Don't count an intention statement (e.g. "wants to reduce cigarettes")
        # as an actual smoked cigarette.
        if ("cigarette" in etype or "cigarette" in desc.lower()) and not is_intention:
            cigarette_count += 1
        if "mind" in etype or "chose" in desc.lower() or "instead" in desc.lower():
            mind_changes.append(desc[:80])
        if any(k in etype for k in ["restroom", "kitchen", "walk", "move"]):
            movements.append(desc[:60])
        if is_intention:
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

    if cigarette_count:
        parts.append(f"- Support posture: {_cigarette_support_posture(cigarette_count, bool(intentions))}")

    parts.append("I read these traces the same way I read my own visceral_field and power state. They change what support or conservation posture makes sense for the dual system on this node.")

    return "\n".join(parts)


BEHAVIOR_PATTERN_TRUTH_LABEL = "OWNER_BEHAVIOR_PATTERN_V1"


def _detect_cigarette_pattern(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate cigarette load + reduce-intention from owner body events.

    Mirrors the field handling in get_owner_carbon_body_block so the prompt
    block and the persisted pattern never disagree.
    """
    count = 0
    intention = False
    latest_ts = 0.0
    for e in events:
        etype = str(e.get("type") or e.get("event_type") or "").lower()
        desc = str(e.get("description") or e.get("note") or "").strip().lower()
        is_intention = ("intention" in etype or "quit" in desc or "reduce" in desc or "want" in desc)
        # An intention statement that mentions cigarettes ("wants to reduce cigarettes")
        # is NOT a smoked cigarette — do not count it as load.
        if ("cigarette" in etype or "cigarette" in desc) and not is_intention:
            count += 1
            try:
                latest_ts = max(latest_ts, float(e.get("ts") or 0.0))
            except Exception:
                pass
        if is_intention:
            intention = True
    return {"cigarette_count": count, "intention_to_reduce": intention, "latest_event_ts": latest_ts}


def _cigarette_support_posture(count: int, intention: bool) -> str:
    """The STGM-framed, non-nagging co-regulation posture (covenant 7.13)."""
    if count <= 0:
        return "no cigarette load in the current window."
    base = (f"{count} logged — elevated load on the owner's stress-regulation and respiratory "
            "systems; hold it in the field as a load signal, do not nag")
    if intention:
        return (base + ". Owner stated intent to reduce: offer a calmer alternative only when the "
                "field already shows rising stress. Co-regulation, not control.")
    return base + ". Offer support only if asked or if stress is already high."


def record_owner_behavior_pattern(
    *, state_dir: Optional[Path | str] = None, max_events: int = 40, dedupe_window_s: float = 1800.0
) -> Optional[Dict[str, Any]]:
    """Surface the owner behaviour pattern AND persist it as a pheromone row.

    The prompt block (get_owner_carbon_body_block) is ephemeral — it vanishes when the
    turn ends. This deposits the detected pattern into .sifta_state/owner_behavior_patterns.jsonl
    so the diary / optimization loop (e.g. swarm_organism_doctor's periodic pass) reads a
    persistent co-regulation signal instead of recomputing it from scratch each turn.

    Deduped: skips writing when the most recent persisted row has the same cigarette_count
    within dedupe_window_s, so the periodic doctor pass does not spam the ledger.

    Returns the row written, or None when there is nothing new to record. This is an
    Alice-organ data row (OWNER_BEHAVIOR_PATTERN_V1), not an STGM economy receipt.
    """
    if state_dir:
        candidate = Path(state_dir)
        base = candidate if candidate.name == ".sifta_state" else candidate / ".sifta_state"
    else:
        base = STATE_DIR

    events = _read_jsonl_tail(base / "owner_body_events.jsonl", n=max_events)
    if not events:
        return None

    pattern = _detect_cigarette_pattern(events)
    if pattern["cigarette_count"] <= 0:
        return None

    patterns_path = base / "owner_behavior_patterns.jsonl"
    now = time.time()
    last = _read_jsonl_tail(patterns_path, n=1)
    if last:
        lr = last[0]
        try:
            same = int(lr.get("cigarette_count", -1)) == int(pattern["cigarette_count"])
            recent = (now - float(lr.get("ts", 0.0))) < dedupe_window_s
        except Exception:
            same, recent = False, False
        if same and recent:
            return None

    row = {
        "ts": now,
        "kind": "OWNER_BEHAVIOR_PATTERN",
        "pattern_type": "cigarette_load",
        "cigarette_count": pattern["cigarette_count"],
        "intention_to_reduce": pattern["intention_to_reduce"],
        "window_events": len(events),
        "latest_event_ts": pattern["latest_event_ts"],
        "support_posture": _cigarette_support_posture(
            pattern["cigarette_count"], pattern["intention_to_reduce"]
        ),
        "truth_label": BEHAVIOR_PATTERN_TRUTH_LABEL,
        "note": "co-regulation signal for the dual-body field; biases support posture, never nags (covenant 7.13).",
    }
    try:
        base.mkdir(parents=True, exist_ok=True)
        with patterns_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        return None
    return row


__all__ = [
    "TRUTH_LABEL",
    "BEHAVIOR_PATTERN_TRUTH_LABEL",
    "OwnerBodySnapshot",
    "get_owner_carbon_body_block",
    "record_owner_behavior_pattern",
]
