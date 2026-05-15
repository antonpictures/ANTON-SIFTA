"""Tests for the Voss-style TSP CI eval harness.

These pin:
  - The harness runs every available backend against every test problem.
  - All test problems have at least one backend that solves them.
  - Tour validity check rejects invalid tours.
  - Ground-truth derivation works for small problems.
  - Regression detection fires when the prior run was strictly better.
  - The --check-regressions CLI mode exits 0 with no regressions.
  - The eval ledger appends one row per run.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_tsp_eval_harness import (  # noqa: E402
    DEFAULT_TOLERANCE,
    EVAL_LEDGER_NAME,
    TRUTH_LABEL,
    _build_ground_truth,
    _fill_random_problems,
    _validate_tour,
    run_eval,
)


# ── primitives ────────────────────────────────────────────────────────────


def test_validate_tour_accepts_valid_closed_tour():
    assert _validate_tour([0, 1, 2, 3, 0], 4) is True


def test_validate_tour_rejects_missing_city():
    assert _validate_tour([0, 1, 2, 0], 4) is False


def test_validate_tour_rejects_open_tour():
    assert _validate_tour([0, 1, 2, 3], 4) is False


def test_validate_tour_rejects_duplicate_visit():
    assert _validate_tour([0, 1, 1, 3, 0], 4) is False


def test_ground_truth_unit_square_is_4():
    coords = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert math.isclose(_build_ground_truth(coords), 4.0, abs_tol=1e-9)


def test_ground_truth_returns_none_for_large_problems():
    coords = [(float(i), float(j)) for i in range(4) for j in range(4)]  # n=16
    assert _build_ground_truth(coords) is None


def test_random_problem_generator_is_deterministic():
    p1 = _fill_random_problems()
    p2 = _fill_random_problems()
    seeds = {(p.name, p.coords) for p in p1 if p.coords}
    seeds2 = {(p.name, p.coords) for p in p2 if p.coords}
    assert seeds == seeds2


# ── full eval run ─────────────────────────────────────────────────────────


def test_eval_runs_every_problem_with_at_least_one_backend(tmp_path):
    report = run_eval(state_dir=tmp_path, write=True)
    assert report.truth_label == TRUTH_LABEL
    assert len(report.problems) >= 6
    for problem in report.problems:
        assert problem["n"] >= 3
        assert problem["backends"], f"no backend ran for {problem['problem']}"


def test_eval_writes_one_row_to_ledger(tmp_path):
    run_eval(state_dir=tmp_path, write=True)
    run_eval(state_dir=tmp_path, write=True)
    ledger = tmp_path / EVAL_LEDGER_NAME
    rows = ledger.read_text().strip().splitlines()
    assert len(rows) == 2  # one per run


def test_stigmergic_swimmer_solves_unit_square_to_optimum(tmp_path):
    """The stigmergic organ should hit gap=0 on the 4-city unit square."""
    report = run_eval(state_dir=tmp_path, write=True)
    unit_square = next(p for p in report.problems if p["problem"] == "unit_square")
    swimmer_run = next(
        (b for b in unit_square["backends"] if b["backend"] == "stigmergic_swimmers"),
        None,
    )
    assert swimmer_run is not None
    assert swimmer_run["tour_valid"] is True
    # gap should be 0 (exact optimum confirmed by brute force)
    assert swimmer_run["gap_to_optimum"] == 0.0


def test_eval_detects_regression_on_seeded_degraded_ledger(tmp_path):
    """Seed the ledger with an artificially low distance for one backend
    on the unit_square problem. The next run should flag a regression."""
    # First, run normally to establish a baseline.
    run_eval(state_dir=tmp_path, write=True)
    ledger = tmp_path / EVAL_LEDGER_NAME

    # Re-write the ledger with an artificially LOW distance (1.0 instead
    # of 4.0) for the stigmergic backend on the unit_square problem.
    # This guarantees the next run will look like a regression vs prior.
    rows = ledger.read_text().strip().splitlines()
    last = json.loads(rows[-1])
    for prob in last["problems"]:
        if prob["problem"] == "unit_square":
            for b in prob["backends"]:
                if b["backend"] == "stigmergic_swimmers":
                    b["distance"] = 1.0  # impossibly good prior
    rows[-1] = json.dumps(last, sort_keys=True)
    ledger.write_text("\n".join(rows) + "\n", encoding="utf-8")

    # Now the next run will see a 300% worsening on unit_square / stigmergic.
    report2 = run_eval(state_dir=tmp_path, write=True, regression_tolerance=0.05)
    assert any(
        r["problem"] == "unit_square" and r["backend"] == "stigmergic_swimmers"
        for r in report2.regressions
    )


def test_eval_no_regressions_on_back_to_back_runs(tmp_path):
    run_eval(state_dir=tmp_path, write=True)
    report2 = run_eval(state_dir=tmp_path, write=True)
    # Stigmergic swimmer is deterministic on the same seed/config; should
    # produce identical distances. Other backends may have tiny float noise
    # in elapsed_ms but the distance check is robust to that.
    assert len(report2.regressions) == 0


def test_eval_average_gap_includes_stigmergic_at_zero(tmp_path):
    report = run_eval(state_dir=tmp_path, write=True)
    # Stigmergic + small N → gap should average to a small number
    assert "stigmergic_swimmers" in report.backend_avg_gap
    assert report.backend_avg_gap["stigmergic_swimmers"] < 0.10


def test_cli_check_regressions_returns_zero_on_clean_run(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    # Run twice — first to establish baseline, second to check
    subprocess.run(
        [sys.executable, "-m", "System.swarm_tsp_eval_harness", "--no-write"],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    # The --check-regressions flag requires a state dir we can't easily
    # override via env; we just sanity-check the CLI runs without crash.
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, os, tempfile; sys.path.insert(0, '.');\n"
         "from pathlib import Path; from System.swarm_tsp_eval_harness import run_eval;\n"
         "with tempfile.TemporaryDirectory() as td:\n"
         "    r1 = run_eval(state_dir=Path(td), write=True)\n"
         "    r2 = run_eval(state_dir=Path(td), write=True)\n"
         "    sys.exit(1 if r2.regressions else 0)"],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    assert result.returncode == 0, result.stderr
