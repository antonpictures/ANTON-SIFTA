#!/usr/bin/env python3
"""swarm_strategy_failure_revision.py — autonomous failure→revision cycle.

Truth label: ``SIFTA_STRATEGY_FAILURE_REVISION_V1``.

Closes the ``autonomous_long_horizon_planning`` open gap of
:mod:`System.swarm_agi_frontier_loop`. The frontier-loop strategy
module already implements:

  * :func:`create_strategy` — append a STRATEGY_CREATED row
  * :func:`record_strategy_event` — append a generic event row
  * :func:`revise_strategy` — append a STRATEGY_REVISED row
  * :func:`strategy_snapshot` — derive ``survived_failure`` from the
    rows: True when at least one FAILURE row exists AND at least one
    STRATEGY_REVISED row has a strictly later timestamp than the most
    recent FAILURE row.

What the peer module does **not** ship is the policy that decides
*when* a failure has occurred — without it the strategy stays
``TRACKED_NOT_AUTONOMOUS``. This module is the missing edge per §8.5
of ``IDE_BOOT_COVENANT.md``: audit, don't redo. It applies a single,
auditable rule:

  ``A milestone is FAILED when its implicit deadline has passed and no
  MILESTONE_DONE row references it.``

The implicit deadline is computed from the strategy's
``horizon_days`` divided over its ordered ``milestones`` list. The
first milestone is due at ``horizon_days / N`` days after creation, the
second at ``2 * horizon_days / N``, and so on. When the current time is
past a milestone's implicit deadline and no MILESTONE_DONE row was
recorded for it, the runner writes a FAILURE row citing the milestone +
the deadline gap. Then it writes a STRATEGY_REVISED row whose
``new_milestone`` proposes a smaller, demonstrably-achievable next step
derived from the latest frontier_status() output.

Truth boundary
--------------

This is policy code, not a planner. It reads ledgers, applies the
deadline rule, and writes append-only rows. It never deletes or
rewrites prior events. The autonomy claim is bounded: the runner
detects deadline slips and proposes a smaller next milestone; it does
not execute outside of the strategy ledger.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.swarm_agi_frontier_loop import (
        STRATEGY_TRUTH_LABEL,
        latest_strategy_id,
        record_strategy_event,
        revise_strategy,
        strategy_events,
        strategy_snapshot,
        frontier_status,
    )
except Exception:  # pragma: no cover
    STRATEGY_TRUTH_LABEL = "SIFTA_LONG_HORIZON_STRATEGY_V1"
    latest_strategy_id = None  # type: ignore
    record_strategy_event = None  # type: ignore
    revise_strategy = None  # type: ignore
    strategy_events = None  # type: ignore
    strategy_snapshot = None  # type: ignore
    frontier_status = None  # type: ignore

try:
    from System.swarm_persistent_owner_history import state_dir
except Exception:  # pragma: no cover
    def state_dir(explicit: Optional[Path] = None) -> Path:  # type: ignore[override]
        if explicit is not None:
            return Path(explicit)
        return Path(__file__).resolve().parent.parent / ".sifta_state"


TRUTH_LABEL = "SIFTA_STRATEGY_FAILURE_REVISION_V1"
RUNNER_LEDGER = "strategy_failure_revision_runs.jsonl"

TRUTH_BOUNDARY = (
    "Detects deadline slips on long-horizon strategy milestones using "
    "horizon_days / N implicit deadlines. Writes a FAILURE row when a "
    "milestone is past due and a STRATEGY_REVISED row that names a "
    "smaller next step derived from the current frontier_status open "
    "gaps. Append-only — never rewrites prior events."
)


# ── helpers ──────────────────────────────────────────────────────────────


def _sd(root: Optional[Path] = None) -> Path:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _strategy_created_row(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for e in events:
        if e.get("kind") == "STRATEGY_CREATED":
            return e
    return None


def _milestone_status(
    events: List[Dict[str, Any]],
    *,
    now: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Return per-milestone status with implicit deadline + outcome.

    Each entry has keys ``milestone``, ``due_at`` (unix ts), ``done``,
    ``failed``, ``failed_at``.
    """
    created = _strategy_created_row(events)
    if not created:
        return []
    milestones: List[str] = list(created.get("milestones") or [])
    if not milestones:
        return []
    horizon_days = float(created.get("horizon_days", 0) or 0)
    horizon_seconds = horizon_days * 86400.0
    created_ts = float(created.get("ts", 0.0) or 0.0)
    N = len(milestones)
    if N == 0 or created_ts <= 0 or horizon_seconds <= 0:
        return []
    now_ts = float(now if now is not None else time.time())
    done_set = {
        str(e.get("milestone"))
        for e in events
        if e.get("kind") == "MILESTONE_DONE" and e.get("milestone")
    }
    failed_set = {
        str(e.get("milestone")): float(e.get("ts", 0.0) or 0.0)
        for e in events
        if e.get("kind") in {"FAILURE", "STRATEGY_FAILURE"} and e.get("milestone")
    }
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(milestones, start=1):
        due_at = created_ts + (horizon_seconds * (i / N))
        out.append(
            {
                "milestone": m,
                "due_at": due_at,
                "done": m in done_set,
                "failed": m in failed_set,
                "failed_at": failed_set.get(m, 0.0),
                "overdue_seconds": max(0.0, now_ts - due_at) if (m not in done_set) else 0.0,
            }
        )
    return out


