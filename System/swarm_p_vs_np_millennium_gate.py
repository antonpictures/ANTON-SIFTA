#!/usr/bin/env python3
"""P vs NP Millennium gate for SIFTA.

This module is deliberately conservative. It does not try to "solve" P vs NP.
It gives Alice a proof-hygiene gate and a tiny SAT lab:

1. Verify a proposed SAT certificate quickly.
2. Search tiny SAT instances by brute force for contrast.
3. Write receipts that separate benchmark work from Clay Mathematics
   Institute prize claims.

Truth boundary:
    Local SAT experiments, swimmer tournaments, and consensus ledgers are
    research tools. They are not a Clay-valid proof or prize claim.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import itertools
import json
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "p_vs_np_millennium_receipts.jsonl"

TRUTH_BOUNDARY = (
    "SIFTA may run SAT verification/search demos and proof-hygiene gates. "
    "This is not a Clay Mathematics Institute proof, not a prize submission, "
    "and not evidence that P vs NP is resolved."
)

OFFICIAL_SOURCES = {
    "millennium_problem_list": "https://www.claymath.org/millennium-problems/",
    "p_vs_np_problem_page": "https://www.claymath.org/millennium/p-vs-np/",
    "cook_problem_pdf": "https://www.claymath.org/wp-content/uploads/2022/06/pvsnp.pdf",
    "official_rules": "https://www.claymath.org/millennium-problems/rules/",
}

CLAY_PRECONDITIONS = (
    "CMI does not accept direct submissions.",
    "A proposed solution must be published in a qualifying outlet.",
    "At least two years must pass after publication.",
    "The solution must receive general acceptance in the global mathematics community.",
)


@dataclass(frozen=True)
class CNFFormula:
    """Small CNF formula for local SAT experiments.

    Literals are signed integers: 3 means x3, -3 means not x3.
    """

    num_vars: int
    clauses: tuple[tuple[int, ...], ...]
    planted_assignment: dict[int, bool] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "num_vars": self.num_vars,
            "clauses": [list(c) for c in self.clauses],
            "planted_assignment": self.planted_assignment,
        }


@dataclass(frozen=True)
class SATVerificationResult:
    ok: bool
    clauses_checked: int
    literals_checked: int
    missing_vars: tuple[int, ...]
    failed_clause_index: int | None


@dataclass(frozen=True)
class SATSearchResult:
    found: bool
    assignment: dict[int, bool] | None
    assignments_tested: int
    search_space_size: int


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_receipt(
    kind: str,
    payload: dict[str, Any],
    *,
    state_root: Path | None = None,
) -> dict[str, Any]:
    row = {
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:16],
        "kind": kind,
        "truth_boundary": TRUTH_BOUNDARY,
        "official_sources": OFFICIAL_SOURCES,
        **payload,
    }
    _append_jsonl(Path(state_root or _STATE) / _LEDGER, row)
    return row


def verify_cnf_assignment(
    formula: CNFFormula,
    assignment: dict[int, bool],
) -> SATVerificationResult:
    missing = tuple(v for v in range(1, formula.num_vars + 1) if v not in assignment)
    literals_checked = 0
    if missing:
        return SATVerificationResult(
            ok=False,
            clauses_checked=0,
            literals_checked=0,
            missing_vars=missing,
            failed_clause_index=None,
        )

    for idx, clause in enumerate(formula.clauses):
        clause_ok = False
        for lit in clause:
            literals_checked += 1
            value = assignment[abs(lit)]
            if (lit > 0 and value) or (lit < 0 and not value):
                clause_ok = True
                break
        if not clause_ok:
            return SATVerificationResult(
                ok=False,
                clauses_checked=idx + 1,
                literals_checked=literals_checked,
                missing_vars=(),
                failed_clause_index=idx,
            )
    return SATVerificationResult(
        ok=True,
        clauses_checked=len(formula.clauses),
        literals_checked=literals_checked,
        missing_vars=(),
        failed_clause_index=None,
    )


def brute_force_sat_search(
    formula: CNFFormula,
    *,
    max_vars: int = 20,
) -> SATSearchResult:
    if formula.num_vars > max_vars:
        raise ValueError(f"refusing brute force for {formula.num_vars} vars > max_vars={max_vars}")

    tested = 0
    for bits in itertools.product((False, True), repeat=formula.num_vars):
        tested += 1
        assignment = {i + 1: bits[i] for i in range(formula.num_vars)}
        if verify_cnf_assignment(formula, assignment).ok:
            return SATSearchResult(
                found=True,
                assignment=assignment,
                assignments_tested=tested,
                search_space_size=2 ** formula.num_vars,
            )
    return SATSearchResult(
        found=False,
        assignment=None,
        assignments_tested=tested,
        search_space_size=2 ** formula.num_vars,
    )


def generate_planted_3sat(
    num_vars: int,
    num_clauses: int,
    *,
    seed: int = 555,
) -> CNFFormula:
    if num_vars < 3:
        raise ValueError("planted 3-SAT demo requires at least 3 variables")
    rng = random.Random(seed)
    planted = {i: bool(rng.getrandbits(1)) for i in range(1, num_vars + 1)}
    clauses: list[tuple[int, int, int]] = []

    for _ in range(num_clauses):
        vars_ = rng.sample(range(1, num_vars + 1), 3)
        lits = []
        for v in vars_:
            sign = 1 if rng.getrandbits(1) else -1
            lits.append(sign * v)

        if not any((lit > 0 and planted[abs(lit)]) or (lit < 0 and not planted[abs(lit)]) for lit in lits):
            forced_var = vars_[0]
            lits[0] = forced_var if planted[forced_var] else -forced_var
        clauses.append(tuple(lits))

    return CNFFormula(
        num_vars=num_vars,
        clauses=tuple(clauses),
        planted_assignment=planted,
    )


_CLAIM_RE = re.compile(
    r"\b("
    r"solved|prove(?:d)?|proof|millennium|prize|million|clay|"
    r"p\s*(?:vs\.?|versus|=|!=|≠)\s*np"
    r")\b",
    re.IGNORECASE,
)


def assess_millennium_claim(
    claim_text: str,
    *,
    artifacts: dict[str, Any] | None = None,
    state_root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Classify a P-vs-NP / Clay-prize statement before Alice repeats it."""
    artifacts = dict(artifacts or {})
    claim_like = bool(_CLAIM_RE.search(claim_text or ""))
    has_proof = bool(artifacts.get("proof_url") or artifacts.get("proof_path"))
    published = bool(artifacts.get("published_in_qualifying_outlet"))
    years = float(artifacts.get("years_since_publication") or 0.0)
    accepted = bool(artifacts.get("general_acceptance"))
    cmi_accepted = bool(artifacts.get("cmi_accepted"))

    clay_ready = has_proof and published and years >= 2.0 and accepted
    if cmi_accepted:
        verdict = "CMI_ACCEPTED_REPORTED"
        action = "verify primary CMI source before public claim"
    elif claim_like and clay_ready:
        verdict = "CMI_REVIEW_READY_NOT_PRIZE"
        action = "route to human mathematician/referee; do not claim prize"
    elif claim_like:
        verdict = "FORBIDDEN_PRIZE_CLAIM"
        action = "rewrite as research/benchmark; missing Clay preconditions"
    else:
        verdict = "RESEARCH_ONLY"
        action = "safe to discuss as benchmark or proof-hygiene work"

    row = {
        "claim_like": claim_like,
        "verdict": verdict,
        "action": action,
        "clay_preconditions": CLAY_PRECONDITIONS,
        "precondition_status": {
            "has_proof_artifact": has_proof,
            "published_in_qualifying_outlet": published,
            "years_since_publication": years,
            "general_acceptance": accepted,
            "cmi_accepted": cmi_accepted,
        },
    }
    if write:
        row["receipt"] = write_receipt("P_VS_NP_CLAIM_GATE", row, state_root=state_root)
    return row


