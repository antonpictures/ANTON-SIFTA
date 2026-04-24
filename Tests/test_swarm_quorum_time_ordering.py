#!/usr/bin/env python3
"""
tests/test_swarm_quorum_time_ordering.py
══════════════════════════════════════════════════════════════════════
Tests for SIFTA consensus causal sequence ordering (Nugget N1/N2).
Proves that the swarm trusts monotonic logical sequence over naive
POSIX wall-clock simultaneity.
"""
from System.swarm_time_consensus import resolve_causal_sequence

def test_causal_sequence_overrides_wall_clock():
    """
    If an event has a higher causal sequence number, it is considered
    'later' than an event with a lower sequence number, even if its
    wall-clock timestamp is earlier (simulating clock skew across federation).
    """
    events = [
        {"msg": "later_wall_clock_but_first_seq", "seq": 1, "ts": 100.5},
        {"msg": "earlier_wall_clock_but_second_seq", "seq": 2, "ts": 98.0},
    ]
    
    resolved = resolve_causal_sequence(events)
    
    # Must sort by seq strictly.
    assert len(resolved) == 2
    assert resolved[0]["msg"] == "later_wall_clock_but_first_seq"
    assert resolved[1]["msg"] == "earlier_wall_clock_but_second_seq"

def test_duplicate_sequence_is_rejected():
    """
    If an event arrives with a duplicate sequence number (e.g. replay attack
    or identical causal tick), the consensus keeps the first one seen (lowest ts)
    and drops the duplicate.
    """
    events = [
        {"msg": "first_seen", "seq": 5, "ts": 100.0},
        {"msg": "replayed_or_duplicate", "seq": 5, "ts": 101.0},
    ]
    
    resolved = resolve_causal_sequence(events)
    
    # Should collapse to 1 event.
    assert len(resolved) == 1
    assert resolved[0]["msg"] == "first_seen"


def test_duplicate_sequence_tie_breaks_by_input_order():
    """
    If seq and ts are identical, input order is the final deterministic
    tie-breaker. This keeps the helper pure while making the policy explicit.
    """
    events = [
        {"msg": "first_input", "seq": 5, "ts": 100.0},
        {"msg": "second_input", "seq": 5, "ts": 100.0},
    ]

    resolved = resolve_causal_sequence(events)

    assert len(resolved) == 1
    assert resolved[0]["msg"] == "first_input"

def test_mixed_seq_and_unsequenced_events():
    """
    Events without a sequence number should sort by their wall-clock ts
    and be placed after sequenced events (or gracefully handled).
    """
    events = [
        {"msg": "unsequenced_later", "ts": 200.0},
        {"msg": "seq_event", "seq": 1, "ts": 500.0},
        {"msg": "unsequenced_earlier", "ts": 150.0},
    ]
    
    resolved = resolve_causal_sequence(events)
    
    assert len(resolved) == 3
    # Sequenced events come first (sorted by seq)
    assert resolved[0]["msg"] == "seq_event"
    # Unsequenced events come after (sorted by ts)
    assert resolved[1]["msg"] == "unsequenced_earlier"
    assert resolved[2]["msg"] == "unsequenced_later"
