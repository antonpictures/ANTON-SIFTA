import json
import math

from System.swarm_assembly_biocode import (
    TRUTH_LABEL,
    analyze_ensemble,
    assembly_equation,
    biocode_demo,
    exact_string_assembly_pathway,
    growth_step,
)


def test_single_monomer_has_zero_assembly_index():
    pathway = exact_string_assembly_pathway("A")

    assert pathway.assembly_index == 0
    assert pathway.exact is True
    assert pathway.steps == ()


def test_repeat_reuse_lowers_assembly_path_for_abab():
    pathway = exact_string_assembly_pathway("ABAB")

    assert pathway.assembly_index == 2
    assert [step.product for step in pathway.steps] == ["AB", "ABAB"]


def test_unique_four_symbol_chain_requires_three_joins():
    pathway = exact_string_assembly_pathway("ABCD")

    assert pathway.assembly_index == 3
    assert pathway.exact is True


def test_repeated_motif_pathway_reuses_constructed_abc():
    pathway = exact_string_assembly_pathway("ABCABCABC")

    assert pathway.assembly_index == 4
    assert pathway.exact is True
    assert pathway.steps[-1].product == "ABCABCABC"


def test_assembly_equation_ignores_single_copy_observations():
    score = assembly_equation({"ABCD": 1}, {"ABCD": 3})

    assert score == 0.0


def test_ensemble_analysis_uses_copy_number_and_honest_truth_label():
    ensemble = analyze_ensemble({"ABAB": 10, "ABCD": 1})

    assert ensemble.truth_label == TRUTH_LABEL
    assert ensemble.assembly_score > 0.0
    assert ensemble.log_assembly_score > 0.0
    assert ensemble.observations["ABCD"] == 1
    assert ensemble.assembly_indices["ABAB"] == 2
    assert ensemble.assembly_indices["ABCD"] == 3


def test_growth_step_matches_alpha_equation():
    next_counts = growth_step({0: 16.0}, alpha=0.5, kd=1.0, dt=1.0)

    assert next_counts[0] == 16.0
    assert math.isclose(next_counts[1], 4.0)


def test_demo_is_json_serializable_and_labeled_symbolic():
    demo = biocode_demo()

    encoded = json.dumps(demo, sort_keys=True)
    assert "mass spec" not in encoded.lower()
    assert TRUTH_LABEL in encoded
    assert demo["research"]["nature_2023_doi"] == "10.1038/s41586-023-06600-9"
