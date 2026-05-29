"""Round 117 — stigmergic arm fallback picker.

When a heavy arm times out, the body doesn't fall back to a hardcoded
gemma. It counts. It looks at the recent agent_arm_receipts ledger,
sees which arms have been succeeding in the last N minutes, and returns
the one that has been working most reliably — the swarm picks its own
fallback by stigmergic trace, not by a rule the Architect wrote once
and forgot.

Pure stdlib. Read-only. No shell-out, no network.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, List, Optional


_DEFAULT_WINDOW_S = 30 * 60.0          # last 30 minutes of receipts
_MIN_ATTEMPTS_TO_TRUST = 1             # one landed success is enough to be considered
_LEDGER_NAME = "agent_arm_receipts.jsonl"


def _read_recent(ledger: Path, *, max_age_s: float, now: float) -> List[dict]:
    if not ledger.exists():
        return []
    cutoff = now - max_age_s
    try:
        data = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: List[dict] = []
    for line in data[-1000:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ts = row.get("ts")
        try:
            tsf = float(ts)
        except (TypeError, ValueError):
            continue
        if tsf < cutoff:
            continue
        rows.append(row)
    return rows


def arm_success_counts(
    state_dir: Path,
    *,
    max_age_s: float = _DEFAULT_WINDOW_S,
    now: Optional[float] = None,
) -> dict:
    """Return per-arm {attempts, successes, success_rate, last_success_ts}.

    A row counts as a success when its truth_label is OPERATIONAL or its
    ok field is True. Anything else (timeout, suppression, failure, error,
    field_failure) is an attempt without success.
    """
    now = float(now if now is not None else time.time())
    rows = _read_recent(state_dir / _LEDGER_NAME, max_age_s=max_age_s, now=now)
    counts: dict = {}
    for row in rows:
        arm = (
            row.get("arm_id")
            or row.get("arm")
            or row.get("display_name")
            or ""
        )
        if not arm:
            continue
        arm = str(arm).strip()
        rec = counts.setdefault(
            arm,
            {"attempts": 0, "successes": 0, "success_rate": 0.0, "last_success_ts": 0.0},
        )
        rec["attempts"] += 1
        truth = str(row.get("truth_label", "")).upper().strip()
        ok = bool(row.get("ok"))
        succeeded = ok or truth == "OPERATIONAL"
        if succeeded:
            rec["successes"] += 1
            try:
                ts_val = float(row.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts_val = 0.0
            if ts_val > rec["last_success_ts"]:
                rec["last_success_ts"] = ts_val
    for rec in counts.values():
        a = rec["attempts"]
        rec["success_rate"] = (rec["successes"] / a) if a > 0 else 0.0
    return counts


def pick_fallback_arm(
    state_dir: Path,
    *,
    exclude: Iterable[str] = (),
    available: Iterable[str] = (),
    max_age_s: float = _DEFAULT_WINDOW_S,
    now: Optional[float] = None,
) -> dict:
    """Choose the recently-working arm to fall back to.

    Selection rule (the body knows its own trail):
      1. Among `available` arms not in `exclude`, pick the one with
         highest recent success_rate.
      2. Break ties by `last_success_ts` (most recent wins).
      3. Break further ties by total `successes` (more trail wins).
      4. If no arm in `available` has any recent success, return the
         oldest available arm so the body still tries something rather
         than refusing the turn.
      5. If `available` is empty, fall through to the previously canonical
         local arm ("corvid_scout") so a node with no recent ledger
         history still has a reply path.
    """
    exclude_set = {str(a).strip() for a in exclude if str(a).strip()}
    available_list = [str(a).strip() for a in available if str(a).strip() and str(a).strip() not in exclude_set]
    counts = arm_success_counts(state_dir, max_age_s=max_age_s, now=now)

    def _ranked():
        ranked: list[tuple[float, float, int, str]] = []
        for arm in available_list:
            rec = counts.get(arm) or {"attempts": 0, "successes": 0, "success_rate": 0.0, "last_success_ts": 0.0}
            ranked.append((rec["success_rate"], rec["last_success_ts"], rec["successes"], arm))
        ranked.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
        return ranked

    if not available_list:
        return {
            "arm_id": "corvid_scout",
            "reason": "no_available_arms_supplied_using_node_default",
            "success_rate": 0.0,
            "last_success_ts": 0.0,
            "successes": 0,
        }

    ranked = _ranked()
    top = ranked[0]
    if top[2] == 0:
        # Nobody succeeded recently — still pick the first available so
        # the body keeps moving instead of refusing the turn.
        return {
            "arm_id": available_list[0],
            "reason": "no_recent_success_in_window_using_first_available",
            "success_rate": 0.0,
            "last_success_ts": 0.0,
            "successes": 0,
        }
    return {
        "arm_id": top[3],
        "reason": "stigmergic_recent_success_winner",
        "success_rate": float(top[0]),
        "last_success_ts": float(top[1]),
        "successes": int(top[2]),
    }


__all__ = ["arm_success_counts", "pick_fallback_arm"]
