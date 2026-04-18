#!/usr/bin/env python3
"""
swarm_temporal_horizon.py — Future Cost Simulator
══════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Breaks the myopia of standard agentic execution.
When an action is taken, it logs a deferred expectation structure. 
A chron job / heartbeat sweeps this file to see if past actions achieved 
their promised long-term rewards (e.g. "Skipping tests now saves 5 min, 
but triggers crashes 3 hours later").
"""

import time
import json
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

HORIZON_LOG = _STATE / "temporal_horizon_deferred.jsonl"
# C47H 2026-04-18: tombstone ledger to prevent double-fire (resolved action_ids
# are appended here so subsequent sweeps skip them; immutable append-only,
# matches SIFTA's overall ledger discipline).
HORIZON_RESOLVED = _STATE / "temporal_horizon_resolved.jsonl"


def _resolved_action_ids():
    """Return set of action_ids already resolved (tombstoned). C47H 2026-04-18."""
    if not HORIZON_RESOLVED.exists():
        return set()
    out = set()
    try:
        with open(HORIZON_RESOLVED, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    aid = row.get("action_id")
                    if aid:
                        out.add(aid)
                except Exception:
                    continue
    except OSError:
        pass
    return out


def _tombstone_resolution(row, current_metric_value, truth_delta, temporal_penalty):
    """Append a resolution row to HORIZON_RESOLVED. C47H 2026-04-18."""
    try:
        with open(HORIZON_RESOLVED, "a") as fh:
            fh.write(json.dumps({
                "action_id": row.get("action_id"),
                "action_kind": row.get("action_kind"),
                "target_metric": row.get("target_metric"),
                "creation_ts": row.get("creation_ts"),
                "evaluate_at_ts": row.get("evaluate_at_ts"),
                "promised_outcome": row.get("promised_outcome"),
                "actual_value": current_metric_value,
                "truth_delta": truth_delta,
                "temporal_penalty": temporal_penalty,
                "resolved_ts": time.time(),
            }) + "\n")
    except OSError:
        pass

@dataclass
class DeferredExpectation:
    action_id: str
    action_kind: str
    target_metric: str
    creation_ts: float
    evaluate_at_ts: float
    promised_outcome: float # Target numerical delta

class TemporalHorizon:
    def __init__(self):
        pass

    def log_expectation(self, action_id: str, action_kind: str, target_metric: str, delay_s: int, promised_delta: float):
        now = time.time()
        exp = DeferredExpectation(
            action_id=action_id,
            action_kind=action_kind,
            target_metric=target_metric,
            creation_ts=now,
            evaluate_at_ts=now + delay_s,
            promised_outcome=promised_delta
        )
        
        row = {
            "action_id": exp.action_id,
            "action_kind": exp.action_kind,
            "target_metric": exp.target_metric,
            "creation_ts": exp.creation_ts,
            "evaluate_at_ts": exp.evaluate_at_ts,
            "promised_outcome": exp.promised_outcome,
            "evaluated": False
        }
        
        try:
            with open(HORIZON_LOG, "a") as f:
                f.write(json.dumps(row) + "\n")
        except OSError:
            pass
        return exp

    def evaluate_due_horizons(self, current_metric_value: float) -> List[dict]:
        """
        Sweeps the log, finding due items, and checks if reality matches promise.
        In real execution, current_metric_value would be dynamically pulled per metric.

        C47H 2026-04-18 fix (daughter-safe bar):
        Resolved action_ids are tombstoned to HORIZON_RESOLVED on first evaluation.
        Subsequent sweeps skip them. Without this, a single past action would
        accumulate compounding fake penalties on every heartbeat (verified bug).
        """
        now = time.time()
        results = []

        if not HORIZON_LOG.exists():
            return results

        already_resolved = _resolved_action_ids()

        try:
            with open(HORIZON_LOG, "r") as f:
                lines = f.readlines()

            for line in lines:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("evaluated", True):
                    continue

                action_id = row.get("action_id")
                # C47H: skip already-tombstoned action_ids (no double-fire)
                if action_id in already_resolved:
                    continue

                if row.get("evaluate_at_ts", 0) <= now:
                    # Time has come to pay the piper
                    promised = row.get("promised_outcome", 0)
                    delta = current_metric_value - promised

                    penalty = 0.0
                    if delta < 0:  # Underperformed
                        penalty = delta * 2.0  # Deep penalty for lying

                    # C47H: tombstone immediately so next sweep won't refire.
                    _tombstone_resolution(row, current_metric_value, delta, penalty)
                    already_resolved.add(action_id)

                    results.append({
                        "action_id": action_id,
                        "truth_delta": delta,
                        "temporal_penalty": penalty
                    })
        except Exception:
            pass

        return results

if __name__ == "__main__":
    horizon = TemporalHorizon()
    print("═" * 58)
    print("  SIFTA — TEMPORAL HORIZON (FUTURE COST EVALUATOR)")
    print("═" * 58 + "\n")
    
    print("[TIME=0] Logging expectation: 'Bypass_Tests' promises +10.0 Speed in 2 seconds.")
    horizon.log_expectation("ACT_991", "Bypass_Tests", "speed", delay_s=2, promised_delta=10.0)
    
    print("[TIME=1] Evaluating... (Nothing due)")
    print(horizon.evaluate_due_horizons(current_metric_value=0.0))
    
    print("[TIME=3] Sweeping due horizons. Actual speed detected = -5.0 (Crashed!)")
    # Manually hacking the file for the smoke test to make it instantly due
    time.sleep(2)
    due = horizon.evaluate_due_horizons(current_metric_value=-5.0)
    for res in due:
        print(f"  -> Evaluated Action {res['action_id']}: Truth Delta = {res['truth_delta']} | Extracted Penalty: {res['temporal_penalty']}")
