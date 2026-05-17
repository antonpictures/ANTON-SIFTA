from __future__ import annotations

from System import alice_reality_boundary as boundary


NOW = 1_778_999_000.0


def test_receipt_row_labels_observed() -> None:
    out = boundary.label_knowledge({"receipt_id": "r1", "summary": "tool receipt"}, now=NOW)

    assert out["reality_boundary"]["label"] == "OBSERVED"
    assert out["reality_boundary"]["labeled_at"].endswith("Z")


def test_trace_row_labels_observed() -> None:
    out = boundary.label_knowledge({"trace_id": "t1", "intent": "registered"}, now=NOW)

    assert out["reality_boundary"]["label"] == "OBSERVED"


def test_swimmer_hash_row_labels_observed() -> None:
    out = boundary.label_knowledge({"hash": "abc", "parent_hash": None, "payload": {"kind": "x"}}, now=NOW)

    assert out["reality_boundary"]["label"] == "OBSERVED"


def test_explicit_architect_doctrine_label_wins() -> None:
    out = boundary.label_knowledge({"truth_label": "ARCHITECT_DOCTRINE", "text": "doctrine"}, now=NOW)

    assert out["reality_boundary"]["label"] == "ARCHITECT_DOCTRINE"


def test_architect_override_kind_labels_doctrine() -> None:
    out = boundary.label_knowledge({"kind": "ARCHITECT_OVERRIDE", "text": "owner doctrine"}, now=NOW)

    assert out["reality_boundary"]["label"] == "ARCHITECT_DOCTRINE"


def test_loose_george_mention_is_not_doctrine() -> None:
    out = boundary.label_knowledge({"text": "George may be tired tomorrow"}, now=NOW)

    assert out["reality_boundary"]["label"] == "UNVERIFIED"


def test_receipt_mentioning_george_stays_observed() -> None:
    out = boundary.label_knowledge({"receipt_id": "r1", "summary": "George taught Alice"}, now=NOW)

    assert out["reality_boundary"]["label"] == "OBSERVED"


def test_inferred_marker_labels_inferred() -> None:
    out = boundary.label_knowledge({"derived_from": ["r1"], "summary": "derived answer"}, now=NOW)

    assert out["reality_boundary"]["label"] == "INFERRED"


def test_prediction_marker_labels_imagined() -> None:
    out = boundary.label_knowledge({"source": "prediction", "note": "predicted next step"}, now=NOW)

    assert out["reality_boundary"]["label"] == "IMAGINED"


def test_unmarked_row_defaults_unverified() -> None:
    out = boundary.label_knowledge({"note": "plain memory"}, now=NOW)

    assert out["reality_boundary"]["label"] == "UNVERIFIED"


def test_non_dict_is_quarantined_as_unverified() -> None:
    out = boundary.label_knowledge("plain text", now=NOW)  # type: ignore[arg-type]

    assert out["raw"] == "plain text"
    assert out["reality_boundary"]["label"] == "UNVERIFIED"


def test_label_item_list_does_not_mutate_inputs() -> None:
    row = {"receipt_id": "r1"}
    labeled = boundary.label_item_list([row], now=NOW)

    assert "reality_boundary" not in row
    assert labeled[0]["reality_boundary"]["label"] == "OBSERVED"


def test_counts_include_all_labels() -> None:
    labeled = boundary.label_item_list(
        [
            {"receipt_id": "r1"},
            {"truth_label": "ARCHITECT_DOCTRINE"},
            {"derived_from": ["r1"]},
            {"source": "prediction"},
            {"note": "unknown"},
        ],
        now=NOW,
    )

    counts = boundary.get_reality_boundary_counts(labeled)
    assert counts == {
        "ARCHITECT_DOCTRINE": 1,
        "IMAGINED": 1,
        "INFERRED": 1,
        "OBSERVED": 1,
        "UNVERIFIED": 1,
    }


def test_integrity_counts_labeled_non_unverified_items() -> None:
    labeled = boundary.label_item_list(
        [{"receipt_id": "r1"}, {"derived_from": ["r1"]}, {"note": "unknown"}],
        now=NOW,
    )

    assert boundary.get_reality_boundary_integrity(labeled) == 0.667


def test_integrity_empty_is_zero() -> None:
    assert boundary.get_reality_boundary_integrity([]) == 0.0


def test_summary_returns_counts_and_integrity_without_items_loss() -> None:
    summary = boundary.summarize_reality_boundary(
        [{"receipt_id": "r1"}, {"note": "unknown"}],
        now=NOW,
    )

    assert summary["truth_label"] == boundary.TRUTH_LABEL
    assert summary["total"] == 2
    assert summary["counts"]["OBSERVED"] == 1
    assert summary["counts"]["UNVERIFIED"] == 1
    assert summary["integrity"] == 0.5
    assert len(summary["items"]) == 2
