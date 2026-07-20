#!/usr/bin/env python3
"""
memory_fitness_overlay.py — Vector 12 (ACMF) fitness substrate (overlay only)
══════════════════════════════════════════════════════════════════════════════

`memory_ledger.jsonl` stays append-only; **PheromoneTrace** lines are never
mutated for fitness. Evolutionary / usage pressure lives in:

    .sifta_state/memory_fitness.json

Updates use **read_write_json_locked** (single LOCK_EX) from jsonl_file_lock.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import read_text_locked, read_write_json_locked  # noqa: E402

FITNESS_FILENAME = "memory_fitness.json"


def fitness_path_for_ledger_dir(ledger_parent: Path) -> Path:
    return ledger_parent / FITNESS_FILENAME


def load_trace_table(ledger_parent: Path) -> Dict[str, Dict[str, Any]]:
    """Shared-lock read of overlay; safe to call every forage."""
    p = fitness_path_for_ledger_dir(ledger_parent)
    if not p.exists():
        return {}
    raw = read_text_locked(p, encoding="utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        import json

        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        from System.adaptive_constraint_memory_field import (  # noqa: PLC0415
            _normalize_top_level,
        )

        flat = _normalize_top_level(data)
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in flat.items()}
    except Exception:
        return {}


def fitness_multiplier(record: Dict[str, Any] | None) -> float:
    """Bounded multiplier for forager confidence (sqrt curve)."""
    if not record:
        return 1.0
    fit = float(record.get("fitness", 1.0))
    return max(0.25, min(2.0, math.sqrt(max(0.01, fit))))


def _fitness_path(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) / FITNESS_FILENAME if state_dir is not None else _REPO / ".sifta_state" / FITNESS_FILENAME


def reinforce(
    trace_or_hash: str,
    source_receipt_id: str,
    *,
    weight: float = 1.0,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Strengthen a recalled row in the overlay only.

    The canonical memory ledgers stay append-only; this records the trail walked
    by recall in memory_fitness.json.
    """
    tid = str(trace_or_hash or "").strip()
    if not tid:
        return {"ok": False, "reason": "missing_trace_id"}
    receipt_id = str(source_receipt_id or "").strip()
    now = time.time()
    delta = 0.05 * max(0.0, float(weight))
    path = _fitness_path(state_dir)

    def _up(data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            data = {}
        data.setdefault("schema_version", 1)
        data.setdefault("overlay", "memory_fitness_acmf_v1")
        data.setdefault("traces", {})
        traces = data.get("traces")
        if not isinstance(traces, dict):
            traces = {}
            data["traces"] = traces
        row = traces.setdefault(
            tid,
            {
                "fitness": 1.0,
                "strength": 1.0,
                "usage_count": 0,
                "reinforcement_count": 0,
                "last_used_ts": 0.0,
            },
        )
        if not isinstance(row, dict):
            row = {
                "fitness": 1.0,
                "strength": 1.0,
                "usage_count": 0,
                "reinforcement_count": 0,
                "last_used_ts": 0.0,
            }
            traces[tid] = row
        strength = float(row.get("strength", row.get("fitness", 1.0)))
        fitness = float(row.get("fitness", strength))
        row["strength"] = float(max(0.1, strength + delta))
        row["fitness"] = float(max(0.1, fitness + delta))
        row["usage_count"] = int(row.get("usage_count", 0)) + 1
        row["reinforcement_count"] = int(row.get("reinforcement_count", 0)) + 1
        row["last_used_ts"] = now
        row["last_reinforced_ts"] = now
        row["last_source_receipt_id"] = receipt_id
        data["updated_ts"] = now
        return data

    read_write_json_locked(path, _up, encoding="utf-8")
    return {
        "ok": True,
        "trace_id": tid,
        "source_receipt_id": receipt_id,
        "weight": float(weight),
    }


def strength_for(ids: Iterable[str], *, state_dir: Optional[Path] = None) -> Dict[str, float]:
    """Return overlay strength for trace ids. Missing rows are neutral 1.0."""
    table = load_trace_table(Path(state_dir) if state_dir is not None else _REPO / ".sifta_state")
    out: Dict[str, float] = {}
    for trace_id in ids:
        tid = str(trace_id or "").strip()
        if not tid:
            continue
        row = table.get(tid, {})
        try:
            out[tid] = float(row.get("strength", row.get("fitness", 1.0)))
        except Exception:
            out[tid] = 1.0
    return out


def bump_after_recall(trace_id: str, *, recall_delta: float = 0.05) -> None:
    """Successful recall: nudge fitness up, bump usage (atomic write)."""
    path = _fitness_path()
    now = time.time()
    tid = str(trace_id)

    def _up(data: Dict[str, Any]) -> Dict[str, Any]:
        data.setdefault("schema_version", 1)
        data.setdefault("overlay", "memory_fitness_acmf_v1")
        data.setdefault("traces", {})
        assert isinstance(data["traces"], dict)
        row = data["traces"].setdefault(
            tid,
            {"fitness": 1.0, "usage_count": 0, "last_used_ts": 0.0},
        )
        row["fitness"] = float(max(0.1, float(row.get("fitness", 1.0)) + recall_delta))
        row["usage_count"] = int(row.get("usage_count", 0)) + 1
        row["last_used_ts"] = now
        data["updated_ts"] = now
        return data

    read_write_json_locked(path, _up, encoding="utf-8")


def apply_outcome(trace_id: str, reward: float) -> None:
    """
    External outcome hook (e.g. gatekeeper / RL reward). Does not touch ledger.
    reward typically in [-1, 1]; scales fitness gently.
    """
    path = _REPO / ".sifta_state" / FITNESS_FILENAME
    tid = str(trace_id)
    delta = 0.15 * float(max(-1.0, min(1.0, reward)))
    now = time.time()

    def _up(data: Dict[str, Any]) -> Dict[str, Any]:
        data.setdefault("schema_version", 1)
        data.setdefault("overlay", "memory_fitness_acmf_v1")
        data.setdefault("traces", {})
        assert isinstance(data["traces"], dict)
        row = data["traces"].setdefault(
            tid,
            {"fitness": 1.0, "usage_count": 0, "last_used_ts": 0.0},
        )
        row["fitness"] = float(max(0.1, float(row.get("fitness", 1.0)) + delta))
        row["last_used_ts"] = now
        data["updated_ts"] = now
        return data

    read_write_json_locked(path, _up, encoding="utf-8")


if __name__ == "__main__":
    bump_after_recall("smoke_trace_id", recall_delta=0.01)
    apply_outcome("smoke_trace_id", reward=0.5)
    tbl = load_trace_table(_REPO / ".sifta_state")
    print("overlay keys:", list(tbl.keys())[-3:])
    print("smoke:", tbl.get("smoke_trace_id"))
