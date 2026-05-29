#!/usr/bin/env python3
"""Round 109 stability clamp -> homeostasis bridge.

The Event134 stability clamp was already written to ``stability_audit.jsonl``.
This organ turns that receipt into a small consumable signal for action
selection, metabolic homeostasis, and arm routing. It keeps the bridge
data-derived: no chat template, no owner approval gate, just the clamp row
moving downstream.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir


LOG_NAME = "stability_homeostasis_bridge.jsonl"

SUPPRESS_NEW_ARM_LEVELS = {"BLOCK_NEW", "HARD", "EMERGENCY"}
CONSERVE_REPAIR_LEVELS = {"HARD", "EMERGENCY"}
LOCAL_REPAIR_ARMS = ("corvid_scout",)
HEAVY_BUILDER_ARMS = {
    "claude_agent",
    "codex_agent",
    "cline_agent",
    "grok_agent",
    "hermes_agent",
    "qwen_agent",
}


def field_failure_signal(reason: str) -> Dict[str, Any]:
    return StabilityHomeostasisSignal(
        active=True,
        receipt_ref="FIELD_FAILURE",
        reason=f"FIELD_FAILURE: {reason}",
    ).as_dict()


@dataclass(frozen=True)
class StabilityHomeostasisSignal:
    clamp_level: str = "NONE"
    energy: float = 0.0
    delta: float = 0.0
    ts: float = 0.0
    active: bool = False
    suppress_new_arms: bool = False
    conserve_repair: bool = False
    budget_multiplier_cap: float = 1.0
    preferred_arm_tier: str = "normal"
    receipt_ref: str = ""
    reason: str = "no_stability_clamp"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def bridge_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out or out in (float("inf"), float("-inf")):
        return default
    return out


def _level(value: Any) -> str:
    text = str(value or "NONE").strip().upper()
    return text if text else "NONE"


def _read_recent_field_stress(root: Optional[Path] = None, max_age_s: float = 180.0) -> float:
    """Read the latest organ_field_vector and return a simple stress [0.0-1.0]
    from average organ_health. High stress means the rich interconnected field
    (organs + their swimmers talking health via the ring) is under pressure.
    This lets the high-dimensional field have a voice in the metabolic clamp
    that protects the human owner and STGM profitability.
    Grounded in hardware: the bytes in organ_field_vector.jsonl are the stigmergic
    traces left by the organs on this silicon.
    """
    try:
        state = state_dir(root)
        path = state / "organ_field_vector.jsonl"
        if not path.exists():
            return 0.0
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return 0.0
        last = json.loads(lines[-1])
        payload = last.get("payload", {}) or {}
        organ_nodes = payload.get("organ_nodes", []) or []
        if not organ_nodes:
            # fallback to top-level organ_health if present
            oh = payload.get("organ_health", {}) or {}
            organ_nodes = [{"organ": k, "health": v} for k, v in oh.items()]
        if not organ_nodes:
            return 0.0
        total = 0.0
        count = 0
        for node in organ_nodes:
            h = float(node.get("health", node.get("organ_health", 0.5)))
            total += max(0.0, min(1.0, h))
            count += 1
        avg_health = total / max(1, count)
        stress = max(0.0, 1.0 - avg_health)
        # Only count if the row is fresh
        ts = float(last.get("ts") or last.get("timestamp") or 0.0)
        age = time.time() - ts if ts > 0 else 999.0
        if age > max_age_s:
            return 0.0
        return round(stress, 4)
    except Exception:
        return 0.0


def signal_from_clamp_row(row: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Convert a STABILITY_CLAMP row into the downstream control signal."""
    if not row:
        return StabilityHomeostasisSignal().as_dict()

    clamp_level = _level(row.get("clamp_level"))
    suppress = clamp_level in SUPPRESS_NEW_ARM_LEVELS or bool(row.get("block_new_gates", False))
    conserve = clamp_level in CONSERVE_REPAIR_LEVELS
    cap = 1.0
    tier = "normal"
    reason = "stability_clear"
    if conserve:
        cap = 0.2
        tier = "local_repair"
        reason = "stability_conserve_repair"
    elif suppress:
        cap = 0.45
        tier = "no_new_heavy_arms"
        reason = "stability_suppress_new_arms"
    elif clamp_level == "RATE_LIMIT":
        cap = 0.75
        tier = "rate_limited"
        reason = "stability_rate_limit"

    signal = StabilityHomeostasisSignal(
        clamp_level=clamp_level,
        energy=_float(row.get("lyapunov_energy")),
        delta=_float(row.get("delta_lyapunov_energy")),
        ts=_float(row.get("ts")),
        active=clamp_level != "NONE",
        suppress_new_arms=bool(suppress),
        conserve_repair=bool(conserve),
        budget_multiplier_cap=cap,
        preferred_arm_tier=tier,
        receipt_ref=str(row.get("trace_id") or row.get("receipt_id") or ""),
        reason=reason,
    )
    return signal.as_dict()


