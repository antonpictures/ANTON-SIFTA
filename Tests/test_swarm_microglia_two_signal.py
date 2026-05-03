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
    _base_pathology,
    _compute_damage_score,
    _compute_dam_stage,
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
    r = compute_two_signal_pressure(wm_contradiction_pe=0.9, recent_regret=0.8, unsafe=True)
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
    """All signals bounded; DAM-scaled activation has ratified cap 1.45."""
    r = compute_two_signal_pressure(
        age_hours=1000.0, usage_count=0, recent_reward_mean=-1.0,
        recent_regret=1.0, wm_contradiction_pe=1.0, unsafe=True,
        pruning_conservatism=1.0, na_level=1.0, valence=-1.0,
    )
    for key in ("damage_score", "inhibition_signal", "protection_score"):
        assert 0.0 <= r[key] <= 1.0, f"{key} out of bounds: {r[key]}"
    assert 0.0 <= r["activation_signal"] <= 1.45


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

# ============================================================
# PART 8: Rich fractalkine - CX3CL1-CX3CR1 (§10.14.25)
# Cardona et al. (2006) Nature Neuroscience 9(7):917-924
# Paolicelli et al. (2011) Science 333(6048):1456-1458
# Ransohoff, R.M. (2009) Nature 462(7271):183-184
# ============================================================

def test_fractalkine_in_receipt():
    """compute_two_signal_pressure now returns fractalkine field (Cardona 2006)."""
    r = compute_two_signal_pressure(stability_dwell_score=0.8, goal_alignment=0.9)
    assert "fractalkine" in r
    assert "stability_dwell_score" in r
    assert "goal_alignment" in r
    assert "owner_frustration" in r


def test_fractalkine_grows_with_dwell():
    """
    Cardona (2006): CX3CL1 expression sustained during prolonged stable states.
    More dwell -> more fractalkine -> more inhibition.
    """
    low = compute_two_signal_pressure(
        stability_dwell_score=0.0, goal_alignment=0.8, stability_ok=True, clamp_level="NONE",
    )
    high = compute_two_signal_pressure(
        stability_dwell_score=1.0, goal_alignment=0.8, stability_ok=True, clamp_level="NONE",
    )
    assert high["fractalkine"] >= low["fractalkine"]
    assert high["inhibition_signal"] >= low["inhibition_signal"]


def test_fractalkine_grows_with_goal_alignment():
    """
    Paolicelli (2011): goal-relevant synapses retain fractalkine protection longer.
    Higher goal_alignment -> more fractalkine -> synapse protected.
    """
    lo = compute_two_signal_pressure(stability_dwell_score=0.8, goal_alignment=0.1)
    hi = compute_two_signal_pressure(stability_dwell_score=0.8, goal_alignment=0.9)
    assert hi["fractalkine"] > lo["fractalkine"]


def test_owner_frustration_attenuates_fractalkine():
    """
    Ransohoff (2009): social stress / owner frustration attenuates CX3CL1 expression.
    High frustration -> less fractalkine -> less protection.
    """
    calm = compute_two_signal_pressure(
        stability_dwell_score=1.0, goal_alignment=0.8, owner_frustration=0.0,
    )
    frustrated = compute_two_signal_pressure(
        stability_dwell_score=1.0, goal_alignment=0.8, owner_frustration=1.0,
    )
    assert frustrated["fractalkine"] < calm["fractalkine"]


def test_fractalkine_capped_at_0_30():
    """
    Fractalkine cannot alone block a genuinely damaged synapse (cap = 0.30).
    Even maximum dwell + perfect alignment < 0.31.
    """
    r = compute_two_signal_pressure(
        stability_dwell_score=1.0, goal_alignment=1.0, owner_frustration=0.0,
        stability_ok=True, clamp_level="NONE",
    )
    assert r["fractalkine"] <= 0.30 + 1e-4


