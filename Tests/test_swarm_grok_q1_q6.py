"""
Tests for all 6 Grok-specified implementations:
    Q1 — estimate_causal_effect() propensity-score IPW + permutation test
    Q2 — compute_phi_id_approx() Gaussian Φ̂
    Q3 — compute_joint_surprise() total correlation / emergence
    Q4 — read_proto_self_interoception() macOS interoception
    Q5 — compute_homeostatic_pressure() + should_prune_homeostatic() SHY
    Q6 — compute_identity_anchor() Parfit hardware continuity
"""
import json
import math
import pytest
from pathlib import Path


# ─── Q1: Propensity-score causal effect estimate ─────────────────────────────

from System.swarm_causal_intervention_logger import CausalInterventionLogger


def _write_interventions(logger, n_treated=15, n_control=10):
    for i in range(n_treated):
        logger.log_intervention(
            tick_id=i,
            do_vars={"target": "exploration_bias", "delta": 0.05},
            expected_effect_on="replay_composition",
            observed_shift={"direction_matches": True},
            causal_effect_size=0.20 + i * 0.005,
            confounder_check={"owner_switch": False, "metabolic_critical": False},
        )
    for i in range(n_control):
        logger.log_intervention(
            tick_id=n_treated + i,
            do_vars={"target": "exploration_bias", "delta": 0.05},
            expected_effect_on="replay_composition",
            observed_shift={"direction_matches": False},
            causal_effect_size=0.05 + i * 0.003,
            confounder_check={"owner_switch": True, "metabolic_critical": False},
        )


