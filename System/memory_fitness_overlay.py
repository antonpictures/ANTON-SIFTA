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
from typing import Any, Dict

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


def bump_after_recall(trace_id: str, *, recall_delta: float = 0.05) -> None:
    """Successful recall: nudge fitness up, bump usage (atomic write)."""
    path = _REPO / ".sifta_state" / FITNESS_FILENAME
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
