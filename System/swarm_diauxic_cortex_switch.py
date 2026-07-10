#!/usr/bin/env python3
"""swarm_diauxic_cortex_switch.py — local-first cortex substrate switch (Gift 4).

Biology: E. coli eats glucose first; only when depleted does it pause (lag phase)
and induce enzymes for lactose. Catabolite repression = cheap substrate fully
before expensive pathway.

Silicon: prefer local/offline cortex (Gemma/Ollama) until it is genuinely
insufficient, *then* pause, write a lag-phase receipt, and escalate to an
OAuth/cloud arm. Never silent thrash between substrates.

Extends metabolic cortex routing with a named, receipted law.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "DIAUXIC_CORTEX_SWITCH_V1"

TIER_LOCAL = "local"
TIER_CLOUD = "cloud"
TIER_HOLD = "lag_phase"


def assess_local_depletion(
    *,
    local_available: bool = True,
    local_empty_replies: int = 0,
    local_timeouts: int = 0,
    local_error: bool = False,
    consecutive_low_quality: int = 0,
    empty_threshold: int = 2,
    timeout_threshold: int = 2,
    quality_threshold: int = 3,
) -> dict[str, Any]:
    """Is the cheap substrate (local cortex) depleted / insufficient?"""
    reasons: list[str] = []
    if not local_available:
        reasons.append("local_unavailable")
    if int(local_empty_replies) >= int(empty_threshold):
        reasons.append("empty_replies")
    if int(local_timeouts) >= int(timeout_threshold):
        reasons.append("timeouts")
    if local_error:
        reasons.append("local_error")
    if int(consecutive_low_quality) >= int(quality_threshold):
        reasons.append("low_quality_streak")
    depleted = bool(reasons)
    return {
        "depleted": depleted,
        "reasons": reasons,
        "local_available": bool(local_available),
        "local_empty_replies": int(local_empty_replies),
        "local_timeouts": int(local_timeouts),
        "consecutive_low_quality": int(consecutive_low_quality),
    }


def choose_cortex_tier(
    *,
    local_available: bool = True,
    local_empty_replies: int = 0,
    local_timeouts: int = 0,
    local_error: bool = False,
    consecutive_low_quality: int = 0,
    cloud_available: bool = True,
    battery_low: bool = False,
    offline_required: bool = False,
    force_cloud: bool = False,
    force_local: bool = False,
    lag_phase_already_receipted: bool = False,
) -> dict[str, Any]:
    """
    Decide local vs cloud with formal lag phase.

    Returns tier in {local, cloud, lag_phase}.
    lag_phase = pause and write receipt before first escalation this episode.
    """
    dep = assess_local_depletion(
        local_available=local_available,
        local_empty_replies=local_empty_replies,
        local_timeouts=local_timeouts,
        local_error=local_error,
        consecutive_low_quality=consecutive_low_quality,
    )

    if force_local or offline_required or battery_low:
        return {
            "truth_label": TRUTH_LABEL,
            "tier": TIER_LOCAL,
            "reason": (
                "force_local"
                if force_local
                else ("offline_required" if offline_required else "battery_low_prefer_local")
            ),
            "lag_phase": False,
            "depletion": dep,
            "cloud_available": bool(cloud_available),
        }

    if force_cloud and cloud_available:
        need_lag = not lag_phase_already_receipted
        return {
            "truth_label": TRUTH_LABEL,
            "tier": TIER_HOLD if need_lag else TIER_CLOUD,
            "reason": "force_cloud",
            "lag_phase": need_lag,
            "depletion": dep,
            "cloud_available": True,
        }

    if not dep["depleted"] and local_available:
        return {
            "truth_label": TRUTH_LABEL,
            "tier": TIER_LOCAL,
            "reason": "cheap_substrate_available",
            "lag_phase": False,
            "depletion": dep,
            "cloud_available": bool(cloud_available),
        }

    # Local depleted — escalate only if cloud available
    if not cloud_available:
        return {
            "truth_label": TRUTH_LABEL,
            "tier": TIER_LOCAL,
            "reason": "local_depleted_but_cloud_unavailable",
            "lag_phase": False,
            "depletion": dep,
            "cloud_available": False,
        }

    if not lag_phase_already_receipted:
        return {
            "truth_label": TRUTH_LABEL,
            "tier": TIER_HOLD,
            "reason": "lag_phase_before_expensive_substrate",
            "lag_phase": True,
            "depletion": dep,
            "cloud_available": True,
            "next_tier": TIER_CLOUD,
        }

    return {
        "truth_label": TRUTH_LABEL,
        "tier": TIER_CLOUD,
        "reason": "expensive_substrate_after_lag",
        "lag_phase": False,
        "depletion": dep,
        "cloud_available": True,
    }


def write_lag_phase_receipt(
    decision: Mapping[str, Any],
    *,
    state_dir: Optional[Path] = None,
    from_tier: str = TIER_LOCAL,
    to_tier: str = TIER_CLOUD,
    note: str = "",
) -> dict[str, Any]:
    """Visible metabolic pause receipt before spinning up expensive cortex."""
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "diauxic_cortex_switch_receipts.jsonl"
    row = {
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "truth_label": TRUTH_LABEL,
        "event": "lag_phase",
        "from_tier": from_tier,
        "to_tier": to_tier,
        "note": note
        or (
            "Diauxic lag phase: local/cheap cortex depleted; pausing before "
            "inducing expensive OAuth/cloud cortex enzymes."
        ),
        "decision": dict(decision),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def write_switch_receipt(
    decision: Mapping[str, Any],
    *,
    state_dir: Optional[Path] = None,
    event: str = "tier_choice",
) -> dict[str, Any]:
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "diauxic_cortex_switch_receipts.jsonl"
    row = {
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "truth_label": TRUTH_LABEL,
        "event": event,
        "decision": dict(decision),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "TIER_LOCAL",
    "TIER_CLOUD",
    "TIER_HOLD",
    "assess_local_depletion",
    "choose_cortex_tier",
    "write_lag_phase_receipt",
    "write_switch_receipt",
]
