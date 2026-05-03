"""
Event 130 - Global workspace attention router.

Several organs can produce valid signals at the same time: direct user speech,
replay pressure, prediction error, body state, tool alerts, and background
media/noise. This module selects a small broadcast set for conscious processing
and writes a receipt showing what was selected and what was dropped.

Truth label:
  GLOBAL_WORKSPACE_BROADCAST

Kill-switch: SIFTA_GLOBAL_WORKSPACE_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

WORKSPACE_LOG_NAME = "global_workspace_broadcasts.jsonl"

KIND_BOOSTS: Dict[str, float] = {
    "critical_system_alert": 0.40,
    "direct_user_speech": 0.35,
    "prediction_error": 0.25,
    "owner_continuity_trigger": 0.20,
    "replay_salience": 0.15,
    "task_goal": 0.15,
    "body_state": 0.10,
    "background_noise": -0.25,
    "background_media": -0.15,
}


def workspace_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / WORKSPACE_LOG_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_GLOBAL_WORKSPACE_DISABLE", "").strip() == "1"


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return round(min(hi, max(lo, f)), 4)


def _prediction_error_bonus(value: Any) -> float:
    try:
        err = abs(float(value))
    except (TypeError, ValueError):
        err = 0.0
    return min(0.30, err * 0.10)


def _compact_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    try:
        encoded = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        return {"preview": str(payload)[:240]}
    if len(encoded) <= 500:
        return payload
    return {"preview": encoded[:500]}


def make_candidate(
    signal_id: str,
    kind: str,
    salience: float,
    *,
    prediction_error: float = 0.0,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Small helper for organs that want a stable candidate shape."""
    return {
        "signal_id": signal_id,
        "kind": kind,
        "salience": salience,
        "prediction_error": prediction_error,
        "payload": payload or {},
    }


def normalize_candidate(candidate: Dict[str, Any], *, index: int = 0) -> Dict[str, Any]:
    kind = str(candidate.get("kind") or candidate.get("signal_type") or "unknown")
    signal_id = str(candidate.get("signal_id") or candidate.get("id") or f"{kind}_{index}")
    salience = _clamp(candidate.get("salience", candidate.get("score", 0.0)))
    prediction_error = _clamp(
        candidate.get("prediction_error", 0.0),
        lo=-1000.0,
        hi=1000.0,
    )
    boost = KIND_BOOSTS.get(kind, 0.0)
    workspace_score = _clamp(salience + boost + _prediction_error_bonus(prediction_error))
    return {
        "signal_id": signal_id,
        "kind": kind,
        "salience": salience,
        "kind_boost": round(boost, 4),
        "prediction_error": prediction_error,
        "workspace_score": workspace_score,
        "payload": _compact_payload(candidate.get("payload", {})),
    }


def select_attention(
    candidates: Iterable[Dict[str, Any]],
    *,
    k: int = 3,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Select top-k signals for global broadcast.

    Sorting is deterministic: highest workspace score first, then signal id.
    """
    top_k = max(0, int(k))
    normalized = [
        normalize_candidate(candidate, index=i)
        for i, candidate in enumerate(candidates)
        if isinstance(candidate, dict)
    ]
    ranked = sorted(normalized, key=lambda row: (-row["workspace_score"], row["signal_id"]))
    selected = ranked[:top_k]
    dropped = ranked[top_k:]
    row: Dict[str, Any] = {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "GLOBAL_WORKSPACE_BROADCAST",
        "kind": "GLOBAL_WORKSPACE_BROADCAST",
        "top_k": top_k,
        "candidates_seen": len(normalized),
        "selected_signals": [s["signal_id"] for s in selected],
        "dropped_signals": [s["signal_id"] for s in dropped],
        "selected": selected,
        "dropped": dropped,
        "disabled": _disabled(),
    }
    if write_ledger and not row["disabled"]:
        append_line_locked(
            workspace_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_broadcast_rows(max_rows: int = 16, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = workspace_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, min(max_rows, 200)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_broadcast_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    selected = ", ".join(row.get("selected_signals") or [])
    dropped = ", ".join(row.get("dropped_signals") or [])
    if not selected and not dropped:
        return ""
    return (
        "GLOBAL WORKSPACE BROADCAST (Event 130): "
        f"selected=[{selected or 'none'}]; dropped=[{dropped or 'none'}]"
    )


__all__ = [
    "KIND_BOOSTS",
    "WORKSPACE_LOG_NAME",
    "make_candidate",
    "normalize_candidate",
    "select_attention",
    "summary_for_prompt",
    "tail_broadcast_rows",
    "workspace_log_path",
]
