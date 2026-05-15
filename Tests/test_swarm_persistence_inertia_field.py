import json
from pathlib import Path

import pytest

from System.swarm_persistence_inertia_field import (
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    DEFAULT_COHORTS,
    ParticipationCohort,
    PerturbationConfig,
    effective_inertia,
    render_summary,
    run_persistence_inertia_protocol,
    simulate_cohort,
)


def test_participation_score_and_inertia_are_monotone():
    cfg = PerturbationConfig()
    scores = [c.participation_score() for c in DEFAULT_COHORTS]
    inertias = [effective_inertia(c, cfg) for c in DEFAULT_COHORTS]

    assert scores == sorted(scores)
    assert inertias == sorted(inertias)
    assert inertias[-1] > inertias[0] * 6.0


def test_same_nudge_moves_embedded_cohort_less_than_free_probe():
    cfg = PerturbationConfig()
    free = simulate_cohort(DEFAULT_COHORTS[0], cfg)
    sentinel = simulate_cohort(DEFAULT_COHORTS[-1], cfg)

    assert sentinel["effective_inertia"] > free["effective_inertia"]
    assert sentinel["peak_displacement"] < free["peak_displacement"] * 0.25
    assert sentinel["revert_work"] > free["revert_work"]
    assert sentinel["stgm_cost"] > free["stgm_cost"]


def test_protocol_reports_resistance_and_truth_boundary(tmp_path):
    result = run_persistence_inertia_protocol(state_root=tmp_path, write=True)

    assert result["truth_label"] == TRUTH_LABEL
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert "no OBSERVED Higgs bosons" in result["truth_boundary"]
    assert result["summary"]["monotone_inertia"] is True
    assert result["summary"]["monotone_resistance_to_nudge"] is True
    assert result["summary"]["most_embedded_resistance_vs_free"] > 4.0

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["kind"] == "PERSISTENCE_INERTIA_PROTOCOL"
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert rows[0]["truth_class"] == "HYPOTHESIS"
    assert rows[0]["truth_boundary"] == TRUTH_BOUNDARY


def test_stronger_force_moves_everyone_more_but_preserves_order():
    weak_force = run_persistence_inertia_protocol(
        config=PerturbationConfig(nudge_force=0.5),
        write=False,
    )
    strong_force = run_persistence_inertia_protocol(
        config=PerturbationConfig(nudge_force=2.0),
        write=False,
    )

    weak_peaks = [row["peak_displacement"] for row in weak_force["cohorts"]]
    strong_peaks = [row["peak_displacement"] for row in strong_force["cohorts"]]

    assert all(strong > weak for strong, weak in zip(strong_peaks, weak_peaks))
    assert strong_force["summary"]["monotone_resistance_to_nudge"] is True


def test_invalid_participation_values_are_rejected():
    with pytest.raises(ValueError):
        ParticipationCohort("bad", -1, 0, 0, 0).participation_score()
    with pytest.raises(ValueError):
        ParticipationCohort("bad", 0, 0, 0, -1).participation_score()


def test_render_summary_names_the_experiment():
    result = run_persistence_inertia_protocol(write=False)
    text = render_summary(result)

    assert "Persistence-inertia perturbation protocol" in text
    assert "embedded/free resistance" in text
    assert "sentinel_swimmer" in text


def test_physics_observatory_exposes_engine_e_tab_without_importing_qt():
    source = Path("Applications/sifta_physics_observatory.py").read_text(encoding="utf-8")

    assert "Engine E — Persistence Inertia" in source
    assert "run_persistence_inertia_protocol" in source
    assert "PERSISTENCE_INERTIA_TRUTH_BOUNDARY" in source
