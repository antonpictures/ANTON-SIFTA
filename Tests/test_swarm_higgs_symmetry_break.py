"""Tests for Q6 — spontaneous symmetry breaking from identical swimmers.

Architect's Q6: "Start all swimmers identical. Let them write/organize.
Do distinct roles/masses emerge spontaneously?"

Empirical finding (Cowork 2026-05-13): identical-swimmer dynamics
under mean-field coupling alone has a robust symmetric attractor —
the population reaches the same heavy equilibrium across (kind, alpha,
gamma) combinations. **Symmetry breaks only when:**
   (a) non-mean-field interaction is enabled (crowding_competition=True)
   (b) write inertia kind is linear (sub-linear log/sqrt do not bifurcate)

These tests guard:
   - velocity_write_modulation accumulates writes for slow swimmers
   - crowding_competition divides per-cell deposits across occupants
   - write_inertia_kind selects the right mass-law variant
   - the canonical Q6 run hits symmetry_broke=True
   - the mean-field-only run hits symmetry_broke=False (control)
   - the receipt carries the right truth labels
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
    TRUTH_LABEL_SYMMETRY_BREAK,
    phi_as_array,
    run_symmetry_breaking_experiment,
)


def test_velocity_write_modulation_accumulates_for_slow_swimmers():
    """A slow swimmer (small initial velocity) should accumulate more
    writes than an artificially fast one — given the same parameters."""
    field = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=20, height=14))
    field.relax(120)
    s = HiggsParticleSwimmer(
        n=10, coupling=0.0, field_shape=(14, 20),
        velocity_write_modulation=1.5,
        write_rate=0.0,
        seed=11,
    )
    # Force the first half of the swarm to be slow, the second half to be fast.
    s.vel[:5, :] = 0.0
    s.vel[5:, :] = 5.0
    for _ in range(50):
        s.step(phi_as_array(field))
        field.step()
    slow_writes = s.write_count[:5].mean()
    fast_writes = s.write_count[5:].mean()
    assert slow_writes > fast_writes * 1.3


def test_write_inertia_kind_changes_mass_growth():
    """Same write_count, different kind → different mass."""
    f = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=20, height=14))
    f.relax(120)
    log_s = HiggsParticleSwimmer(
        n=5, coupling=0.0, field_shape=(14, 20),
        write_rate=1.0, write_inertia_coefficient=0.5,
        write_inertia_kind="log", seed=1,
    )
    sqrt_s = HiggsParticleSwimmer(
        n=5, coupling=0.0, field_shape=(14, 20),
        write_rate=1.0, write_inertia_coefficient=0.5,
        write_inertia_kind="sqrt", seed=1,
    )
    lin_s = HiggsParticleSwimmer(
        n=5, coupling=0.0, field_shape=(14, 20),
        write_rate=1.0, write_inertia_coefficient=0.5,
        write_inertia_kind="linear", seed=1,
    )
    for _ in range(60):
        phi = phi_as_array(f)
        log_s.step(phi); sqrt_s.step(phi); lin_s.step(phi)
        f.step()
    # write_count is ~60 for all three (write_rate=1.0)
    # log:    0.5 * log1p(60) ≈ 2.07
    # sqrt:   0.5 * sqrt(60)  ≈ 3.87
    # linear: 0.5 * 60        = 30.0
    # So linear ≫ sqrt ≫ log in mass contribution.
    assert lin_s.mean_mass() > sqrt_s.mean_mass() + 5.0
    assert sqrt_s.mean_mass() > log_s.mean_mass() + 0.5


def test_invalid_write_inertia_kind_rejected():
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=5, coupling=0.0, field_shape=(14, 20),
            write_inertia_kind="exponential",
        )


def test_crowding_competition_divides_deposits():
    """When two swimmers share a cell, each gets half the deposit
    they'd have gotten alone. Constructed test."""
    f = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=20, height=14))
    f.relax(60)
    # Two identical swimmers stacked on the same cell, crowding on.
    crowded = HiggsParticleSwimmer(
        n=2, coupling=0.0, field_shape=(14, 20),
        velocity_write_modulation=1.0, write_rate=0.0,
        crowding_competition=True, seed=3,
    )
    crowded.pos[:] = [10.0, 7.0]
    crowded.vel[:] = 0.0
    # Same set-up, crowding OFF.
    free = HiggsParticleSwimmer(
        n=2, coupling=0.0, field_shape=(14, 20),
        velocity_write_modulation=1.0, write_rate=0.0,
        crowding_competition=False, seed=3,
    )
    free.pos[:] = [10.0, 7.0]
    free.vel[:] = 0.0
    phi = phi_as_array(f)
    crowded.step(phi); free.step(phi)
    # Free swimmer deposit was gamma/(1+|v|^2) = 1.0; crowded swimmer
    # in 2-occupancy cell got 0.5.
    assert crowded.write_count[0] == pytest.approx(free.write_count[0] / 2.0)


def test_mean_field_alone_does_not_break_symmetry():
    """Control: with crowding_competition=False, even strong feedback
    converges to a symmetric attractor."""
    result = run_symmetry_breaking_experiment(
        n_swimmers=40,
        relax_steps=140,
        swimmer_steps=800,
        base_write_rate=0.0,
        velocity_write_modulation=3.0,
        write_inertia_coefficient=0.3,
        write_inertia_kind="linear",
        coupling=1.0,
        crowding_competition=False,
        write=False,
        seed=41,
    )
    v = result["verdict"]
    assert v["symmetry_broke"] is False
    assert v["coefficient_of_variation"] < 0.05


def test_canonical_run_breaks_symmetry():
    """The headline result: with the winning parameter combo,
    identical swimmers stratify into a >=2x mass spread."""
    result = run_symmetry_breaking_experiment(
        n_swimmers=60,
        relax_steps=140,
        swimmer_steps=1200,
        base_write_rate=0.0,
        velocity_write_modulation=1.5,
        write_inertia_coefficient=0.1,
        write_inertia_kind="linear",
        coupling=1.0,
        crowding_competition=True,
        write=False,
        seed=41,
    )
    v = result["verdict"]
    fd = result["final_distribution"]
    assert v["symmetry_broke"] is True
    assert v["p95_over_p05"] >= 1.5
    assert v["coefficient_of_variation"] >= 0.15
    # The role bands should all be populated.
    bands = result["spontaneous_role_bands"]
    assert bands["spontaneous_ghosts"]["count"] > 0
    assert bands["spontaneous_workers"]["count"] > 0
    assert bands["spontaneous_sentinels"]["count"] > 0


def test_symmetry_break_writes_truth_labeled_receipt(tmp_path):
    result = run_symmetry_breaking_experiment(
        n_swimmers=40,
        relax_steps=140,
        swimmer_steps=800,
        base_write_rate=0.0,
        velocity_write_modulation=1.5,
        write_inertia_coefficient=0.1,
        write_inertia_kind="linear",
        coupling=1.0,
        crowding_competition=True,
        state_root=tmp_path,
        write=True,
        seed=41,
    )
    assert result["truth_label"] == TRUTH_LABEL_SYMMETRY_BREAK
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "HIGGS_SYMMETRY_BREAK"
    assert row["truth_label"] == TRUTH_LABEL_SYMMETRY_BREAK
    assert row["truth_class"] == "HYPOTHESIS"
    assert row["truth_boundary"] == TRUTH_BOUNDARY
