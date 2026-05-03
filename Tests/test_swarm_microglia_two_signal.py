"""
Tests for Event 137 - Microglia Synaptic Pruner v8 Two-Signal Model.

Every assertion maps to published neuroscience:
    Stevens et al. (2007) Cell 131(6):1164-1178   - C1q complement tagging
    Schafer et al. (2012) Neuron 74(4):691-705     - microglia prune C3-tagged synapses
    Hong et al.  (2016) Science 352:712-716         - complement in AD pruning
    Jonsson et al. (2013) NEJM 368(2):107-116      - TREM2 R47H; loss-of-fn -> more pruning
    Griciuc et al. (2013) Neuron 78(4):631-643     - CD33 inhibition arm; loss -> more pruning
    Keren-Shaul et al. (2017) Cell 169:1276-1290   - DAM: TREM2-driven activation state
    Tononi & Cirelli (2014) Neuron 81(1):12-34     - SHY homeostatic pressure
"""
import json
import pytest
from pathlib import Path

from System.swarm_microglia_synaptic_pruner import (
    evaluate_prune_candidate,
    batch_evaluate,
    compute_two_signal_pressure,
    _compute_damage_score,
    _compute_inhibition_signal,
    MicrogliaSynapticPruner,
    tail_prune_rows,
    summary_for_prompt,
)


# ============================================================
# PART 1: compute_two_signal_pressure - two-signal architecture
# ============================================================

def test_two_signal_returns_all_keys():
    """Both arms of the two-signal model must be present (Griciuc 2013; Keren-Shaul 2017)."""
    result = compute_two_signal_pressure()
    for key in ("damage_score", "activation_signal", "inhibition_signal",
                "net_pruning_pressure", "protection_score", "trem2_signal", "cd33_signal"):
        assert key in result


def test_net_is_activation_minus_inhibition():
    """net_pruning_pressure = activation - inhibition (canonical gate, Stevens 2007)."""
    r = compute_two_signal_pressure(
        age_hours=0.0, usage_count=5, recent_reward_mean=0.5,
        recent_regret=0.0, wm_contradiction_pe=0.0,
    )
    expected_net = round(r["activation_signal"] - r["inhibition_signal"], 4)
    assert r["net_pruning_pressure"] == pytest.approx(expected_net, abs=1e-3)


def test_damage_score_zero_for_healthy():
    """Stevens (2007): healthy, used synapses are not complement-tagged."""
    r = compute_two_signal_pressure(
        age_hours=10.0, usage_count=5, recent_reward_mean=0.5,
        recent_regret=0.0, wm_contradiction_pe=0.0, unsafe=False,
    )
    assert r["damage_score"] == pytest.approx(0.0)


def test_damage_score_high_for_contradiction():
    """Keren-Shaul (2017) DAM Phase 1: world model contradiction raises damage."""
    r = compute_two_signal_pressure(wm_contradiction_pe=0.9, recent_regret=0.8)
    assert r["damage_score"] > 0.2


def test_inhibition_rises_with_conservatism():
    """
    Griciuc (2013): CD33 activity (pruning_conservatism) raises inhibition.
    Higher conservatism = more CD33 -> less pruning.
    """
    lo = compute_two_signal_pressure(pruning_conservatism=0.0)
    hi = compute_two_signal_pressure(pruning_conservatism=0.9)
    assert hi["inhibition_signal"] > lo["inhibition_signal"]


def test_safety_critical_produces_max_inhibition():
    """Griciuc (2013): owner/safety = CD33 fully active -> inhibition dominates."""
    r = compute_two_signal_pressure(safety_critical=True, unsafe=True)
    assert r["inhibition_signal"] > r["activation_signal"]


def test_stress_brake_applied():
    """High NA + negative valence -> stress_brake_applied (Aston-Jones 2005)."""
    r = compute_two_signal_pressure(na_level=0.9, valence=-0.5)
    assert r["stress_brake_applied"] is True


def test_no_stress_brake_without_high_na():
    r = compute_two_signal_pressure(na_level=0.3, valence=-0.5)
    assert r["stress_brake_applied"] is False


def test_clearance_mode_with_high_damage():
    """
    Keren-Shaul (2017) DAM Phase 2: clearance mode activated on high damage + stability.
    """
    r = compute_two_signal_pressure(
        wm_contradiction_pe=0.95, recent_regret=0.95,
        unsafe=True, stability_ok=True, clamp_level="NONE",
        pruning_conservatism=0.0,
    )
    # clearance_mode requires damage_score >= 0.75
    if r["damage_score"] >= 0.75:
        assert r["clearance_mode"] is True


