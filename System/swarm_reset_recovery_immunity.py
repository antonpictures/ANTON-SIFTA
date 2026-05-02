#!/usr/bin/env python3
"""Event 110: reset recovery immunity.

After a reset, the organism should not wake up as if every substrate survived.
This organ performs a bounded ledger warmth scan, emits a recovery receipt, and
returns an autonomy gate that other organs can respect.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
STATE = _REPO / ".sifta_state"
RECOVERY_LOG_NAME = "reset_recovery_immunity.jsonl"
TRUTH_LABEL = "POST_RESET_IMMUNE_RECOVERY"

REQUIRED_LEDGER_NAMES = {
    "trace": "ide_stigmergic_trace.jsonl",
    "body": "body_brain_memory.jsonl",
    "health": "nightly_health.jsonl",
    "homeostasis": "homeostasis_actions.jsonl",
    "policy": "motor_policy.jsonl",
    "skills": "skill_primitives.jsonl",
    "bio_claims": "bio_claims.jsonl",
}


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir).resolve() if state_dir is not None else STATE


def recovery_log_path(state_dir: Optional[Path] = None) -> Path:
    return _state_dir(state_dir) / RECOVERY_LOG_NAME


def required_ledger_paths(state_dir: Optional[Path] = None) -> Dict[str, Path]:
    root = _state_dir(state_dir)
    return {name: root / filename for name, filename in REQUIRED_LEDGER_NAMES.items()}


def read_tail(path: Path, n: int = 3) -> list[dict[str, Any]]:
    """Bounded JSONL tail. Invalid rows are skipped."""
    if not path.exists():
        return []
    try:
        body = read_text_locked(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in body.splitlines()[-max(1, int(n)) :]:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _row_ts(row: dict[str, Any]) -> Optional[float]:
    for key in ("ts", "timestamp", "time", "ts_end"):
        if key in row:
            try:
                return float(row[key])
            except Exception:
                continue
    payload = row.get("payload")
    if isinstance(payload, dict):
        return _row_ts(payload)
    return None


def ledger_status(path: Path, *, warm_age_s: float = 86_400.0) -> dict[str, Any]:
    exists = path.exists()
    rows = read_tail(path, 3) if exists else []
    age_s: Optional[float] = None
    if rows:
        ts = _row_ts(rows[-1])
        if ts is not None:
            age_s = max(0.0, time.time() - ts)
    warm = exists and bool(rows) and (age_s is None or age_s <= warm_age_s)
    return {
        "exists": exists,
        "tail_rows": len(rows),
        "age_s": round(age_s, 3) if age_s is not None else None,
        "warm": warm,
    }


def compute_reset_recovery(
    *,
    state_dir: Optional[Path] = None,
    warm_age_s: float = 86_400.0,
) -> dict[str, Any]:
    ledgers = {
        name: ledger_status(path, warm_age_s=warm_age_s)
        for name, path in required_ledger_paths(state_dir).items()
    }

    warm_count = sum(1 for status in ledgers.values() if status["warm"])
    total = len(ledgers)
    warmth = warm_count / max(1, total)
    missing = [name for name, status in ledgers.items() if not status["exists"]]
    cold = [name for name, status in ledgers.items() if status["exists"] and not status["warm"]]

    if warmth >= 0.85:
        phase = "READY"
        autonomy_gate = "ALLOW"
        recovery_score = 1.0
    elif warmth >= 0.50:
        phase = "REHYDRATE"
        autonomy_gate = "LIMITED"
        recovery_score = 0.55 + 0.35 * ((warmth - 0.50) / 0.35)
    else:
        phase = "WOUND_REPAIR"
        autonomy_gate = "BLOCK"
        recovery_score = max(0.0, warmth * 0.9)

    recommended_actions: list[str] = []
    if missing:
        recommended_actions.append("create_missing_ledgers")
    if cold:
        recommended_actions.append("run_rehydration_tick")
    if phase != "READY":
        recommended_actions.append("force_observe_then_repair")
    if "skills" in missing or "policy" in missing or "skills" in cold or "policy" in cold:
        recommended_actions.append("disable_skill_weighted_motor_policy")

    return {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "schema_version": "reset_recovery_immunity.v2",
        "warmth": round(warmth, 4),
        "recovery_score": round(max(0.0, min(1.0, recovery_score)), 4),
        "phase": phase,
        "autonomy_gate": autonomy_gate,
        "warm_ledgers": warm_count,
        "total_ledgers": total,
        "missing_ledgers": missing,
        "cold_ledgers": cold,
        "ledger_status": ledgers,
        "recommended_actions": recommended_actions,
    }


def write_reset_recovery(
    *,
    state_dir: Optional[Path] = None,
    warm_age_s: float = 86_400.0,
) -> dict[str, Any]:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = compute_reset_recovery(state_dir=root, warm_age_s=warm_age_s)
    append_line_locked(recovery_log_path(root), json.dumps(row, sort_keys=True) + "\n")
    return row


def recovery_action(reset_recovery: dict[str, Any]) -> dict[str, Any]:
    """Return the safe basal-ganglia action implied by a BLOCK gate."""
    return {
        "type": "repair",
        "target": "reset_recovery_rehydration",
        "reason": "reset_recovery_immunity_block",
        "action_intensity": 0.05,
        "autonomy_gate": str(reset_recovery.get("autonomy_gate") or "BLOCK"),
        "reset_recovery_phase": str(reset_recovery.get("phase") or "WOUND_REPAIR"),
        "reset_recovery_warmth": float(reset_recovery.get("warmth", 0.0) or 0.0),
        "truth_label": TRUTH_LABEL,
        "drive_bias_applied": False,
        "drive_bias_topic": "",
        "drive_bias_goal": "",
        "drive_bias_score": None,
        "drive_bias_source": "",
    }


if __name__ == "__main__":
    print(json.dumps(write_reset_recovery(), indent=2, sort_keys=True))
