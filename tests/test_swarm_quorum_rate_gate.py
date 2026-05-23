#!/usr/bin/env python3
"""tests/test_swarm_quorum_rate_gate.py — AO46 Event 51"""
import pytest
from System.swarm_quorum_rate_gate import (
    rate_gate_filter,
    quorum_threshold,
    is_quorum_active,
    RATE_GATE_MEMORY_S,
    RATE_GATE_INTERVAL_S,
    TOPOLOGICAL_K,
)

NOW = 1_000_000.0


def test_stale_votes_are_dropped():
    votes = [
        {"ts": NOW - 10},
        {"ts": NOW - 50},  # > 45s memory window — must be dropped
        {"ts": NOW - 200},
    ]
    result = rate_gate_filter(votes, now=NOW)
    assert len(result) == 1


def test_burst_votes_in_same_window_collapse_to_one():
    # Anonymous votes cannot prove distinct voter identity, so burst evidence
    # collapses to one.
    votes = [{"ts": NOW - 1}, {"ts": NOW - 2}, {"ts": NOW - 3}]
    result = rate_gate_filter(votes, now=NOW)
    assert len(result) == 1


def test_epoch_bucket_boundary_does_not_leak_burst_votes():
    votes = [
        {"ts": 999.9},
        {"ts": 1000.1},
    ]
    result = rate_gate_filter(votes, now=1005.0)
    assert len(result) == 1


def test_distinct_voters_in_same_window_all_count():
    votes = [
        {"ts": NOW - 1, "voter_id": "A"},
        {"ts": NOW - 2, "voter_id": "B"},
        {"ts": NOW - 3, "voter_id": "C"},
    ]
    result = rate_gate_filter(votes, now=NOW)
    assert {v["voter_id"] for v in result} == {"A", "B", "C"}


def test_same_voter_cannot_slow_spam_memory_window():
    votes = [
        {"ts": NOW - 5, "voter_id": "A"},
        {"ts": NOW - 16, "voter_id": "A"},
        {"ts": NOW - 27, "voter_id": "A"},
        {"ts": NOW - 38, "voter_id": "A"},
    ]
    result = rate_gate_filter(votes, now=NOW)
    assert len(result) == 1
    assert result[0]["ts"] == NOW - 5


def test_votes_across_multiple_windows_all_pass():
    votes = [
        {"ts": NOW - 5},
        {"ts": NOW - 15},
        {"ts": NOW - 25},
        {"ts": NOW - 35},
    ]
    result = rate_gate_filter(votes, now=NOW)
    assert len(result) == 4


def test_quorum_threshold_sublinear_scaling():
    assert quorum_threshold(1) == 1
    assert quorum_threshold(4) == 2
    assert quorum_threshold(9) == 3
    assert quorum_threshold(16) == 4
    assert quorum_threshold(100) == 10


def test_quorum_threshold_zero_swarm():
    assert quorum_threshold(0) == 1


def test_is_quorum_active_passes():
    # 3 active votes, swarm=9 → threshold=3 → exactly passes
    votes = [
        {"ts": NOW - 5, "voter_id": "A"},
        {"ts": NOW - 6, "voter_id": "B"},
        {"ts": NOW - 7, "voter_id": "C"},
    ]
    assert is_quorum_active(votes, swarm_size=9, now=NOW) is True


def test_is_quorum_active_fails_when_stale():
    # Only 1 active vote after filtering, threshold=3 for swarm=9
    votes = [
        {"ts": NOW - 3},
        {"ts": NOW - 60},   # stale
        {"ts": NOW - 90},   # stale
    ]
    assert is_quorum_active(votes, swarm_size=9, now=NOW) is False


def test_topological_k_constant():
    """The starling neighbor constant (Cavagna 2008) must be exactly 7."""
    assert TOPOLOGICAL_K == 7


def test_single_bad_actor_cannot_redirect_large_swarm():
    """One voter must not activate a large swarm quorum by repeated voting."""
    one_rogue_vote = [
        {"ts": NOW - 1, "voter_id": "ROGUE"},
        {"ts": NOW - 12, "voter_id": "ROGUE"},
        {"ts": NOW - 23, "voter_id": "ROGUE"},
        {"ts": NOW - 34, "voter_id": "ROGUE"},
    ]
    # For swarm_size=100, threshold=10 — one vote is never enough
    assert is_quorum_active(one_rogue_vote, swarm_size=100, now=NOW) is False


def test_large_swarm_can_reach_quorum_with_distinct_voters():
    votes = [{"ts": NOW - 1, "voter_id": f"V{i}"} for i in range(10)]
    assert is_quorum_active(votes, swarm_size=100, now=NOW) is True
