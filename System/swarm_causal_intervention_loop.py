"""
Event 139 - Pearl-style causal intervention loop.

This module records `do(...)` trials as receipts. It does not claim causal
truth from observational logs alone. The point is to make intervention claims
auditable:

  baseline state/outcome
  intervention do(variable=value)
  intervened state/outcome
  effect size
  assumptions/backdoor notes

Kill-switch: SIFTA_CAUSAL_LOOP_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "causal_intervention_trials.jsonl"


def causal_intervention_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _metric(outcome: Dict[str, Any], metric: str) -> float:
    try:
        return float(outcome.get(metric, 0.0))
    except (TypeError, ValueError):
        return 0.0


def compute_effect_size(
    baseline_outcome: Dict[str, Any],
    intervention_outcome: Dict[str, Any],
    *,
    metric: str = "reward",
) -> float:
    return round(_metric(intervention_outcome, metric) - _metric(baseline_outcome, metric), 6)


def run_intervention_trial(
    *,
    variable: str,
    intervention_value: Any,
    baseline_state: Dict[str, Any],
    intervened_state: Dict[str, Any],
    baseline_outcome: Dict[str, Any],
    intervention_outcome: Dict[str, Any],
    metric: str = "reward",
    blocked_backdoors: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if os.environ.get("SIFTA_CAUSAL_LOOP_DISABLE", "").strip() == "1":
        return {
            "ts": now or time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "CAUSAL_INTERVENTION_TRIAL",
            "kind": "CAUSAL_INTERVENTION_TRIAL",
            "disabled": True,
            "do": {variable: intervention_value},
            "effect_size": 0.0,
        }

    baseline_metric = _metric(baseline_outcome, metric)
    intervention_metric = _metric(intervention_outcome, metric)
    effect = round(intervention_metric - baseline_metric, 6)
    if effect > 0:
        direction = "positive"
    elif effect < 0:
        direction = "negative"
    else:
        direction = "neutral"

    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "CAUSAL_INTERVENTION_TRIAL",
        "kind": "CAUSAL_INTERVENTION_TRIAL",
        "disabled": False,
        "do": {variable: intervention_value},
        "metric": metric,
        "baseline_state": baseline_state,
        "intervened_state": intervened_state,
        "baseline_outcome": baseline_outcome,
        "intervention_outcome": intervention_outcome,
        "baseline_metric": round(baseline_metric, 6),
        "intervention_metric": round(intervention_metric, 6),
        "effect_size": effect,
        "direction": direction,
        "blocked_backdoors": blocked_backdoors or [],
        "assumptions": assumptions or [],
        "causal_claim": "INTERVENTION_RECEIPT_NOT_CAUSAL_PROOF",
    }
    if write_ledger:
        append_line_locked(
            causal_intervention_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_intervention_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = causal_intervention_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out[-max(1, min(max_rows, 200)) :]


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_intervention_rows(8, root=root)
    if not rows:
        return ""
    positives = sum(1 for r in rows if r.get("direction") == "positive")
    negatives = sum(1 for r in rows if r.get("direction") == "negative")
    latest = rows[-1]
    return (
        "CAUSAL INTERVENTION LOOP (Pearl do-receipts): "
        f"recent={len(rows)}, positive={positives}, negative={negatives}, "
        f"latest_effect={latest.get('effect_size')}"
    )


__all__ = [
    "causal_intervention_log_path",
    "compute_effect_size",
    "run_intervention_trial",
    "summary_for_prompt",
    "tail_intervention_rows",
]