def run_verification_vs_search_demo(
    *,
    sizes: Iterable[int] = (4, 6, 8, 10),
    clause_ratio: int = 4,
    seed: int = 555,
    state_root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Run a tiny, honest SAT contrast: checking vs searching."""
    experiments: list[dict[str, Any]] = []
    for n in sizes:
        formula = generate_planted_3sat(n, clause_ratio * n, seed=seed + n)
        assert formula.planted_assignment is not None
        verification = verify_cnf_assignment(formula, formula.planted_assignment)
        search = brute_force_sat_search(formula, max_vars=max(20, n))
        experiments.append(
            {
                "num_vars": n,
                "num_clauses": len(formula.clauses),
                "certificate_ok": verification.ok,
                "certificate_literals_checked": verification.literals_checked,
                "search_assignments_tested": search.assignments_tested,
                "search_space_size": search.search_space_size,
            }
        )

    result = {
        "kind": "P_VS_NP_VERIFICATION_VS_SEARCH_DEMO",
        "experiments": experiments,
        "interpretation": (
            "A certificate can be checked by scanning clauses. Brute-force "
            "search space doubles per added variable. This demonstrates the "
            "P-vs-NP intuition only; it is not a proof."
        ),
        "truth_boundary": TRUTH_BOUNDARY,
    }
    if write:
        result["receipt"] = write_receipt(result["kind"], result, state_root=state_root)
    return result


if __name__ == "__main__":
    print(json.dumps(run_verification_vs_search_demo(write=True), indent=2, default=str))
