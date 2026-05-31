#!/usr/bin/env python3
"""Tests: MemoryForager guarded Semantic A* pre-rank integration (SIFTA r208)."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System.stigmergic_memory_bus import _astar_prerank_candidates
from System.swarm_forager_hierarchy import deposit_hierarchical_trace


class Trace:
    def __init__(self, trace_id: str, raw_text: str, *, recall_count: int = 0):
        self.trace_id = trace_id
        self.raw_text = raw_text
        self.timestamp = time.time()
        self.recall_count = recall_count

    def retention(self) -> float:
        return 1.0


def _ids(candidates):
    return [trace.trace_id for _confidence, trace in candidates]


def test_no_overlay_preserves_flat_order(tmp_path):
    candidates = [
        (0.5, Trace("a", "plain unrelated memory")),
        (0.5, Trace("b", "coffee memory")),
    ]

    out = _astar_prerank_candidates("coffee", candidates, tmp_path)

    assert _ids(out) == ["a", "b"]


def test_unmatched_overlay_preserves_flat_order(tmp_path):
    candidates = [
        (0.5, Trace("a", "plain unrelated memory")),
        (0.5, Trace("b", "coffee memory")),
    ]
    deposit_hierarchical_trace({"text": "other trace"}, ref="not-a-candidate", state_dir=tmp_path)

    out = _astar_prerank_candidates("coffee", candidates, tmp_path)

    assert _ids(out) == ["a", "b"]


def test_matched_overlay_enables_astar_rerank_without_changing_confidence(tmp_path):
    a = Trace("a", "plain unrelated memory")
    b = Trace("b", "coffee memory")
    candidates = [(0.5, a), (0.5, b)]
    deposit_hierarchical_trace({"text": a.raw_text, "source": "test"}, ref="a", state_dir=tmp_path)
    deposit_hierarchical_trace({"text": b.raw_text, "source": "test"}, ref="b", state_dir=tmp_path)

    out = _astar_prerank_candidates("coffee", candidates, tmp_path)

    assert _ids(out) == ["b", "a"]
    assert sorted(conf for conf, _trace in out) == [0.5, 0.5]


def test_recall_count_becomes_pheromone_when_overlay_matches(tmp_path):
    a = Trace("a", "coffee memory", recall_count=0)
    b = Trace("b", "coffee memory", recall_count=3)
    candidates = [(0.5, a), (0.5, b)]
    deposit_hierarchical_trace({"text": a.raw_text, "source": "test"}, ref="a", state_dir=tmp_path)
    deposit_hierarchical_trace({"text": b.raw_text, "source": "test"}, ref="b", state_dir=tmp_path)

    out = _astar_prerank_candidates("coffee", candidates, tmp_path)

    assert _ids(out)[0] == "b"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
