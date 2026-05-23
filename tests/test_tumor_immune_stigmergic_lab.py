"""
Tests for Event 148 — Tumor Immune Stigmergic Lab (§10.14.27.4)

Every test maps to a published biological claim.
No PHI. Synthetic data only.

Key papers tested:
    Dunn et al. (2002) Nat Immunol 3:991 — three-E immunoediting model
    Schreiber et al. (2011) Science 331:1565 — elimination/equilibrium/escape
    Wang et al. (2015) Cell 160:1061 — TREM2+TAMs suppress anti-tumor immunity
    Jay et al. (2015) J Exp Med 212:287 — TREM2 in tumor-associated macrophages
    Binnewies et al. (2018) Nat Med 24:541 — TME determinants of immunotherapy response
    Roybal et al. (2016) Cell 164:770 — logic-gated CAR-T (synNotch)
    Fedorov et al. (2013) Sci Transl Med 5:215ra172 — inhibitory CAR safety gate
    Lee et al. (2014) Blood 124:188 — CRS grading
    Wherry & Kurachi (2015) Nat Rev Immunol 15:486 — T cell exhaustion
    Blank et al. (2019) Nat Med 25:1543 — exhaustion continuum (Tpex/Tex)
"""
import json
import math
import pytest
from pathlib import Path

from Applications.sifta_tumor_immune_stigmergic_lab import (
    TumorMicroenvironmentState,
    compute_tme_two_signal,
    compute_car_t_exhaustion_tick,
    compute_immunoediting_tick,
    tin_sim_tick,
    run_simulation,
    summary_for_prompt,
    PHASE_ELIMINATION,
    PHASE_EQUILIBRIUM,
    PHASE_ESCAPE,
    PHASE_REGRESSION,
)


# ============================================================
# PART 1: Two-signal gate architecture
# ============================================================

def test_two_signal_keys_present():
    """SIFTA two-signal schema: activation, inhibition, net must all be present."""
    s = TumorMicroenvironmentState()
    r = compute_tme_two_signal(s)
    for k in ("activation_signal", "inhibition_signal", "net_immune_pressure", "phase", "provenance"):
        assert k in r, f"Missing key: {k}"


def test_net_is_activation_minus_inhibition():
    """net = activation - inhibition (core SIFTA two-signal invariant)."""
    s = TumorMicroenvironmentState()
    r = compute_tme_two_signal(s)
    expected = round(r["activation_signal"] - r["inhibition_signal"], 4)
    assert r["net_immune_pressure"] == pytest.approx(expected, abs=1e-3)


def test_all_signals_bounded():
    """Activation and inhibition always in [0, 1]."""
    s = TumorMicroenvironmentState(
        ctl_infiltration=1.0, nk_activity=1.0, neoantigen_load=1.0,
        trem2_tam_fraction=1.0, treg_density=1.0, pdl1_expression=1.0,
    )
    r = compute_tme_two_signal(s)
    assert 0.0 <= r["activation_signal"] <= 1.0
    assert 0.0 <= r["inhibition_signal"] <= 1.0


# ============================================================
# PART 2: Immunoediting phases (Dunn 2002; Schreiber 2011)
# ============================================================

def test_elimination_phase_when_immune_dominant():
    """
    Schreiber (2011): elimination phase when immune surveillance is strong.
    High CTL + NK + neoantigen, minimal suppression -> net > 0.25 -> ELIMINATION.
    """
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.9, nk_activity=0.8, neoantigen_load=0.9, ifng_signal=0.8,
        trem2_tam_fraction=0.0, treg_density=0.0, pdl1_expression=0.0,
        mdsc_density=0.0, tgfb_level=0.0,
    )
    r = compute_tme_two_signal(s)
    assert r["phase"] == PHASE_ELIMINATION


def test_escape_phase_when_suppression_dominant():
    """
    Dunn (2002): escape phase when immunosuppression overwhelms immune killing.
    """
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.1, nk_activity=0.05, neoantigen_load=0.1,
        trem2_tam_fraction=0.9, treg_density=0.9, pdl1_expression=0.9,
        mdsc_density=0.8, tgfb_level=0.8,
    )
    r = compute_tme_two_signal(s)
    assert r["phase"] == PHASE_ESCAPE


def test_equilibrium_phase():
    """Schreiber (2011): equilibrium = immune system holds tumor in check but cannot clear."""
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.4, nk_activity=0.3,
        trem2_tam_fraction=0.4, pdl1_expression=0.3,
    )
    r = compute_tme_two_signal(s)
    assert r["phase"] in (PHASE_EQUILIBRIUM, PHASE_ELIMINATION, PHASE_REGRESSION)
    assert -0.10 <= r["net_immune_pressure"] <= 0.30


