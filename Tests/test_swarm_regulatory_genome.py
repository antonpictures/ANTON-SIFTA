import json
import time
from pathlib import Path

from System.swarm_regulatory_genome import (
    load_regulatory_parameters,
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

    params = load_regulatory_parameters(root=tmp_path, current_tick=50)
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

    params = load_regulatory_parameters(root=tmp_path, current_tick=50)
    assert params["metacog_evidence_threshold"] == 0.65

    reset_regulatory_genome("test_reset", root=tmp_path, current_tick_id=100)

    params2 = load_regulatory_parameters(root=tmp_path, current_tick=150)
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
    assert params["metacog_evidence_threshold"] == BOUNDS["metacog_evidence_threshold"]["default"]


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
    assert params["metacog_evidence_threshold"] == BOUNDS["metacog_evidence_threshold"]["default"]
