"""Tests for the §20.F killer-demo answering architect questions Q1/Q5/Q8/Q9.

    Q1 — "Participation → inertia"
    Q5 — "Organ-layer mass"
    Q8 — "Unified mass law m_eff = 1 + g|phi| + alpha·writes + beta·organs"
    Q9 — "Killer demo: ghost / worker / organ / sentinel — same force,
          different response = visible computational mass"

These tests guard the unified mass law and the killer-demo run.
"""
import json
import math
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    HiggsFieldConfig,
    HiggsParticleSwimmer,
    HiggsStigmergyField,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_KILLER_DEMO,
    phi_as_array,
    run_killer_demo_experiment,
)


def _relaxed(seed=29, w=20, h=14, steps=140):
    f = HiggsStigmergyField(HiggsFieldConfig(seed=seed, width=w, height=h))
    f.relax(steps)
    return f


# ── Q1: participation → inertia ───────────────────────────────────────────

def test_write_count_increases_with_write_rate():
    f = _relaxed()
    silent = HiggsParticleSwimmer(
        n=20, coupling=0.0, field_shape=(14, 20),
        write_rate=0.0, seed=5,
    )
    loud = HiggsParticleSwimmer(
        n=20, coupling=0.0, field_shape=(14, 20),
        write_rate=0.8, seed=5,
    )
    for _ in range(100):
        phi = phi_as_array(f)
        silent.step(phi)
        loud.step(phi)
        f.step()
    assert silent.write_count.sum() == 0
    assert loud.write_count.mean() > 50  # ~0.8 × 100


def test_writes_increase_effective_mass():
    """Two identical swimmers — one writes, one doesn't — coupling=0,
    no organs. The writer should end up heavier."""
    f = _relaxed()
    quiet = HiggsParticleSwimmer(
        n=20, coupling=0.0, field_shape=(14, 20),
        write_rate=0.0, write_inertia_coefficient=0.5, seed=7,
    )
    chatty = HiggsParticleSwimmer(
        n=20, coupling=0.0, field_shape=(14, 20),
        write_rate=0.6, write_inertia_coefficient=0.5, seed=7,
    )
    for _ in range(200):
        phi = phi_as_array(f)
        quiet.step(phi)
        chatty.step(phi)
        f.step()
    assert quiet.mean_mass() == pytest.approx(1.0, abs=1e-9)
    assert chatty.mean_mass() > 1.5


def test_writes_reduce_mobility_under_same_drive():
    """The Q1 punchline — more participation ⇒ less mobility."""
    f = _relaxed()
    free = HiggsParticleSwimmer(
        n=30, coupling=0.0, field_shape=(14, 20),
        write_rate=0.0, write_inertia_coefficient=0.5,
        drive_amplitude=1.0, seed=11,
    )
    heavy_writer = HiggsParticleSwimmer(
        n=30, coupling=0.0, field_shape=(14, 20),
        write_rate=0.7, write_inertia_coefficient=0.5,
        drive_amplitude=1.0, seed=11,
    )
    for _ in range(300):
        phi = phi_as_array(f)
        free.step(phi)
        heavy_writer.step(phi)
        f.step()
    assert free.mobility() > heavy_writer.mobility() * 1.5


# ── Q5: organ-layer mass ──────────────────────────────────────────────────

def test_organ_membership_adds_mass_with_no_writes_no_coupling():
    """Q5: an isolated swimmer has m=1.0; one in 4 organs (same code,
    no writes, no coupling) is heavier by exactly 4·beta."""
    f = _relaxed()
    isolated = HiggsParticleSwimmer(
        n=5, coupling=0.0, field_shape=(14, 20),
        write_rate=0.0, organ_memberships=(),
        organ_inertia_coefficient=0.25, seed=3,
    )
    embedded = HiggsParticleSwimmer(
        n=5, coupling=0.0, field_shape=(14, 20),
        write_rate=0.0,
        organ_memberships=("a", "b", "c", "d"),
        organ_inertia_coefficient=0.25, seed=3,
    )
    f.step()
    phi = phi_as_array(f)
    isolated.step(phi)
    embedded.step(phi)
    # m_eff = 1 + 0·phi + 0 + 0.25 · n_organs
    assert isolated.mean_mass() == pytest.approx(1.0, abs=1e-9)
    assert embedded.mean_mass() == pytest.approx(2.0, abs=1e-6)


# ── Q8: unified mass law ──────────────────────────────────────────────────

