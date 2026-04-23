"""tests/test_swarm_somatosensory_homunculus.py
══════════════════════════════════════════════════════════════════════
Verification tests for the Repo Proprioception cortex (BISHOP Event 29).

Covers:
  1. BISHOP's three-phase synthetic proof (clean / controlled / orphaned)
  2. Structured STIGTIME parser — canonical marker shapes
  3. Per-agent dedup — same agent ping-ponging counts once at most-recent
  4. Recency window — old markers are filtered out
  5. Real-substrate smoke — read_homeostasis() runs without crashing
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System.swarm_somatosensory_homunculus import (
    DEFAULT_STIGTIME_WINDOW_SEC,
    HomeostasisReading,
    StigtimeMarker,
    SwarmSomatosensoryHomunculus,
    parse_stigtime_marker,
    proof_of_property,
    read_homeostasis,
    read_real_git_dirty_count,
    read_real_stigtime_log,
)


# ─────────────────────────────────────────────────────────────────
# 1. BISHOP's three-phase synthetic proof
# ─────────────────────────────────────────────────────────────────

def test_bishop_proof_runs():
    """The original Event 29 proof must still pass after the seal."""
    assert proof_of_property() is True


def test_clean_repo_zero_free_energy():
    cortex = SwarmSomatosensoryHomunculus()
    F, blocked = cortex.calculate_free_energy(
        git_dirty_count=0,
        stigtime_log=[
            "STIGTIME: standby @ 2026-04-22T10:00:00Z by C47H",
            "STIGTIME: standby @ 2026-04-22T10:01:00Z by AG31",
        ],
    )
    assert F == 0.0
    assert blocked == 0


def test_controlled_metabolism_linear_in_dirty():
    """Dirty repo + active agent → linear cost, not exponential."""
    cortex = SwarmSomatosensoryHomunculus()
    F, _ = cortex.calculate_free_energy(
        git_dirty_count=5,
        stigtime_log=[
            "STIGTIME: active(phase-8) @ 2026-04-22T10:06:00Z by AG31",
        ],
    )
    assert F == 5.0


def test_orphaned_mutation_quadratic_spike():
    """Dirty repo + no active agent → exponential surprise (BISHOP's formula)."""
    cortex = SwarmSomatosensoryHomunculus()
    F_orphan, _ = cortex.calculate_free_energy(
        git_dirty_count=5,
        stigtime_log=[
            "STIGTIME: standby @ 2026-04-22T10:10:00Z by C47H",
            "STIGTIME: standby @ 2026-04-22T10:11:00Z by AG31",
        ],
    )
    F_active, _ = cortex.calculate_free_energy(
        git_dirty_count=5,
        stigtime_log=[
            "STIGTIME: active(phase-8) @ 2026-04-22T10:06:00Z by AG31",
        ],
    )
    assert F_orphan == 25.0
    assert F_active == 5.0
    assert F_orphan > F_active


def test_blocked_agent_adds_five_per():
    cortex = SwarmSomatosensoryHomunculus()
    F, blocked = cortex.calculate_free_energy(
        git_dirty_count=0,
        stigtime_log=[
            "STIGTIME: blocked(needs-operator-auth) @ 2026-04-22T10:10:00Z by AG31",
        ],
    )
    assert blocked == 1
    assert F == 5.0


# ─────────────────────────────────────────────────────────────────
# 2. Structured STIGTIME parser
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected_state,expected_context,expected_agent", [
    ("STIGTIME: standby @ 2026-04-22T10:00:00Z by c47h_ide_llm",
     "standby", None, "c47h_ide_llm"),
    ("STIGTIME: active(emergency-re-anchor) @ 2026-04-22T23:41:39Z by c47h_ide_llm",
     "active", "emergency-re-anchor", "c47h_ide_llm"),
    ("STIGTIME: blocked(needs-operator-auth-on-public-repo-create) @ 2026-04-22T22:00:00Z by ag31",
     "blocked", "needs-operator-auth-on-public-repo-create", "ag31"),
    ("STIGTIME: verify-only(post-phase-7.5) @ 2026-04-22T23:28:55Z by c47h_ide_llm",
     "verify-only", "post-phase-7.5", "c47h_ide_llm"),
    # No STIGTIME prefix — bare marker (the format used inside the JSON 'stigtime' field)
    ("active(emergency-re-anchor) @ 2026-04-22T23:41:39Z by c47h_ide_llm",
     "active", "emergency-re-anchor", "c47h_ide_llm"),
])
def test_parser_canonical_shapes(text, expected_state, expected_context, expected_agent):
    m = parse_stigtime_marker(text)
    assert m is not None, f"parser returned None on {text!r}"
    assert m.state == expected_state
    assert m.context == expected_context
    assert m.agent == expected_agent


def test_parser_rejects_garbage():
    assert parse_stigtime_marker("") is None
    assert parse_stigtime_marker("hello world") is None
    assert parse_stigtime_marker("blocked but not really") is None
    assert parse_stigtime_marker(None) is None  # type: ignore[arg-type]


