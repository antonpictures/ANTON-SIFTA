"""Tests for HiggsParticleSwimmer — the numpy particle organ.

Architect 2026-05-13 doctrine:
    Treat swimmers as literal particles. Give them (x,y), velocity,
    coupling strength. Mass = 1 + coupling × |phi|. Gradient force
    from the field pulls them. Free swimmers diffuse fast; coupled
    ones get heavy and slow.

These tests guard:
    - effective mass climbs monotonically with coupling
    - mobility falls monotonically with coupling at the end of a long run
    - the 1000-step experiment writes a HIGGS_PARTICLE_MOBILITY receipt
      with the right truth labels
    - the mobility ratio strong/free is well below 1 (mass spectrum
      visible in the headline number)
    - positions stay inside the torus
"""
import json
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    HiggsFieldConfig,
    HiggsParticleSwimmer,
    HiggsStigmergyField,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_PARTICLE,
    phi_as_array,
    run_particle_higgs_experiment,
)


@pytest.fixture
def relaxed_field():
    f = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=20, height=14))
    f.relax(160)
    return f


def test_swimmer_mass_climbs_with_coupling(relaxed_field):
    phi = phi_as_array(relaxed_field)
    free = HiggsParticleSwimmer(n=20, coupling=0.0, field_shape=phi.shape, seed=31)
    weak = HiggsParticleSwimmer(n=20, coupling=1.0, field_shape=phi.shape, seed=32)
    strong = HiggsParticleSwimmer(n=20, coupling=4.0, field_shape=phi.shape, seed=33)
    for _ in range(60):
        relaxed_field.step()
        phi = phi_as_array(relaxed_field)
        free.step(phi)
        weak.step(phi)
        strong.step(phi)
    assert free.mean_mass() == pytest.approx(1.0, abs=1e-9)
    assert weak.mean_mass() > free.mean_mass() + 0.5
    assert strong.mean_mass() > weak.mean_mass() + 1.5


def test_swimmer_mobility_drops_with_coupling(relaxed_field):
    phi = phi_as_array(relaxed_field)
    free = HiggsParticleSwimmer(n=30, coupling=0.0, field_shape=phi.shape, seed=41)
    strong = HiggsParticleSwimmer(n=30, coupling=4.0, field_shape=phi.shape, seed=42)
    # Warm up — the very first step has too much initial-velocity noise to
    # compare meaningfully.
    for _ in range(200):
        relaxed_field.step()
        phi = phi_as_array(relaxed_field)
        free.step(phi)
        strong.step(phi)
    assert strong.mobility() < free.mobility()
    # The strong swimmers should be at least 1.5x slower in steady state.
    assert free.mobility() / max(strong.mobility(), 1e-9) > 1.5


def test_swimmer_positions_stay_in_torus(relaxed_field):
    phi = phi_as_array(relaxed_field)
    h, w = phi.shape
    swimmers = HiggsParticleSwimmer(
        n=50, coupling=1.0, field_shape=(h, w), seed=99,
        thermal_kick=2.0,  # crank up noise to try to push them out
    )
    for _ in range(300):
        relaxed_field.step()
        phi = phi_as_array(relaxed_field)
        swimmers.step(phi)
    assert (swimmers.pos[:, 0] >= 0).all()
    assert (swimmers.pos[:, 0] < w).all()
    assert (swimmers.pos[:, 1] >= 0).all()
    assert (swimmers.pos[:, 1] < h).all()


def test_run_particle_higgs_experiment_writes_truth_labeled_receipt(tmp_path):
    result = run_particle_higgs_experiment(
        couplings=(0.0, 1.0, 4.0),
        n_per_band=15,
        field_config=HiggsFieldConfig(seed=13, width=20, height=14),
        relax_steps=140,
        swimmer_steps=300,
        sample_every=100,
        state_root=tmp_path,
        write=True,
        seed=17,
    )
    assert result["truth_label"] == TRUTH_LABEL_PARTICLE
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert "no OBSERVED Higgs bosons" in result["truth_boundary"]
    assert result["final_mobility_ratio_strong_over_free"] is not None
    assert result["final_mobility_ratio_strong_over_free"] < 1.0
    assert len(result["samples"]) >= 3

    # Receipt landed on disk.
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "HIGGS_PARTICLE_MOBILITY"
    assert row["truth_label"] == TRUTH_LABEL_PARTICLE
    assert row["truth_boundary"] == TRUTH_BOUNDARY
    assert row["payload"]["no_particle_physics_claim"] is True


def test_swimmer_state_dict_shape(relaxed_field):
    s = HiggsParticleSwimmer(n=5, coupling=1.5, field_shape=(14, 20), seed=1, name="probe")
    relaxed_field.step()
    s.step(phi_as_array(relaxed_field))
    st = s.state()
    assert st["name"] == "probe"
    assert st["n"] == 5
    assert st["coupling"] == 1.5
    assert "mean_mass" in st and "mobility" in st and "steps" in st
    assert st["steps"] == 1


def test_swimmer_rejects_wrong_phi_shape():
    s = HiggsParticleSwimmer(n=3, coupling=1.0, field_shape=(14, 20), seed=1)
    bad = np.zeros((10, 10))
    with pytest.raises(ValueError):
        s.step(bad)
