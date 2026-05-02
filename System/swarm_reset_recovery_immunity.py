# System/swarm_reset_recovery_immunity.py

"""
Event 110 — Reset Recovery Immunity

Problem:
After reset, the Swarm needs to know what survived, what broke,
and what must be rehydrated before autonomy resumes.

Biology:
After injury/sleep/reset, organisms perform immune scan + wound repair
before returning to full behavior.

SIFTA:
Post-reset recovery organ:
- checks required ledgers
- checks recent heartbeat continuity
- computes recovery phase
- emits rehydration actions
- blocks unsafe autonomy when memory substrate is cold

Truth label:
POST_RESET_IMMUNE_RECOVERY
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


STATE = Path(".sifta_state")
RECOVERY_LOG = STATE / "reset_recovery_immunity.jsonl"

REQUIRED_LEDGER_PATHS = {
    "trace": STATE / "ide_stigmergic_trace.jsonl",
    "body": STATE / "body_brain_memory.jsonl",
    "health": STATE / "nightly_health.jsonl",
    "homeostasis": STATE / "homeostasis_actions.jsonl",
    "policy": STATE / "motor_policy.jsonl",
    "skills": STATE / "skill_primitives.jsonl",
    "bio_claims": STATE / "bio_claims.jsonl",
}


def read_tail(path: Path, n: int = 3) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(errors="ignore").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def ledger_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    rows = read_tail(path, 3) if exists else []
    age_s = None

    if rows:
        ts = rows[-1].get("ts", rows[-1].get("timestamp"))
        try:
            age_s = max(0.0, time.time() - float(ts))
        except Exception:
            age_s = None

    return {
        "exists": exists,
        "tail_rows": len(rows),
        "age_s": age_s,
        "warm": exists and len(rows) > 0 and (age_s is None or age_s < 86400),
    }


def compute_reset_recovery() -> dict[str, Any]:
    ledgers = {
        name: ledger_status(path)
        for name, path in REQUIRED_LEDGER_PATHS.items()
    }

    warm_count = sum(1 for s in ledgers.values() if s["warm"])
    total = len(ledgers)
    warmth = warm_count / max(1, total)

    missing = [name for name, s in ledgers.items() if not s["exists"]]
    cold = [name for name, s in ledgers.items() if s["exists"] and not s["warm"]]

    if warmth >= 0.85:
        phase = "READY"
        autonomy_gate = "ALLOW"
    elif warmth >= 0.50:
        phase = "REHYDRATE"
        autonomy_gate = "LIMITED"
    else:
        phase = "WOUND_REPAIR"
        autonomy_gate = "BLOCK"

    recommended_actions = []

    if missing:
        recommended_actions.append("create_missing_ledgers")
    if cold:
        recommended_actions.append("run_rehydration_tick")
    if phase != "READY":
        recommended_actions.append("force_observe_then_repair")
    if "skills" in missing or "policy" in missing:
        recommended_actions.append("disable_skill_weighted_motor_policy")

    return {
        "ts": time.time(),
        "truth_label": "POST_RESET_IMMUNE_RECOVERY",
        "warmth": round(warmth, 4),
        "phase": phase,
        "autonomy_gate": autonomy_gate,
        "missing_ledgers": missing,
        "cold_ledgers": cold,
        "ledger_status": ledgers,
        "recommended_actions": recommended_actions,
    }


def write_reset_recovery() -> dict[str, Any]:
    STATE.mkdir(parents=True, exist_ok=True)
    row = compute_reset_recovery()
    with RECOVERY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    print(json.dumps(write_reset_recovery(), indent=2, sort_keys=True))
