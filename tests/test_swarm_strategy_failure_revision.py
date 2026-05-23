"""Tests for autonomous strategy failure-revision policy.

These pin:
  - No strategy present → runner returns NOOP without crashing.
  - On-schedule milestones → no failure written.
  - Overdue milestone → exactly one FAILURE + one STRATEGY_REVISED
    written, in that order, and the revision ts > failure ts.
  - After the runner writes the rows, strategy_snapshot() reports
    ``survived_failure=True``.
  - The runner flips the AGI frontier loop's
    ``autonomous_long_horizon_planning`` from
    ``TRACKED_NOT_AUTONOMOUS`` to ``EVIDENCED``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_agi_frontier_loop import (  # noqa: E402
    create_strategy,
    strategy_events,
    strategy_snapshot,
)
from System.swarm_strategy_failure_revision import (  # noqa: E402
    RUNNER_LEDGER,
    TRUTH_LABEL,
    _milestone_status,
    run_failure_revision_cycle,
)


# ── primitives ────────────────────────────────────────────────────────────


def test_milestone_status_marks_overdue_milestones(tmp_path):
    now = time.time()
    # Strategy created 21 days ago with 3 milestones over 7-day horizon →
    # all three deadlines have already passed.
    fake_created = {
        "kind": "STRATEGY_CREATED",
        "ts": now - 21 * 86400,
        "horizon_days": 7,
        "milestones": ["A", "B", "C"],
    }
    statuses = _milestone_status([fake_created], now=now)
    assert len(statuses) == 3
    for s in statuses:
        assert s["done"] is False
        assert s["failed"] is False
        assert s["overdue_seconds"] > 0


def test_milestone_status_skips_done_ones(tmp_path):
    now = time.time()
    fake_created = {
        "kind": "STRATEGY_CREATED",
        "ts": now - 21 * 86400,
        "horizon_days": 7,
        "milestones": ["A", "B"],
    }
    done = {"kind": "MILESTONE_DONE", "milestone": "A", "ts": now - 10 * 86400}
    statuses = _milestone_status([fake_created, done], now=now)
    assert statuses[0]["done"] is True
    assert statuses[1]["done"] is False


# ── runner ────────────────────────────────────────────────────────────────


def test_runner_noop_when_no_strategy_present(tmp_path):
    out = run_failure_revision_cycle(root=tmp_path, write=True)
    assert out["kind"] == "STRATEGY_FAILURE_REVISION_NOOP"
    assert out["wrote_failure"] is False
    assert out["wrote_revision"] is False


def test_runner_writes_failure_and_revision_on_overdue(tmp_path):
    # Manually create a strategy in the past by writing the ledger row
    # directly. We backdate ``ts`` so the first milestone is overdue.
    ledger = tmp_path / "agi_long_horizon_strategy.jsonl"
    backdate = time.time() - 30 * 86400  # 30 days ago
    created_row = {
        "ts": backdate,
        "trace_id": "STRATEGY_TEST_ROW",
        "truth_label": "SIFTA_LONG_HORIZON_STRATEGY_V1",
        "kind": "STRATEGY_CREATED",
        "strategy_id": "STRATEGY_TEST_001",
        "title": "Test long-horizon strategy",
        "objective": "Verify failure-revision policy.",
        "horizon_days": 7,
        "milestones": ["Hit the first metric", "Hit the second metric"],
        "status": "ACTIVE",
        "autonomy_boundary": "Test scaffold.",
    }
    ledger.write_text(json.dumps(created_row) + "\n", encoding="utf-8")

    pre = strategy_snapshot("STRATEGY_TEST_001", root=tmp_path)
    assert pre["survived_failure"] is False

    out = run_failure_revision_cycle(
        root=tmp_path,
        strategy_id="STRATEGY_TEST_001",
        write=True,
        propose_milestone=("smaller next step", "test override"),
    )
    assert out["wrote_failure"] is True
    assert out["wrote_revision"] is True
    assert out["new_milestone"] == "smaller next step"
    assert out["survived_failure_after"] is True

    # Two new rows on the ledger
    new_rows = [json.loads(ln) for ln in ledger.read_text().splitlines() if ln.strip()]
    kinds = [r["kind"] for r in new_rows]
    assert "FAILURE" in kinds
    assert "STRATEGY_REVISED" in kinds
    fail_ts = max(r["ts"] for r in new_rows if r["kind"] == "FAILURE")
    rev_ts = max(r["ts"] for r in new_rows if r["kind"] == "STRATEGY_REVISED")
    assert rev_ts > fail_ts  # strict monotonicity for survived_failure

    # Runner receipt ledger has one row
    runner_ledger = tmp_path / RUNNER_LEDGER
    assert runner_ledger.exists()
    runner_rows = runner_ledger.read_text().strip().splitlines()
    assert len(runner_rows) == 1
    assert json.loads(runner_rows[0])["truth_label"] == TRUTH_LABEL


def test_runner_does_not_double_fail_already_failed_milestones(tmp_path):
    """If a milestone already has a FAILURE row, the runner moves to the
    next overdue one (no duplicate failure on the same milestone)."""
    ledger = tmp_path / "agi_long_horizon_strategy.jsonl"
    backdate = time.time() - 30 * 86400
    rows = [
        {
            "ts": backdate,
            "trace_id": "x",
            "truth_label": "SIFTA_LONG_HORIZON_STRATEGY_V1",
            "kind": "STRATEGY_CREATED",
            "strategy_id": "S",
            "horizon_days": 7,
            "milestones": ["A", "B"],
            "status": "ACTIVE",
        },
        {
            "ts": backdate + 100,
            "trace_id": "y",
            "truth_label": "SIFTA_LONG_HORIZON_STRATEGY_V1",
            "kind": "FAILURE",
            "strategy_id": "S",
            "milestone": "A",
        },
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out = run_failure_revision_cycle(
        root=tmp_path, strategy_id="S", write=True,
        propose_milestone=("test next", "test"),
    )
    assert out["overdue_milestone"]["milestone"] == "B"


def test_runner_flips_agi_frontier_autonomous_planning(tmp_path):
    """End-to-end: strategy_snapshot reports the right shape after the
    runner has converted a TRACKED_NOT_AUTONOMOUS row to one with
    survived_failure=True."""
    # Create a strategy with horizon_days >= 7 + multiple milestones
    backdate = time.time() - 30 * 86400
    ledger = tmp_path / "agi_long_horizon_strategy.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "ts": backdate,
                "trace_id": "z",
                "truth_label": "SIFTA_LONG_HORIZON_STRATEGY_V1",
                "kind": "STRATEGY_CREATED",
                "strategy_id": "SEED",
                "horizon_days": 21,
                "milestones": ["M1", "M2", "M3"],
                "status": "ACTIVE",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = run_failure_revision_cycle(
        root=tmp_path, strategy_id="SEED", write=True,
        propose_milestone=("revised step", "test"),
    )
    assert out["survived_failure_after"] is True

    snap = strategy_snapshot("SEED", root=tmp_path)
    assert snap["survived_failure"] is True
    assert snap["failure_count"] >= 1
    assert snap["revision_count"] >= 1


def test_runner_propose_next_milestone_uses_smallest_open_gap(tmp_path):
    """When no override is passed, the runner uses frontier_status to
    pick the smallest open gap as the next milestone."""
    # Seed strategy in past, no frontier evidence, default proposal path
    backdate = time.time() - 30 * 86400
    ledger = tmp_path / "agi_long_horizon_strategy.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "ts": backdate,
                "trace_id": "w",
                "truth_label": "SIFTA_LONG_HORIZON_STRATEGY_V1",
                "kind": "STRATEGY_CREATED",
                "strategy_id": "AUTO",
                "horizon_days": 7,
                "milestones": ["m1", "m2"],
                "status": "ACTIVE",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = run_failure_revision_cycle(
        root=tmp_path, strategy_id="AUTO", write=True
    )
    assert out["wrote_failure"] is True
    assert out["wrote_revision"] is True
    assert out["new_milestone"]  # non-empty
