#!/usr/bin/env python3
"""Behavior tests for swarm_reconsolidation_operator — twist the field, not the ledger.

These verify the cork-twist (reconsolidation) is real and SAFE:
  - a sacred recall twists the derived field (behavior changes)
  - the twist NEVER mutates the canonical sacred ledger (byte-identical, delta=0)
  - the twist writes no STGM/economic field
  - only sacred recalls twist; non-sacred is a no-op
  - moderate prediction error moves the field MORE than tiny or extreme (inverted-U)
  - field weight stays bounded [0, 1]
Each assertion fails if the mechanism is broken.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_reconsolidation_operator as rc
from System import swarm_sacred_memory_guard as guard


SACRED = "the song made me think of her, I miss you"   # trips the guard
ORDINARY = "open the eval loop and run the tests"     # does not


def test_sacred_recall_twists_the_field():
    res = rc.reconsolidate(SACRED, new_salience=0.8, prior_weight=0.3)
    assert res.is_sacred is True
    assert res.twisted is True
    assert res.behavior_changed is True
    assert res.new_weight != res.prior_weight
    # downstream behavior actually moves with the field
    assert rc.protective_nudge_weight(res.new_weight) > rc.protective_nudge_weight(res.prior_weight)


def test_non_sacred_recall_is_a_noop():
    res = rc.reconsolidate(ORDINARY, new_salience=0.9, prior_weight=0.1)
    assert res.is_sacred is False
    assert res.twisted is False
    assert res.field_delta == 0.0
    assert res.new_weight == res.prior_weight


def test_twist_never_mutates_canonical_ledger(tmp_path):
    """The TOPOLOGY (canonical sacred ledger) must be byte-identical after a twist."""
    canonical = tmp_path / "sacred.jsonl"
    # write a real canonical row via the guard
    guard.record_sacred_memory(
        trigger="song_memory", owner_feeling="missing wife",
        care_action="emailed wife: I miss you", source_text=SACRED,
        ledger_path=canonical,
    )
    before_bytes = canonical.read_bytes()

    # twist the smooth field, persisting to a SEPARATE field ledger
    field = tmp_path / "field.jsonl"
    res = rc.reconsolidate(SACRED, new_salience=0.9, prior_weight=0.2,
                           field_ledger=field, persist=True)
    assert res.twisted is True

    after_bytes = canonical.read_bytes()
    assert after_bytes == before_bytes, "twist must not touch the canonical ledger topology"
    # the field row exists and is non-economic
    rows = [json.loads(l) for l in field.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1
    assert "stgm" not in json.dumps(rows[0]).lower()
    assert "wallet" not in json.dumps(rows[0]).lower()
    assert rows[0]["truth_label"] == rc.TRUTH_LABEL


def test_moderate_prediction_error_moves_more_than_extreme():
    """Inverted-U gate: a moderate surprise reshapes the field more than a tiny or huge one."""
    # tiny surprise: prior near salience
    tiny = rc.reconsolidate(SACRED, new_salience=0.52, prior_weight=0.50)
    # moderate surprise: prior far from salience by ~0.5
    moderate = rc.reconsolidate(SACRED, new_salience=1.0, prior_weight=0.5)
    # extreme surprise: prior maximally far
    extreme = rc.reconsolidate(SACRED, new_salience=1.0, prior_weight=0.0)
    assert moderate.gate > tiny.gate
    assert moderate.gate > extreme.gate
    assert abs(moderate.field_delta) > abs(tiny.field_delta)


def test_field_weight_stays_bounded():
    over = rc.reconsolidate(SACRED, new_salience=5.0, prior_weight=0.9)   # salience clamped
    assert 0.0 <= over.new_weight <= 1.0
    under = rc.reconsolidate(SACRED, new_salience=-3.0, prior_weight=0.1)  # clamped to 0
    assert 0.0 <= under.new_weight <= 1.0


def test_default_does_not_persist(tmp_path):
    field = tmp_path / "field.jsonl"
    rc.reconsolidate(SACRED, new_salience=0.8, prior_weight=0.2, field_ledger=field)  # persist=False
    assert not field.exists()


def test_default_run_touches_no_real_ledgers():
    watch = [
        Path(".sifta_state/sacred_field_weights.jsonl"),
        Path(".sifta_state/work_receipts.jsonl"),
        Path(".sifta_state/stgm_memory_rewards.jsonl"),
        Path(".sifta_state/memory_ledger.jsonl"),
        Path(".sifta_state/unified_stigmergic_field.jsonl"),
    ]
    before = {
        str(path): path.read_text(encoding="utf-8", errors="replace").count("\n")
        if path.exists()
        else 0
        for path in watch
    }
    rc.reconsolidate(SACRED, new_salience=0.8, prior_weight=0.2)
    after = {
        str(path): path.read_text(encoding="utf-8", errors="replace").count("\n")
        if path.exists()
        else 0
        for path in watch
    }
    assert after == before


def test_gate_is_inverted_u():
    assert rc.prediction_error_gate(0.0) == 0.0
    assert rc.prediction_error_gate(1.0) == 0.0
    assert rc.prediction_error_gate(0.5) == pytest.approx(1.0)
    assert rc.prediction_error_gate(0.5) > rc.prediction_error_gate(0.1)