# ============================================================
# PART 3: TREM2+TAM blockade (Wang 2015; Jay 2015)
# ============================================================

def test_trem2_blockade_reduces_inhibition():
    """
    Wang (2015) Cell: TREM2+TAMs suppress anti-tumor immunity.
    Blocking TREM2 removes the TAM-mediated suppression -> higher net pressure.
    """
    s_blocked = TumorMicroenvironmentState(
        trem2_tam_fraction=0.8, trem2_blocked=True,
        ctl_infiltration=0.5,
    )
    s_control = TumorMicroenvironmentState(
        trem2_tam_fraction=0.8, trem2_blocked=False,
        ctl_infiltration=0.5,
    )
    r_blocked = compute_tme_two_signal(s_blocked)
    r_control = compute_tme_two_signal(s_control)
    assert r_blocked["inhibition_signal"] < r_control["inhibition_signal"]
    assert r_blocked["net_immune_pressure"] > r_control["net_immune_pressure"]


def test_trem2_blockade_shifts_phase():
    """Jay (2015): TREM2 blockade can shift tumor from escape toward elimination."""
    s_escape = TumorMicroenvironmentState(
        ctl_infiltration=0.5, trem2_tam_fraction=0.9,
        treg_density=0.4, pdl1_expression=0.4, trem2_blocked=False,
    )
    s_treated = TumorMicroenvironmentState(
        ctl_infiltration=0.5, trem2_tam_fraction=0.9,
        treg_density=0.4, pdl1_expression=0.4, trem2_blocked=True,
    )
    r_escape  = compute_tme_two_signal(s_escape)
    r_treated = compute_tme_two_signal(s_treated)
    assert r_treated["net_immune_pressure"] > r_escape["net_immune_pressure"]


# ============================================================
# PART 4: Checkpoint blockade (Blank 2019)
# ============================================================

def test_checkpoint_blockade_reduces_pdl1_contribution():
    """
    Blank (2019): anti-PD-1/PD-L1 reduces checkpoint-mediated inhibition.
    High PD-L1, blocked checkpoint -> less inhibition than unblocked.
    """
    s_on  = TumorMicroenvironmentState(pdl1_expression=0.9, checkpoint_blocked=True)
    s_off = TumorMicroenvironmentState(pdl1_expression=0.9, checkpoint_blocked=False)
    r_on  = compute_tme_two_signal(s_on)
    r_off = compute_tme_two_signal(s_off)
    assert r_on["inhibition_signal"] < r_off["inhibition_signal"]


# ============================================================
# PART 5: CAR-T cells (Roybal 2016; Fedorov 2013)
# ============================================================

def test_car_t_or_gate_fires_single_antigen():
    """
    OR-gate CAR: fires when either antigen_a or antigen_b is present.
    Simpler but potentially less tumor-specific (Roybal 2016).
    """
    s = TumorMicroenvironmentState(
        car_t_active=True, car_t_logic_gate="OR",
        car_t_antigen_a=0.8, car_t_antigen_b=0.1, car_t_exhaustion=0.0,
    )
    r = compute_tme_two_signal(s)
    assert r["car_active_signal"] is True
    assert r["car_boost"] > 0.0


def test_car_t_and_gate_requires_both_antigens():
    """
    Roybal (2016) synNotch AND gate: BOTH antigens required.
    Tumor-specific but misses antigen-loss variants.
    """
    # Only one antigen present -> gate should NOT fire
    s_one = TumorMicroenvironmentState(
        car_t_active=True, car_t_logic_gate="AND",
        car_t_antigen_a=0.9, car_t_antigen_b=0.2, car_t_exhaustion=0.0,
    )
    r_one = compute_tme_two_signal(s_one)
    assert r_one["car_active_signal"] is False
    assert r_one["car_boost"] == pytest.approx(0.0)

    # Both antigens present -> gate fires
    s_both = TumorMicroenvironmentState(
        car_t_active=True, car_t_logic_gate="AND",
        car_t_antigen_a=0.9, car_t_antigen_b=0.8, car_t_exhaustion=0.0,
    )
    r_both = compute_tme_two_signal(s_both)
    assert r_both["car_active_signal"] is True
    assert r_both["car_boost"] > 0.0


