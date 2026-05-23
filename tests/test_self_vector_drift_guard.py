#!/usr/bin/env python3
"""Tests for swarm_self_vector_drift_guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_self_vector_drift_guard as drift


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])


def test_cosine_similarity_validates_vectors():
    assert drift.cosine_similarity([1, 0], [1, 0]) == 1.0
    assert round(drift.cosine_similarity([1, 0], [0, 1]), 6) == 0.0
    with pytest.raises(ValueError, match="same dimension"):
        drift.cosine_similarity([1, 2], [1])
    with pytest.raises(ValueError, match="non-zero"):
        drift.cosine_similarity([0, 0], [1, 0])


def test_stable_vector_stays_stable():
    decision = drift.evaluate_self_vector_drift([1, 0, 0], [0.99, 0.01, 0.0])
    assert decision.truth_label == "SELF_VECTOR_DRIFT_GUARD_HYPOTHESIS_V1"
    assert decision.claim_status == "HYPOTHESIS_LOCAL_MECHANIC"
    assert decision.action == "STABLE"
    assert decision.threshold_band == "stable"


def test_review_and_lockdown_thresholds():
    review = drift.evaluate_self_vector_drift([1, 0], [0.75, 0.66])
    assert review.action == "META_REVIEW"
    assert "identity_shape_mismatch" in review.reasons

    lockdown = drift.evaluate_self_vector_drift([1, 0], [0, 1])
    assert lockdown.action == "LOCKDOWN_REVIEW"
    assert lockdown.threshold_band == "lockdown"


def test_missing_anchor_is_explicit_not_crash():
    decision = drift.evaluate_self_vector_drift(None, [1, 2, 3])
    assert decision.action == "NO_ANCHOR"
    assert decision.drift_score == 1.0
    assert "missing_anchor_or_current_vector" in decision.reasons


def test_guard_does_not_touch_real_ledgers():
    watch = [
        Path(".sifta_state/work_receipts.jsonl"),
        Path(".sifta_state/stgm_memory_rewards.jsonl"),
        Path(".sifta_state/memory_ledger.jsonl"),
        Path(".sifta_state/unified_stigmergic_field.jsonl"),
    ]
    before = {str(path): _count_lines(path) for path in watch}
    _ = drift.evaluate_self_vector_drift([1, 0, 0], [0.5, 0.5, 0.0])
    after = {str(path): _count_lines(path) for path in watch}
    assert after == before
