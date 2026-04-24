#!/usr/bin/env python3
"""
System/swarm_quorum_rate_gate.py
══════════════════════════════════════════════════════════════════════
Concept: Biological Quorum Rate-Gate
Author:  AO46 (Event 51 — Swarm Intelligence Triage)
Status:  Active

BIOLOGICAL SOURCE (empirical claims separated from engineering heuristics):

  [1] Greene & Gordon, Behavioral Ecology, 18(2):451-458, 2007.
      "Interaction rate informs harvester ant task decisions."
      Finding used here: ant foragers respond to interaction rate;
      the 10s threshold is the paper-backed rate-gate anchor. The
      45s cutoff is an operational memory window motivated by Gordon's
      public explanation, not a direct fitted parameter from the paper.

  [2] Sumpter, Krause et al., PNAS, 2008.
      "Quorum decision-making facilitates information transfer in fish shoals."
      Finding: Swarms use a NONLINEAR quorum response. The required
      confirmation response is sigmoidal/nonlinear. SIFTA approximates
      that sub-linear behavior with a computable sqrt(N) heuristic.

  [3] Ballerini/Cavagna et al., PNAS, 2008.
      "Interaction ruling animal collective behaviour depends on topological
      rather than metric distance."
      Finding used here: starlings interact with roughly six to seven
      topological neighbors; TOPOLOGICAL_K rounds this to 7.

SIFTA IMPLEMENTATION:

  This module provides functions prepared for mutation_governor.py and
  code reading quorum_votes.jsonl. Until those callers import this module,
  it is a tested library, not a load-bearing integration.

  rate_gate_filter(votes) → filtered_votes
      Drops votes older than RATE_GATE_MEMORY_S (45s).
      Counts at most one vote per voter_id inside the memory window.
      Anonymous votes cannot prove distinct identity, so they are also
      collapsed by a sliding RATE_GATE_INTERVAL_S gap.

  quorum_threshold(swarm_size) → int
      Returns the minimum confirming vote count required for a quorum.
      Formula: ceil(swarm_size ** 0.5)
      This is sub-linear (nonlinear) — prevents manipulation
      by a single rogue actor while remaining achievable for large
      healthy swarms.

  is_quorum_active(votes, swarm_size) → bool
      Combines both: filters stale votes, then checks threshold.
      Single entry-point for all quorum decisions in the OS.

CONSTANTS:
  RATE_GATE_INTERVAL_S = 10.0   (minimum inter-event gap to count)
  RATE_GATE_MEMORY_S   = 45.0   (operational stale-vote cutoff)
  TOPOLOGICAL_K        = 7      (Ballerini/Cavagna — rounded six-to-seven neighbor count)
"""

import math
import time
from typing import List, Dict, Any

# ── Biologically-verified constants ──────────────────────────────────────────

RATE_GATE_INTERVAL_S: float = 10.0
"""Anonymous-vote burst interval anchored to the 10s Greene & Gordon rate signal."""

RATE_GATE_MEMORY_S: float = 45.0
"""Operational memory window. Votes older than this are forgotten by the gate."""

TOPOLOGICAL_K: int = 7
"""Fixed topological neighbor count. Each SIFTA agent tracks exactly K peers,
irrespective of metric distance. (Ballerini/Cavagna, PNAS 2008; Cavagna, PNAS 2010)."""


# ── Core gate functions ───────────────────────────────────────────────────────

def rate_gate_filter(
    votes: List[Dict[str, Any]],
    now: float = None,
    memory_s: float = RATE_GATE_MEMORY_S,
    interval_s: float = RATE_GATE_INTERVAL_S,
) -> List[Dict[str, Any]]:
    """
    Filter a list of vote dicts by the biological rate-gate.

    Args:
        votes:     List of dicts with at least a "ts" (float, epoch) key.
        now:       Reference time. Defaults to time.time().
        memory_s:  Hard cutoff — votes older than this are dropped.
        interval_s: Minimum inter-event gap for anonymous votes only.
                   Known voters are deduplicated by voter_id.

    Returns:
        Filtered list of vote dicts that pass the rate-gate.

    Biological model:
        "If an ant meets another, say, every 45 seconds or every 60 seconds,
        it's as if it never happened." — Deborah Gordon, cited in documentary.

    Security model:
        A quorum is made of distinct actors. Known voters are therefore
        deduplicated by voter_id, keeping only the newest vote per voter.
        Anonymous votes are weaker evidence and are collapsed by a sliding
        minimum inter-event gap so fixed epoch bucket boundaries cannot be
        gamed by submitting votes milliseconds apart.
    """
    if not votes:
        return []

    if now is None:
        now = time.time()

    recent: List[tuple[float, Dict[str, Any]]] = []
    for vote in votes:
        try:
            ts = float(vote.get("ts", 0))
        except (TypeError, ValueError):
            continue
        age = now - ts
        if 0 <= age <= memory_s:
            recent.append((ts, vote))

    latest_by_voter: Dict[str, tuple[float, Dict[str, Any]]] = {}
    anonymous: List[tuple[float, Dict[str, Any]]] = []

    for ts, vote in recent:
        voter_id = str(vote.get("voter_id", "") or "").strip()
        if voter_id:
            current = latest_by_voter.get(voter_id)
            if current is None or ts > current[0]:
                latest_by_voter[voter_id] = (ts, vote)
        else:
            anonymous.append((ts, vote))

    anonymous.sort(key=lambda item: item[0])
    kept_anonymous: List[tuple[float, Dict[str, Any]]] = []
    last_kept_ts = None
    for ts, vote in anonymous:
        if last_kept_ts is None or ts - last_kept_ts >= interval_s:
            kept_anonymous.append((ts, vote))
            last_kept_ts = ts

    kept = list(latest_by_voter.values()) + kept_anonymous
    kept.sort(key=lambda item: item[0])
    return [vote for _, vote in kept]


