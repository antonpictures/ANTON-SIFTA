"""test_adaptation_natural_induction.py — r184
No selection, no competing populations: Hebbian memory that generalizes to unseen input.
"""

from System.adaptation_lab import natural_induction as nat


def test_module_imports_cleanly():
    assert nat.train_hebbian is not None


def test_trains_and_recalls_trained_patterns():
    patterns = [
        [1, 1, -1, -1],
        [1, -1, 1, -1],
        [-1, 1, -1, 1],
    ]
    weights = nat.train_hebbian(patterns)

    for p in patterns:
        result = nat.recall(p, weights)
        assert result.recalled_state == nat._normalize_pattern(p)
        assert result.steps >= 0


def test_unseen_pattern_recalls_neighbor_pattern():
    patterns = [
        [1, 1, -1, -1],
        [1, -1, 1, -1],
        [-1, 1, -1, 1],
    ]
    weights = nat.train_hebbian(patterns)

    unseen = [1, 1, 1, -1]
    result = nat.recall(unseen, weights)
    nearest, _, _ = nat.nearest_match(result.recalled_state, patterns)

    # The recall should move toward a trained attractor, not return a random
    # identity from no-memory state.
    assert result.recalled_state in [nat._normalize_pattern(p) for p in patterns]
    assert result.recalled_state == nearest


def test_empty_inputs_are_graceful():
    assert nat.train_hebbian([]) == []
    result = nat.recall([], [])
    assert result.recalled_state == []
    assert result.steps == 0