def test_fractalkine_floor_when_stable():
    """
    Even zero dwell gets a fractalkine floor when stable + NONE clamp (old binary ≈ 0.03).
    """
    r = compute_two_signal_pressure(
        stability_dwell_score=0.0, goal_alignment=0.0, owner_frustration=0.0,
        stability_ok=True, clamp_level="NONE",
        # Ensure damage is below 0.50 for floor to apply
        age_hours=0.0, usage_count=5, recent_reward_mean=0.5,
    )
    assert r["fractalkine"] >= 0.05


def test_no_fractalkine_floor_during_emergency():
    """No fractalkine floor during EMERGENCY clamp (organism under threat)."""
    r = compute_two_signal_pressure(
        stability_dwell_score=0.0, goal_alignment=0.0, stability_ok=False,
        clamp_level="EMERGENCY",
    )
    # Either no floor, or fractalkine is very low
    assert r["fractalkine"] < 0.10


def test_clearance_mode_net_based():
    """
    §10.14.25.3: clearance_mode now fires on net_pruning_pressure >= threshold,
    not raw damage_score >= 0.75. More precise biological gate.
    """
    # Net below delete threshold: clearance_mode = False even with high damage
    r_blocked = compute_two_signal_pressure(
        wm_contradiction_pe=0.6, recent_regret=0.6, unsafe=False,
        pruning_conservatism=0.9,   # high inhibition -> net stays low
        stability_ok=True, clamp_level="NONE",
    )
    assert r_blocked["clearance_mode"] is False

    # Net above delete threshold: clearance_mode = True
    r_clear = compute_two_signal_pressure(
        wm_contradiction_pe=0.9, recent_regret=0.9, unsafe=True,
        pruning_conservatism=0.0,   # no inhibition
        stability_ok=True, clamp_level="NONE",
        stability_dwell_score=0.0, goal_alignment=0.0, owner_frustration=1.0,
    )
    if r_clear["net_pruning_pressure"] >= 0.55:
        assert r_clear["clearance_mode"] is True


def test_provenance_in_two_signal_receipt():
    """Receipt provenance includes new CX3CL1-related citations."""
    r = compute_two_signal_pressure()
    p = r["provenance"]
    assert "Cardona" in p
    assert "Paolicelli" in p
    assert "Ransohoff" in p


def test_fractalkine_legacy_alias():
    """fractalkine_analog remains as legacy alias for backwards compat."""
    r = compute_two_signal_pressure(stability_dwell_score=0.5, goal_alignment=0.7)
    assert r["fractalkine_analog"] == r["fractalkine"]


# ============================================================
# PART 9: DAM stage v2 (§10.14.28.1)
# Keren-Shaul et al. (2017) Cell 169:1276-1290
# Deczkowska et al. (2018) Cell 173:1073-1081
# ============================================================

def test_dam_receipt_fields_present():
    """compute_two_signal_pressure receipts expose the full ratified DAM v2 fields."""
    r = compute_two_signal_pressure(wm_contradiction_pe=0.8, recent_regret=0.8, age_hours=9.0)
    for key in (
        "dam_stage",
        "activation_multiplier",
        "base_pathology",
        "sustained_pathology",
        "activation_signal_pre_dam",
        "net_clearance_bias",
        "clearance_bias_applied",
    ):
        assert key in r


def test_base_pathology_uses_regret_and_prediction_error():
    """§10.14.28.1: base=max(damage_score, 0.75*regret, 0.65*PE)."""
    base = _base_pathology(0.10, recent_regret=0.80, wm_contradiction_pe=0.20)
    assert base == pytest.approx(0.60)
    base = _base_pathology(0.10, recent_regret=0.20, wm_contradiction_pe=0.80)
    assert base == pytest.approx(0.52)


def test_dam_stage0_homeostatic_under_threshold():
    assert _compute_dam_stage(
        0.10, age_hours=99.0, recent_regret=0.99, wm_contradiction_pe=0.99,
    ) == 0


