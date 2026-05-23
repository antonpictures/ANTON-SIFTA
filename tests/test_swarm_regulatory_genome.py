import json
import time
import pytest
from pathlib import Path

from System.swarm_regulatory_genome import (
    default_regulatory_meta_rules,
    load_regulatory_parameters,
    load_regulatory_meta_rules,
    propose_regulatory_update,
    reset_regulatory_genome,
    get_latest_genome_hash,
    BOUNDS,
    get_regulatory_genome_path,
)


def test_load_defaults_when_no_ledger(tmp_path):
    params = load_regulatory_parameters(root=tmp_path)
    assert params["metacog_evidence_threshold"] == BOUNDS["metacog_evidence_threshold"]["default"]
    assert params["arbiter_risk_weight"] == BOUNDS["arbiter_risk_weight"]["default"]


def test_persist_and_reload_valid_update(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"metacog_evidence_threshold": 0.65}
    row = propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=1
    )
    assert row is not None
    assert row["parameters"]["metacog_evidence_threshold"] == 0.65

    params = load_regulatory_parameters(root=tmp_path, current_tick=1)
    assert params["metacog_evidence_threshold"] == 0.65


def test_reject_out_of_bounds_proposal(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"metacog_evidence_threshold": 0.90}
    row = propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=1
    )
    assert row is None

    params = load_regulatory_parameters(root=tmp_path, current_tick=50)
    assert params["metacog_evidence_threshold"] == BOUNDS["metacog_evidence_threshold"]["default"]


def test_metacognitive_monitor_proposes_on_sustained_underconfident(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"causal_prober_uncertainty_threshold": 0.60}
    row = propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=2
    )
    assert row is not None
    assert row["parameters"]["causal_prober_uncertainty_threshold"] == 0.60


def test_arbiter_proposes_on_high_regret_with_high_resilience(tmp_path):
    trigger = {
        "duration_ticks": 45,
        "resilience_floor": 0.10,
        "avg_regret": 0.3,
    }
    proposed = {"arbiter_risk_weight": 1.5}
    row = propose_regulatory_update(
        proposed, trigger, "Arbiter", root=tmp_path, current_tick_id=3
    )
    assert row is not None
    assert row["parameters"]["arbiter_risk_weight"] == 1.5


def test_reset_returns_to_defaults(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"metacog_evidence_threshold": 0.65}
    propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=10
    )

    params = load_regulatory_parameters(root=tmp_path, current_tick=10)
    assert params["metacog_evidence_threshold"] == 0.65

    reset_regulatory_genome("test_reset", root=tmp_path, current_tick_id=100)

    params2 = load_regulatory_parameters(root=tmp_path, current_tick=100)
    assert params2["metacog_evidence_threshold"] == BOUNDS["metacog_evidence_threshold"]["default"]


def test_decay_toward_defaults_when_stale_by_tick(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"metacog_evidence_threshold": 0.65}
    propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=100
    )
    # age > decay + decay => full blend to defaults
    params = load_regulatory_parameters(
        root=tmp_path, current_tick=100 + 500 + 500 + 1, decay_after_ticks=500
    )
    assert params["metacog_evidence_threshold"] == pytest.approx(BOUNDS["metacog_evidence_threshold"]["default"], abs=0.03)


