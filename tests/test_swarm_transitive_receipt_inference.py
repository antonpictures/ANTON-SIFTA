from __future__ import annotations

import json

from System.swarm_transitive_receipt_inference import (
    TRUTH_LABEL,
    PreferenceEdge,
    edge_from_receipt,
    infer_transitive_preferences,
    rank_candidates,
    write_preference_graph_receipt,
)


def test_edge_from_common_receipt_shape():
    edge = edge_from_receipt(
        {
            "receipt_id": "r1",
            "winner": "copy_rank_offset_retry",
            "loser": "raw_clipboard",
            "context": "grok copy",
        }
    )

    assert edge is not None
    assert edge.winner == "copy_rank_offset_retry"
    assert edge.loser == "raw_clipboard"
    assert edge.receipt_id == "r1"


def test_transitive_inference_a_beats_c_from_a_b_and_b_c():
    prefs = infer_transitive_preferences(
        [
            PreferenceEdge("A", "B", receipt_id="r-ab"),
            PreferenceEdge("B", "C", receipt_id="r-bc"),
        ]
    )

    inferred = [p for p in prefs if p.winner == "A" and p.loser == "C"]
    assert inferred
    assert inferred[0].direct is False
    assert inferred[0].path == ["A", "B", "C"]
    assert inferred[0].evidence_receipts == ["r-ab", "r-bc"]


def test_rank_candidates_uses_inferred_wins_without_refighting():
    ranks = rank_candidates(
        [
            {"receipt_id": "r1", "winner": "bee81_send", "loser": "manual_paste"},
            {"receipt_id": "r2", "winner": "manual_paste", "loser": "stale_clipboard"},
        ],
        candidates=["bee81_send", "manual_paste", "stale_clipboard"],
    )

    assert ranks[0]["candidate"] == "bee81_send"
    assert ranks[0]["inferred_wins"] >= 1


def test_write_preference_graph_receipt_fans_out(tmp_path):
    row = write_preference_graph_receipt(
        [
            PreferenceEdge("A", "B", receipt_id="r-ab"),
            PreferenceEdge("B", "C", receipt_id="r-bc"),
        ],
        state_dir=tmp_path,
        source="test",
    )

    assert row["truth_label"] == TRUTH_LABEL
    assert row["preference_count"] >= 3
    sd = tmp_path / ".sifta_state"
    for name in ("receipt_preference_graph.jsonl", "work_receipts.jsonl"):
        rows = [json.loads(line) for line in (sd / name).read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["receipt_id"] == row["receipt_id"]
        assert rows[-1]["graph_sha256"] == row["graph_sha256"]