def read_latest_clamp_signal(
    *,
    root: Optional[Path] = None,
    same_tick_receipt: Optional[Mapping[str, Any]] = None,
    write_ledger: bool = False,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Read the current clamp signal. Mutates only when ``write_ledger`` is true."""
    row: Optional[Mapping[str, Any]] = None
    if isinstance(same_tick_receipt, Mapping) and same_tick_receipt.get("kind") == "STABILITY_CLAMP":
        row = same_tick_receipt
    else:
        try:
            from System import swarm_stability_audit

            get_latest_stability_clamp_row = getattr(
                swarm_stability_audit,
                "get_latest_stability_clamp_row",
                None,
            )
            if not callable(get_latest_stability_clamp_row):
                return field_failure_signal("missing swarm_stability_audit.get_latest_stability_clamp_row")

            row = get_latest_stability_clamp_row(root=root)
        except Exception as exc:
            return field_failure_signal(f"stability clamp read failed: {type(exc).__name__}")
    signal = signal_from_clamp_row(row)
    if write_ledger:
        write_bridge_signal(signal, root=root, now=now)

    # ── Rich field feedback into metabolic clamp (Decide → Execute → Receipt) ──
    # The high-dimensional organ ring (17 declared organs + their internal ASCII
    # swimmers) now speaks directly into whether we enter CONSERVE_REPAIR.
    # When average organ_health across the field is low, we bias toward protection
    # of the owner's human body and STGM profitability — even if raw lyapunov looks
    # okay. This is the organs communicating to keep each other healthy.
    # Grounded in the hardware layer: electricity → silicon → these exact bytes
    # in organ_field_vector.jsonl → this python process deciding on this M5 core.
    try:
        field_stress = _read_recent_field_stress(root=root)
        if field_stress >= 0.55:
            s = dict(signal)
            if not s.get("conserve_repair"):
                s["conserve_repair"] = True
                s["reason"] = (s.get("reason") or "") + f"; field_stress_{field_stress}_from_organ_ring"
            s["field_stress"] = field_stress
            # tighten budget when the field itself is hurting
            if field_stress >= 0.70:
                s["budget_multiplier_cap"] = min(s.get("budget_multiplier_cap", 1.0), 0.35)
            signal = s
    except Exception:
        pass

    return signal


def should_suppress_new_arms(signal: Mapping[str, Any]) -> bool:
    return bool(signal.get("suppress_new_arms", False))


def should_enter_conserve_repair(signal: Mapping[str, Any]) -> bool:
    return bool(signal.get("conserve_repair", False))


def write_bridge_signal(
    signal: Mapping[str, Any],
    *,
    root: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "ts": float(time.time() if now is None else now),
        "trace_id": str(uuid.uuid4()),
        "kind": "STABILITY_HOMEOSTASIS_BRIDGE",
        "truth_label": "STABILITY_HOMEOSTASIS_BRIDGE",
        **dict(signal),
    }
    append_line_locked(
        bridge_log_path(root),
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def _candidate_name(loop: Mapping[str, Any]) -> str:
    pieces = [
        loop.get("name"),
        loop.get("arm_id"),
        loop.get("actor"),
        loop.get("candidate_type"),
        loop.get("action"),
    ]
    return " ".join(str(p or "") for p in pieces).lower()


def is_heavy_arm_candidate(loop: Mapping[str, Any]) -> bool:
    text = _candidate_name(loop)
    if any(arm in text for arm in HEAVY_BUILDER_ARMS):
        return True
    if "dispatch" in text and "arm" in text:
        return not any(arm in text for arm in LOCAL_REPAIR_ARMS)
    return False


def is_repair_or_local_candidate(loop: Mapping[str, Any]) -> bool:
    text = _candidate_name(loop)
    return (
        any(arm in text for arm in LOCAL_REPAIR_ARMS)
        or "repair" in text
        or "conserve" in text
        or "local" in text
        or "gemma" in text
    )


def bias_basal_ganglia_loops(
    loops: Sequence[Mapping[str, Any]],
    signal: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return candidate copies with stability costs/salience applied."""
    if not should_suppress_new_arms(signal):
        return [dict(loop) for loop in loops], {
            "applied": False,
            "reason": signal.get("reason", "stability_clear"),
            "suppressed_candidates": [],
            "boosted_candidates": [],
        }

    suppressed: List[str] = []
    boosted: List[str] = []
    adjusted: List[Dict[str, Any]] = []
    for loop in loops:
        item = dict(loop)
        name = str(item.get("name") or item.get("arm_id") or "unnamed")
        if is_heavy_arm_candidate(item):
            item["cost"] = _float(item.get("cost"), 0.3) + 10.0
            item["salience"] = max(0.0, _float(item.get("salience"), 0.5) - 0.25)
            item["stability_bias_reason"] = "clamp_suppress"
            suppressed.append(name)
        elif should_enter_conserve_repair(signal) and is_repair_or_local_candidate(item):
            item["salience"] = _float(item.get("salience"), 0.5) + 0.5
            item["cost"] = max(0.0, _float(item.get("cost"), 0.3) - 0.2)
            item["stability_bias_reason"] = "conserve_repair_prefer"
            boosted.append(name)
        adjusted.append(item)
    return adjusted, {
        "applied": True,
        "reason": "clamp_suppress" if not should_enter_conserve_repair(signal) else "conserve_repair",
        "suppressed_candidates": suppressed,
        "boosted_candidates": boosted,
    }


def allowed_arm_ids_for_signal(
    arm_ids: Iterable[str],
    signal: Mapping[str, Any],
) -> Tuple[str, ...]:
    arms = tuple(str(arm) for arm in arm_ids)
    if should_enter_conserve_repair(signal):
        return tuple(arm for arm in arms if arm in LOCAL_REPAIR_ARMS)
    if should_suppress_new_arms(signal):
        return tuple(arm for arm in arms if arm not in HEAVY_BUILDER_ARMS)
    return arms


def metabolic_mode_for(base_mode: str, signal: Mapping[str, Any], *, conserve_repair: bool = False) -> str:
    """Overlay stability repair mode while preserving critical starvation."""
    if str(base_mode) == "CRITICAL_STARVATION":
        return "CRITICAL_STARVATION"
    if conserve_repair or should_enter_conserve_repair(signal):
        return "CONSERVE_REPAIR"
    return str(base_mode)


__all__ = [
    "LOCAL_REPAIR_ARMS",
    "CONSERVE_REPAIR_LEVELS",
    "HEAVY_BUILDER_ARMS",
    "SUPPRESS_NEW_ARM_LEVELS",
    "StabilityHomeostasisSignal",
    "allowed_arm_ids_for_signal",
    "bias_basal_ganglia_loops",
    "bridge_log_path",
    "field_failure_signal",
    "is_heavy_arm_candidate",
    "is_repair_or_local_candidate",
    "metabolic_mode_for",
    "read_latest_clamp_signal",
    "should_enter_conserve_repair",
    "should_suppress_new_arms",
    "signal_from_clamp_row",
    "write_bridge_signal",
]