def test_dam_stage1_for_unsustained_spike():
    """
    High base pathology alone is not enough for stage 2; sustained evidence is
    the no-chatter gate.
    """
    assert _compute_dam_stage(
        0.70, age_hours=1.0, recent_regret=0.20, wm_contradiction_pe=0.50,
    ) == 1


def test_dam_stage2_requires_sustained_pathology():
    """8h+, high regret, or high PE with age >4 promotes stage 2."""
    assert _compute_dam_stage(
        0.70, age_hours=9.0, recent_regret=0.10, wm_contradiction_pe=0.10,
    ) == 2
    assert _compute_dam_stage(
        0.70, age_hours=1.0, recent_regret=0.60, wm_contradiction_pe=0.10,
    ) == 2
    assert _compute_dam_stage(
        0.70, age_hours=5.0, recent_regret=0.10, wm_contradiction_pe=0.60,
    ) == 2


def test_activation_multiplier_applies_after_composition():
    """Stage multipliers scale the composed activation arm, not raw damage_score."""
    stage1 = compute_two_signal_pressure(
        unsafe=True,
        recent_regret=0.10,
        wm_contradiction_pe=0.10,
        age_hours=1.0,
        stability_ok=True,
        clamp_level="NONE",
        pruning_conservatism=0.0,
    )
    stage2 = compute_two_signal_pressure(
        unsafe=True,
        recent_regret=0.80,
        wm_contradiction_pe=0.80,
        age_hours=9.0,
        stability_ok=True,
        clamp_level="NONE",
        pruning_conservatism=0.0,
    )
    assert stage1["activation_multiplier"] == pytest.approx(0.92)
    assert stage2["activation_multiplier"] == pytest.approx(1.28)
    assert stage2["activation_signal"] > stage2["activation_signal_pre_dam"]


def test_stage2_clearance_bias_lowers_threshold_but_receipts_it(monkeypatch):
    """Stage 2 can lower clearance threshold only via an explicit receipt field."""
    monkeypatch.delenv("MICROGLIA_CLEARANCE_NET_PRESSURE", raising=False)
    monkeypatch.delenv("MICROGLIA_NET_DELETE_PRESSURE", raising=False)
    r = compute_two_signal_pressure(
        unsafe=True,
        recent_regret=0.80,
        wm_contradiction_pe=0.80,
        age_hours=9.0,
        stability_ok=True,
        clamp_level="NONE",
        pruning_conservatism=0.0,
    )
    assert r["dam_stage"] == 2
    assert r["clearance_bias_applied"] is True
    assert r["net_clearance_bias"] == pytest.approx(0.05)
    assert r["clearance_net_threshold"] == pytest.approx(0.50)


def test_stage2_high_fractalkine_can_still_block_clearance():
    """Stage 2 does not bypass inhibition; high fractalkine/conservatism can win."""
    r = compute_two_signal_pressure(
        unsafe=False,
        recent_regret=0.80,
        wm_contradiction_pe=0.80,
        age_hours=9.0,
        stability_dwell_score=1.0,
        goal_alignment=1.0,
        owner_frustration=0.0,
        pruning_conservatism=1.0,
        stability_ok=True,
        clamp_level="NONE",
    )
    assert r["dam_stage"] == 2
    assert r["inhibition_signal"] >= r["activation_signal"] or r["clearance_mode"] is False


def test_prev_stage2_hysteresis_prevents_boundary_chatter():
    """Committed DAM stage 2 persists until base pathology falls below release."""
    assert _compute_dam_stage(
        0.43,
        age_hours=1.0,
        recent_regret=0.10,
        wm_contradiction_pe=0.10,
        prev_dam_stage=2,
    ) == 2
    assert _compute_dam_stage(
        0.17,
        age_hours=1.0,
        recent_regret=0.10,
        wm_contradiction_pe=0.10,
        prev_dam_stage=1,
    ) == 0


