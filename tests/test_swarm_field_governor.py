from __future__ import annotations

import json


def test_high_surprise_samples_faster_than_static() -> None:
    from System.swarm_field_governor import decide_from_delta

    static = decide_from_delta(delta=0.002, baseline=0.01)
    surprise = decide_from_delta(delta=0.65, baseline=0.01)

    assert surprise.sample_period_s < static.sample_period_s
    assert surprise.wake_reason == "surprise"


def test_costs_slow_the_same_signal() -> None:
    from System.swarm_field_governor import FieldGovernorInput, decide_sampling

    base = FieldGovernorInput(prediction_error=0.45, salience=0.3)
    cheap = decide_sampling(base)
    costly = decide_sampling(
        FieldGovernorInput(
            prediction_error=0.45,
            salience=0.3,
            thermal_cost=0.9,
            stgm_cost=0.9,
            interrupt_risk=0.3,
        )
    )

    assert costly.sample_period_s > cheap.sample_period_s
    assert costly.wake_reason in {"cost_throttle", "mid", "static"}


def test_rk4_keeps_state_bounded() -> None:
    from System.swarm_field_governor import (
        FieldGovernorInput,
        FieldGovernorState,
        rk4_step,
    )

    state = FieldGovernorState(attention=0.9, fatigue=0.2, uncertainty=0.7)
    inputs = FieldGovernorInput(
        prediction_error=1.0,
        salience=1.0,
        owner_presence=1.0,
        thermal_cost=0.5,
    )
    for _ in range(30):
        state = rk4_step(state, inputs, dt_s=0.25)
        assert 0.0 <= state.attention <= 1.0
        assert 0.0 <= state.fatigue <= 1.0
        assert 0.0 <= state.uncertainty <= 1.0


def test_delta_adapter_returns_receipt_grade_dict() -> None:
    from System.swarm_field_governor import TRUTH_LABEL, decide_from_delta

    decision = decide_from_delta(delta=0.12, baseline=0.02, organ_id="eye_test")
    payload = decision.as_dict()

    assert payload["truth_label"] == TRUTH_LABEL
    assert payload["organ_id"] == "eye_test"
    assert payload["method"] == "rk4_phase_space_exp_schedule"
    assert payload["schedule_ms"] == int(round(payload["sample_period_s"] * 1000))


def test_write_decision_receipt(tmp_path) -> None:
    from System.swarm_field_governor import LEDGER_NAME, decide_from_delta, write_decision_receipt

    decision = decide_from_delta(delta=0.3, baseline=0.01)
    row = write_decision_receipt(decision, state_root=tmp_path)

    assert row["kind"] == "FIELD_GOVERNOR_DECISION"
    assert row["receipt_id"]
    ledger = tmp_path / LEDGER_NAME
    loaded = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert loaded["receipt_id"] == row["receipt_id"]
    assert loaded["decision"]["wake_reason"] == decision.wake_reason
