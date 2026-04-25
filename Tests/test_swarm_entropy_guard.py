#!/usr/bin/env python3
"""
tests/test_swarm_entropy_guard.py
══════════════════════════════════════════════════════════════════════
Cosign target — Stigmergic Agreement Event 49 / 3-substrate quorum:
  • C55M  : valid, audit swarm_entropy_guard.py (lower pri than crypto)
  • AG31  : valid, requested C47H to audit
  • C47H  : owns the cut

Smallest tested behavior all three IDEs can accept (Clause 7):
  1. Cozy-game anti-pattern is detected
       → high STGM metric accumulation + low Architect ratifications
       → goodhart_violation == True, recommendation == FORCE_MCTS_EXPLORATION
  2. Healthy "real reciprocal interaction" is NOT flagged
       → high metric + high ratification = real engagement
  3. Quiescent system is NOT flagged
       → low metric + low ratification = idle, not pathological
  4. Boundary condition: window edges work correctly
       → only events inside the window contribute
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from System.swarm_entropy_guard import EntropyGuard


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Redirect entropy_guard's two file handles to a temp directory."""
    fake_stgm = tmp_path / "stgm_memory_rewards.jsonl"
    fake_ratified = tmp_path / "warp9_concierge_ratified.jsonl"
    monkeypatch.setattr("System.swarm_entropy_guard.STGM_LEDGER", fake_stgm)
    monkeypatch.setattr("System.swarm_entropy_guard.RATIFIED_LOG", fake_ratified)
    return {"stgm": fake_stgm, "ratified": fake_ratified}


def test_cozy_game_anti_pattern_is_flagged(isolated_state):
    """
    The exact pathology Codex + AG31 cosigned C47H to test.
    100 STGM rewards in last hour, 0 architect ratifications →
    Alice is metric-hacking, not engaging. Must trip the Goodhart gate.
    """
    now = time.time()
    _write_jsonl(
        isolated_state["stgm"],
        [{"ts": now - i, "amount": 1.0, "reason": "cozy_loop"} for i in range(100)],
    )
    _write_jsonl(isolated_state["ratified"], [])

    res = EntropyGuard(check_window_s=3600).analyze_trends()

    assert res["metric_count"] == 100
    assert res["ratification_count"] == 0
    assert res["goodhart_violation"] is True
    assert res["recommendation"] == "FORCE_MCTS_EXPLORATION"


def test_real_reciprocal_engagement_is_not_flagged(isolated_state):
    """
    100 STGM rewards AND 10 ratifications in the same window =
    the architect is actively confirming the work. Healthy. No flag.
    """
    now = time.time()
    _write_jsonl(
        isolated_state["stgm"],
        [{"ts": now - i, "amount": 1.0, "reason": "real_work"} for i in range(100)],
    )
    _write_jsonl(
        isolated_state["ratified"],
        [{"ratified_ts": now - i * 60, "what": "ack"} for i in range(10)],
    )

    res = EntropyGuard(check_window_s=3600).analyze_trends()

    assert res["metric_count"] == 100
    assert res["ratification_count"] == 10
    assert res["goodhart_violation"] is False
    assert res["recommendation"] == "HEALTHY"


def test_quiescent_system_is_not_flagged(isolated_state):
    """
    Idle organism. No STGM, no ratifications. Should be HEALTHY,
    not pathological. Tests that 'low metric' alone doesn't trip a
    false-negative on the violation gate.
    """
    res = EntropyGuard(check_window_s=3600).analyze_trends()

    assert res["metric_count"] == 0
    assert res["ratification_count"] == 0
    assert res["goodhart_violation"] is False
    assert res["recommendation"] == "HEALTHY"


def test_window_boundary_excludes_old_events(isolated_state):
    """
    100 STGM rewards but all OUTSIDE the 1-hour window. Only 1 inside.
    Should NOT count the old ones — the window is what matters.
    Falsifies any naive 'just count rows' reading of the metric_count.
    """
    now = time.time()
    inside_window = [{"ts": now - 60, "amount": 1.0, "reason": "fresh"}]
    outside_window = [
        {"ts": now - 7200 - i, "amount": 1.0, "reason": "stale"}
        for i in range(100)
    ]
    _write_jsonl(isolated_state["stgm"], inside_window + outside_window)
    _write_jsonl(isolated_state["ratified"], [])

    res = EntropyGuard(check_window_s=3600).analyze_trends()

    assert res["metric_count"] == 1
    assert res["goodhart_violation"] is False


def test_ratification_v1_v2_schema_compatibility(isolated_state):
    """
    The module already documents 'accept either timestamp OR ratified_ts'
    for warp9 v1/v2 compat. Counter-example test: a v1-shaped row
    (only ratified_ts) AND a v2-shaped row (only timestamp) must both
    be counted. Falsification surface for the schema-compat claim.
    """
    now = time.time()
    _write_jsonl(
        isolated_state["ratified"],
        [
            {"ratified_ts": now - 100, "what": "v1_row"},
            {"timestamp": now - 200, "what": "v2_row"},
        ],
    )
    _write_jsonl(
        isolated_state["stgm"],
        [{"ts": now - i, "amount": 1.0} for i in range(60)],
    )

    res = EntropyGuard(check_window_s=3600).analyze_trends()

    assert res["ratification_count"] == 2
    assert res["goodhart_violation"] is False