def test_wall_clock_stale_when_no_tick_id_on_row(tmp_path, monkeypatch):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    proposed = {"metacog_evidence_threshold": 0.65}
    row = propose_regulatory_update(
        proposed, trigger, "MetacognitiveMonitor", root=tmp_path, current_tick_id=None
    )
    assert row is not None
    path = get_regulatory_genome_path(tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    obj = json.loads(lines[-1])
    assert "tick_id" not in obj

    original_time = time.time

    def mock_time():
        return original_time() + 1000

    monkeypatch.setattr(time, "time", mock_time)
    params = load_regulatory_parameters(tmp_path, current_tick=None, decay_after_ticks=500)
    assert params["metacog_evidence_threshold"] == pytest.approx(BOUNDS["metacog_evidence_threshold"]["default"], abs=0.03)


def test_updates_record_previous_params_delta_and_default_meta_rules(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    row = propose_regulatory_update(
        {"metacog_evidence_threshold": 0.55},
        trigger,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=200,
    )

    assert row is not None
    assert row["previous_parameters"]["metacog_evidence_threshold"] == 0.50
    assert row["parameter_delta"]["metacog_evidence_threshold"] == 0.05
    assert row["meta_rules"] == default_regulatory_meta_rules()
    assert row["third_order_closure"]["applied"] is False


def test_third_order_closure_increases_meta_rate_and_priming_half_life(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }

    row1 = propose_regulatory_update(
        {"metacog_evidence_threshold": 0.55},
        trigger,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=100,
    )
    row2 = propose_regulatory_update(
        {"metacog_evidence_threshold": 0.60},
        trigger,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=121,
    )
    row3 = propose_regulatory_update(
        {"metacog_evidence_threshold": 0.65},
        trigger,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=142,
    )

    assert row1 is not None and row2 is not None and row3 is not None
    assert row1["third_order_closure"]["applied"] is False
    assert row2["third_order_closure"]["applied"] is False
    assert row3["third_order_closure"]["applied"] is True
    assert row3["third_order_closure"]["rule"] == "metacog_threshold_up_under_chronic_dam"
    assert row3["third_order_closure"]["streak_with_current"] == 3
    assert row3["meta_rules"]["meta_adjustment_rate"] > default_regulatory_meta_rules()["meta_adjustment_rate"]
    assert row3["parameters"]["microglia_priming_half_life_hours"] > row2["parameters"]["microglia_priming_half_life_hours"]
    assert load_regulatory_meta_rules(tmp_path)["meta_adjustment_rate"] == row3["meta_rules"]["meta_adjustment_rate"]


def test_third_order_closure_does_not_apply_without_chronic_dam_stage2(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 1,
        "tme_phase": "EQUILIBRIUM",
    }
    rows = []
    for tick, threshold in ((100, 0.55), (121, 0.60), (142, 0.65)):
        rows.append(propose_regulatory_update(
            {"metacog_evidence_threshold": threshold},
            trigger,
            "MetacognitiveMonitor",
            root=tmp_path,
            current_tick_id=tick,
        ))

    assert all(r is not None for r in rows)
    assert rows[-1]["third_order_closure"]["applied"] is False
    assert rows[-1]["meta_rules"] == default_regulatory_meta_rules()


def test_third_order_meta_rate_decays_toward_default_when_pattern_breaks(tmp_path):
    trigger_dam = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    propose_regulatory_update(
        {"metacog_evidence_threshold": 0.55},
        trigger_dam,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=100,
    )
    propose_regulatory_update(
        {"metacog_evidence_threshold": 0.60},
        trigger_dam,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=121,
    )
    row3 = propose_regulatory_update(
        {"metacog_evidence_threshold": 0.65},
        trigger_dam,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=142,
    )
    assert row3["meta_rules"]["meta_adjustment_rate"] == 0.06

    trigger_escape = {
        "sustained_regime": "OVERCONFIDENT",
        "duration_ticks": 25,
        "dam_stage": 0,
        "tme_phase": "ESCAPE",
    }
    row4 = propose_regulatory_update(
        {"causal_prober_uncertainty_threshold": 0.45},
        trigger_escape,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=163,
    )

    assert row4 is not None
    assert row4["third_order_closure"]["rule"] == "meta_adjustment_rate_decay"
    assert row4["meta_rules"]["meta_adjustment_rate"] == 0.055


def test_governance_reset_restores_meta_rules(tmp_path):
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    for tick, threshold in ((100, 0.55), (121, 0.60), (142, 0.65)):
        propose_regulatory_update(
            {"metacog_evidence_threshold": threshold},
            trigger,
            "MetacognitiveMonitor",
            root=tmp_path,
            current_tick_id=tick,
        )
    assert load_regulatory_meta_rules(tmp_path)["meta_adjustment_rate"] > 0.05

    row = reset_regulatory_genome("reset_meta", root=tmp_path, current_tick_id=200)

    assert row["meta_rules"] == default_regulatory_meta_rules()
    assert load_regulatory_meta_rules(tmp_path) == default_regulatory_meta_rules()