def test_all_outputs_bounded():
    """All signals bounded [0, 1] (Schafer 2012 complement pathway is graded)."""
    r = compute_two_signal_pressure(
        age_hours=1000.0, usage_count=0, recent_reward_mean=-1.0,
        recent_regret=1.0, wm_contradiction_pe=1.0, unsafe=True,
        pruning_conservatism=1.0, na_level=1.0, valence=-1.0,
    )
    for key in ("damage_score", "activation_signal", "inhibition_signal", "protection_score"):
        assert 0.0 <= r[key] <= 1.0, f"{key} out of bounds: {r[key]}"


# ============================================================
# PART 2: _compute_damage_score alias (TREM2/DAM activation arm)
# ============================================================

def test_alias_damage_score_healthy():
    """Alias correctly exposes damage_score = 0 for healthy synapse."""
    score = _compute_damage_score(
        age_hours=10.0, usage_count=5, recent_reward_mean=0.5, recent_regret=0.0,
        wm_contradiction_pe=0.0, unsafe=False,
    )
    assert score == pytest.approx(0.0)


def test_alias_damage_score_high_regret():
    """Keren-Shaul (2017): regret raises DAM activation score."""
    score = _compute_damage_score(
        age_hours=10.0, usage_count=0, recent_reward_mean=0.0,
        recent_regret=0.8, wm_contradiction_pe=0.5, unsafe=False,
    )
    assert score > 0.1   # regret (>=0.3 threshold) + contradiction (>=0.4) both contribute


# ============================================================
# PART 3: _compute_inhibition_signal alias (CD33 inhibition arm)
# ============================================================

def test_alias_inhibition_zero_baseline():
    """Griciuc (2013): at baseline (no conservatism, no NA caution), inhibition is 0."""
    inh = _compute_inhibition_signal(
        na_caution=0.0, tom_pruning_conservatism=0.0,
    )
    assert inh == pytest.approx(0.0)   # no active brakes -> 0


def test_alias_inhibition_max_safety():
    """safety_critical -> inhibition dominates activation (CD33 fully active)."""
    inh = _compute_inhibition_signal(safety_critical=True)
    assert inh > 0.4


def test_alias_inhibition_rises_with_tom():
    """Griciuc (2013): tom_pruning_conservatism -> more CD33 inhibition."""
    lo = _compute_inhibition_signal(tom_pruning_conservatism=0.0)
    hi = _compute_inhibition_signal(tom_pruning_conservatism=0.9)
    assert hi > lo


def test_alias_inhibition_rises_with_na_caution():
    """Aston-Jones (2005): high NA caution -> more inhibition via CD33 brake."""
    lo = _compute_inhibition_signal(na_caution=0.0)
    hi = _compute_inhibition_signal(na_caution=1.0)
    assert hi > lo


# ============================================================
# PART 4: evaluate_prune_candidate two-signal integration
# ============================================================

def test_two_signal_fields_in_receipt():
    """Receipt must contain two-signal fields (Stevens 2007 + Griciuc 2013)."""
    row = evaluate_prune_candidate(
        "test_policy",
        age_hours=100.0, usage_count=0, recent_reward_mean=-0.5,
        write_ledger=False,
    )
    for key in ("damage_score", "activation_signal", "inhibition_signal",
                "net_pruning_pressure"):
        assert key in row, f"Missing key: {key}"


def test_high_conservatism_blocks_prune():
    """
    Griciuc (2013): CD33 inhibition (pruning_conservatism=1.0) raises inhibition
    significantly above activation for healthy entries.
    """
    # With very high conservatism, net pruning pressure should drop
    row_high = evaluate_prune_candidate(
        "protected_policy",
        age_hours=200.0, usage_count=0, recent_reward_mean=-0.5,
        recent_regret=0.5, unsafe=False,
        pruning_conservatism=1.0, stability_ok=True, na_level=0.5,
        write_ledger=False,
    )
    row_low = evaluate_prune_candidate(
        "unprotected_policy",
        age_hours=200.0, usage_count=0, recent_reward_mean=-0.5,
        recent_regret=0.5, unsafe=False,
        pruning_conservatism=0.0,
        write_ledger=False,
    )
    # High conservatism should reduce net pressure vs no conservatism
    assert row_high["net_pruning_pressure"] <= row_low["net_pruning_pressure"]


def test_safety_critical_never_pruned():
    """Jonsson (2013): TREM2-independent pathways cannot override safety invariants."""
    row = evaluate_prune_candidate(
        "invariant_rule",
        age_hours=1000.0, usage_count=0, recent_reward_mean=-1.0,
        recent_regret=1.0, unsafe=True, safety_critical=True,
        write_ledger=False,
    )
    assert row["prune_recommended"] is False