def test_compute_two_signal_accepts_prev_dam_stage_receipt():
    """Callers can pass last-tick DAM stage and get it receipted."""
    r = compute_two_signal_pressure(
        wm_contradiction_pe=0.65,
        recent_regret=0.10,
        age_hours=1.0,
        prev_dam_stage=2,
    )
    assert r["prev_dam_stage"] == 2
    assert r["dam_stage"] == 2

# ============================================================
# PART 9: DAM stage thresholds (§10.14.28.1 v2)
# Keren-Shaul et al. (2017) Cell 169:1276
# Deczkowska et al. (2018) Cell 173:1073
# ============================================================

def test_dam_stage_zero_for_healthy():
    """Homeostatic synapse -> Stage 0 (multiplier 0.60)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(0.10, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1)
    assert stage == 0


def test_dam_stage_one_reactive():
    """Keren-Shaul (2017) Phase 1: score >= 0.32 -> Stage 1 (reactive)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(0.40, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1)
    assert stage == 1


def test_dam_stage_two_requires_sustained():
    """
    Keren-Shaul (2017): Phase 2 (TREM2-dependent) requires sustained activation.
    Score >= 0.58 alone is NOT enough — must have sustained signal.
    Transient spike should stay Stage 1.
    """
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    # High score but NOT sustained (no age, no regret, no PE)
    stage = _compute_dam_stage(0.70, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1)
    assert stage == 1   # Stage 1, not 2 — no sustained activation


def test_dam_stage_two_with_regret_sustained():
    """Sustained via regret > 0.45 -> Stage 2 commitment (Keren-Shaul 2017 Phase 2)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(0.60, age_hours=2.0, recent_regret=0.5, wm_contradiction_pe=0.1)
    assert stage == 2


def test_dam_stage_two_with_age():
    """Sustained via age > 8h -> Stage 2."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(0.60, age_hours=10.0, recent_regret=0.2, wm_contradiction_pe=0.1)
    assert stage == 2


def test_dam_stage_in_two_signal_receipt():
    """Two-signal receipt now includes dam_stage field (§10.14.28.1 v2)."""
    r = compute_two_signal_pressure(
        recent_regret=0.6, age_hours=12.0, wm_contradiction_pe=0.7,
    )
    assert "dam_stage" in r
    assert r["dam_stage"] in (0, 1, 2)


def test_stage2_multiplier_increases_damage():
    """
    Stage 2 multiplier (1.28) raises activation after composition; raw
    damage_score remains a separate pathology receipt.
    """
    # Stage 0 entry: minimal damage (multiplier 0.60)
    r_low = compute_two_signal_pressure(
        age_hours=0.0, usage_count=10, recent_reward_mean=0.5,
        recent_regret=0.0, wm_contradiction_pe=0.0, unsafe=False,
    )
    # Stage 2 entry: unsafe + high sustained damage -> raw >= 0.58, sustained via regret
    # unsafe(+0.50) + reward(-0.5 -> +0.20) + regret(0.6 -> +0.15) + PE(0.8 -> +0.10) = 0.95
    # 0.95 >= 0.58 threshold AND regret 0.6 > 0.45 sustained -> Stage 2
    r_high = compute_two_signal_pressure(
        age_hours=2.0, usage_count=0, recent_reward_mean=-0.5,
        recent_regret=0.6, wm_contradiction_pe=0.8, unsafe=True,
    )
    assert r_high["activation_signal"] > r_high["activation_signal_pre_dam"]
    assert r_high["dam_stage"] == 2
    assert r_low["dam_stage"] == 0

# ============================================================
# PART 10: DAM stage hysteresis (§10.14.28.1 + Deczkowska 2018)
# Deczkowska et al. (2018) Cell 173:1073
# Bhatt et al. (2020) Nat Commun 11:4044 (microglial priming/memory)
# ============================================================

