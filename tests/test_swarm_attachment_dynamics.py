"""Tests for swarm_attachment_dynamics V2.

V1 used positional bond-pull + mass relief and produced the wrong
polarity (bonded recovered SLOWER than control). V2 inverts the
mechanism: momentum sharing across bonded pairs + mass burden (heavier
inertia for bonded agents). These tests guard the V2 polarity so a
future "optimisation" doesn't quietly flip the sign and ship a
silently broken model.

Truth class: HYPOTHESIS — the tests verify that the implementation
matches the V2 design, not that the design is biologically accurate.
"""
import math

import pytest

np = pytest.importorskip("numpy")

from System.swarm_attachment_dynamics import (
    AttachmentDynamicsSwarm,
    run_attachment_experiment,
    TRUTH_LABEL,
)


# ── Static / shape tests ────────────────────────────────────────────

def test_truth_label_is_v2():
    """Guard against accidental V1 regression."""
    assert TRUTH_LABEL == "ATTACHMENT_DYNAMICS_V2"


def test_default_mechanism_is_momentum_share():
    s = AttachmentDynamicsSwarm(n=5, field_shape=(8, 8), seed=1)
    assert s._bond_mechanism == "momentum_share"
    # V1 fields renamed — burden, not relief
    assert hasattr(s, "_bond_mass_burden")
    assert not hasattr(s, "_bond_mass_relief")


def test_invalid_bond_mechanism_rejected():
    with pytest.raises(ValueError):
        AttachmentDynamicsSwarm(
            n=4, field_shape=(8, 8), seed=1, bond_mechanism="hug",
        )


def test_affinity_matrix_initially_zero():
    s = AttachmentDynamicsSwarm(n=6, field_shape=(8, 8), seed=1)
    assert s.affinity.shape == (6, 6)
    assert float(s.affinity.sum()) == 0.0


# ── Mechanism polarity ──────────────────────────────────────────────

def test_mass_burden_makes_bonded_agents_heavier_not_lighter():
    """V1 made bonded agents lighter. V2 makes them heavier. This test
    catches a polarity flip in either direction."""
    s = AttachmentDynamicsSwarm(
        n=4, field_shape=(8, 8), seed=1,
        affinity_growth=0.5, affinity_decay=0.0,
        bond_mass_burden=0.5, momentum_share_fraction=0.0,
    )
    base_mass = s._base_mass.copy()
    # Inject a strong bond directly into the matrix.
    s.affinity[0, 1] = s.affinity[1, 0] = 5.0
    # Step the swarm so the mass burden gets applied.
    from System.swarm_higgs_stigmergy_field import (
        HiggsFieldConfig, HiggsStigmergyField, phi_as_array,
    )
    field = HiggsStigmergyField(HiggsFieldConfig(seed=1, width=8, height=8))
    field.relax(50)
    s.step(phi_as_array(field))
    # Bonded agents 0 and 1 must be HEAVIER than their base mass.
    assert s.mass[0] >= base_mass[0], (
        f"agent 0 mass dropped from {base_mass[0]} to {s.mass[0]} — "
        "V2 polarity broken (this would be V1 mass relief)"
    )
    assert s.mass[1] >= base_mass[1]


def test_momentum_share_damps_velocity_difference():
    """Two strongly bonded agents with opposite velocities should see
    their velocity gap shrink after a momentum-share step."""
    s = AttachmentDynamicsSwarm(
        n=2, field_shape=(8, 8), seed=1,
        affinity_growth=0.0, affinity_decay=0.0,
        bond_mass_burden=0.0,  # isolate the momentum-share effect
        momentum_share_fraction=0.5,
    )
    # Force a strong bond between the two agents.
    s.affinity[0, 1] = s.affinity[1, 0] = 10.0
    # Set opposite velocities by hand.
    s._swarm.vel[0] = np.array([1.0, 0.0])
    s._swarm.vel[1] = np.array([-1.0, 0.0])
    pre_gap = float(np.linalg.norm(s._swarm.vel[0] - s._swarm.vel[1]))
    # Step the swarm.
    from System.swarm_higgs_stigmergy_field import (
        HiggsFieldConfig, HiggsStigmergyField, phi_as_array,
    )
    field = HiggsStigmergyField(HiggsFieldConfig(seed=1, width=8, height=8))
    field.relax(20)
    s.step(phi_as_array(field))
    post_gap = float(np.linalg.norm(s._swarm.vel[0] - s._swarm.vel[1]))
    # The momentum-share blend must REDUCE the gap, not increase it.
    assert post_gap < pre_gap, (
        f"momentum sharing failed to dampen velocity gap: "
        f"pre={pre_gap:.3f} post={post_gap:.3f}"
    )


# ── End-to-end experiment ───────────────────────────────────────────

@pytest.mark.parametrize("seed", [113, 217, 331])
def test_bonded_swarm_recovers_at_least_as_fast_as_control(seed):
    """V2's headline claim: bonded pairs recover from perturbation at
    least as fast as the unbonded control. We use 'at most as slow'
    (ttr_bonded <= ttr_control + small slack) because a single
    random seed isn't a 100% guarantee, but flipping the sign would
    be a catastrophic regression."""
    r = run_attachment_experiment(
        n_agents=40, bond_steps=600, recovery_steps=250,
        perturbation_amplitude=3.0, seed=seed, write=False,
    )
    tb = r["recovery_measurement"]["ttr_bonded_steps"]
    tc = r["recovery_measurement"]["ttr_control_steps"]
    # Allow a 5-step slack for stochastic wiggle, but no more.
    assert tb <= tc + 5, (
        f"V2 polarity regression at seed={seed}: bonded={tb} > "
        f"control={tc} (V1-style failure)."
    )


def test_run_attachment_experiment_returns_v2_metadata():
    r = run_attachment_experiment(
        n_agents=20, bond_steps=200, recovery_steps=80,
        perturbation_amplitude=2.0, seed=113, write=False,
    )
    assert r["truth_label"] == "ATTACHMENT_DYNAMICS_V2"
    assert r["mechanism"] == "momentum_share + mass_burden (V2)"
    assert "v1_history_note" in r
    assert "wrong polarity" in r["v1_history_note"].lower() or \
           "V1" in r["v1_history_note"]


def test_zero_bonds_branch_disables_mechanism():
    """The control branch in run_attachment_experiment must actually
    silence both the momentum-share and the mass-burden paths so the
    control truly is an unbonded baseline."""
    s = AttachmentDynamicsSwarm(n=5, field_shape=(8, 8), seed=1)
    s._affinity_growth = 0.0
    s._bond_pull_strength = 0.0
    s._bond_mass_burden = 0.0
    s._momentum_share_fraction = 0.0
    s._bond_mechanism = "none"
    # Step a few times — affinity must stay flat at zero and mass must
    # stay at base (not increased by burden, not reduced by relief).
    from System.swarm_higgs_stigmergy_field import (
        HiggsFieldConfig, HiggsStigmergyField, phi_as_array,
    )
    field = HiggsStigmergyField(HiggsFieldConfig(seed=1, width=8, height=8))
    field.relax(30)
    base = s._base_mass.copy()
    for _ in range(30):
        s.step(phi_as_array(field))
    assert float(s.affinity.sum()) == 0.0
    assert np.allclose(s.mass, base)
