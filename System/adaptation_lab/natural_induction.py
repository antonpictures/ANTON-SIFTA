"""natural_induction.py — r184 module 2
One-hop adaptation with a tiny Hebbian/connectionist field.
No population of competing variants; no global selection loop.

The module should remember trained patterns and recall a nearby unseen state to
its nearest attractor by local recurrent updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


Pattern = List[float]


@dataclass
class InductionResult:
    recalled_state: Pattern
    steps: int
    training_steps: int
    output_hash: str


def _normalize_pattern(pattern: Sequence[float]) -> Pattern:
    """Map pattern values to bipolar {-1.0, 1.0} and validate finite shape."""
    normalized: Pattern = []
    for value in pattern:
        v = float(value)
        if v >= 0:
            normalized.append(1.0)
        else:
            normalized.append(-1.0)
    return normalized


def _hamming_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("patterns must share dimensionality")
    if not a:
        return 0.0
    matches = sum(1 for i, j in zip(a, b) if (1 if i >= 0 else -1) == (1 if j >= 0 else -1))
    return matches / len(a)


def _make_weight_matrix(size: int) -> List[List[float]]:
    return [[0.0 for _ in range(size)] for _ in range(size)]


def train_hebbian(patterns: Iterable[Sequence[float]]) -> List[List[float]]:
    """Build a dense recurrent weight matrix from one-shot Hebbian updates."""
    pattern_list = [_normalize_pattern(p) for p in patterns]
    if not pattern_list:
        return []

    n = len(pattern_list[0])
    if any(len(p) != n for p in pattern_list):
        raise ValueError("all patterns must share the same length")

    w = _make_weight_matrix(n)
    for pattern in pattern_list:
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                w[i][j] += pattern[i] * pattern[j]
    return w


def recall(pattern: Sequence[float], weights: List[List[float]], max_steps: int = 50) -> InductionResult:
    """Run recurrent stabilization to recover a stored attractor.

    The updates are synchronous-by-structure but with in-place updates per
    position to let local field pressure propagate through a single call.
    """
    if not pattern:
        return InductionResult([], 0, 0, "empty")

    n = len(pattern)
    if n != len(weights) or any(len(row) != n for row in weights):
        raise ValueError("weights must be a square matrix matching pattern length")

    state = _normalize_pattern(pattern)
    seen = {"".join("1" if v >= 0 else "0" for v in state)}

    steps = 0
    for step in range(1, max_steps + 1):
        changed = False
        for i in range(n):
            total = 0.0
            for j in range(n):
                total += weights[i][j] * state[j]
            new_value = 1.0 if total >= 0 else -1.0
            if new_value != state[i]:
                changed = True
                state[i] = new_value
        signature = "".join("1" if v >= 0 else "0" for v in state)
        if signature in seen:
            # deterministic cycle detection: stop on repeat state
            return InductionResult(recalled_state=state, steps=steps, training_steps=0, output_hash=signature)
        seen.add(signature)
        steps = step
        if not changed:
            break

    return InductionResult(
        recalled_state=state,
        steps=steps,
        training_steps=0,
        output_hash="".join("1" if v >= 0 else "0" for v in state),
    )


def nearest_match(query: Sequence[float], patterns: Iterable[Sequence[float]]) -> Tuple[Pattern, int, float]:
    """Map a query to nearest trained pattern via Hamming similarity."""
    encoded = _normalize_pattern(query)
    parsed_patterns = [_normalize_pattern(p) for p in patterns]
    best = parsed_patterns[0]
    best_idx = 0
    best_score = -1.0
    for idx, pattern in enumerate(parsed_patterns):
        score = _hamming_similarity(encoded, pattern)
        if score > best_score:
            best_idx = idx
            best_score = score
            best = pattern
    return best, best_idx, best_score


if __name__ == "__main__":
    training = [
        [1, 1, -1, -1],
        [1, -1, 1, -1],
        [-1, 1, -1, 1],
    ]
    weights = train_hebbian(training)
    unseen = [1, 1, 1, -1]
    result = recall(unseen, weights)
    nearest, _, score = nearest_match(result.recalled_state, training)
    print(f"unseen->{result.recalled_state} (nearest match score={score:.2f})")
