#!/usr/bin/env python3
"""Tests for System/swarm_causal_vector_clock.py — strict causal readiness."""

from System.swarm_causal_vector_clock import SwarmVectorClock


def test_valid_first_message_delivers():
    m5 = SwarmVectorClock("M5")
    m1 = SwarmVectorClock("M1")
    vc1 = m5.increment()
    assert m1.is_causally_ready("M5", vc1)
    m1.merge(vc1)
    assert m1.clock.get("M5") == 1


def test_out_of_order_sender_sequence_rejected():
    m5 = SwarmVectorClock("M5")
    m1 = SwarmVectorClock("M1")
    m1.merge(m5.increment())
    m5.increment()  # M5 now at 2 — not delivered to M1
    vc3 = m5.increment()  # M5 at 3, arrives "early"
    assert not m1.is_causally_ready("M5", vc3)
    ok, reason = m1.check_readiness("M5", vc3)
    assert ok is False
    assert reason is not None
    assert "seq_jump" in reason


def test_replay_rejected():
    m5 = SwarmVectorClock("M5")
    m1 = SwarmVectorClock("M1")
    vc1 = m5.increment()
    assert m1.is_causally_ready("M5", vc1)
    m1.merge(vc1)
    assert not m1.is_causally_ready("M5", vc1)


def test_missing_peer_dependency_rejected():
    m1 = SwarmVectorClock("M1")
    # Sender claims to have seen M2 at 5 but M1 has never seen M2
    incoming = {"M5": 1, "M2": 5}
    ok, reason = m1.check_readiness("M5", incoming)
    assert ok is False
    assert reason is not None
    assert "missing_dep" in reason
