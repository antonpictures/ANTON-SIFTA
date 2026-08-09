"""r1744 — the stationary measure of a window is its belief system.

WCT r1743 §3, borging Hoffman. Raw frequency is the icon; the stationary
measure is the structure behind it. Measured on the live field, the two
disagree by real margins: rlhs_channel is 27.96% of rows but only 17.22% of
the long run (it self-loops — chatter), while ide_surgery_landed is 4.71% of
rows and 9.33% of the long run (it is structurally central).
"""
from __future__ import annotations

import json

import pytest

from System.swarm_stationary_belief import (
    MIN_TICKS_FOR_BELIEF,
    belief_report,
    read_state_sequence,
    stationary_measure,
    transition_counts,
    transition_matrix,
)


def _write(path, states):
    path.write_text(
        "".join(json.dumps({"event": s}) + "\n" for s in states),
        encoding="utf-8",
    )
    return path


def test_transition_counts_read_the_chain_not_the_histogram():
    counts = transition_counts(["a", "b", "a", "b", "c"])

    assert counts["a"] == {"b": 2}
    assert counts["b"] == {"a": 1, "c": 1}
    assert "c" not in counts, "a final state has no outgoing evidence"


def test_matrix_rows_are_probabilities():
    labels, matrix = transition_matrix(["a", "b", "a", "c", "a", "b"])

    assert labels == ["a", "b", "c"]
    for row in matrix:
        assert pytest.approx(sum(row), abs=1e-9) == 1.0


def test_a_state_never_seen_leaving_does_not_absorb_the_chain():
    """An unseen exit is missing evidence, not a black hole."""
    _labels, matrix = transition_matrix(["a", "b"])

    assert pytest.approx(sum(matrix[1]), abs=1e-9) == 1.0


def test_stationary_measure_favours_the_state_the_chain_returns_to():
    labels, matrix = transition_matrix(["hub", "x", "hub", "y", "hub", "z", "hub", "x"])
    measure, converged, _iters = stationary_measure(matrix)
    belief = dict(zip(labels, measure))

    assert converged
    assert belief["hub"] > belief["x"], "the chain keeps coming back to hub"


def test_a_periodic_chain_still_settles():
    """The paper monitor alternates two states forever; it must not oscillate."""
    _labels, matrix = transition_matrix(["on", "off"] * 40)
    measure, converged, _iters = stationary_measure(matrix)

    assert converged
    assert pytest.approx(sum(measure), abs=1e-9) == 1.0


def test_thin_evidence_is_reported_as_thin(tmp_path):
    """A long run over eleven ticks is arithmetic, not belief (§2)."""
    ledger = _write(tmp_path / "thin.jsonl", ["a", "b"] * 5 + ["a"])

    report = belief_report(ledger)

    assert report["ticks"] < MIN_TICKS_FOR_BELIEF
    assert report["enough_evidence"] is False


def test_report_carries_its_own_convergence_and_tick_count(tmp_path):
    ledger = _write(tmp_path / "rich.jsonl", ["a", "b", "c", "a", "c", "b"] * 40)

    report = belief_report(ledger)

    assert report["ticks"] == 240
    assert report["enough_evidence"] is True
    assert report["converged"] is True
    assert report["truth_label"] == "OBSERVED_STATIONARY_BELIEF_V1"
    assert pytest.approx(sum(b["belief"] for b in report["beliefs"]), abs=1e-6) == 1.0


def test_state_key_falls_back_across_organ_naming(tmp_path):
    """Organs never agreed on a field name; one reader still sees the chain."""
    ledger = tmp_path / "mixed.jsonl"
    ledger.write_text(
        json.dumps({"event": "one"}) + "\n"
        + json.dumps({"kind": "two"}) + "\n"
        + json.dumps({"action": "three"}) + "\n"
        + json.dumps({"system": "four"}) + "\n",
        encoding="utf-8",
    )

    assert read_state_sequence(ledger) == ["one", "two", "three", "four"]


def test_unreadable_ledger_yields_no_beliefs(tmp_path):
    report = belief_report(tmp_path / "does_not_exist.jsonl")

    assert report["ticks"] == 0
    assert report["enough_evidence"] is False
