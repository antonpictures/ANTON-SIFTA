#!/usr/bin/env python3
"""
System/swarm_causal_vector_clock.py
══════════════════════════════════════════════════════════════════════
Per-node vector clock (Fidge–Mattern style merge; Lamport-style local tick).

Boundary (Event 52 discipline):
  This is NOT imported by swarm_time_consensus_guard.py. That guard remains a
  pure batch sorter + submission-shape gate (see its explicit non-claims).
  Warp9 / federation callers may use this module when they attach a full
  vector to payloads; until then it stays an optional library + tests.

is_causally_ready:
  Rule 1 — next message from sender must be exactly local[sender]+1.
  Rule 2 — for every other peer P in the *incoming* vector, local[P] >= V[P]
           (receiver has observed all dependencies the sender attached).
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

MODULE_VERSION = "2026-04-24.swarm-causal-vector-clock.v1"


class SwarmVectorClock:
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.clock: Dict[str, int] = {node_id: 0}

    def increment(self) -> Dict[str, int]:
        """IR1: bump local component before emitting a message."""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        return dict(self.clock)

    def merge(self, incoming_clock: Mapping[str, int]) -> None:
        """IR2: element-wise max on receive (standard vector-clock merge)."""
        for peer_id, ts in incoming_clock.items():
            self.clock[peer_id] = max(self.clock.get(peer_id, 0), int(ts))

    def check_readiness(
        self, sender_id: str, incoming_clock: Mapping[str, int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Strict causal delivery check (BISHOP Event 52 semantics).

        Returns (True, None) if the message may be delivered now; else
        (False, short machine-readable reason).
        """
        expected = self.clock.get(sender_id, 0) + 1
        got = int(incoming_clock.get(sender_id, 0))
        if got != expected:
            return False, f"seq_jump:{sender_id}:expected_{expected}:got_{got}"

        for peer_id, ts in incoming_clock.items():
            if peer_id == sender_id:
                continue
            local = self.clock.get(peer_id, 0)
            if int(ts) > local:
                return False, f"missing_dep:{peer_id}:need_{ts}:have_{local}"

        return True, None

    def is_causally_ready(self, sender_id: str, incoming_clock: Mapping[str, int]) -> bool:
        return self.check_readiness(sender_id, incoming_clock)[0]