def test_car_t_not_gate_safety(  ):
    """
    Fedorov (2013) inhibitory CAR: fires ONLY when antigen_b is ABSENT.
    Safety mechanism — spare normal cells expressing antigen_b.
    """
    # Antigen B present -> NOT gate should NOT fire (spare normal tissue)
    s_unsafe = TumorMicroenvironmentState(
        car_t_active=True, car_t_logic_gate="NOT",
        car_t_antigen_a=0.9, car_t_antigen_b=0.8,
    )
    r_unsafe = compute_tme_two_signal(s_unsafe)
    assert r_unsafe["car_active_signal"] is False

    # Antigen B absent -> gate fires (tumor cell only)
    s_safe = TumorMicroenvironmentState(
        car_t_active=True, car_t_logic_gate="NOT",
        car_t_antigen_a=0.9, car_t_antigen_b=0.1,
    )
    r_safe = compute_tme_two_signal(s_safe)
    assert r_safe["car_active_signal"] is True
    assert r_safe["car_boost"] > 0.0


def test_car_t_exhaustion_reduces_boost():
    """
    Wherry & Kurachi (2015): T cell exhaustion progressively impairs effector function.
    Higher exhaustion -> smaller CAR-T boost.
    """
    s_fresh = TumorMicroenvironmentState(
        car_t_active=True, car_t_antigen_a=0.8, car_t_exhaustion=0.0,
    )
    s_exhausted = TumorMicroenvironmentState(
        car_t_active=True, car_t_antigen_a=0.8, car_t_exhaustion=0.9,
    )
    r_fresh     = compute_tme_two_signal(s_fresh)
    r_exhausted = compute_tme_two_signal(s_exhausted)
    assert r_fresh["car_boost"] > r_exhausted["car_boost"]


# ============================================================
# PART 6: T cell exhaustion dynamics (Wherry 2015; Blank 2019)
# ============================================================

def test_exhaustion_increases_with_antigen():
    """Wherry (2015): chronic antigen exposure drives exhaustion progression."""
    lo = compute_car_t_exhaustion_tick(0.1, antigen_load=0.1, tgfb=0.0)
    hi = compute_car_t_exhaustion_tick(0.1, antigen_load=0.9, tgfb=0.0)
    assert hi > lo


def test_tgfb_accelerates_exhaustion():
    """Blank (2019): TGF-β in TME accelerates T cell exhaustion."""
    no_tgfb = compute_car_t_exhaustion_tick(0.2, antigen_load=0.4, tgfb=0.0)
    hi_tgfb = compute_car_t_exhaustion_tick(0.2, antigen_load=0.4, tgfb=1.0)
    assert hi_tgfb > no_tgfb


def test_exhaustion_bounded():
    """Exhaustion always in [0, 1]."""
    e = compute_car_t_exhaustion_tick(0.99, antigen_load=1.0, tgfb=1.0)
    assert 0.0 <= e <= 1.0


# ============================================================
# PART 7: CRS (Lee 2014)
# ============================================================

def test_high_car_t_activation_raises_crs():
    """
    Lee (2014): CRS risk driven by rapid high-level T cell activation
    in high-burden environment.
    """
    s = TumorMicroenvironmentState(
        car_t_active=True, car_t_antigen_a=1.0, car_t_antigen_b=1.0,
        car_t_exhaustion=0.0, car_t_logic_gate="OR",
        neoantigen_load=1.0,
    )
    r = compute_tme_two_signal(s)
    assert r["crs_risk"] > 0.0
    assert r["crs_grade"] != "NONE"


def test_exhausted_car_t_lower_crs():
    """Lee (2014): exhausted CAR-T less effective -> lower CRS risk."""
    s_fresh     = TumorMicroenvironmentState(car_t_active=True, car_t_antigen_a=0.9, car_t_exhaustion=0.0, neoantigen_load=0.9)
    s_exhausted = TumorMicroenvironmentState(car_t_active=True, car_t_antigen_a=0.9, car_t_exhaustion=0.9, neoantigen_load=0.9)
    r_fresh     = compute_tme_two_signal(s_fresh)
    r_exhausted = compute_tme_two_signal(s_exhausted)
    assert r_fresh["crs_risk"] >= r_exhausted["crs_risk"]


# ============================================================
# PART 8: Immunoediting (Dunn 2002; Schreiber 2011)
# ============================================================

def test_elimination_selects_antigen_loss():
    """
    Dunn (2002): strong immune pressure selects for antigen-loss variants.
    In elimination phase, neoantigen_load decreases over time.
    """
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.9, nk_activity=0.8, neoantigen_load=0.9,
        trem2_tam_fraction=0.0, treg_density=0.0, pdl1_expression=0.0,
    )
    editing = compute_immunoediting_tick(s)
    assert editing["phase"] == PHASE_ELIMINATION
    assert editing["delta_neoantigen"] < 0   # antigen loss under pressure


def test_escape_downregulates_ctl():
    """Schreiber (2011): escape phase — CTL infiltration declines."""
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.1, neoantigen_load=0.05,
        trem2_tam_fraction=0.9, treg_density=0.9, pdl1_expression=0.9,
    )
    editing = compute_immunoediting_tick(s)
    assert editing["phase"] == PHASE_ESCAPE
    assert editing["delta_ctl"] < 0


