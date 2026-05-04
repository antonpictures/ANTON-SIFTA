"""
System/swarm_visual_confirmation.py
==============================================================================
Visual confirmation organ for Motor Cortex actions.

The organ does not decide Alice's whole safety policy. It records whether the
body looked before/after a motor act at the risk tier requested by the Motor
Cortex, so the Arbiter and identity organs can learn from what actually
happened.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "visual_confirmation_log.jsonl"
TRUTH_LABEL = "VISUAL_CONFIRMATION"


def visual_confirmation_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _hash_bytes(data: Optional[bytes]) -> str:
    if not data:
        return ""
    return hashlib.sha256(data).hexdigest()


def _coerce_xy(value: Any) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    try:
        return int(round(float(value[0]))), int(round(float(value[1])))
    except Exception:
        return None


@dataclass
class VisualConfirmation:
    semantic_target: str
    stage: str
    risk_tier: str
    observed: bool
    confidence: float
    resolved_coordinates: Optional[Tuple[int, int]] = None
    screenshot_hash: str = ""
    action_trace_id: str = ""
    target_app: str = ""
    target_window: str = ""
    notes: str = ""
    tick_id: Optional[int] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

    def to_row(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "trace_id": self.trace_id,
            "tick_id": self.tick_id,
            "kind": TRUTH_LABEL,
            "truth_label": TRUTH_LABEL,
            "schema": "SIFTA_VISUAL_CONFIRMATION_V1",
            "action_trace_id": self.action_trace_id,
            "semantic_target": self.semantic_target,
            "stage": self.stage,
            "risk_tier": self.risk_tier,
            "observed": bool(self.observed),
            "confidence": round(float(self.confidence), 3),
            "resolved_coordinates": list(self.resolved_coordinates) if self.resolved_coordinates else None,
            "screenshot_hash": self.screenshot_hash,
            "target_app": self.target_app,
            "target_window": self.target_window,
            "notes": self.notes,
        }


def required_stages_for_action(risk_tier: str, action_type: str) -> Tuple[str, ...]:
    """Risk-tier table from the Motor Cortex spec."""
    tier = str(risk_tier or "LOW").upper()
    action = str(action_type or "").upper()
    if tier == "HARD_PERIMETER":
        return ("owner_go",)
    if tier in {"HIGH", "MEDIUM"} or action in {"TYPE", "PASTE"}:
        return ("before", "after")
    return ("before",)


def record_visual_confirmation(
    *,
    semantic_target: str,
    stage: str,
    risk_tier: str,
    observed: bool,
    confidence: float,
    root: Optional[Path] = None,
    action_trace_id: str = "",
    resolved_coordinates: Any = None,
    screenshot_bytes: Optional[bytes] = None,
    screenshot_hash: str = "",
    target_app: str = "",
    target_window: str = "",
    notes: str = "",
    tick_id: Optional[int] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    row = VisualConfirmation(
        semantic_target=semantic_target,
        stage=stage,
        risk_tier=str(risk_tier or "LOW").upper(),
        observed=bool(observed),
        confidence=max(0.0, min(1.0, float(confidence))),
        resolved_coordinates=_coerce_xy(resolved_coordinates),
        screenshot_hash=screenshot_hash or _hash_bytes(screenshot_bytes),
        action_trace_id=action_trace_id,
        target_app=target_app,
        target_window=target_window,
        notes=notes,
        tick_id=tick_id,
    ).to_row()
    if write_ledger:
        append_line_locked(
            visual_confirmation_log_path(root),
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def visual_confirmation_passed(
    confirmations: Sequence[Dict[str, Any]],
    *,
    required_stages: Sequence[str],
    min_confidence: float = 0.70,
) -> bool:
    by_stage: Dict[str, Dict[str, Any]] = {}
    for row in confirmations:
        stage = str(row.get("stage") or "").lower()
        if stage:
            by_stage[stage] = row
    for stage in required_stages:
        if stage == "owner_go":
            continue
        row = by_stage.get(str(stage).lower())
        if not row:
            return False
        if not row.get("observed"):
            return False
        try:
            if float(row.get("confidence") or 0.0) < min_confidence:
                return False
        except Exception:
            return False
    return True


def recent_visual_confirmations(n: int = 10, *, root: Optional[Path] = None) -> list[Dict[str, Any]]:
    path = visual_confirmation_log_path(root)
    if not path.exists():
        return []
    rows: list[Dict[str, Any]] = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-max(1, int(n)):]


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = recent_visual_confirmations(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    return (
        "VISUAL CONFIRMATION:\n"
        f"- last={row.get('semantic_target')} stage={row.get('stage')} "
        f"observed={row.get('observed')} conf={row.get('confidence')}"
    )