def quorum_threshold(swarm_size: int) -> int:
    """
    Nonlinear quorum threshold — votes required to pass a quorum decision.

    Formula: ceil(swarm_size ** 0.5)

    This is a sqrt(N) engineering heuristic approximating the nonlinear
    quorum response documented in fish shoal experiments (Sumpter/Krause,
    PNAS 2008):
    - Small swarms (2 agents): threshold = 2 (full consensus required)
    - Medium swarms (9 agents): threshold = 3
    - Large swarms (100 agents): threshold = 10

    The sub-linear design prevents two failure modes:
    1. Single-actor hijack: one rogue vote cannot redirect a large swarm.
    2. Paralysis: large healthy swarms don't require impossible supermajority.
    """
    if swarm_size <= 0:
        return 1
    return max(1, math.ceil(math.sqrt(swarm_size)))

def is_quorum_active(
    votes: List[Dict[str, Any]],
    swarm_size: int,
    now: float = None,
) -> bool:
    """
    Single entry-point for all quorum decisions.

    Applies the biological rate-gate filter, then checks if the remaining
    active votes exceed the nonlinear quorum threshold.

    Args:
        votes:       All candidate votes (may include stale entries).
        swarm_size:  Total active agent count in the swarm.
        now:         Reference time for memory window. Defaults to time.time().

    Returns:
        True if quorum is active (safe to proceed with decision).
        False if quorum is insufficient (hold / abort).
    """
    if now is None:
        now = time.time()

    active_votes = rate_gate_filter(votes, now=now)
    threshold = quorum_threshold(swarm_size)
    return len(active_votes) >= threshold


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke():
    now = 1000.0

    # 1. Rate gate basics
    votes = [
        {"ts": now - 5},   # recent, passes
        {"ts": now - 50},  # too old (> 45s), dropped
        {"ts": now - 15},  # recent, passes
        {"ts": now - 4},   # same 10s bucket as ts=now-5, duplicate — dropped
    ]
    filtered = rate_gate_filter(votes, now=now)
    assert len(filtered) == 2, f"Expected 2 filtered votes, got {len(filtered)}"
    print(f"[PASS] rate_gate_filter: {len(filtered)} votes pass (expected 2)")

    # 2. Quorum threshold scaling
    assert quorum_threshold(1) == 1
    assert quorum_threshold(4) == 2
    assert quorum_threshold(9) == 3
    assert quorum_threshold(100) == 10
    print("[PASS] quorum_threshold: sub-linear scaling verified")

    # 3. is_quorum_active: barely passes
    votes_ok = [
        {"ts": now - 2, "voter_id": "A"},
        {"ts": now - 3, "voter_id": "B"},
        {"ts": now - 4, "voter_id": "C"},
    ]
    assert is_quorum_active(votes_ok, swarm_size=9, now=now), "Expected quorum to pass"
    print("[PASS] is_quorum_active: 3 votes / swarm_size=9 → threshold=3 → ACTIVE")

    # 4. is_quorum_active: fails (only 1 active vote for swarm of 9)
    votes_fail = [{"ts": now - 2}, {"ts": now - 60}]  # one recent, one stale
    assert not is_quorum_active(votes_fail, swarm_size=9, now=now), "Expected quorum to fail"
    print("[PASS] is_quorum_active: 1 active vote / swarm_size=9 → threshold=3 → INACTIVE")

    # 5. TOPOLOGICAL_K constant is in place
    assert TOPOLOGICAL_K == 7
    print(f"[PASS] TOPOLOGICAL_K = {TOPOLOGICAL_K} (rounded Ballerini/Cavagna starling neighbor count)")

    print("\nswarm_quorum_rate_gate smoke complete. Biology compiles.")


if __name__ == "__main__":
    _smoke()
