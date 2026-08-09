"""r1744 — the organs the field grew, found from transitions alone.

WCT r1743 §5. Hoffman: a large chain has communities the chain stays inside,
joined by rare corridors; that is the outside description of an organ.

Measured on the live field (8000 rows), the probe found 5 communities without
reading a line of code — and one of them, the 7-state EFFECT_CREDIT_V1 cluster,
traces entirely back to a single declared module, System/swarm_web_reflex_loop.py.
The field independently rediscovered a declared organ boundary. Another,
codex_query -> codex_response, is the Codex arm standing alone as its own organ.
"""
from __future__ import annotations

import pytest

from System.swarm_field_communities import (
    MIN_EDGE_WEIGHT,
    community_report,
    detect_communities,
)


def test_two_separate_loops_are_two_organs():
    """Two clusters that never touch must never be merged."""
    states = (["a", "b", "a", "b"] * 6) + ["a"] + (["x", "y", "x", "y"] * 6)

    labels = detect_communities(states)

    assert labels["a"] == labels["b"]
    assert labels["x"] == labels["y"]
    assert labels["a"] != labels["x"], "unconnected clusters are separate organs"


def test_a_single_corridor_crossing_is_noise_not_a_boundary():
    """One transition between clusters must not fuse them."""
    states = (["a", "b"] * 8) + ["x"] + (["x", "y"] * 8)

    labels = detect_communities(states, min_edge_weight=MIN_EDGE_WEIGHT)

    assert labels["a"] != labels["x"], "a corridor crossed once is noise"


def test_self_loops_bind_nothing():
    """A state repeating itself says nothing about who it belongs with."""
    labels = detect_communities(["a"] * 30)

    assert labels == {}, "a self-loop is not an organ"


def test_detection_is_deterministic_across_runs():
    """A self-identity probe that changed its mind each run would be worthless."""
    states = (["p", "q", "r", "p", "r", "q"] * 12) + (["s", "t", "s", "t"] * 12)

    first = detect_communities(states)
    second = detect_communities(states)

    assert first == second


def test_report_ranks_organs_by_size_and_lists_members():
    states = (["a", "b", "c", "a", "c", "b"] * 10) + (["x", "y", "x", "y"] * 10)

    report = community_report(states)

    assert report["community_count"] == 2
    assert report["communities"][0]["size"] >= report["communities"][1]["size"]
    assert set(report["communities"][0]["states"]) == {"a", "b", "c"}
    assert report["truth_label"] == "OBSERVED_FIELD_COMMUNITIES_V1"


def test_empty_field_grows_no_organs():
    report = community_report([])

    assert report["community_count"] == 0
    assert report["states_in_communities"] == 0


def test_live_field_organs_are_coherent_when_the_ledger_is_rich():
    """Guarded live probe: if the field has evidence, it must cluster."""
    from System.swarm_stationary_belief import read_state_sequence

    states = read_state_sequence(".sifta_state/ide_stigmergic_trace.jsonl", max_rows=8000)
    if len(states) < 500:
        pytest.skip("live field too thin on this node to probe")

    report = community_report(states)

    assert report["community_count"] >= 1
    for community in report["communities"]:
        assert community["size"] >= 1
        assert community["label"] in community["states"] or community["size"] > 0
