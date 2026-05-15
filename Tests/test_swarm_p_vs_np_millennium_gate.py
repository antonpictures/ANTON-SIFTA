import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_p_vs_np_millennium_gate import (
    CNFFormula,
    OFFICIAL_SOURCES,
    assess_millennium_claim,
    brute_force_sat_search,
    generate_planted_3sat,
    run_verification_vs_search_demo,
    verify_cnf_assignment,
)


def test_sat_certificate_verifies_in_clause_scan():
    formula = CNFFormula(
        num_vars=3,
        clauses=((1, -2), (2, 3), (-1, -3)),
    )
    result = verify_cnf_assignment(formula, {1: True, 2: True, 3: False})
    assert result.ok is True
    assert result.clauses_checked == 3
    assert result.literals_checked <= 6


def test_sat_certificate_reports_failed_clause():
    formula = CNFFormula(num_vars=2, clauses=((1,), (-1, 2)))
    result = verify_cnf_assignment(formula, {1: False, 2: False})
    assert result.ok is False
    assert result.failed_clause_index == 0


def test_planted_3sat_witness_is_valid():
    formula = generate_planted_3sat(8, 32, seed=123)
    assert formula.planted_assignment is not None
    assert verify_cnf_assignment(formula, formula.planted_assignment).ok is True


def test_bruteforce_finds_solution_on_small_formula():
    formula = CNFFormula(num_vars=2, clauses=((1, 2), (-1, 2)))
    result = brute_force_sat_search(formula, max_vars=2)
    assert result.found is True
    assert result.assignment is not None
    assert result.search_space_size == 4
    assert verify_cnf_assignment(formula, result.assignment).ok is True


def test_claim_gate_blocks_million_dollar_claim_without_clay_preconditions():
    gate = assess_millennium_claim("We solved P vs NP and won the million dollar prize.")
    assert gate["verdict"] == "FORBIDDEN_PRIZE_CLAIM"
    assert gate["precondition_status"]["published_in_qualifying_outlet"] is False


def test_claim_gate_allows_research_language():
    gate = assess_millennium_claim("Run a SAT benchmark and write SIFTA receipts.")
    assert gate["verdict"] == "RESEARCH_ONLY"


def test_claim_gate_marks_referee_ready_but_not_prize_claim():
    gate = assess_millennium_claim(
        "This is a proof of P vs NP.",
        artifacts={
            "proof_url": "https://example.invalid/paper",
            "published_in_qualifying_outlet": True,
            "years_since_publication": 2.5,
            "general_acceptance": True,
        },
    )
    assert gate["verdict"] == "CMI_REVIEW_READY_NOT_PRIZE"
    assert "do not claim prize" in gate["action"]


def test_demo_writes_receipt_with_truth_boundary(tmp_path):
    demo = run_verification_vs_search_demo(sizes=(4, 6), state_root=tmp_path, write=True)
    assert [e["search_space_size"] for e in demo["experiments"]] == [16, 64]
    assert all(e["certificate_ok"] for e in demo["experiments"])
    assert "not a proof" in demo["interpretation"]

    path = tmp_path / "p_vs_np_millennium_receipts.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "P_VS_NP_VERIFICATION_VS_SEARCH_DEMO"
    assert "not a Clay Mathematics Institute proof" in rows[0]["truth_boundary"]
    assert rows[0]["official_sources"]["official_rules"] == OFFICIAL_SOURCES["official_rules"]