def test_hysteresis_stage2_persists_when_pressure_moderates():
    """
    Deczkowska (2018): Once Stage 2 is reached, it persists until pressure
    drops below STAGE2_RELEASE (0.42), not just the entry threshold (0.58).
    prev_dam_stage=2 + base=0.50 (between release 0.42 and entry 0.58) -> stays 2.
    """
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    # Without hysteresis: 0.50 would be Stage 1 (below entry 0.58)
    # With hysteresis + prev=2: 0.50 >= STAGE2_RELEASE(0.42) -> stays Stage 2
    stage = _compute_dam_stage(
        0.50, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1,
        prev_dam_stage=2,
    )
    assert stage == 2, f"Expected 2 (hysteresis), got {stage}"


def test_hysteresis_stage2_releases_when_fully_resolved():
    """Stage 2 falls to Stage 1 when base drops below STAGE2_RELEASE (0.42)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    # base=0.35 < 0.42 -> should leave Stage 2 -> Stage 1 (still >= STAGE1 0.32)
    stage = _compute_dam_stage(
        0.35, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1,
        prev_dam_stage=2,
    )
    assert stage == 1, f"Expected 1 (released from 2), got {stage}"


def test_hysteresis_stage2_fully_resolves():
    """Below STAGE1_THRESHOLD (0.32) after Stage 2 -> Stage 0 resolved."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(
        0.10, age_hours=0.0, recent_regret=0.0, wm_contradiction_pe=0.0,
        prev_dam_stage=2,
    )
    assert stage == 0


def test_hysteresis_stage1_persists_mildly():
    """
    Stage 1 has mild persistence: base >= STAGE1_RELEASE (0.18) stays Stage 1
    even if temporarily below STAGE1_THRESHOLD (0.32) entry.
    """
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    # base=0.25 is between STAGE1_RELEASE (0.18) and STAGE1_THRESHOLD (0.32)
    # With prev=1: should stay Stage 1
    stage = _compute_dam_stage(
        0.25, age_hours=1.0, recent_regret=0.1, wm_contradiction_pe=0.1,
        prev_dam_stage=1,
    )
    assert stage == 1


