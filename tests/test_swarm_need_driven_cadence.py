"""Need-driven cadence — body law, not hardcoded 3-second thrash."""
from __future__ import annotations

from System.swarm_need_driven_cadence import (
    attention_interval_s,
    compute_need,
    explain_cadence,
    need_to_interval_ms,
    scheduler_interval_ms,
)


def test_need_zero_rests_near_rest_ceiling():
    need = compute_need(policy="idle", salience=0.0, pending_count=0)
    assert need == 0.0
    ms = need_to_interval_ms(need, t_min_ms=200, t_rest_ms=30_000)
    assert ms == 30_000


def test_need_one_collapses_to_refractory_floor():
    need = compute_need(policy="engage", salience=1.0, pending_count=8)
    assert need == 1.0
    ms = need_to_interval_ms(need, t_min_ms=200, t_rest_ms=30_000)
    assert ms == 200


def test_no_hardcoded_three_second_engage_tick():
    """The old disease: engage always = 3000ms. Body law must not pin 3000."""
    engage = scheduler_interval_ms(policy="engage", salience=0.9, pending_count=2)
    sample = scheduler_interval_ms(policy="sample", salience=0.4, pending_count=0)
    idle = scheduler_interval_ms(policy="idle", salience=0.0, pending_count=0)
    assert engage != 3000
    assert sample != 3000
    assert idle == 30_000
    # Higher need → strictly shorter or equal interval
    assert engage <= sample <= idle


def test_pending_work_raises_need_without_policy_engage():
    cold = compute_need(policy="idle", salience=0.0, pending_count=0)
    one = compute_need(policy="idle", salience=0.0, pending_count=1)
    warm = compute_need(policy="idle", salience=0.0, pending_count=4)
    assert cold == 0.0
    # Any real pending task is full wake — body does not half-wake for one wound.
    assert one == 1.0
    assert warm == 1.0
    assert scheduler_interval_ms(policy="idle", pending_count=1, floor_ms=250) == 250
    assert scheduler_interval_ms(policy="idle", pending_count=0) == 30_000


def test_attention_interval_not_fixed_tiers():
    """Replaces hardcoded 1.5 / 3.0 / 6.0 second kitchen tiers."""
    engage_s = attention_interval_s(policy="engage", salience=1.0)
    sample_s = attention_interval_s(policy="sample", salience=0.3)
    idle_s = attention_interval_s(policy="idle", salience=0.0)
    assert engage_s < sample_s < idle_s
    # Must not be exactly the old magic constants for mid sample
    assert sample_s != 3.0
    assert idle_s != 6.0
    assert engage_s != 1.5


def test_formula_is_monotonic_in_need():
    prev = need_to_interval_ms(0.0)
    for i in range(1, 21):
        n = i / 20.0
        cur = need_to_interval_ms(n)
        assert cur <= prev
        prev = cur


def test_explain_receipt_names_formula_not_three_seconds():
    row = explain_cadence(policy="sample", salience=0.6, pending_count=1)
    assert row["truth_label"] == "NEED_DRIVEN_CADENCE_V1"
    assert "(1 - need)^2" in row["formula"]
    assert "3-second" in row["note"] or "kitchen" in row["note"].lower()
    assert row["need"] > 0.0


def test_floor_ms_only_tightens_when_need_high():
    # Low need: rest wins even if floor is tiny (floor applies only when need high)
    rest = scheduler_interval_ms(policy="idle", salience=0.0, pending_count=0, floor_ms=250)
    assert rest == 30_000
    # High need: floor can raise the minimum wake
    hot = scheduler_interval_ms(policy="engage", salience=1.0, pending_count=4, floor_ms=250)
    assert hot == 250