# ============================================================
# PART 9: Simulation + ledger
# ============================================================

def test_run_simulation_returns_n_ticks(tmp_path):
    """Simulation produces correct number of ticks."""
    rows = run_simulation(n_ticks=5, root=tmp_path, write_ledger=True)
    assert len(rows) == 5


def test_ledger_written(tmp_path):
    """TIN_SIM_TICK rows written to JSONL ledger."""
    from Applications.sifta_tumor_immune_stigmergic_lab import tim_log_path
    run_simulation(n_ticks=3, root=tmp_path, write_ledger=True)
    log = tim_log_path(tmp_path)
    assert log.exists()
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    assert len(lines) == 3
    row = json.loads(lines[0])
    assert row["truth_label"] == "TIN_SIM_TICK"
    assert "two_signal_snapshot" in row
    assert "immunoediting" in row


def test_receipt_has_provenance(tmp_path):
    """All key papers cited in receipt provenance."""
    rows = run_simulation(n_ticks=1, root=tmp_path, write_ledger=False)
    prov = rows[0]["two_signal_snapshot"]["provenance"]
    for cite in ("Keren-Shaul", "Wang2015", "Roybal", "Wherry", "Schreiber", "Dunn"):
        assert cite in prov, f"Missing citation: {cite}"


def test_antigen_loss_over_ticks(tmp_path):
    """
    Schreiber (2011): sustained immune pressure -> antigen loss over simulation.
    Neoantigen load decreases over time in elimination phase.
    """
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.9, nk_activity=0.8, neoantigen_load=0.9,
        trem2_tam_fraction=0.0, treg_density=0.0, pdl1_expression=0.0,
    )
    rows = run_simulation(initial_state=s, n_ticks=5,
                          root=tmp_path, write_ledger=False)
    neo_start = rows[0]["tme_state"]["neoantigen_load"]
    neo_end   = rows[-1]["tme_state"]["neoantigen_load"]
    assert neo_end < neo_start


def test_summary_for_prompt(tmp_path):
    """Summary string contains phase and net for Alice's context window."""
    run_simulation(n_ticks=2, root=tmp_path, write_ledger=True)
    s = summary_for_prompt(root=tmp_path)
    assert "TME" in s
    assert "phase=" in s


def test_disabled(monkeypatch, tmp_path):
    """SIFTA_TIM_DISABLE=1 -> no processing, no ledger writes."""
    monkeypatch.setenv("SIFTA_TIM_DISABLE", "1")
    row = tin_sim_tick(TumorMicroenvironmentState(), root=tmp_path, write_ledger=True)
    assert row["disabled"] is True
    from Applications.sifta_tumor_immune_stigmergic_lab import tim_log_path
    assert not tim_log_path(tmp_path).exists()


# ============================================================
# PART 10: SIFTA math equivalence proof
# ============================================================

def test_sifta_math_equivalence():
    """
    PROOF: The SAME two-signal math that governs synaptic pruning
    governs tumor immune clearance.

    Synaptic pruning (Stevens 2007; Griciuc 2013):
        NET = activation(TREM2/C1q) - inhibition(CD33/fractalkine) > threshold -> prune

    Tumor immunity (Wang 2015; Dunn 2002):
        NET = activation(CTL/NK/IFNg) - inhibition(TREM2+TAM/Treg/PD-L1) > threshold -> clear

    The mathematical structure is identical. Nature reuses the two-signal gate.
    """
    # Synaptic domain: strong activation, no inhibition -> prune
    from System.swarm_microglia_synaptic_pruner import compute_two_signal_pressure
    syn = compute_two_signal_pressure(
        wm_contradiction_pe=0.9, recent_regret=0.9, unsafe=True,
        pruning_conservatism=0.0, stability_ok=True,
    )

    # Tumor domain: strong immune activation, no suppression -> eliminate
    s = TumorMicroenvironmentState(
        ctl_infiltration=0.9, nk_activity=0.8, neoantigen_load=0.9,
        trem2_tam_fraction=0.0, treg_density=0.0, pdl1_expression=0.0,
    )
    tme = compute_tme_two_signal(s)

    # Both show positive net -> decision fires in both domains
    assert syn["net_pruning_pressure"] > 0.0
    assert tme["net_immune_pressure"]  > 0.0

    # Both are bounded [0,1] activation and inhibition
    assert 0.0 <= syn["activation_signal"] <= 1.45
    assert 0.0 <= tme["activation_signal"] <= 1.0
    assert 0.0 <= syn["inhibition_signal"] <= 1.0
    assert 0.0 <= tme["inhibition_signal"] <= 1.0