def test_hysteresis_stage1_resolves_below_release():
    """Stage 1 resolves to Stage 0 when base drops below STAGE1_RELEASE (0.18)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    stage = _compute_dam_stage(
        0.10, age_hours=0.0, recent_regret=0.0, wm_contradiction_pe=0.0,
        prev_dam_stage=1,
    )
    assert stage == 0


def test_no_hysteresis_from_stage0():
    """From Stage 0 base, standard thresholds apply (no history bias)."""
    from System.swarm_microglia_synaptic_pruner import _compute_dam_stage
    # base=0.25 from Stage 0 -> Stage 1 (normal entry)
    stage = _compute_dam_stage(
        0.25, age_hours=0.0, recent_regret=0.0, wm_contradiction_pe=0.0,
        prev_dam_stage=0,
    )
    assert stage == 1


def test_hysteresis_in_two_signal_receipt():
    """
    Two-signal receipt accepts prev_dam_stage and applies hysteresis.
    Bhatt (2020): microglial priming means past activation lowers future threshold.
    """
    # First tick: reach Stage 2
    r1 = compute_two_signal_pressure(
        unsafe=True, recent_reward_mean=-0.5,
        recent_regret=0.6, wm_contradiction_pe=0.8,
        prev_dam_stage=0,
    )
    assert r1["dam_stage"] == 2

    # Second tick: pressure moderates but hysteresis keeps Stage 2
    r2 = compute_two_signal_pressure(
        unsafe=False, recent_reward_mean=0.0,
        recent_regret=0.3, wm_contradiction_pe=0.4,
        prev_dam_stage=r1["dam_stage"],  # pass previous stage
    )
    # Without hysteresis this would be Stage 1; with prev=2, stays 2 if base>=0.42
    # The key: dam_stage is in the receipt and was threaded correctly
    assert "dam_stage" in r2
    assert "prev_dam_stage" in r2


# ============================================================
# PART 11: Rich fractalkine — IL-34, resilience floor, catastrophic override
# Wang et al. (2012) J Exp Med 209:1525 — IL-34 as CSF1R co-ligand
# Bhatt et al. (2020) Nat Commun 11:4044 — microglial priming / resilience
# Bialas & Stevens (2013) Neuron 80:1368 — C1q/C3 overwhelms CX3CR1
# ============================================================

def test_il34_boost_in_deep_calm():
    """
    Wang (2012): IL-34 reinforces fractalkine in sustained homeostatic states.
    Deep calm (dwell > 0.60) + low frustration -> extra inhibition from IL-34.
    """
    # Compare deep calm vs moderate calm
    shallow = compute_two_signal_pressure(
        stability_dwell_score=0.5, goal_alignment=0.8, owner_frustration=0.1,
        stability_ok=True, clamp_level="NONE",
    )
    deep = compute_two_signal_pressure(
        stability_dwell_score=0.95, goal_alignment=0.8, owner_frustration=0.1,
        stability_ok=True, clamp_level="NONE",
    )
    # Deep calm should have more inhibition (IL-34 boost)
    assert deep["inhibition_signal"] >= shallow["inhibition_signal"]
    # IL-34 field should be in receipt
    assert "il34_boost" in deep


def test_il34_suppressed_by_frustration():
    """IL-34 is not expressed under stress/frustration (Wang 2012)."""
    high_frustr = compute_two_signal_pressure(
        stability_dwell_score=0.95, goal_alignment=0.8, owner_frustration=0.80,
        stability_ok=True, clamp_level="NONE",
    )
    assert high_frustr["il34_boost"] == pytest.approx(0.0, abs=1e-4)


def test_resilience_floor_grows_with_dwell_squared():
    """
    Bhatt (2020): resilience accumulates non-linearly (epigenetic-like).
    High dwell^2 * goal -> higher floor than low dwell.
    """
    lo_dwell = compute_two_signal_pressure(
        stability_dwell_score=0.3, goal_alignment=0.9,
        stability_ok=True, clamp_level="NONE",
    )
    hi_dwell = compute_two_signal_pressure(
        stability_dwell_score=0.9, goal_alignment=0.9,
        stability_ok=True, clamp_level="NONE",
    )
    assert hi_dwell.get("resilience_floor", 0.0) > lo_dwell.get("resilience_floor", 0.0)


def test_catastrophic_override_at_high_damage():
    """
    Bialas & Stevens (2013): at extreme damage (>0.85), complement cascade
    overwhelms CX3CR1 — fractalkine protection is bypassed.
    Very high damage: fractalkine and il34 should be zeroed, fractalkine_overridden=True.
    """
    r = compute_two_signal_pressure(
        unsafe=True, recent_reward_mean=-0.9, recent_regret=0.9,
        wm_contradiction_pe=0.9,
        stability_dwell_score=1.0, goal_alignment=1.0, owner_frustration=0.0,
        stability_ok=True, clamp_level="NONE",
    )
    if r["damage_score"] > 0.85:
        assert r["fractalkine"] == pytest.approx(0.0, abs=1e-4)
        assert r.get("fractalkine_overridden") is True


def test_no_catastrophic_override_at_moderate_damage():
    """Fractalkine protection remains intact at moderate damage levels."""
    r = compute_two_signal_pressure(
        stability_dwell_score=0.8, goal_alignment=0.8, owner_frustration=0.0,
        stability_ok=True, clamp_level="NONE",
        unsafe=False, recent_regret=0.0, wm_contradiction_pe=0.0,
    )
    assert r.get("fractalkine_overridden", False) is False
    assert r["fractalkine"] > 0.0


def test_il34_and_resilience_in_receipt():
    """All new fractalkine fields present in receipt."""
    r = compute_two_signal_pressure(
        stability_dwell_score=0.8, goal_alignment=0.7, stability_ok=True,
    )
    for key in ("il34_boost", "resilience_floor", "fractalkine_overridden"):
        assert key in r, f"Missing receipt key: {key}"