def test_parser_does_not_false_positive_on_unblocked():
    """BISHOP's substring parser would count 'unblocked' as blocked. The
    structured parser must not."""
    # 'unblocked' contains 'blocked' as substring but is not a valid state.
    assert parse_stigtime_marker("unblocked @ 2026-04-22T10:00:00Z by c47h") is None


# ─────────────────────────────────────────────────────────────────
# 3. Per-agent dedup
# ─────────────────────────────────────────────────────────────────

def test_per_agent_dedup_keeps_most_recent():
    """If AG31 ping-pongs standby→active→standby, only the most recent
    state counts. BISHOP's substring parser would have counted active+standby
    both, double-counting the agent."""
    cortex = SwarmSomatosensoryHomunculus()
    log = [
        "STIGTIME: standby @ 2026-04-22T10:00:00Z by AG31",
        "STIGTIME: active(phase-8) @ 2026-04-22T10:05:00Z by AG31",
        "STIGTIME: standby @ 2026-04-22T10:10:00Z by AG31",  # most recent
    ]
    blocked, active = cortex._parse_stigtime_autoinducers(log)
    assert blocked == 0
    assert active == 0  # most-recent is standby, not active


def test_per_agent_dedup_preserves_distinct_agents():
    cortex = SwarmSomatosensoryHomunculus()
    log = [
        "STIGTIME: active(phase-8) @ 2026-04-22T10:05:00Z by AG31",
        "STIGTIME: blocked(needs-auth) @ 2026-04-22T10:06:00Z by codex",
    ]
    blocked, active = cortex._parse_stigtime_autoinducers(log)
    assert blocked == 1
    assert active == 1


# ─────────────────────────────────────────────────────────────────
# 4. Recency window
# ─────────────────────────────────────────────────────────────────

def test_recency_window_filters_stale_markers(tmp_path: Path):
    """Markers older than window_sec must be dropped — they're settled
    epigenetic state, not active autoinducers.

    Time-stamps are computed relative to `now` so the test never goes
    flaky against wall-clock drift."""
    from datetime import datetime, timezone
    now = time.time()
    fresh_epoch = now - 60          # 1 min ago — well inside the window
    stale_epoch = now - 365 * 24 * 3600  # 1 year ago — well outside

    def _iso(epoch: float) -> str:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )

    fresh_iso = _iso(fresh_epoch)
    stale_iso = _iso(stale_epoch)

    receipts = tmp_path / "work_receipts.jsonl"
    rows = [
        {"ts": fresh_epoch, "stigtime": f"active(phase-8) @ {fresh_iso} by ag31"},
        {"ts": stale_epoch, "stigtime": f"active(ancient-history) @ {stale_iso} by codex"},
    ]
    with receipts.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    markers = read_real_stigtime_log(
        window_sec=DEFAULT_STIGTIME_WINDOW_SEC,
        receipts_path=receipts,
        now=now,
    )
    agents = {m.agent for m in markers}
    assert "ag31" in agents, f"fresh marker dropped: agents={agents}"
    assert "codex" not in agents, f"stale marker leaked: agents={agents}"


def test_recency_window_handles_missing_receipts_file(tmp_path: Path):
    markers = read_real_stigtime_log(
        receipts_path=tmp_path / "does-not-exist.jsonl",
    )
    assert markers == []


# ─────────────────────────────────────────────────────────────────
# 5. Real-substrate smoke
# ─────────────────────────────────────────────────────────────────

def test_real_substrate_read_does_not_crash():
    """End-to-end: read_homeostasis() runs on the live repo without
    raising, returns a typed snapshot, and produces a sane directive."""
    reading = read_homeostasis(persist=False)
    assert isinstance(reading, HomeostasisReading)
    assert reading.git_dirty_count >= 0
    assert reading.free_energy >= 0.0
    assert reading.active_agents >= 0
    assert reading.blocked_agents >= 0
    assert isinstance(reading.directive, str) and len(reading.directive) > 0


def test_git_reader_degrades_gracefully(tmp_path: Path):
    """On a non-git directory, the reader returns 0 instead of crashing."""
    n = read_real_git_dirty_count(repo=tmp_path)
    assert n == 0


def test_dict_log_entries_supported():
    """Accept work_receipts rows directly — operators should be able to
    feed `[json.loads(line) for line in receipts]` straight in."""
    cortex = SwarmSomatosensoryHomunculus()
    rows = [
        {"ts": 1.0, "stigtime": "active(phase-8) @ 2026-04-22T10:05:00Z by AG31"},
        {"ts": 2.0, "stigtime": "standby @ 2026-04-22T10:00:00Z by c47h_ide_llm"},
    ]
    blocked, active = cortex._parse_stigtime_autoinducers(rows)
    assert blocked == 0
    assert active == 1
