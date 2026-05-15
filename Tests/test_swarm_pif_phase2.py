"""Phase-2 tests: Memory field (Q4), damage zones, Q7 collider, and the
generic perturbation harness.

All experiments are HYPOTHESIS class. Tests guard the mechanism and the
receipt format, not the magnitude of the finding (which depends on
seeds + parameters).
"""
import json
import math
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    AdaptivePolicySwarm,
    HiggsStigmergyField,
    HiggsFieldConfig,
    MemoryDrivenField,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_MEMORY_FIELD,
    TRUTH_LABEL_COLLIDER,
    phi_as_array,
    run_memory_field_experiment,
    run_collider_experiment,
)


# ── MemoryDrivenField (Q4) ────────────────────────────────────────────────

def test_memory_field_starts_at_zero_order_parameter():
    f = MemoryDrivenField()
    assert f.order_parameter == pytest.approx(0.0, abs=1e-9)


def test_memory_field_grows_on_deposit():
    f = MemoryDrivenField()
    f.deposit_at(np.array([5, 6, 7]), np.array([3, 3, 3]), amount=np.array([1.0, 1.0, 1.0]))
    f.step()
    assert f.order_parameter > 0.0


def test_memory_field_decays_without_deposits():
    f = MemoryDrivenField(MemoryDrivenField._Config(decay=0.2))
    f.deposit_at(10, 5, amount=10.0)
    f.step()
    before = f.order_parameter
    for _ in range(50):
        f.step()
    assert f.order_parameter < before * 0.1


def test_memory_field_phi_list_view_synced():
    """field.phi should be a list-of-lists that matches the array view."""
    f = MemoryDrivenField()
    f.deposit_at(4, 5, amount=2.0)
    f.step()
    arr = np.asarray(f.phi, dtype=float)
    assert arr.shape == (f.config.height, f.config.width)
    assert arr[5, 4] != 0.0


def test_run_memory_field_experiment_receipt(tmp_path):
    r = run_memory_field_experiment(
        n_swimmers=20, swimmer_steps=200, state_root=tmp_path, write=True,
    )
    assert r["truth_label"] == TRUTH_LABEL_MEMORY_FIELD
    assert r["truth_class"] == "HYPOTHESIS"
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["kind"] == "PERSISTENCE_INERTIA_FIELD_MEMORY"
    assert rows[0]["truth_boundary"] == TRUTH_BOUNDARY


# ── Damage zones / niche activation ───────────────────────────────────────

def test_damage_field_rejected_with_wrong_shape():
    with pytest.raises(ValueError):
        AdaptivePolicySwarm(
            n=5, field_shape=(14, 20),
            damage_field=np.zeros((10, 10)),
        )


def test_damage_field_increases_wander_and_flee_reward():
    """With damage covering the whole field, wander/flee rewards should
    exceed deposit/chase rewards."""
    f = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=20, height=14))
    f.relax(80)
    damage = np.full((14, 20), 1.0)
    swarm = AdaptivePolicySwarm(
        n=20, field_shape=(14, 20), seed=3,
        learning_rate=0.1, damage_field=damage,
    )
    swarm.step(phi_as_array(f))
    rewards = swarm._last_reward.mean(axis=0)
    # rewards is [wander, chase, deposit, flee]
    assert rewards[3] > rewards[2]  # flee > deposit in damaged terrain
    assert rewards[0] > rewards[2]  # wander > deposit in damaged terrain


# ── Q7 collider ───────────────────────────────────────────────────────────

def test_collider_experiment_receipt(tmp_path):
    r = run_collider_experiment(
        n_per_side=15, settle_steps=200, collision_steps=300,
        state_root=tmp_path, write=True,
    )
    assert r["truth_label"] == TRUTH_LABEL_COLLIDER
    assert r["truth_class"] == "HYPOTHESIS"
    # Pre-collision should report role counts summing to n_per_side
    pre_a = r["pre_collision"]["civilization_a"]["role_counts"]
    pre_b = r["pre_collision"]["civilization_b"]["role_counts"]
    assert sum(pre_a.values()) == 15
    assert sum(pre_b.values()) == 15
    # Mass exchange must be non-negative and at most n_per_side
    me = r["mass_exchange"]
    assert 0 <= me["a_agents_crossed_into_b_side_final"] <= 15
    assert 0 <= me["b_agents_crossed_into_a_side_final"] <= 15
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["kind"] == "PERSISTENCE_INERTIA_FIELD_COLLIDER"


def test_collider_produces_some_interpenetration():
    """With the canonical bulk-velocity injection, at least a few agents
    on each side should cross the midline within the collision window."""
    r = run_collider_experiment(
        n_per_side=30, settle_steps=400, collision_steps=600, write=False,
    )
    me = r["mass_exchange"]
    assert me["a_agents_crossed_into_b_side_max"] >= 1
    assert me["b_agents_crossed_into_a_side_max"] >= 1


# ── Codex's naturalness-audit harness (cross-doctor verification) ──────────
# Codex/Cursor shipped swarm_perturbation_harness.py during my session
# (OrganProbe / PerturbationSpec / run_naturalness_audit). Per §8.5 I
# left their work intact and just check it loads + runs from this suite.

def test_codex_naturalness_audit_runs():
    """Cross-doctor sanity check: Codex's audit imports + produces a
    receipt-shaped result. Detailed correctness lives in their tests."""
    from System.swarm_perturbation_harness import (
        run_naturalness_audit, DEFAULT_ORGAN_PROBES, PerturbationSpec,
    )
    spec = PerturbationSpec(
        baseline_ticks=4, nudge_ticks=6, recovery_ticks=10,
    )
    result = run_naturalness_audit(
        probes=DEFAULT_ORGAN_PROBES[:2],
        spec=spec,
        write=False,
    )
    assert result["truth_label"] == "NATURALNESS_FIELD_AUDIT_V1"
    assert result["truth_class"] == "HYPOTHESIS"
    assert "summary" in result
    assert result["summary"]["organ_count"] == 2