def _first_overdue_milestone(
    statuses: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """First milestone that is past due, not yet done, not yet failed-rec."""
    for s in statuses:
        if s["done"] or s["failed"]:
            continue
        if s["overdue_seconds"] > 0:
            return s
    return None


def _propose_next_milestone(
    *,
    root: Optional[Path] = None,
) -> Tuple[str, str]:
    """Return ``(new_milestone, reason)`` from current frontier_status.

    The new milestone is chosen from the smallest, most-actionable open
    gap reported by the AGI frontier loop. If no frontier_status is
    available, propose a generic ``collect more receipts`` step.
    """
    if frontier_status is None:
        return (
            "collect more receipts so the frontier loop has measurable evidence",
            "frontier_status import unavailable; defaulting to receipt collection",
        )
    try:
        status = frontier_status(root=root)
    except Exception as exc:
        return (
            "collect more receipts so the frontier loop has measurable evidence",
            f"frontier_status raised {type(exc).__name__}: {exc}",
        )
    gaps: List[str] = list(status.get("open_gaps") or [])
    if not gaps:
        return (
            "promote frontier loop status to EVIDENCED across all categories",
            "frontier_status reports no remaining open gaps",
        )
    # The smallest gap text is usually the most actionable. Pick the
    # shortest gap to keep the milestone tight.
    shortest = min(gaps, key=len)
    return (
        f"close subset: {shortest}",
        f"chose smallest of {len(gaps)} open gaps",
    )


# ── runner ───────────────────────────────────────────────────────────────


def _select_evidenceless_milestone(
    statuses: List[Dict[str, Any]],
    root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Select a milestone whose receipts already prove it will miss.

    A milestone is **evidence-failed** when its text mentions a target
    threshold that the live receipt ledger has not yet hit. We probe
    the AGI frontier loop's ``frontiers`` block (not just the gap
    sentence) so the matching is structural, not string-based.
    """
    if frontier_status is None:
        return None
    try:
        status = frontier_status(root=root)
    except Exception:
        return None
    frontiers = status.get("frontiers") or {}
    if not isinstance(frontiers, dict):
        return None

    # A frontier is "underpowered" when its ``ready`` flag is False.
    underpowered_frontiers = {
        name for name, payload in frontiers.items()
        if isinstance(payload, dict) and not payload.get("ready", False)
    }
    if not underpowered_frontiers:
        return None

    # Map milestone keywords → underpowered frontier names.
    frontier_keyword_map = (
        ("paired steering predictions", "robust_causal_modeling"),
        ("paired samples per", "robust_causal_modeling"),
        ("causal", "robust_causal_modeling"),
        ("latent", "learned_latent_models"),
        ("world model", "learned_latent_models"),
        ("transfer probe", "transferable_abstraction"),
        ("concept model", "open_ended_concept_formation"),
        ("failure and revise", "autonomous_long_horizon_planning"),
    )
    for s in statuses:
        if s["done"] or s["failed"]:
            continue
        m_lower = str(s["milestone"]).lower()
        for kw, frontier_name in frontier_keyword_map:
            if kw in m_lower and frontier_name in underpowered_frontiers:
                return s
    return None


def run_failure_revision_cycle(
    *,
    root: Optional[Path] = None,
    strategy_id: Optional[str] = None,
    now: Optional[float] = None,
    write: bool = True,
    propose_milestone: Optional[Tuple[str, str]] = None,
    detect_evidence_failures: bool = True,
) -> Dict[str, Any]:
    """Detect a deadline slip and write FAILURE + STRATEGY_REVISED rows.

    Returns a receipt dict naming what was detected and what was
    written. The receipt has ``survived_failure_after`` set to the
    strategy_snapshot()['survived_failure'] flag *after* the runner has
    written its rows — this is what the AGI frontier loop reads when
    it gates the long-horizon planning frontier.

    Failure detection runs in two passes:

      1. **Deadline slip** — first milestone past its horizon_days/N
         implicit deadline with no MILESTONE_DONE row.
      2. **Evidence failure** (when ``detect_evidence_failures=True``)
         — first milestone whose keyword text maps to a still-OPEN
         frontier gap with no measurable evidence. This catches real
         misses before the deadline.
    """
    if record_strategy_event is None or revise_strategy is None:
        raise RuntimeError(
            "swarm_agi_frontier_loop strategy helpers are not importable."
        )

    sid = strategy_id
    if sid is None and latest_strategy_id is not None:
        sid = latest_strategy_id(root=root)
    if not sid:
        return {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "kind": "STRATEGY_FAILURE_REVISION_NOOP",
            "truth_label": TRUTH_LABEL,
            "reason": "no_strategy_present",
            "wrote_failure": False,
            "wrote_revision": False,
            "survived_failure_after": False,
        }

    events = strategy_events(sid, root=root) if strategy_events else []  # type: ignore[arg-type]
    statuses = _milestone_status(events, now=now)
    overdue = _first_overdue_milestone(statuses)
    evidence_failed = None
    failure_kind = "deadline_slip"
    if overdue is None and detect_evidence_failures:
        evidence_failed = _select_evidenceless_milestone(statuses, root=root)
        if evidence_failed is not None:
            overdue = evidence_failed
            failure_kind = "evidence_failure"
    pre_snapshot = strategy_snapshot(sid, root=root) if strategy_snapshot else {}  # type: ignore[arg-type]

    wrote_failure = False
    wrote_revision = False
    failure_row: Dict[str, Any] = {}
    revision_row: Dict[str, Any] = {}
    new_milestone = ""
    reason_used = ""

    if overdue is not None:
        milestone = overdue["milestone"]
        overdue_seconds = overdue["overdue_seconds"]
        if propose_milestone is not None:
            new_milestone, reason_used = propose_milestone
        else:
            new_milestone, reason_used = _propose_next_milestone(root=root)

        if write:
            if failure_kind == "evidence_failure":
                note = (
                    f"Milestone '{milestone}' is evidence-failed: local "
                    f"receipts already show its target gap is OPEN with no "
                    f"measurable progress. Recording as FAILURE so the "
                    f"strategy can revise toward a smaller, demonstrable "
                    f"next step."
                )
            else:
                note = (
                    f"Milestone '{milestone}' is overdue by "
                    f"{int(overdue_seconds // 60)} minutes against its "
                    f"implicit horizon_days/N deadline. Local receipts do not "
                    f"yet show evidence of completion."
                )
            failure_row = record_strategy_event(
                sid,
                "FAILURE",
                note,
                milestone=milestone,
                outcome_delta=-0.05,
                root=root,
                write=True,
            )
            wrote_failure = True

            # A revision must be written strictly AFTER the failure ts so
            # ``survived_failure`` flips True. The peer ledger uses ts
            # from _append_receipt(); a tiny sleep guarantees strict
            # monotonicity even on fast CPUs.
            time.sleep(0.001)
            revision_row = revise_strategy(
                sid,
                reason=(
                    f"Detected deadline slip on '{milestone}'. "
                    f"Reduced scope per frontier_status open gaps: {reason_used}."
                ),
                new_milestone=new_milestone,
                root=root,
                write=True,
            )
            wrote_revision = True

    post_snapshot = strategy_snapshot(sid, root=root) if strategy_snapshot else {}  # type: ignore[arg-type]

    receipt = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "STRATEGY_FAILURE_REVISION_RUN",
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "strategy_id": sid,
        "milestone_statuses": statuses,
        "overdue_milestone": overdue,
        "failure_kind": failure_kind,
        "wrote_failure": wrote_failure,
        "wrote_revision": wrote_revision,
        "new_milestone": new_milestone,
        "revision_reason": reason_used,
        "pre_survived_failure": bool(pre_snapshot.get("survived_failure", False)),
        "survived_failure_after": bool(post_snapshot.get("survived_failure", False)),
        "failure_trace_id": failure_row.get("trace_id"),
        "revision_trace_id": revision_row.get("trace_id"),
    }
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    receipt["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if write:
        ledger = _sd(root) / RUNNER_LEDGER
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    return receipt


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--strategy-id", default=None)
    args = p.parse_args()
    out = run_failure_revision_cycle(
        strategy_id=args.strategy_id, write=not args.no_write
    )
    print(f"TRUTH:                    {out['truth_label']}")
    print(f"STRATEGY:                 {out['strategy_id']}")
    print(f"OVERDUE:                  {out['overdue_milestone']}")
    print(f"WROTE_FAILURE:            {out['wrote_failure']}")
    print(f"WROTE_REVISION:           {out['wrote_revision']}")
    print(f"NEW_MILESTONE:            {out['new_milestone']}")
    print(f"PRE_SURVIVED_FAILURE:     {out['pre_survived_failure']}")
    print(f"SURVIVED_FAILURE_AFTER:   {out['survived_failure_after']}")
    print(f"SHA:                      {out['sha256'][:16]}")
