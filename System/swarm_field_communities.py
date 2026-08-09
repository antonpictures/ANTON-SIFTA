#!/usr/bin/env python3
"""System/swarm_field_communities.py — the organs the body actually grew.
Lane contract: trace (zero-surprise).

r1744 cut #5 from WCT r1743 §5, the §0-grade self-identity probe.

Hoffman: a large Markov chain has communities — clusters of states the chain
tends to stay inside, joined by rare corridors. Nest them and you have
multiscale collective intelligence. That is the cleanest outside description of
SIFTA's organ structure anyone has handed us: an organ is a community of
swimmer states, a dispatch is a corridor crossing, the Predator Gate is a
corridor with a guard on it.

The declared organs live in the code. The *grown* organs live in the field, in
which states actually follow which. Where the two disagree, the body has an
organ nobody named — and per §0, general problem-solving includes self-identity
realization, so finding one is not bookkeeping, it is the goal.

Label propagation is used deliberately: no dependencies, no resolution
parameter to tune until the answer flatters us, and it returns whatever
structure the transitions carry, including none. Ties break on the sorted label
so a rerun on the same field gives the same answer — a self-identity probe that
changed its mind every run would be worthless.

Honest label: OBSERVED_FIELD_COMMUNITIES_V1.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from System.swarm_stationary_belief import transition_counts

TRUTH_LABEL = "OBSERVED_FIELD_COMMUNITIES_V1"

# A corridor crossed once is noise; an organ boundary should survive repetition.
MIN_EDGE_WEIGHT = 2


def _undirected_weights(
    states: Sequence[str],
    *,
    min_edge_weight: int = MIN_EDGE_WEIGHT,
) -> Dict[str, Dict[str, int]]:
    """Symmetric co-occurrence: A followed by B binds A and B either way."""
    counts = transition_counts(states)
    weights: Dict[str, Dict[str, int]] = {}
    for current, row in counts.items():
        for following, n in row.items():
            if current == following:
                continue  # a self-loop binds nothing to anything else
            if n < min_edge_weight:
                continue
            weights.setdefault(current, {})
            weights.setdefault(following, {})
            weights[current][following] = weights[current].get(following, 0) + n
            weights[following][current] = weights[following].get(current, 0) + n
    return weights


def detect_communities(
    states: Sequence[str],
    *,
    min_edge_weight: int = MIN_EDGE_WEIGHT,
    max_rounds: int = 60,
) -> Dict[str, str]:
    """Map each state to the community label it settles into.

    Every state starts as its own community and repeatedly adopts the
    heaviest-weighted label among its neighbours. Deterministic: states are
    visited in sorted order and ties fall to the sorted label.
    """
    weights = _undirected_weights(states, min_edge_weight=min_edge_weight)
    labels: Dict[str, str] = {state: state for state in weights}
    if not labels:
        return {}
    for _round in range(max_rounds):
        changed = False
        for state in sorted(weights):
            tally: Dict[str, int] = {}
            for neighbour, weight in weights[state].items():
                label = labels[neighbour]
                tally[label] = tally.get(label, 0) + weight
            if not tally:
                continue
            best = max(sorted(tally), key=lambda label: (tally[label], label))
            if best != labels[state]:
                labels[state] = best
                changed = True
        if not changed:
            break
    return labels


def community_report(
    states: Sequence[str],
    *,
    min_edge_weight: int = MIN_EDGE_WEIGHT,
    top: int = 10,
) -> Dict[str, Any]:
    """The organs the field grew, largest first, with the states in each."""
    labels = detect_communities(states, min_edge_weight=min_edge_weight)
    grouped: Dict[str, List[str]] = {}
    for state, label in labels.items():
        grouped.setdefault(label, []).append(state)
    communities = sorted(
        (
            {"label": label, "size": len(members), "states": sorted(members)}
            for label, members in grouped.items()
        ),
        key=lambda item: (-item["size"], item["label"]),
    )
    return {
        "ticks": len(states),
        "states_in_communities": len(labels),
        "community_count": len(communities),
        "communities": communities[: max(1, int(top))],
        "truth_label": TRUTH_LABEL,
    }


__all__ = [
    "MIN_EDGE_WEIGHT",
    "TRUTH_LABEL",
    "community_report",
    "detect_communities",
]
