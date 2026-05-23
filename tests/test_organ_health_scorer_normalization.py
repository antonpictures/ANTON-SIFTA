"""Regression guard for the organ-health scorer normalization fixes.

Locks in two patches to System/swarm_canonical_organ_registry._ledger_health so a
future Doctor cannot silently reintroduce the un-normalized-penalty floor:

  * Reliability (trace bdef3d8d, 2026-05-22): measured over outcome-bearing rows
    only, with a sample-normalized timeout penalty and K-shrinkage. Decision/
    telemetry rows that carry no ok/status must NOT drag reliability to the floor.
  * truth_alignment (trace 067cdd6f, 2026-05-22): error/bad penalties applied as
    RATES (bounded fractions), not flat per-event counts, with K-shrinkage. A
    handful of error rows must not floor a well-receipted organ to 0.0.

Hermetic: every ledger is written under tmp_path. No test touches the live
.sifta_state/ (the lesson from Round 1.5).
"""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_canonical_organ_registry import _ledger_health


def _write_ledger(state: Path, name: str, rows: list[dict]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state / name).open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_telemetry_rows_do_not_floor_reliability(tmp_path: Path) -> None:
    """100 telemetry rows (no ok/status) + 20 real successes => high reliability.

    Pre-fix, the 100 unknown rows were counted as half-failures and dragged the
    score down. Post-fix, reliability is measured over the 20 outcome-bearing rows.
    """
    state = tmp_path / ".sifta_state"
    telemetry = [{"entropy_bits": 7.1, "motion_mean": 0.1, "saliency_peak": 0.3} for _ in range(100)]
    successes = [{"ok": True, "status": "EXECUTED"} for _ in range(20)]
    _write_ledger(state, "vision_like.jsonl", telemetry + successes)

    h = _ledger_health(state, ["vision_like.jsonl"])
    assert h["functional_reliability"] > 0.7, h
    # the telemetry rows are still visible as unknown, just not counted as failures
    assert h["rel_classified_rows"] == 20, h


def test_errors_reduce_but_do_not_floor_truth(tmp_path: Path) -> None:
    """Well-receipted ledger with 20 error rows: truth dips, never floors to 0.

    Pre-fix: 50/100 - 0.15*20 -> clamped to 0.0. Post-fix: rates, so ~0.47.
    """
    state = tmp_path / ".sifta_state"
    receipted = [{"ok": True, "receipt_id": f"r{i}"} for i in range(50)]
    plain = [{"ok": True} for _ in range(30)]
    errored = [{"status": "EXEC_FAILED", "error": "boom"} for _ in range(20)]
    _write_ledger(state, "router_like.jsonl", receipted + plain + errored)

    h = _ledger_health(state, ["router_like.jsonl"])
    assert h["truth_alignment"] > 0.1, h  # not floored
    assert h["truth_alignment"] < 0.9, h  # errors still cost something


def test_structured_sensor_events_count_as_receipt_evidence(tmp_path: Path) -> None:
    """Sensor ledgers with event/truth_label rows are receipts even without receipt_id."""
    state = tmp_path / ".sifta_state"
    face_events = [
        {"ts": i, "event": "FACE_DETECTION", "faces_detected": i % 2, "error": None}
        for i in range(40)
    ]
    stale_events = [
        {"ts": 100 + i, "event": "FACE_RECOGNITION", "error": "latest_frame_stale"}
        for i in range(5)
    ]
    _write_ledger(state, "face_detection_events.jsonl", face_events + stale_events)

    h = _ledger_health(state, ["face_detection_events.jsonl"])
    assert h["receipt_rows"] == 45, h
    assert h["ok_rows"] == 40, h
    assert h["bad_rows"] == 5, h
    assert h["truth_alignment"] > 0.7, h


def test_small_sample_shrinks_toward_neutral(tmp_path: Path) -> None:
    """A single bad row must not read as 0.00 reliability; it shrinks toward 0.5."""
    state = tmp_path / ".sifta_state"
    _write_ledger(state, "thin.jsonl", [{"ok": False, "status": "EXEC_FAILED"}])

    h = _ledger_health(state, ["thin.jsonl"])
    assert 0.3 < h["functional_reliability"] < 0.7, h


def test_genuine_mass_failure_still_scores_low(tmp_path: Path) -> None:
    """The fix must not whitewash a truly broken organ: 100 failures => low score."""
    state = tmp_path / ".sifta_state"
    _write_ledger(state, "broken.jsonl", [{"ok": False, "status": "EXEC_FAILED"} for _ in range(100)])

    h = _ledger_health(state, ["broken.jsonl"])
    assert h["functional_reliability"] < 0.2, h


def test_health_score_formula_weights_unchanged(tmp_path: Path) -> None:
    """Guard the documented weighting so a refactor can't silently re-weight it."""
    state = tmp_path / ".sifta_state"
    _write_ledger(state, "any.jsonl", [{"ok": True, "receipt_id": "r"} for _ in range(40)])

    h = _ledger_health(state, ["any.jsonl"])
    expected = (
        0.35 * h["functional_reliability"]
        + 0.25 * h["truth_alignment"]
        + 0.20 * h["freshness"]
        + 0.20 * h["coverage"]
    )
    assert abs(h["score"] - round(expected, 4)) < 1e-3, h
