"""r1622-02 — offline memory recall ranking."""
from __future__ import annotations

from System.swarm_sie_memory_recall import jaccard, recall, score_candidates


def test_jaccard_ranks_related_higher():
    assert jaccard("alice self code body", "self code for alice body") > jaccard(
        "alice self code body", "weather in paris tomorrow"
    )


def test_score_candidates_orders(tmp_path):
    cands = [
        {"source": "a", "text": "unrelated weather report"},
        {"source": "b", "text": "we code together self code R1621 browser mouth"},
    ]
    out = score_candidates("self code browser mouth", cands, prefer_sie=False)
    assert out["ranked"][0]["source"] == "b"
    assert out["method"]


def test_recall_on_empty_state(tmp_path):
    out = recall("remember R1621", state_dir=tmp_path, top_k=3)
    assert "ranked" in out
