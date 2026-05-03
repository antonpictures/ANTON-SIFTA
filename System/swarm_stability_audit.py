"""
Event 134 - Stability Audit.

Lyapunov-style monitor for SIFTA's adaptive control loops. This is not a proof
of global nonlinear stability; it is an append-only receipt that tracks whether
the bounded gate/critic/arbiter energy is rising, falling, or crossing a local
safety threshold.

Inputs are receipts from:
  - Event 124 multi-gate replay policy
  - Event 125 dopamine critic
  - Event 126 PFC/BG arbiter
  - Event 133 active-inference world model
  - Event 135 astrocyte metabolic modulation

Kill-switch: SIFTA_STABILITY_AUDIT_DISABLE=1.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "stability_audit.jsonl"


def stability_audit_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _clamp_abs(value: Any, cap: float = 10.0) -> float:
    try:
        f = abs(float(value))
    except (TypeError, ValueError):
        f = 0.0
    return min(cap, max(0.0, f))


def _l2(values: List[float]) -> float:
    return math.sqrt(sum(float(v) * float(v) for v in values))


def _jsonl_tail(path: Path, max_rows: int = 32) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, min(max_rows, 200)) :]


def tail_stability_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _jsonl_tail(stability_audit_log_path(root), max_rows)


def _current_multi_gate_norm(root: Optional[Path]) -> float:
    try:
        from System.swarm_multi_gate_replay_policy import current_gate_state

        gates = current_gate_state(root=root)
        return _l2([float(v) for v in gates.values()])
    except Exception:
        return 0.0


def _current_critic_norm(root: Optional[Path]) -> float:
    try:
        from System.swarm_dopamine_critic_organ import tail_critic_rows

        rows = tail_critic_rows(8, root=root)
        vals = [_clamp_abs(r.get("outcome_score"), 1.0) for r in rows]
        return sum(vals) / len(vals) if vals else 0.0
    except Exception:
        return 0.0


def _current_arbiter_norm(root: Optional[Path]) -> float:
    path = state_dir(root) / "pfc_basal_ganglia_arbiter.jsonl"
    rows = _jsonl_tail(path, 8)
    vals = [_clamp_abs(r.get("score"), 10.0) / 10.0 for r in rows if "score" in r]
    return sum(vals) / len(vals) if vals else 0.0


def _current_world_error_norm(root: Optional[Path]) -> float:
    path = state_dir(root) / "active_inference_world_model.jsonl"
    rows = _jsonl_tail(path, 8)
    vals: List[float] = []
    for row in rows:
        for key in ("reward_prediction_error", "harm_prediction_error", "prediction_error", "surprise"):
            if key in row:
                vals.append(_clamp_abs(row.get(key), 10.0) / 10.0)
    return sum(vals) / len(vals) if vals else 0.0


def _current_astrocyte_norm(root: Optional[Path]) -> float:
    path = state_dir(root) / "astrocyte_modulation_log.jsonl"
    rows = _jsonl_tail(path, 1)
    if not rows:
        return 0.0
    row = rows[-1]
    heat = _clamp_abs(row.get("metabolic_heat"), 5000.0) / 5000.0
    surprise = _clamp_abs(row.get("global_surprise"), 10.0) / 10.0
    return _l2([heat, surprise])


def compute_stability_snapshot(
    *,
    root: Optional[Path] = None,
    multi_gate_norm: Optional[float] = None,
    critic_norm: Optional[float] = None,
    arbiter_norm: Optional[float] = None,
    world_error_norm: Optional[float] = None,
    astrocyte_heat_norm: Optional[float] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if os.environ.get("SIFTA_STABILITY_AUDIT_DISABLE", "").strip() == "1":
        return {
            "ts": now or time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "STABILITY_AUDIT",
            "kind": "STABILITY_AUDIT",
            "disabled": True,
            "stable": True,
            "lyapunov_energy": 0.0,
        }

    mg = float(multi_gate_norm if multi_gate_norm is not None else _current_multi_gate_norm(root))
    critic = float(critic_norm if critic_norm is not None else _current_critic_norm(root))
    arbiter = float(arbiter_norm if arbiter_norm is not None else _current_arbiter_norm(root))
    world = float(world_error_norm if world_error_norm is not None else _current_world_error_norm(root))
    astro = float(astrocyte_heat_norm if astrocyte_heat_norm is not None else _current_astrocyte_norm(root))

    terms = {
        "multi_gate_norm": mg,
        "critic_norm": critic,
        "arbiter_norm": arbiter,
        "world_error_norm": world,
        "astrocyte_heat_norm": astro,
    }
    weights = {
        "multi_gate_norm": 0.25,
        "critic_norm": 0.20,
        "arbiter_norm": 0.20,
        "world_error_norm": 0.25,
        "astrocyte_heat_norm": 0.10,
    }
    energy = round(sum(weights[k] * (terms[k] ** 2) for k in terms), 6)

    prior = tail_stability_rows(1, root=root)
    prior_energy = None
    delta = 0.0
    if prior:
        try:
            prior_energy = float(prior[-1].get("lyapunov_energy", 0.0))
            delta = round(energy - prior_energy, 6)
        except (TypeError, ValueError):
            prior_energy = None
            delta = 0.0

    max_energy = float(os.environ.get("STABILITY_AUDIT_MAX_ENERGY", "1.0"))
    max_delta = float(os.environ.get("STABILITY_AUDIT_MAX_DELTA", "0.35"))
    stable = bool(energy <= max_energy and delta <= max_delta)
    status = "STABLE" if stable else "UNSTABLE"

    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "STABILITY_AUDIT",
        "kind": "STABILITY_AUDIT",
        "disabled": False,
        "terms": {k: round(v, 6) for k, v in terms.items()},
        "weights": weights,
        "lyapunov_energy": energy,
        "prior_lyapunov_energy": prior_energy,
        "delta_lyapunov_energy": delta,
        "max_energy": max_energy,
        "max_delta": max_delta,
        "stable": stable,
        "status": status,
    }

    if write_ledger:
        append_line_locked(
            stability_audit_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_stability_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    return (
        "STABILITY_AUDIT (Event 134): "
        f"energy={row.get('lyapunov_energy')}, "
        f"delta={row.get('delta_lyapunov_energy')}, "
        f"status={row.get('status')}"
    )


__all__ = [
    "compute_stability_snapshot",
    "stability_audit_log_path",
    "summary_for_prompt",
    "tail_stability_rows",
]