def test_unified_mass_law_matches_analytical_formula():
    """m_eff = 1 + g·|phi| + alpha · log(1+writes) + beta · n_organs"""
    f = _relaxed()
    s = HiggsParticleSwimmer(
        n=10, coupling=2.0, field_shape=(14, 20),
        write_rate=1.0,            # writes every step
        write_inertia_coefficient=0.3,
        organ_memberships=("a", "b", "c"),
        organ_inertia_coefficient=0.4,
        seed=9,
    )
    for _ in range(40):
        phi = phi_as_array(f)
        s.step(phi)
        f.step()
    # After 40 steps with write_rate=1.0 the mean write count is 40.
    expected_memory_term = 0.3 * math.log1p(40)
    expected_organ_term = 0.4 * 3
    # Field-coupling term is per-position; check that the AVERAGE
    # mass is at least the sum of the constant terms + 1.
    base_expected = 1.0 + expected_memory_term + expected_organ_term
    assert s.mean_mass() >= base_expected - 0.05
    # Upper bound: max contribution from field coupling is 2.0 * vev = 2.0
    assert s.mean_mass() <= base_expected + 2.1


# ── Q9: killer demo ───────────────────────────────────────────────────────

def test_run_killer_demo_writes_truth_labeled_receipt(tmp_path):
    result = run_killer_demo_experiment(
        n_per_type=20,
        relax_steps=140,
        swimmer_steps=400,
        drive_amplitude=1.0,
        state_root=tmp_path,
        write=True,
    )
    assert result["truth_label"] == TRUTH_LABEL_KILLER_DEMO
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert "no OBSERVED Higgs bosons" in result["truth_boundary"]

    # All four named types present.
    names = {s["name"] for s in result["swimmer_types"]}
    assert names == {"ghost", "worker", "organ", "sentinel"}

    # Visible computational mass should be True at default coefficients.
    assert result["visible_computational_mass"] is True
    assert result["mobility_spread"] > 0.01

    # Receipt on disk.
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "HIGGS_KILLER_DEMO"
    assert row["truth_label"] == TRUTH_LABEL_KILLER_DEMO
    assert row["truth_class"] == "HYPOTHESIS"
    assert row["truth_boundary"] == TRUTH_BOUNDARY


def test_killer_demo_orders_types_correctly(tmp_path):
    """Q9 success criterion: ghost lightest, sentinel heaviest by
    mean_mass; mobility orders in reverse."""
    result = run_killer_demo_experiment(
        n_per_type=20,
        relax_steps=140,
        swimmer_steps=400,
        drive_amplitude=1.0,
        state_root=tmp_path,
        write=False,
    )
    final = result["final_state"]
    masses = {k: final[k]["mean_mass"] for k in final}
    mobilities = {k: final[k]["mobility"] for k in final}

    # ghost is the only baseline at mass=1.0 exactly
    assert masses["ghost"] == pytest.approx(1.0, abs=1e-9)
    # sentinel has all three contributions → heaviest
    assert masses["sentinel"] >= masses["worker"]
    assert masses["sentinel"] >= masses["organ"]
    assert masses["sentinel"] > masses["ghost"]
    # mobilities order in reverse: heaviest moves least
    assert mobilities["sentinel"] < mobilities["ghost"]
    assert mobilities["organ"] < mobilities["ghost"]
    assert mobilities["worker"] < mobilities["ghost"]


# ── Constructor validation ────────────────────────────────────────────────

def test_swimmer_rejects_bad_write_rate():
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=5, coupling=0.0, field_shape=(14, 20),
            write_rate=-0.1,
        )
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=5, coupling=0.0, field_shape=(14, 20),
            write_rate=2.0,
        )


def test_swimmer_rejects_negative_inertia_coefficients():
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=5, coupling=0.0, field_shape=(14, 20),
            write_inertia_coefficient=-0.1,
        )
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=5, coupling=0.0, field_shape=(14, 20),
            organ_inertia_coefficient=-0.1,
        )


def test_state_dict_surfaces_new_fields():
    s = HiggsParticleSwimmer(
        n=5, coupling=1.0, field_shape=(14, 20),
        write_rate=0.5, write_inertia_coefficient=0.3,
        organ_memberships=("a", "b"),
        organ_inertia_coefficient=0.4,
        name="probe",
    )
    st = s.state()
    assert st["write_rate"] == 0.5
    assert st["write_inertia_coefficient"] == 0.3
    assert st["organ_memberships"] == ["a", "b"]
    assert st["organ_inertia_coefficient"] == 0.4
    assert st["mean_write_count"] == 0.0  # before any step
