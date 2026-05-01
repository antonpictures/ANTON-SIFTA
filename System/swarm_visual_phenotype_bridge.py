#!/usr/bin/env python3
"""
Event 92 — Visual Phenotype Bridge

Maps receipt-backed body_brain_memory rows into shader-safe uniform scalars.
Chromatophore + honeybee waggle .novel fragments consume these keys off-disk.

Truth: OPERATIONAL bridge — no live OpenGL until ModernGL pass lands; ledger rows
are receipts that the uniforms were derived from stigmergy, not hand-painted.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402


def _state_root() -> Path:
    """Align with body_brain loop state dir (supports tests that patch _STATE_DIR)."""
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def body_memory_path() -> Path:
    return _state_root() / "body_brain_memory.jsonl"


def phenotype_ledger_path() -> Path:
    return _state_root() / "visual_phenotype_uniforms.jsonl"


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def read_last_jsonl(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or body_memory_path()
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return {}


def normalize_td_value(value: Any) -> float:
    """Map signed TD / value into 0..1 for chromatophore drive (tanh, covenant-safe)."""
    try:
        v = float(value)
    except Exception:
        return 0.5
    return clamp01((math.tanh(v) + 1.0) * 0.5)


def chemotaxis_uniform(row: Dict[str, Any]) -> float:
    """Chromatophore v3 `u_chemotaxis_gradient` — optional trace_gradient on memory row."""
    g = row.get("trace_gradient")
    if g is None:
        return 0.1
    return normalize_td_value(g)


def _action_label(action: Any) -> str:
    if isinstance(action, dict):
        parts = [str(action.get("type") or ""), str(action.get("target") or "")]
        return " ".join(p for p in parts if p).strip() or "unknown"
    return str(action or "unknown")


def infer_heading_from_action(action: Any) -> float:
    """Stable radians for common action families (visual waggle axis)."""
    s = _action_label(action).lower()
    table = {
        "rest": math.pi / 2,
        "repair": math.pi * 0.75,
        "forage": 0.0,
        "explore": -math.pi / 4,
        "observe": math.pi,
        "mutate": -math.pi / 2,
    }
    for key, heading in table.items():
        if key in s:
            return heading
    return 0.0


def _cost_from_metabolic_row(row: Dict[str, Any]) -> float:
    mode = str(row.get("metabolic_mode") or "").upper()
    pd = str(row.get("plasticity_danger") or "")
    if mode in {"RED_CONSERVE", "CRITICAL_STARVATION"} or pd == "CIRCADIAN_SLEEP_PRESSURE":
        return 0.85
    if mode in {"YELLOW_THROTTLE", "YELLOW_WARN", "AMBER"}:
        return 0.55
    return 0.15


def build_visual_phenotype_uniforms(row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build one uniform dict. If row is None, read last body_brain_memory line.
    """
    row = dict(row) if row else read_last_jsonl(body_memory_path())
    action = row.get("action")
    drive = str(row.get("drive_state") or row.get("drive") or "unknown")

    value = normalize_td_value(row.get("td_value", row.get("value", 0.0)))
    cost = _cost_from_metabolic_row(row)

    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    lat = result.get("latency")
    try:
        latency_norm = clamp01(float(lat) / 5.0) if lat is not None else cost
    except Exception:
        latency_norm = cost

    confidence = clamp01(row.get("confidence", 0.5), 0.5)
    q_accum = row.get("quorum_accum", row.get("quorum_signal"))
    quorum = clamp01(q_accum if q_accum is not None else confidence, confidence)

    uniforms: Dict[str, Any] = {
        "ts": time.time(),
        "source": "body_brain_memory.jsonl",
        "tick_id": str(row.get("tick_id") or ""),
        "receipt_backed": row.get("event") == "body_brain_tick" and "td_value" in row,
        "u_stigmergic_drive": value,
        "u_metabolic_scope": clamp01(1.0 - cost),
        "u_cot_factor": cost,
        "u_quorum_signal": quorum,
        "u_chemotaxis_gradient": chemotaxis_uniform(row),
        "u_reward": value,
        "u_distance": latency_norm,
        "u_confidence": confidence,
        "u_cost": cost,
        "u_heading": infer_heading_from_action(action),
        "drive_state": drive,
        "action": _action_label(action),
        "metabolic_mode": str(row.get("metabolic_mode") or ""),
        "plasticity_danger": str(row.get("plasticity_danger") or ""),
    }
    return uniforms


def write_visual_phenotype_uniforms(row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append one phenotype row (JSONL) for GPU / debug consumers."""
    uniforms = build_visual_phenotype_uniforms(row=row)
    out = phenotype_ledger_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(out, json.dumps(uniforms, sort_keys=True) + "\n")
    return uniforms


if __name__ == "__main__":
    print(json.dumps(write_visual_phenotype_uniforms(), indent=2, sort_keys=True))
