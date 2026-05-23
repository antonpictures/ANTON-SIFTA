"""Tests for the Persistence Inertia Field — adaptive agent layer.

Architect 2026-05-13 doctrine update:
    The swimmers are dumb particles with memory weight. The next upgrade
    is local rules + emergence. Agents pick from a small set of behaviors
    and learn from contextual reward.

These tests guard:
   - AdaptivePolicySwarm initialises with a uniform policy over K behaviors
   - policy_entropy starts at log(K) and falls with learning
   - dominant_behavior_index converges (entropy collapses) under reward
   - roles_emerged signal in the receipt is honest
   - the receipt carries the right truth label and HYPOTHESIS class
   - constructor rejects bad inputs
"""
import json
import math
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    AdaptivePolicySwarm,
    HiggsFieldConfig,
    HiggsStigmergyField,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_ADAPTIVE,
    phi_as_array,
    run_adaptive_experiment,
)


def _relaxed_field(seed=37, w=20, h=14, steps=140):
    f = HiggsStigmergyField(HiggsFieldConfig(seed=seed, width=w, height=h))
    f.relax(steps)
    return f


def test_adaptive_swarm_initialises_uniform():
    """At t=0 the policy is uniform over K behaviors and entropy = log(K)."""
    swarm = AdaptivePolicySwarm(n=20, field_shape=(14, 20), seed=1)
    K = len(swarm.behavior_names)
    expected = math.log(K)
    assert swarm.policy_entropy() == pytest.approx(expected, abs=1e-9)
    # Every row of policy sums to 1
    sums = swarm.policy.sum(axis=1)
    assert np.allclose(sums, 1.0)


def test_adaptive_swarm_entropy_falls_under_reward():
    """After many steps the policy entropy must drop substantially."""
    f = _relaxed_field()
    swarm = AdaptivePolicySwarm(
        n=30, field_shape=(14, 20), seed=7,
        learning_rate=0.1,
    )
    initial_entropy = swarm.policy_entropy()
    for _ in range(500):
        f.step()
        swarm.step(phi_as_array(f))
    final_entropy = swarm.policy_entropy()
    assert final_entropy < initial_entropy * 0.5


def test_adaptive_swarm_role_counts_sum_to_n():
    swarm = AdaptivePolicySwarm(n=15, field_shape=(14, 20), seed=2)
    counts = swarm.role_counts()
    assert sum(counts.values()) == 15


def test_adaptive_swarm_dominant_behavior_distribution_non_uniform_after_run():
    """The whole point: identical agents end up with DIFFERENT dominant
    behaviors. The role-counts dict should not be a flat partition."""
    f = _relaxed_field()
    swarm = AdaptivePolicySwarm(
        n=60, field_shape=(14, 20), seed=11,
        learning_rate=0.06, coupling=1.0,
    )
    for _ in range(800):
        f.step()
        swarm.step(phi_as_array(f))
    counts = swarm.role_counts()
    # At least one behavior should dominate (max > 30% of agents) AND
    # at least one other should be non-empty.
    sorted_counts = sorted(counts.values(), reverse=True)
    assert sorted_counts[0] > swarm.n * 0.3
    assert sorted_counts[1] >= 1


def test_run_adaptive_experiment_writes_truth_labeled_receipt(tmp_path):
    result = run_adaptive_experiment(
        n_agents=40,
        relax_steps=140,
        swarm_steps=600,
        learning_rate=0.08,
        state_root=tmp_path,
        write=True,
    )
    assert result["truth_label"] == TRUTH_LABEL_ADAPTIVE
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert result["final_policy_entropy_nats"] < result["initial_policy_entropy_nats"]
    assert sum(result["final_role_counts"].values()) == 40

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "PERSISTENCE_INERTIA_FIELD_ADAPTIVE"
    assert row["truth_label"] == TRUTH_LABEL_ADAPTIVE
    assert row["truth_class"] == "HYPOTHESIS"
    assert row["truth_boundary"] == TRUTH_BOUNDARY


def test_canonical_adaptive_experiment_emerges_roles():
    """Canonical config from architect's GO. Expect roles_emerged=True
    and entropy way below the uniform baseline."""
    result = run_adaptive_experiment(
        n_agents=60,
        relax_steps=160,
        swarm_steps=1000,
        learning_rate=0.08,
        coupling=1.0,
        write_inertia_coefficient=0.1,
        write_inertia_kind="linear",
        write=False,
    )
    assert result["roles_emerged"] is True
    assert result["final_policy_entropy_nats"] < 0.5


def test_adaptive_swarm_rejects_bad_learning_rate():
    with pytest.raises(ValueError):
        AdaptivePolicySwarm(n=5, field_shape=(14, 20), learning_rate=0.0)
    with pytest.raises(ValueError):
        AdaptivePolicySwarm(n=5, field_shape=(14, 20), learning_rate=1.0)


def test_adaptive_swarm_rejects_bad_field_shape():
    with pytest.raises(ValueError):
        AdaptivePolicySwarm(n=5, field_shape=(2, 20))


def test_adaptive_step_rejects_wrong_phi_shape():
    swarm = AdaptivePolicySwarm(n=5, field_shape=(14, 20))
    with pytest.raises(ValueError):
        swarm.step(np.zeros((10, 10)))
