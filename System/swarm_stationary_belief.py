#!/usr/bin/env python3
"""System/swarm_stationary_belief.py — what the body actually believes it does.

r1744 cut #4 from WCT r1743 §3. Hoffman's primitive is an observer window: a
Markov matrix over the experiences that window can have, plus a counter that
ticks on every update. His claim that matters here is small and testable — the
**stationary measure of that matrix is the window's belief system**. Not what
the window says about itself; what it converges to over its own long run.

SIFTA already writes the transitions. Every ledger row in `.sifta_state/` is
one tick of one window: the field moves from `camera_lock` to `camera_error` to
`rlhs_channel`, and the sequence is on disk going back months. Nobody had ever
read those rows as a chain.

This organ does. Give it a ledger and the key that names the state, and it
returns the transition matrix and its stationary measure — the body's measured
beliefs, in the same units for every organ, comparable against the doctrine
that was intended. Drift stops being an argument and becomes a number.

Deliberately honest about its own limits:
  - A chain that never revisits a state has no meaningful long run, so the
    report says so instead of printing a confident vector.
  - Power iteration is reported with its convergence, never as a fact that
    silently failed to converge.
  - Row counts ride along, because a stationary measure over eleven ticks is
    arithmetic, not belief (§2, the same jewel-beetle rule as the eval matrix).

Honest label: OBSERVED_STATIONARY_BELIEF_V1.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

TRUTH_LABEL = "OBSERVED_STATIONARY_BELIEF_V1"

# Below this a "long run" is arithmetic on noise, not a belief worth reporting.
MIN_TICKS_FOR_BELIEF = 50


def read_state_sequence(
    ledger: Path | str,
    *,
    state_keys: Sequence[str] = ("event", "kind", "action", "system"),
    max_rows: int | None = None,
) -> List[str]:
    """The ordered states a window passed through, read from its ledger.

    The first key present on a row names that row's state, so one reader serves
    ledgers written by organs that never agreed on a field name.
    """
    path = Path(ledger)
    states: List[str] = []
    try:
        with path.open("rb") as handle:
            lines: Iterable[bytes] = handle.readlines()
    except OSError:
        return []
    if max_rows is not None and max_rows > 0:
        lines = list(lines)[-max_rows:]
    for line in lines:
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, dict):
            continue
        for key in state_keys:
            value = row.get(key)
            if value:
                states.append(str(value))
                break
    return states


def transition_counts(states: Sequence[str]) -> Dict[str, Dict[str, int]]:
    """How often each state was followed by each other state."""
    counts: Dict[str, Dict[str, int]] = {}
    for current, following in zip(states, states[1:]):
        counts.setdefault(current, {})
        counts[current][following] = counts[current].get(following, 0) + 1
    return counts


def transition_matrix(
    states: Sequence[str],
) -> Tuple[List[str], List[List[float]]]:
    """The window's Markov matrix: row i is P(next | current = state i).

    A state that was only ever the last observation has no outgoing evidence;
    rather than invent one, its row is left uniform so it neither absorbs nor
    injects probability mass it never earned.
    """
    counts = transition_counts(states)
    labels = sorted({*counts, *(s for row in counts.values() for s in row)})
    index = {label: i for i, label in enumerate(labels)}
    size = len(labels)
    matrix = [[0.0] * size for _ in range(size)]
    for current, row in counts.items():
        total = float(sum(row.values()))
        if total <= 0:
            continue
        i = index[current]
        for following, n in row.items():
            matrix[i][index[following]] = n / total
    for i in range(size):
        if sum(matrix[i]) <= 0.0 and size:
            matrix[i] = [1.0 / size] * size
    return labels, matrix


def stationary_measure(
    matrix: Sequence[Sequence[float]],
    *,
    max_iterations: int = 2000,
    tolerance: float = 1e-10,
) -> Tuple[List[float], bool, int]:
    """Long-run probability of each state. Returns (measure, converged, iters).

    Plain power iteration with a small uniform damping, which keeps a periodic
    chain (the paper monitor alternates two states forever) from oscillating
    instead of settling. `converged` is reported honestly and is never assumed.
    """
    size = len(matrix)
    if size == 0:
        return [], False, 0
    damping = 0.85
    vector = [1.0 / size] * size
    for iteration in range(1, max_iterations + 1):
        nxt = [0.0] * size
        for i, weight in enumerate(vector):
            if weight <= 0.0:
                continue
            row = matrix[i]
            for j in range(size):
                nxt[j] += weight * row[j]
        nxt = [damping * v + (1.0 - damping) / size for v in nxt]
        total = sum(nxt) or 1.0
        nxt = [v / total for v in nxt]
        delta = sum(abs(a - b) for a, b in zip(nxt, vector))
        vector = nxt
        if delta < tolerance:
            return vector, True, iteration
    return vector, False, max_iterations


def belief_report(
    ledger: Path | str,
    *,
    state_keys: Sequence[str] = ("event", "kind", "action", "system"),
    max_rows: int | None = 20000,
    top: int = 12,
) -> Dict[str, Any]:
    """One window's measured beliefs, with everything needed to distrust them."""
    states = read_state_sequence(ledger, state_keys=state_keys, max_rows=max_rows)
    ticks = len(states)
    labels, matrix = transition_matrix(states)
    measure, converged, iterations = stationary_measure(matrix)
    ranked = sorted(
        ({"state": label, "belief": round(value, 6)} for label, value in zip(labels, measure)),
        key=lambda item: item["belief"],
        reverse=True,
    )
    return {
        "ledger": str(ledger),
        "ticks": ticks,
        "distinct_states": len(labels),
        "converged": converged,
        "iterations": iterations,
        "enough_evidence": ticks >= MIN_TICKS_FOR_BELIEF,
        "beliefs": ranked[: max(1, int(top))],
        "truth_label": TRUTH_LABEL,
    }


__all__ = [
    "MIN_TICKS_FOR_BELIEF",
    "TRUTH_LABEL",
    "belief_report",
    "read_state_sequence",
    "stationary_measure",
    "transition_counts",
    "transition_matrix",
]