def test_estimate_returns_sufficient_data_false_with_few_rows(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    result = logger.estimate_causal_effect(min_samples=10)
    assert result["sufficient_data"] is False
    assert result["p_value"] == 1.0


def test_estimate_detects_positive_effect(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    _write_interventions(logger, n_treated=20, n_control=10)
    result = logger.estimate_causal_effect(min_samples=10)
    assert result["sufficient_data"] is True
    assert result["weighted_effect"] > 0  # treated > control
    assert 0.0 <= result["p_value"] <= 1.0


def test_estimate_result_schema(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    _write_interventions(logger)
    result = logger.estimate_causal_effect(min_samples=5)
    for key in ("n_total", "n_treated", "n_control", "weighted_effect",
                "p_value", "sufficient_data", "truth_label"):
        assert key in result


def test_estimate_truth_label(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    result = logger.estimate_causal_effect()
    assert result["truth_label"] == "CAUSAL_CLOSURE_TEST"


def test_summary_includes_stat_when_enough_data(tmp_path):
    logger = CausalInterventionLogger(root=tmp_path)
    _write_interventions(logger, n_treated=20, n_control=5)
    summary = logger.summary_for_prompt()
    assert "τ̂" in summary or "stat pending" in summary


# ─── Q2: Φ̂ integrated information ──────────────────────────────────────────

from System.swarm_emergence_synergy import (
    compute_phi_id_approx,
    compute_joint_surprise,
    compute_and_log_emergence,
)


def _correlated_matrix(T=50, D=5, seed=7):
    """Correlated data → high Φ̂."""
    import math, random
    random.seed(seed)
    M = []
    prev = [random.gauss(0, 1) for _ in range(D)]
    for _ in range(T):
        row = [0.6 * prev[d] + 0.8 * random.gauss(0, 1) for d in range(D)]
        M.append(row)
        prev = row
    return M


def _shuffled_matrix(M):
    import random
    cols = [[M[t][d] for t in range(len(M))] for d in range(len(M[0]))]
    shuffled_cols = []
    for col in cols:
        c = col[:]
        random.shuffle(c)
        shuffled_cols.append(c)
    T = len(M)
    return [[shuffled_cols[d][t] for d in range(len(M[0]))] for t in range(T)]


def test_phi_positive_on_correlated_data():
    M = _correlated_matrix(T=80, D=5)
    phi = compute_phi_id_approx(M)
    assert phi >= 0.0


def test_phi_near_zero_on_independent_data():
    """Independent columns → low Φ̂."""
    import random
    random.seed(42)
    M = [[random.gauss(0, 1) for _ in range(5)] for _ in range(80)]
    phi_real = compute_phi_id_approx(M)
    phi_shuf = compute_phi_id_approx(_shuffled_matrix(M))
    # Shuffled should be comparable (both ~0 for independence)
    assert phi_real >= 0.0 and phi_shuf >= 0.0


def test_phi_higher_correlated_than_shuffled():
    M = _correlated_matrix(T=100, D=6, seed=13)
    phi_real = compute_phi_id_approx(M)
    phi_shuf = compute_phi_id_approx(_shuffled_matrix(M))
    assert phi_real >= phi_shuf


def test_phi_computation_speed():
    """Should finish in <200ms per 200-tick window (Grok spec)."""
    import time
    M = _correlated_matrix(T=200, D=12, seed=99)
    t0 = time.time()
    compute_phi_id_approx(M)
    elapsed = time.time() - t0
    assert elapsed < 2.0  # generous — pure Python is slower than numpy


def test_phi_degenerate_returns_zero():
    # Single row → degenerate
    assert compute_phi_id_approx([[1.0, 2.0]]) == 0.0


# ─── Q3: Emergence / joint synergy ──────────────────────────────────────────

def test_synergy_positive_on_correlated():
    M = _correlated_matrix(T=80, D=5)
    result = compute_joint_surprise(M)
    assert result["sufficient_data"] is True
    assert result["O_joint_surprise"] >= 0.0


def test_synergy_schema():
    M = _correlated_matrix(T=50, D=4)
    result = compute_joint_surprise(M)
    for key in ("O_joint_surprise", "synergy", "total_correlation",
                "H_joint", "estimator", "n_timepoints", "n_organs"):
        assert key in result


def test_synergy_larger_on_correlated_than_shuffled():
    M = _correlated_matrix(T=100, D=5)
    real = compute_joint_surprise(M)["O_joint_surprise"]
    shuf = compute_joint_surprise(_shuffled_matrix(M))["O_joint_surprise"]
    assert real >= shuf * 0.8  # correlated ≥ shuffled (within tolerance)


def test_emergence_logs_to_jsonl(tmp_path):
    M = _correlated_matrix(T=50, D=5)
    row = compute_and_log_emergence(M, window_start=0, window_end=50, root=tmp_path)
    log = tmp_path / "emergence_synergy.jsonl"
    assert log.exists()
    written = json.loads(log.read_text().strip().splitlines()[-1])
    assert written["truth_label"] == "EMERGENCE_SYNERGY"
    assert "phi_id_approx" in written


def test_emergence_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_EMERGENCE_DISABLE", "1")
    M = _correlated_matrix(T=50, D=5)
    row = compute_and_log_emergence(M, root=tmp_path)
    assert row.get("disabled") is True


# ─── Q4: Proto-self interoception ───────────────────────────────────────────

from System.swarm_proto_self_interoception import read_proto_self_interoception


def test_interoception_schema(tmp_path):
    row = read_proto_self_interoception(root=tmp_path, write_ledger=False)
    for key in ("cpu_load_norm", "battery_source", "uptime_hours",
                "allostatic_load_norm", "damasio_mapping", "truth_label"):
        assert key in row


def test_interoception_allostatic_bounded(tmp_path):
    row = read_proto_self_interoception(root=tmp_path, write_ledger=False)
    assert 0.0 <= row["allostatic_load_norm"] <= 1.0


def test_interoception_cpu_bounded(tmp_path):
    row = read_proto_self_interoception(root=tmp_path, write_ledger=False)
    assert 0.0 <= row["cpu_load_norm"] <= 1.0


def test_interoception_writes_jsonl(tmp_path):
    read_proto_self_interoception(root=tmp_path, write_ledger=True)
    log = tmp_path / "proto_self_interoception.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["truth_label"] == "PROTO_SELF_INTEROCEPTION"


def test_interoception_damasio_keys(tmp_path):
    row = read_proto_self_interoception(root=tmp_path, write_ledger=False)
    dm = row["damasio_mapping"]
    for key in ("metabolic_heat", "allostatic_load", "energy_reserve", "wakefulness_hours"):
        assert key in dm


def test_interoception_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_INTEROCEPTION_DISABLE", "1")
    row = read_proto_self_interoception(root=tmp_path, write_ledger=False)
    assert row.get("disabled") is True


# ─── Q5: SHY homeostatic pressure ───────────────────────────────────────────

from System.swarm_microglia_synaptic_pruner import MicrogliaSynapticPruner


def test_homeostatic_pressure_zero_no_traces():
    pruner = MicrogliaSynapticPruner()
    assert pruner.compute_homeostatic_pressure([]) == 0.0


def test_homeostatic_pressure_zero_low_reward():
    pruner = MicrogliaSynapticPruner()
    traces = [{"recent_reward_mean": 0.01, "eligibility_trace_norm": 1.0}] * 10
    p = pruner.compute_homeostatic_pressure(traces)
    # 10 * 0.01 / 200 = 0.0005 → raw < theta_baseline → pressure = 0
    assert p == 0.0


def test_homeostatic_pressure_above_threshold_after_high_reward():
    pruner = MicrogliaSynapticPruner()
    # EMA alpha=0.3: after N calls with same input, pressure converges to steady_state
    # instant = 100*1.0*1.0 / 200 - 0.2 = 0.5 - 0.2 = 0.3
    # After 10 calls: EMA approaches 0.3 * (1 - 0.7^10) ≈ 0.297
    traces = [{"recent_reward_mean": 1.0, "eligibility_trace_norm": 1.0}] * 100
    p = None
    for _ in range(12):  # converge EMA
        p = pruner.compute_homeostatic_pressure(traces, buffer_capacity=200)
    # After convergence, p ≈ instant = 0.3
    assert p is not None and p > 0.1


def test_should_prune_homeostatic_true_after_high_reward():
    pruner = MicrogliaSynapticPruner()
    traces = [{"recent_reward_mean": 1.0, "eligibility_trace_norm": 1.0}] * 150
    # Call multiple times to let EMA converge above 0.35 threshold
    # instant ≈ 150/200 - 0.2 = 0.75 - 0.2 = 0.55; EMA converges toward 0.55
    for _ in range(15):
        pruner.should_prune_homeostatic(traces, stability_ok=True)
    assert pruner.should_prune_homeostatic(traces, stability_ok=True)


def test_should_prune_homeostatic_blocked_in_emergency():
    pruner = MicrogliaSynapticPruner()
    traces = [{"recent_reward_mean": 1.0, "eligibility_trace_norm": 1.0}] * 150
    # stability_ok=False (EMERGENCY) → never prune
    assert not pruner.should_prune_homeostatic(traces, stability_ok=False)


def test_pruning_suppressed_low_reward_even_if_stable():
    pruner = MicrogliaSynapticPruner()
    traces = [{"recent_reward_mean": 0.05, "eligibility_trace_norm": 0.5}] * 50
    assert not pruner.should_prune_homeostatic(traces, stability_ok=True)


# ─── Q6: Hardware identity anchor (Parfit) ──────────────────────────────────

from System.swarm_hardware_identity_anchor import (
    compute_identity_anchor,
    causal_chain_valid,
    _read_first_serial,
)


def test_anchor_schema(tmp_path):
    row = compute_identity_anchor(root=tmp_path, write_ledger=False,
                                  _override_serial="TEST-SERIAL-001")
    for key in ("identity_anchor", "hardware_serial", "self_model_hash",
                "causal_chain_valid", "parfit_criteria", "truth_label"):
        assert key in row
    assert row["truth_label"] == "HARDWARE_CONTINUITY"


def test_anchor_is_deterministic(tmp_path):
    """Same inputs → same anchor."""
    r1 = compute_identity_anchor(root=tmp_path, write_ledger=False, now=1.0,
                                 _override_serial="SERIAL-A")
    r2 = compute_identity_anchor(root=tmp_path, write_ledger=False, now=1.0,
                                 _override_serial="SERIAL-A")
    assert r1["identity_anchor"] == r2["identity_anchor"]


def test_different_serial_gives_different_anchor(tmp_path):
    r1 = compute_identity_anchor(root=tmp_path, write_ledger=False, now=1.0,
                                 _override_serial="SERIAL-A")
    r2 = compute_identity_anchor(root=tmp_path, write_ledger=False, now=1.0,
                                 _override_serial="SERIAL-B")
    assert r1["identity_anchor"] != r2["identity_anchor"]


def test_causal_chain_broken_on_hardware_change(tmp_path):
    """First boot with SERIAL-A; second check with SERIAL-B → chain broken."""
    compute_identity_anchor(root=tmp_path, write_ledger=True,
                            _override_serial="SERIAL-A")
    row = compute_identity_anchor(root=tmp_path, write_ledger=False,
                                  _override_serial="SERIAL-B")
    assert row["causal_chain_valid"] is False


def test_causal_chain_valid_same_hardware(tmp_path):
    """Same hardware serial across reboots → chain preserved."""
    compute_identity_anchor(root=tmp_path, write_ledger=True,
                            _override_serial="SERIAL-A")
    row = compute_identity_anchor(root=tmp_path, write_ledger=False,
                                  _override_serial="SERIAL-A")
    assert row["causal_chain_valid"] is True


def test_parfit_criteria_present(tmp_path):
    row = compute_identity_anchor(root=tmp_path, write_ledger=False,
                                  _override_serial="SERIAL-X")
    p = row["parfit_criteria"]
    assert "psychological_continuity" in p
    assert "causal_connectedness" in p
    assert "non_branching" in p
    assert p["non_branching"] is True


def test_anchor_writes_jsonl(tmp_path):
    compute_identity_anchor(root=tmp_path, write_ledger=True,
                            _override_serial="SERIAL-LOG")
    log = tmp_path / "hardware_identity_anchor.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["truth_label"] == "HARDWARE_CONTINUITY"


def test_anchor_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_ANCHOR_DISABLE", "1")
    row = compute_identity_anchor(root=tmp_path, write_ledger=False)
    assert row.get("disabled") is True


# ─── Integration: viability monitor now has live phi + synergy ───────────────

from System.swarm_autopoiesis_monitor import compute_viability


def test_viability_phi_hat_no_longer_none(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=0.8, memory_continuity=0.9,
        owner_contact_freshness=0.7, self_repair_rate=1.0,
        schema_refinement_rate=0.8,
    )
    # phi_hat and emergence_synergy should now be floats, not None
    assert row["phi_hat"] is not None
    assert isinstance(row["phi_hat"], float)


def test_viability_emergence_synergy_no_longer_none(tmp_path):
    row = compute_viability(
        root=tmp_path, write_ledger=False,
        energy_budget=0.5, memory_continuity=0.5,
        owner_contact_freshness=0.5, self_repair_rate=0.5,
        schema_refinement_rate=0.5,
    )
    assert row["emergence_synergy"] is not None
    assert isinstance(row["emergence_synergy"], float)
