"""Hermetic tests for the Representational-Escape organ (TIER 4 seed).

Locks in the core thesis: changing the REPRESENTATION of the unit-distance
problem escapes the local-geometry trap. No test touches the live .sifta_state/.
"""
from __future__ import annotations

from pathlib import Path

from System.swarm_representation_escape import (
    bisociative_bridge,
    blend_representations,
    cm_field_degree_rung,
    run_escape_cycle,
    run_escape_search,
    _triangular_local,
    _gaussian_norm_form,
)


def test_number_theory_representation_beats_local_geometry():
    """The escape itself: re-representing geometry -> number theory wins big."""
    n = 2500
    local = _triangular_local(n)
    algebraic = _gaussian_norm_form(n)
    assert local < 3.2, f"local geometry should cap near triangular ~3, got {local}"
    assert algebraic > local, f"algebra ({algebraic}) must beat local ({local})"
    assert algebraic > 5.0, f"algebraic escape should clear ~5/pt, got {algebraic}"


def test_escape_cycle_picks_the_escaping_representation(tmp_path: Path):
    """run_escape_cycle names the winner, reports gain, flags the escape — hermetic."""
    r = run_escape_cycle(n=2500, write_receipt=True, state_dir=tmp_path)
    assert r["winning_representation"] == "gaussian_norm_form", r
    assert r["escaped_local_trap"] is True, r
    assert r["escape_gain_x"] > 1.5, r
    # receipt landed in the TMP ledger, never the live one
    ledger = tmp_path / "erdos_unit_distance_sentinel.jsonl"
    assert ledger.exists()
    assert "REPRESENTATION_ESCAPE_V1" in ledger.read_text()


def test_no_write_when_disabled(tmp_path: Path):
    """write_receipt=False performs zero IO."""
    run_escape_cycle(n=400, write_receipt=False, state_dir=tmp_path)
    assert not (tmp_path / "erdos_unit_distance_sentinel.jsonl").exists()


def test_honest_label_present():
    """The organ must keep the no-false-summit truth label on every receipt."""
    r = run_escape_cycle(n=400, write_receipt=False)
    assert "does not yet INVENT" in r["honest_label"]
    assert "NOT a re-proof" in r["honest_label"]


def test_constraint_relaxation_mutator_knoblich():
    """Round 10.1 #1: relax_constraint drops an implicit local-geometry constraint
    and the relaxed variant beats the trap (hermetic, no live state)."""
    from System.swarm_representation_escape import relax_constraint
    res = relax_constraint("triangular_local", "perfect_lattice_no_perturbation")
    assert res["base"] == "triangular_local"
    assert "constraint_relaxed" in res
    assert res["relaxed_to"] == "gaussian_norm_form"
    assert res["edges_per_point"] > 5.0, "relaxed must reach the algebraic escape level"
    assert res["escape_gain_over_base"] > 1.5
    assert "Knoblich" in res["source_prior"]
    assert "Does not claim to have invented" in res["honest_note"]


def test_constraint_relaxation_is_derived_not_looked_up():
    """Cowork audit fix: the escape must be DISCOVERED by searching the relaxed
    scale t, not returned as a hard-coded constant. Lock the genuine mechanism."""
    from System.swarm_representation_escape import relax_constraint
    res = relax_constraint("triangular_local")
    # the relaxed degree of freedom and the discovered scale must be reported
    assert "relaxed_degree_of_freedom" in res, "must name what constraint was relaxed"
    assert res["discovered_t"] > 1, "search must DISCOVER an escaping scale, not t=1"
    # the discovered scale must factor into primes ≡ 1 (mod 4) (the real mechanism)
    t = res["discovered_t"]
    for p in (5, 13, 17, 29, 37, 41):
        while t % p == 0:
            t //= p
    assert t == 1, f"discovered_t must be a product of primes ≡1 mod4, leftover {t}"
    # gain is computed against the real base, not a magic constant
    assert res["base_edges_per_point"] > 0
    assert abs(res["escape_gain_over_base"]
               - res["edges_per_point"] / res["base_edges_per_point"]) < 0.05


def test_domain_blend_records_parents_and_score(tmp_path: Path):
    """Round 10.1 #2: blend records both parent scores and exact counter output."""
    res = blend_representations(
        "triangular_local",
        "gaussian_norm_form",
        n=2500,
        write_receipt=True,
        state_dir=tmp_path,
    )
    assert res["repr_a"] == "triangular_local"
    assert res["repr_b"] == "gaussian_norm_form"
    assert res["blended_edges_per_point"] >= res["score_a"]
    assert res["construction"]["exact_counter"] == "unit_pairs_on_grid(side, t)"
    assert "Curated domain blend" in res["honest_label"]
    assert (tmp_path / "erdos_unit_distance_sentinel.jsonl").exists()


def test_bisociative_bridge_meets_gaussian_baseline(tmp_path: Path):
    """Round 10.1 #3: the number-theory bridge reaches the gaussian escape."""
    res = bisociative_bridge(n=2500, write_receipt=True, state_dir=tmp_path)
    assert res["foreign_matrix"] == "sum_of_two_squares_norm"
    assert res["target_representation"] == "gaussian_norm_form"
    assert res["bridged_edges_per_point"] >= _gaussian_norm_form(2500)
    assert res["meets_or_beats_gaussian"] is True
    assert "Curated bridge registry" in res["honest_label"]


def test_cm_field_degree_rung_is_scaffold_not_theorem():
    """Round 10.1 #5: CM field degree grows, with a strict no-false-summit label."""
    res = cm_field_degree_rung(write_receipt=False)
    assert res["row_count"] >= 4
    assert res["top_degree"] >= 64
    assert res["honest_status"] == "CM_CYCLOTOMIC_SCAFFOLD_NOT_CLASS_FIELD_TOWER"
    assert "does not claim a theorem" in res["honest_label"]


def test_escape_search_discovers_nonlocal_winner_and_writes_receipt(tmp_path: Path):
    """Round 10.1 #4: the search loop composes mutators and finds an escape."""
    res = run_escape_search(budget=8, n=2500, write_receipt=True, state_dir=tmp_path)
    assert res["discovered_escape"] is True
    assert res["winning_candidate"] != "triangular_local"
    assert res["winning_score"] > res["local_edges_per_point"]
    assert res["pheromone_trace"]
    assert (tmp_path / "erdos_unit_distance_sentinel.jsonl").exists()
    assert "Generative over curated mutators" in res["honest_label"]
