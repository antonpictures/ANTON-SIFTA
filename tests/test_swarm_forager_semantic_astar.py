#!/usr/bin/env python3
"""Tests: bounded Semantic A* recall (SIFTA r207)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_forager_semantic_astar as sa


def _rows():
    return [
        {"id": "a", "text": "yoga nighttime stretch routine", "wing": "browser", "ts": 1000.0},
        {"id": "b", "text": "ferrari engine torque review", "wing": "browser", "ts": 1000.0},
        {"id": "c", "text": "kitchen coffee monday morning", "wing": "browser", "ts": 1000.0},
    ]


def test_empty_returns_empty():
    assert sa.semantic_astar("anything", []) == []


def test_lexical_match_ranks_first():
    out = sa.semantic_astar("ferrari engine", _rows(), now=1000.0)
    assert out[0]["id"] == "b"
    assert out[0]["lexical"] > 0


def test_pheromone_lowers_cost_and_lifts_rank():
    rows = _rows()
    base = sa.semantic_astar("coffee", rows, now=1000.0)
    base_c = {d["id"]: d["cost"] for d in base}
    boosted = sa.semantic_astar(
        "coffee", rows,
        pheromone_rows=[{"id": "c", "strength": 1.0, "ts": 1000.0}],
        now=1000.0,
    )
    boosted_c = {d["id"]: d["cost"] for d in boosted}
    assert boosted_c["c"] < base_c["c"]          # pheromone made 'c' cheaper
    assert boosted[0]["id"] == "c"


def test_stale_pheromone_decays():
    rows = _rows()
    fresh = sa.semantic_astar("coffee", rows,
                              pheromone_rows=[{"id": "c", "strength": 1.0, "ts": 1000.0}],
                              now=1000.0)
    stale = sa.semantic_astar("coffee", rows,
                              pheromone_rows=[{"id": "c", "strength": 1.0, "ts": 1000.0}],
                              now=1000.0 + 60 * 86400)  # 60 days later
    fresh_c = {d["id"]: d["cost"] for d in fresh}["c"]
    stale_c = {d["id"]: d["cost"] for d in stale}["c"]
    assert stale_c > fresh_c   # decayed pheromone gives less boost → higher cost


def test_graph_neighbours_pulled_in_and_bounded():
    rows = [{"id": str(i), "text": f"node {i}", "ts": 1000.0} for i in range(20)]
    edges = [(str(i), str(i + 1)) for i in range(19)]
    out = sa.semantic_astar("node 5", rows, graph_edges=edges,
                            max_expansions=10, top_k=5, now=1000.0)
    assert len(out) <= 5
    # deterministic: same inputs → same order
    out2 = sa.semantic_astar("node 5", rows, graph_edges=edges,
                             max_expansions=10, top_k=5, now=1000.0)
    assert [d["id"] for d in out] == [d["id"] for d in out2]


def test_graph_distance_is_meaningful_for_related_silent_node():
    rows = [
        {"id": "anchor", "text": "alpha source", "ts": 1000.0},
        {"id": "related", "text": "quiet neighbour", "ts": 1000.0},
        {"id": "far", "text": "quiet isolated", "ts": 1000.0},
    ]
    out = sa.semantic_astar(
        "alpha",
        rows,
        graph_edges=[("anchor", "related")],
        top_k=3,
        now=1000.0,
    )
    ids = [d["id"] for d in out]
    assert ids.index("related") < ids.index("far")
    dist = {d["id"]: d["graph_dist"] for d in out}
    assert dist["related"] == 1
    assert dist["far"] == 6


def test_deterministic_tie_break_by_id():
    rows = [{"id": "z", "text": "same", "ts": 1.0}, {"id": "a", "text": "same", "ts": 1.0}]
    out = sa.semantic_astar("nomatch", rows, now=1.0)
    assert [d["id"] for d in out] == ["a", "z"]  # equal cost → id order


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
