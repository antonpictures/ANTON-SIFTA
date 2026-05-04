"""
Event 127 — Transfer gain evaluator (baseline vs replay-informed gates).

**Threshold tuning:** ``meaningful_transfer`` defaults to relative improvement
``(replay - baseline) / max(ε, baseline) > τ`` with ``τ`` from
``SIFTA_TRANSFER_GAIN_MEANINGFUL_REL`` (default ``0.15``). When
``baseline <= 0``, relative gain is undefined; set ``meaningful_transfer`` from
absolute gain vs ``SIFTA_TRANSFER_GAIN_MEANINGFUL_ABS`` (default ``0.05``) if
``SIFTA_TRANSFER_GAIN_USE_ABS_FOR_ZERO_BASELINE=1`` (default on).

**RL baseline nugget:** this module only **logs** scalar scores you already
computed offline or online; it does not train a tabular Q baseline. Pair logged
rows with controlled A/B (same task seed, different gate policies) to mimic
``off-policy evaluation`` / ``counterfactual`` style comparisons.

Truth label: **OPERATIONAL** — ledger + aggregates; not a statistical test.
Kill-switch: ``SIFTA_TRANSFER_GAIN_EVAL_DISABLE=1``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "transfer_gain_evaluations.jsonl"


def evaluation_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _meaningful_rel_threshold() -> float:
    raw = os.environ.get("SIFTA_TRANSFER_GAIN_MEANINGFUL_REL", "0.15").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.15


def _meaningful_abs_threshold() -> float:
    raw = os.environ.get("SIFTA_TRANSFER_GAIN_MEANINGFUL_ABS", "0.05").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.05


def _use_abs_for_zero_baseline() -> bool:
    return os.environ.get("SIFTA_TRANSFER_GAIN_USE_ABS_FOR_ZERO_BASELINE", "1").strip() == "1"


class TransferGainEvaluator:
    """
    Baseline vs replay-informed performance on the same task_id / task_name.
    Append-only JSONL for dashboards and nightly audits.
    """

    @staticmethod
    def evaluate_transfer_gain(
        baseline_performance: float,
        replay_performance: float,
        task_name: str,
        *,
        root: Optional[Path] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if os.environ.get("SIFTA_TRANSFER_GAIN_EVAL_DISABLE", "").strip() == "1":
            return {
                "evaluation_id": "disabled",
                "task_name": task_name,
                "skipped": True,
            }

        b = float(baseline_performance)
        r = float(replay_performance)
        gain = r - b
        eps = 1e-6
        denom = max(eps, b) if b > 0 else 0.0
        if b > 0:
            relative_gain = round(gain / denom, 4)
        else:
            relative_gain = 0.0

        tau_rel = _meaningful_rel_threshold()
        tau_abs = _meaningful_abs_threshold()
        if b > 0:
            meaningful = relative_gain > tau_rel
        else:
            meaningful = (
                _use_abs_for_zero_baseline() and gain > tau_abs
            ) or (not _use_abs_for_zero_baseline() and False)

        rid = hashlib.sha256(
            f"{task_name}|{time.time()}|{uuid.uuid4()}".encode("utf-8")
        ).hexdigest()[:16]

        evaluation: Dict[str, Any] = {
            "kind": "TRANSFER_GAIN_EVALUATION",
            "evaluation_id": rid,
            "ts": time.time(),
            "task_name": task_name,
            "baseline_score": round(b, 4),
            "replay_score": round(r, 4),
            "absolute_gain": round(gain, 4),
            "relative_gain": relative_gain,
            "meaningful_transfer": meaningful,
            "thresholds": {
                "meaningful_rel": tau_rel,
                "meaningful_abs": tau_abs,
                "zero_baseline_abs": _use_abs_for_zero_baseline(),
            },
        }
        if extra:
            evaluation["extra"] = extra

        append_line_locked(
            evaluation_log_path(root),
            json.dumps(evaluation, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return evaluation

    @staticmethod
    def get_overall_transfer_health(*, root: Optional[Path] = None) -> Dict[str, Any]:
        path = evaluation_log_path(root)
        if not path.exists():
            return {
                "avg_gain": 0.0,
                "avg_relative_gain": 0.0,
                "tasks_evaluated": 0,
                "successful_transfers": 0,
                "transfer_health": 0.0,
            }

        total = 0
        successful = 0
        abs_sum = 0.0
        rel_sum = 0.0
        raw = read_text_locked(path, encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("kind") != "TRANSFER_GAIN_EVALUATION":
                continue
            if e.get("skipped"):
                continue
            total += 1
            abs_sum += float(e.get("absolute_gain", 0.0) or 0.0)
            rel_sum += float(e.get("relative_gain", 0.0) or 0.0)
            if e.get("meaningful_transfer"):
                successful += 1

        avg_abs = round(abs_sum / total, 4) if total > 0 else 0.0
        avg_rel = round(rel_sum / total, 4) if total > 0 else 0.0
        return {
            "avg_gain": avg_rel,
            "avg_absolute_gain": avg_abs,
            "avg_relative_gain": avg_rel,
            "tasks_evaluated": total,
            "successful_transfers": successful,
            "transfer_health": round(successful / total, 3) if total > 0 else 0.0,
        }


__all__ = [
    "TransferGainEvaluator",
    "evaluation_log_path",
]
