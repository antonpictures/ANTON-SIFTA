#!/usr/bin/env python3
"""Tests for System/swarm_time_consensus_guard.py — submission + ordering gate."""

import json
from pathlib import Path

import pytest

from System.swarm_time_consensus_guard import enforce_time_consensus


def test_invariant_guard_pass():
    events = [
        {"logical_seq": 2, "ts": 100},
        {"logical_seq": 1, "ts": 999},
    ]

    result = enforce_time_consensus(events, write_ledger=False)

    assert result.invariant_passed
    assert result.ordered_events[0]["logical_seq"] == 1
    assert result.ordered_events[1]["logical_seq"] == 2


def test_duplicate_seq_detected():
    events = [
        {"logical_seq": 1, "ts": 100},
        {"logical_seq": 1, "ts": 101},
    ]

    result = enforce_time_consensus(events, write_ledger=False)

    assert not result.invariant_passed
    assert "duplicate_seq@1" in result.violations
    # Resolver still produces a single canonical row for replay consumers.
    assert len(result.ordered_events) == 1


def test_unsequenced_interleaved():
    events = [
        {"logical_seq": 1, "ts": 100},
        {"ts": 50},
        {"logical_seq": 2, "ts": 10},
    ]

    result = enforce_time_consensus(events, write_ledger=False)

    assert not result.invariant_passed
    assert any("unsequenced_interleaved" in v for v in result.violations)


def test_deterministic_fingerprint():
    events = [
        {"logical_seq": 2, "ts": 100},
        {"logical_seq": 1, "ts": 100},
    ]

    r1 = enforce_time_consensus(events, write_ledger=False)
    r2 = enforce_time_consensus(events, write_ledger=False)

    assert r1.ordering_hash == r2.ordering_hash


def test_seq_dominates_timestamp():
    events = [
        {"logical_seq": 10, "ts": 1},
        {"logical_seq": 1, "ts": 999999},
    ]

    result = enforce_time_consensus(events, write_ledger=False)

    assert result.invariant_passed
    assert result.ordered_events[0]["logical_seq"] == 1


def test_ledger_row_matches_canonical_schema(tmp_path: Path):
    ledger = tmp_path / "time_consensus_enforced.jsonl"
    events = [{"seq": 1, "ts": 1.0}]
    enforce_time_consensus(events, write_ledger=True, ledger_path=ledger)

    line = ledger.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(line)
    from System.canonical_schemas import LEDGER_SCHEMAS

    assert set(row.keys()) == LEDGER_SCHEMAS["time_consensus_enforced.jsonl"]
    assert row["event"] == "time_consensus_enforced"
    assert row["invariant_passed"] is True
    assert row["violations"] == []
    assert row["event_count"] == 1


def test_conflicting_seq_and_logical_seq():
    events = [
        {"seq": 1, "logical_seq": 2, "ts": 0.0},
    ]
    r = enforce_time_consensus(events, write_ledger=False)
    assert not r.invariant_passed
    assert any("conflicting_seq_logical_seq" in v for v in r.violations)
