import json

from System.swarm_higgs_stigmergy_field import (
    LEDGER_NAME,
    TRUTH_LABEL,
    TRUTH_BOUNDARY,
    HiggsFieldConfig,
    HiggsStigmergyField,
    SwimmerProbe,
    run_higgs_stigmergy_demo,
)


def test_scalar_field_relaxes_to_nonzero_substrate():
    field = HiggsStigmergyField(HiggsFieldConfig(seed=7, width=16, height=10))
    before_order = field.order_parameter
    before_energy = field.mean_potential

    summary = field.relax(180)

    assert summary["final_order_parameter"] > before_order + 0.55
    assert field.order_parameter > 0.70
    assert field.mean_potential < before_energy * 0.40


def test_coupling_creates_effective_swimmer_inertia():
    field = HiggsStigmergyField(HiggsFieldConfig(seed=3, width=16, height=10))
    field.relax(180)

    free = field.evaluate_swimmer(SwimmerProbe("free", 8, 5, 0.0))
    weak = field.evaluate_swimmer(SwimmerProbe("weak", 8, 5, 1.0))
    strong = field.evaluate_swimmer(SwimmerProbe("strong", 8, 5, 4.0))

    assert free["effective_mass"] == 1.0
    assert weak["effective_mass"] > free["effective_mass"]
    assert strong["effective_mass"] > weak["effective_mass"]
    assert strong["mobility"] < weak["mobility"] < free["mobility"]
    assert strong["latency_ms"] > weak["latency_ms"] > free["latency_ms"]


def test_demo_writes_truth_labeled_receipt(tmp_path):
    result = run_higgs_stigmergy_demo(
        config=HiggsFieldConfig(seed=5, width=14, height=9),
        steps=160,
        state_root=tmp_path,
        write=True,
    )

    assert result["truth_label"] == TRUTH_LABEL
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert "no OBSERVED Higgs bosons" in result["truth_boundary"]
    assert result["mass_span"] > 2.0

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert rows[0]["truth_boundary"] == TRUTH_BOUNDARY
    assert rows[0]["payload"]["no_particle_physics_claim"] is True
