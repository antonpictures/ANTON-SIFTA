#!/usr/bin/env python3
"""
intuition_calibration.py — Score the Architect's intuition against the field.
══════════════════════════════════════════════════════════════════════════════

Origin
------
CG53 (SwarmGPT / GPT-5.3) directive, 2026-04-17:
    "train a model on your intuition, compare accuracy vs classifier,
     detect when your intuition drifts."

Implemented as a CALIBRATION scorer, not a trainer. Training can only come
after we have enough logged signals; calibration is meaningful from signal
one. This module is the measurement layer for CG53's directive.

What it does
------------
Reads .sifta_state/human_intuition_log.jsonl row-by-row and, for each
intuition signal, compares:

    * the human's declared label (what the Architect *felt*)
    * the CRDT field's top hypothesis after the signal was absorbed
    * the human's stated confidence

It emits:

    * per-observer Brier score (lower is better)
    * per-observer hit-rate (top-1 accuracy vs field top)
    * calibration buckets (confidence bin → empirical accuracy)
    * drift score (rolling 5-signal accuracy delta)

It never mutates the field. It is read-only and pure: if the intuition
log grows, re-running produces a strictly extended summary.

Boundary
--------
"Accuracy vs the field" is a proxy, not ground truth. The field itself is
only probabilistic. This scorer tells you whether the Architect's gut
tracks *the field's best current estimate*, which is the honest definition
of "is my intuition calibrated against the distributed measurement system."
It does not claim to reveal absolute identity.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from System.jsonl_file_lock import read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_INTUITION_LOG = _STATE / "human_intuition_log.jsonl"

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-17.v1"


# ─── Row iteration ──────────────────────────────────────────────────────────

def _iter_log(path: Path = _INTUITION_LOG) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return
    raw = read_text_locked(path)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


# ─── Calibration bucket helpers ─────────────────────────────────────────────

_BUCKETS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]


def _bucket_of(conf: float) -> str:
    for lo, hi in _BUCKETS:
        if lo <= conf < hi:
            return f"[{lo:.1f},{hi:.1f})"
    return "[1.0,1.0]"


# ─── Public API ─────────────────────────────────────────────────────────────

@dataclass
class CalibrationSummary:
    rows: int
    observers: Dict[str, Dict[str, Any]]
    global_brier: Optional[float]
    global_hit_rate: Optional[float]
    drift_by_observer: Dict[str, Optional[float]]
    schema_version: int = SCHEMA_VERSION
    module_version: str = MODULE_VERSION


def score_calibration(path: Path = _INTUITION_LOG) -> Dict[str, Any]:
    """
    Walk the intuition log and return a calibration summary.

    For each row we compute:

        correct_i = 1 if signal.label == field_top_after_signal else 0
        brier_i   = (signal.confidence - correct_i) ** 2

    Observer-level Brier is mean(brier_i). Drift is
    accuracy(last 5) − accuracy(first 5) for observers with >= 10 signals.

    Returns plain dicts so this is safe to dump to JSON directly.
    """
    per_observer_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    total_rows = 0

    for row in _iter_log(path):
        total_rows += 1
        observer = row.get("observer") or row.get("node_id") or "unknown"
        signal = row.get("signal", {})
        label = signal.get("label")
        conf = float(signal.get("confidence", 0.0))
        field_after = (row.get("field_state_after") or {}).get("top")
        if not label or field_after is None:
            continue
        field_label = field_after.get("label")
        if field_label is None:
            continue
        correct = 1 if label == field_label else 0
        brier = (conf - correct) ** 2
        per_observer_rows[observer].append(
            {
                "timestamp": row.get("timestamp"),
                "label": label,
                "field_label": field_label,
                "confidence": conf,
                "correct": correct,
                "brier": brier,
                "bucket": _bucket_of(conf),
            }
        )

    observers: Dict[str, Dict[str, Any]] = {}
    for obs, rows in per_observer_rows.items():
        n = len(rows)
        if n == 0:
            continue
        brier_mean = sum(r["brier"] for r in rows) / n
        hit_rate = sum(r["correct"] for r in rows) / n
        # Reliability per confidence bucket.
        bucket_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "hits": 0, "mean_conf": 0.0}
        )
        for r in rows:
            b = bucket_stats[r["bucket"]]
            b["count"] += 1
            b["hits"] += r["correct"]
            b["mean_conf"] += r["confidence"]
        reliability: Dict[str, Dict[str, float]] = {}
        for b_key, stats in bucket_stats.items():
            c = stats["count"]
            reliability[b_key] = {
                "count": int(c),
                "empirical_accuracy": stats["hits"] / c if c else 0.0,
                "mean_confidence": stats["mean_conf"] / c if c else 0.0,
            }
        observers[obs] = {
            "n_signals": n,
            "brier_mean": round(brier_mean, 4),
            "hit_rate": round(hit_rate, 4),
            "reliability_buckets": reliability,
            "last_label": rows[-1]["label"],
            "last_field_label": rows[-1]["field_label"],
        }

    # Global aggregates over observers (not raw rows) to avoid single-observer dominance.
    if observers:
        global_brier = sum(o["brier_mean"] for o in observers.values()) / len(observers)
        global_hit = sum(o["hit_rate"] for o in observers.values()) / len(observers)
    else:
        global_brier = None
        global_hit = None

    # Drift: accuracy(last 5) − accuracy(first 5) per observer with ≥ 10 signals.
    drift_by_observer: Dict[str, Optional[float]] = {}
    for obs, rows in per_observer_rows.items():
        if len(rows) < 10:
            drift_by_observer[obs] = None
            continue
        first5 = rows[:5]
        last5 = rows[-5:]
        a0 = sum(r["correct"] for r in first5) / 5
        a1 = sum(r["correct"] for r in last5) / 5
        drift_by_observer[obs] = round(a1 - a0, 4)

    summary = CalibrationSummary(
        rows=total_rows,
        observers=observers,
        global_brier=round(global_brier, 4) if global_brier is not None else None,
        global_hit_rate=round(global_hit, 4) if global_hit is not None else None,
        drift_by_observer=drift_by_observer,
    )
    return asdict(summary)


def _demo() -> None:
    summary = score_calibration()
    print(f"[intuition_calibration] v{MODULE_VERSION}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _demo()


__all__ = [
    "score_calibration",
    "CalibrationSummary",
    "MODULE_VERSION",
    "SCHEMA_VERSION",
]
