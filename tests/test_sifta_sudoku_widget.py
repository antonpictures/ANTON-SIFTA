import inspect
import random

from Applications import sifta_sudoku_widget as sudoku


def test_stigmergic_solver_has_no_solution_oracle():
    source = inspect.getsource(sudoku._StigmergicSolver)

    assert "self.solution" not in source
    assert "solution[" not in source
    assert "correct =" not in source

    solver = sudoku._StigmergicSolver([[0] * 9 for _ in range(9)])
    assert not hasattr(solver, "solution")
    assert solver.used_solution_oracle is False


def test_generated_puzzle_is_constraint_solvable_without_oracle():
    random.seed(12)
    puzzle, _solution, given = sudoku._make_puzzle(32)

    ok, solved, placements = sudoku._logical_solve_without_oracle(puzzle)

    assert len(given) >= 17
    assert placements > 0
    assert ok
    assert sudoku._is_valid_complete(solved)


def test_swarm_solves_generated_puzzle_without_oracle():
    random.seed(21)
    puzzle, _solution, _given = sudoku._make_puzzle(32)
    solver = sudoku._StigmergicSolver(puzzle)

    done = False
    for _ in range(200):
        done = solver.step()
        if done:
            break

    assert done
    assert solver.used_solution_oracle is False
    assert solver.total_deposits > 0
    assert sudoku._is_valid_complete(solver.board)


def test_sudoku_help_entry_exists_for_mdi_gear_title():
    from System.sifta_base_widget import _load_help_text

    body = _load_help_text("⚙ Stigmergic Sudoku")

    assert "No help entry found" not in body
    assert body.startswith("### Stigmergic Sudoku")
    assert "How to play manually" in body
    assert "Self-Play x3" in body


def test_stigmergic_self_play_runs_three_rounds_without_oracle():
    results = sudoku.run_stigmergic_self_play(rounds=3, clues=32, max_steps=220, seed=303)

    assert len(results) == 3
    for row in results:
        assert row["truth_label"] == sudoku.SELF_PLAY_TRUTH_LABEL
        assert row["mode"] == "two_independent_pheromone_fields_race_same_puzzle"
        assert row["used_solution_oracle"] is False
        assert row["winner"] in {"alpha_swarm", "beta_swarm"}
        assert len(row["sides"]) == 2
        for side in row["sides"]:
            assert side["used_solution_oracle"] is False
            assert side["solver_truth_label"] == sudoku._StigmergicSolver.truth_label
            assert side["deposits"] > 0
            assert side["pheromone_mass"] > 0
            assert side["iterations"] > 0
            assert side["solved"] is True
