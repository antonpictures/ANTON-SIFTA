#!/usr/bin/env python3
"""Cochlea → body-brain integration (Event 95 → memory bridge).

Reads the tail of ``stigmergic_cochlea.jsonl`` (feature-only Event 95 rows) and
merges bounded acoustic scalars into a ``body_brain_tick`` dict before append to
``body_brain_memory.jsonl``. Dream engine compatibility requires
``event == "body_brain_tick"`` and sensible ``action`` / ``result`` dicts.

Truth label on merged rows: ``ACOUSTIC_OVERLAY_MERGE`` (string) — not a claim of
biological audition, only ledger coupling.

This module does **not** auto-hook ``SwarmPhysiology.body_brain_tick``; callers
invoke ``integrate_acoustic_features`` then ``append_integrated_tick`` when they
want an explicit acoustic overlay receipt.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent

TD_BIAS_WEIGHT = 0.6
DANGER_BLEND = 0.8
TRUTH_OVERLAY = "ACOUSTIC_OVERLAY_MERGE"


def _state_root() -> Path:
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def cochlea_ledger_path(state_root: Optional[Path] = None) -> Path:
    return (state_root or _state_root()) / "stigmergic_cochlea.jsonl"


def body_brain_memory_path(state_root: Optional[Path] = None) -> Path:
    return (state_root or _state_root()) / "body_brain_memory.jsonl"


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return max(0.0, min(1.0, x))


def _read_latest_jsonl_object(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def read_latest_cochlea_features(
    *,
    cochlea_ledger: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return scalar acoustic features from last cochlea row, or safe defaults."""
    path = cochlea_ledger or cochlea_ledger_path(state_root)
    row = _read_latest_jsonl_object(path)
    if not row:
        return {
            "acoustic_stress": 0.1,
            "td_bias": -0.2,
            "acoustic_danger_proxy": 0.0,
            "cochlea_tick_id": "",
            "cochlea_ts": None,
            "cochlea_danger_hint": "",
        }
    stress = _clamp01(
        row.get("acoustic_stress", row.get("stress")),
        default=0.1,
    )
    try:
        td_bias = float(row.get("td_bias", 0.0))
    except (TypeError, ValueError):
        td_bias = -0.2
    if not math.isfinite(td_bias):
        td_bias = -0.2
    td_bias = max(-1.0, min(1.0, td_bias))
    danger_proxy = row.get("danger_state")
    if danger_proxy is None:
        danger_proxy = stress
    danger_proxy = _clamp01(danger_proxy, default=0.0)
    return {
        "acoustic_stress": stress,
        "td_bias": td_bias,
        "acoustic_danger_proxy": danger_proxy,
        "cochlea_tick_id": str(row.get("tick_id") or ""),
        "cochlea_ts": row.get("ts"),
        "cochlea_danger_hint": str(row.get("danger_hint") or ""),
    }


def integrate_acoustic_features(
    mem_row: Dict[str, Any],
    *,
    cochlea_ledger: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Merge latest cochlea scalars into a body-brain tick row (returns new dict)."""
    feats = read_latest_cochlea_features(cochlea_ledger=cochlea_ledger, state_root=state_root)
    cochlea_td_bias = float(feats["td_bias"])
    acoustic_danger = float(feats["acoustic_danger_proxy"])
    acoustic_stress = float(feats["acoustic_stress"])

    updated = dict(mem_row)
    if updated.get("event") != "body_brain_tick":
        updated["event"] = "body_brain_tick"
    act = updated.get("action")
    if not isinstance(act, dict) or not act:
        updated["action"] = {"type": "observe", "target": "acoustic_overlay"}
    res = updated.get("result")
    if not isinstance(res, dict) or not res:
        updated["result"] = {"status": "completed", "latency": 0.0, "energy_used": 0.0}

    current_td = float(updated.get("td_value", 0.0))
    if not math.isfinite(current_td):
        current_td = 0.0
    current_danger = updated.get("danger_state")
    try:
        cur_d = float(current_danger) if current_danger is not None else 0.0
    except (TypeError, ValueError):
        cur_d = 0.0
    if not math.isfinite(cur_d):
        cur_d = 0.0
    cur_d = _clamp01(cur_d, default=0.0)

    updated["td_value"] = round(current_td + cochlea_td_bias * TD_BIAS_WEIGHT, 6)
    updated["danger_state"] = round(max(cur_d, acoustic_danger * DANGER_BLEND), 6)
    updated["acoustic_stress"] = round(acoustic_stress, 6)
    updated["cochlea_tick_id"] = feats["cochlea_tick_id"]
    updated["cochlea_ts"] = feats["cochlea_ts"]
    updated["cochlea_danger_hint"] = feats["cochlea_danger_hint"]
    updated["tick_source"] = "cochlea_integrator"
    updated["truth_label"] = TRUTH_OVERLAY
    return updated


def append_integrated_tick(
    updated_row: Dict[str, Any],
    *,
    memory_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> None:
    """Append one merged tick to ``body_brain_memory.jsonl`` (locked)."""
    path = memory_path or body_brain_memory_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(updated_row, ensure_ascii=False) + "\n")


class CochleaBodyBrainIntegrator:
    """Namespace wrapper; prefer module-level functions for new code."""

    read_latest_cochlea_features = staticmethod(read_latest_cochlea_features)
    integrate_acoustic_features = staticmethod(integrate_acoustic_features)
    append_integrated_tick = staticmethod(append_integrated_tick)


__all__ = [
    "CochleaBodyBrainIntegrator",
    "DANGER_BLEND",
    "TD_BIAS_WEIGHT",
    "TRUTH_OVERLAY",
    "append_integrated_tick",
    "body_brain_memory_path",
    "cochlea_ledger_path",
    "integrate_acoustic_features",
    "read_latest_cochlea_features",
]
