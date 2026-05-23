import json

import pytest

from System.swarm_perturbation_loop import (
    DEFAULT_ORGAN_PROBES,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    OrganProbe,
    PerturbationSpec,
    render_summary,
    run_naturalness_audit,
    simulate_organ_probe,
)


def test_probe_validation_rejects_invalid_ranges():
    with pytest.raises(ValueError):
        OrganProbe("", 1, 1, 0.1, 0.9).validate()
    with pytest.raises(ValueError):
        OrganProbe("bad", -1, 1, 0.1, 0.9).validate()
    with pytest.raises(ValueError):
        OrganProbe("bad", 1, 1, 1.5, 0.9).validate()
    with pytest.raises(ValueError):
        OrganProbe("bad", 1, 1, 0.1, -0.1).validate()


def test_resilient_probe_recovers_faster_than_fragile_probe():
    spec = PerturbationSpec(amplitude=1.0)
    resilient = OrganProbe("resilient", 100, 1, 0.02, 0.95, resilience=1.0, coupling=1.0)
    fragile = OrganProbe("fragile", 100, 1, 0.02, 0.95, resilience=0.05, coupling=1.0)

    r = simulate_organ_probe(resilient, spec)
    f = simulate_organ_probe(fragile, spec)

    assert r["recovered_coherence"] > f["recovered_coherence"]
    assert r["naturalness_score"] > f["naturalness_score"]


def test_stronger_perturbation_costs_more_and_scores_lower():
    weak = run_naturalness_audit(spec=PerturbationSpec(amplitude=0.4), write=False)
    strong = run_naturalness_audit(spec=PerturbationSpec(amplitude=2.0), write=False)

    assert strong["summary"]["total_stgm_cost"] > weak["summary"]["total_stgm_cost"]
    assert strong["summary"]["mean_naturalness_score"] < weak["summary"]["mean_naturalness_score"]


def test_audit_writes_receipt_with_truth_boundary(tmp_path):
    result = run_naturalness_audit(state_root=tmp_path, write=True)

    assert result["truth_label"] == TRUTH_LABEL
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert result["truth_boundary"] == TRUTH_BOUNDARY
    assert len(result["organs"]) == len(DEFAULT_ORGAN_PROBES)

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["kind"] == "NATURALNESS_FIELD_AUDIT"
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert rows[0]["truth_boundary"] == TRUTH_BOUNDARY


def test_render_summary_names_worst_organ():
    result = run_naturalness_audit(write=False)
    text = render_summary(result)

    assert "Naturalness Field Audit" in text
    assert result["summary"]["worst_organ"] in text
    assert "retune" in text

