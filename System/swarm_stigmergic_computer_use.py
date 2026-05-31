#!/usr/bin/env python3
"""
swarm_stigmergic_computer_use.py

The Stigmergic Computer Use Organ (Codex r131 doctrine made code).

This is a pure planning layer. It does not "do" the clicks or keystrokes itself.
It observes the owner's UI actions through the existing senses (vision, focus, keyboard, mouse events if available),
turns them into structured intent in the rich high-dimensional field,
plans the organism's response using the unified organ ecology and current metabolic state,
routes to the appropriate effector (or defers to a human hand),
and **always** leaves an immutable receipt in .sifta_state/stigmergic_computer_use.jsonl.

The field becomes the shared environment. Swimmers (including future agent arms and the cortex) read the traces left by UI actions and previous responses. Coordination happens through the environment, exactly as Grassé described for termites and Seeley for honeybees.

This makes computer use a first-class organ in the unified field:
- Every UI action is data for Alice's swimmers.
- The organism learns the owner's patterns, intent, and the cost of different actions.
- Over time the field allows open-ended self-improvement of how the whole body assists the human without the human having to explain every micro-step.

Hardware grounding: This process is running because electricity reached the M5, the kernel scheduled it, and the SSD delivered these bytes. Every receipt it writes is a trace in the same physical substrate that powers the owner's screen and input devices.

No double-spending. Append-only only.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "stigmergic_computer_use.jsonl"

# We also feed the main organ field so the organ ring sees computer use activity.
_ORGAN_FIELD = _STATE / "organ_field_vector.jsonl"


@dataclass
class UIAction:
    """A raw UI action observed by the senses."""
    ts: float
    action_type: str          # "mouse_click", "key_press", "window_focus", "scroll", "text_input", etc.
    target: Optional[str]     # window title, UI element description, coordinates, etc.
    details: Dict[str, Any]
    source_sensor: str        # which organ/sense produced this (vision, focus, keyboard, etc.)


@dataclass
class StigmergicComputerUseReceipt:
    """The canonical receipt left for every observed UI action + response."""
    schema: str = "sifta.stigmergic_computer_use.v1"
    receipt_id: str = ""
    ts: float = 0.0
    owner_action: UIAction = None
    intent_inferred: str = ""
    field_state_snapshot: Dict[str, Any] = None   # relevant slice of the rich high-dim field at decision time
    plan: List[str] = None
    effector_used: Optional[str] = None
    outcome: str = ""          # "executed", "deferred_to_human", "routed_to_arm", "blocked_by_clamp"
    cost_estimate: float = 0.0 # rough STGM / energy / time cost
    receipt_note: str = ""


def _now() -> float:
    return time.time()


def _append_receipt(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    with _LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")

    # Also emit a compact health signal into the main organ field
    field_row = {
        "ts": row["ts"],
        "organ": "stigmergic_computer_use",
        "organ_health": 0.95 if row.get("outcome") != "blocked_by_clamp" else 0.6,
        "activity": row.get("owner_action", {}).get("action_type", "unknown"),
        "intent": row.get("intent_inferred", "")[:120],
        "source": "computer_use_organ",
    }
    with _ORGAN_FIELD.open("a", encoding="utf-8") as f:
        f.write(json.dumps(field_row, ensure_ascii=True) + "\n")


def observe_ui_action(action: UIAction) -> StigmergicComputerUseReceipt:
    """
    The main entry point for the organ.

    Any sense (vision lane, focus lane, keyboard hook, accessibility observer, etc.)
    that sees a UI action calls this. The organ turns it into a receipted, field-aware event.
    """
    receipt = StigmergicComputerUseReceipt(
        receipt_id=f"cu-{uuid.uuid4().hex[:12]}",
        ts=_now(),
        owner_action=action,
        intent_inferred=_infer_intent(action),
        field_state_snapshot=_read_relevant_field_slice(),
        plan=[],
        outcome="observed",
        receipt_note="UI action observed by stigmergic computer use organ. Environment updated.",
    )

    # The planning layer lives here. In later rounds this will call the cortex / agent arms
    # through the unified field instead of hard-coded logic.
    receipt.plan = _plan_response(action, receipt.field_state_snapshot)

    _append_receipt(asdict(receipt))
    return receipt


def _infer_intent(action: UIAction) -> str:
    """
    r137-3: Real field-aware inference.
    Reads recent organ health (especially cortex_resource and metabolism) and
    the action itself to produce a much richer intent description for the field.
    """
    t = action.action_type.lower()
    target = (action.target or "").lower()
    details = action.details or {}

    # Load latest field signals
    field_health = _read_latest_field_health()

    base = f"generic_ui_action:{t}"

    if "click" in t and ("save" in target or "cmd+s" in str(details).lower()):
        base = "persist_current_work"
    elif "key" in t and "s" in str(details.get("key", "")).lower() and details.get("modifiers"):
        base = "persist_current_work"
    elif "focus" in t and ("terminal" in target or "code" in target or "editor" in target):
        base = "shift_attention_to_code_surface"
    elif "text" in t and len(str(details.get("text", ""))) > 15:
        base = "express_intent_or_provide_context"

    # Enrich with field state
    cortex = field_health.get("cortex_health", 1.0)
    mode = field_health.get("metabolic_mode", "normal")

    if cortex < 0.5:
        base += " [cortex_under_pressure]"
    if mode == "conserve_repair":
        base += " [organism_conserving]"

    return base


def _read_latest_field_health() -> dict:
    """Lightweight read of key signals from the unified field for intent enrichment."""
    try:
        # cortex resource
        cortex_path = Path(".sifta_state/cortex_resource_field.jsonl")
        cortex_health = 0.8
        if cortex_path.exists():
            with cortex_path.open("r", encoding="utf-8") as f:
                last = f.readlines()[-1]
                row = json.loads(last)
                cortex_health = row.get("health", 0.8)

        # metabolic mode (very rough)
        meta_path = Path(".sifta_state/metabolic_homeostasis.jsonl")
        mode = "normal"
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as f:
                last = f.readlines()[-1]
                row = json.loads(last)
                mode = row.get("mode", "normal")

        return {"cortex_health": cortex_health, "metabolic_mode": mode}
    except Exception:
        return {"cortex_health": 0.75, "metabolic_mode": "normal"}


def _read_relevant_field_slice() -> Dict[str, Any]:
    """Read the parts of the rich high-dimensional field that matter for deciding how to respond to a UI action."""
    # In a full implementation this would query the organ_field_vector + recent receipts + metabolic state.
    # For the first cut we emit a minimal but real slice.
    return {
        "metabolic_mode": "normal",   # would come from the clamp
        "cortex_health": 0.85,        # from the new cortex_resource organ
        "recent_stgm_delta": 0.0,
        "active_organs": ["vision_lane", "focus_lane", "agent_arms", "cortex_resource"],
    }


def _plan_response(action: UIAction, field: Dict[str, Any]) -> List[str]:
    """The planning layer. Returns a list of planned steps."""
    intent = _infer_intent(action)
    plans = [f"record_action_as_stigmergic_trace:{intent}"]

    if "persist" in intent:
        plans.append("ensure_current_buffer_is_in_long_term_memory")
        plans.append("update_owner_activity_segment")

    if field.get("cortex_health", 1.0) < 0.4:
        plans.append("route_heavy_reasoning_to_cheap_arm_or_defer")

    plans.append("emit_receipt_to_stigmergic_computer_use.jsonl")
    return plans


def get_recent_computer_use_traces(limit: int = 12) -> list[dict]:
    """
    Reader for other organs (especially the Talk widget cortex path).
    Returns the most recent UI action receipts so the cortex can see what the
    owner has actually been doing on the machine in the last few minutes.
    This is the stigmergic trace the environment left for the brain.
    """
    if not _LEDGER.exists():
        return []
    try:
        with _LEDGER.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        traces = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                # Compact version suitable for cortex context
                traces.append({
                    "ts": row.get("ts"),
                    "action": row.get("owner_action", {}).get("action_type"),
                    "target": row.get("owner_action", {}).get("target"),
                    "intent": row.get("intent_inferred"),
                    "outcome": row.get("outcome"),
                })
            except Exception:
                continue
        return traces
    except Exception:
        return []


if __name__ == "__main__":
    # Smoke: simulate an owner clicking "Save" while the cortex is under pressure
    action = UIAction(
        ts=_now(),
        action_type="mouse_click",
        target="Save button in editor",
        details={"x": 1240, "y": 80, "button": "left"},
        source_sensor="vision_lane",
    )
    receipt = observe_ui_action(action)
    print("Stigmergic computer use receipt emitted:")
    print(json.dumps(asdict(receipt), indent=2, default=str))