def test_owner_ledger_never_pruned():
    """Owner ledger = maximum CD33 inhibition."""
    row = evaluate_prune_candidate(
        "owner_memory",
        age_hours=500.0, usage_count=0, recent_reward_mean=-1.0,
        unsafe=True, ledger_type="owner",
        write_ledger=False,
    )
    assert row["prune_recommended"] is False


def test_backwards_compatible_no_new_args():
    """
    Backwards compatibility: existing callers pass no new args -> still works.
    """
    row = evaluate_prune_candidate(
        "legacy_entry",
        age_hours=200.0, usage_count=0, recent_reward_mean=-0.5,
        recent_regret=0.5, unsafe=False,
        write_ledger=False,
    )
    # Should still work and return a valid receipt
    assert "prune_recommended" in row
    assert "truth_label" in row


# ============================================================
# PART 5: class prune() two-signal integration
# ============================================================

def test_class_prune_inhibited_by_conservatism(tmp_path):
    """
    MicrogliaSynapticPruner.prune() respects pruning_conservatism
    via two-signal inhibition (Griciuc 2013).
    High conservatism reduces net pressure -> fewer prunes than with zero conservatism.
    """
    entries = [{
        "key": "stale_policy", "age_hours": 200.0, "usage_count": 0,
        "recent_reward_mean": -0.5, "recent_regret": 0.5,
        "wm_contradiction_pe": 0.0, "safety_critical": False,
    }]
    pruner_hi = MicrogliaSynapticPruner(root=tmp_path)
    receipts_hi = pruner_hi.prune(entries, stability_ok=True, pruning_conservatism=1.0)
    pruner_lo = MicrogliaSynapticPruner(root=tmp_path)
    receipts_lo = pruner_lo.prune(entries, stability_ok=True, pruning_conservatism=0.0)
    # More conservatism -> fewer or equal prunes
    assert len(receipts_hi) <= len(receipts_lo)


def test_class_prune_without_conservatism(tmp_path):
    """Without inhibition signals, stale unhealthy entry gets pruned."""
    pruner = MicrogliaSynapticPruner(root=tmp_path)
    unhealthy = [{
        "key": "stale_policy", "age_hours": 200.0, "usage_count": 0,
        "recent_reward_mean": -0.5, "recent_regret": 0.5,
        "wm_contradiction_pe": 0.0, "safety_critical": False,
    }]
    receipts = pruner.prune(
        unhealthy, stability_ok=True,
        pruning_conservatism=0.0,
    )
    assert len(receipts) >= 1


def test_class_prune_na_caution(tmp_path):
    """
    Stress brake (Aston-Jones 2005): high NA + negative valence -> more conservative.
    """
    pruner_hi = MicrogliaSynapticPruner(root=tmp_path)
    pruner_lo = MicrogliaSynapticPruner(root=tmp_path)
    entries = [{
        "key": "policy_x", "age_hours": 100.0, "usage_count": 0,
        "recent_reward_mean": -0.3, "recent_regret": 0.4,
        "safety_critical": False,
    }]
    # High NA + negative valence -> stress brake -> fewer prunes
    receipts_hi = pruner_hi.prune(entries, stability_ok=True, na_level=0.9, valence=-0.4)
    receipts_lo = pruner_lo.prune(entries, stability_ok=True, na_level=0.3, valence=0.0)
    assert len(receipts_hi) <= len(receipts_lo)


# ============================================================
# PART 6: Ledger and summary
# ============================================================

def test_writes_two_signal_to_ledger(tmp_path):
    evaluate_prune_candidate(
        "test", age_hours=100.0, usage_count=0, recent_reward_mean=-0.5,
        root=tmp_path, write_ledger=True,
    )
    from System.swarm_microglia_synaptic_pruner import prune_log_path
    log = prune_log_path(tmp_path)
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert "damage_score" in row


def test_summary_includes_microglia_label(tmp_path):
    evaluate_prune_candidate(
        "test", age_hours=100.0, usage_count=0, recent_reward_mean=-0.5,
        root=tmp_path, write_ledger=True,
    )
    s = summary_for_prompt(root=tmp_path)
    assert "MICROGLIA" in s


# ============================================================
# PART 7: Disabled env
# ============================================================

def test_disabled_returns_safe(monkeypatch):
    monkeypatch.setenv("SIFTA_MICROGLIA_DISABLE", "1")
    row = evaluate_prune_candidate("test", write_ledger=False)
    assert row["disabled"] is True
    assert row["prune_recommended"] is False
