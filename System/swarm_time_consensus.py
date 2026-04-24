#!/usr/bin/env python3
"""
System/swarm_time_consensus.py
══════════════════════════════════════════════════════════════════════
Concept: Event-Time Consensus Helpers
Author:  AG31 cut, C55M boundary repair (Event 52)
Status:  Pure helper library

Purpose:
  Prove and reuse the daughter-safe invariant from the wormhole/time STIGALL:
  monotonic logical sequence dominates wall-clock simultaneity under clock skew.

Boundary:
  This module does not touch Warp9, gossip fanout, actuator sync, or federation
  transport. It sorts already-received event dictionaries only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _event_ts(event: Dict[str, Any]) -> float:
    try:
        return float(event.get("ts", 0.0))
    except (TypeError, ValueError):
        return 0.0


def resolve_causal_sequence(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolve causal order using logical `seq` before wall-clock `ts`.

    Rules:
    - Sequenced events sort by ascending `seq`, then ascending `ts`.
    - Duplicate sequence numbers collapse to one canonical event.
    - For duplicates, the earliest timestamp wins as the conservative replay
      policy. If timestamps tie, the input order breaks the tie deterministically.
    - Unsequenced events have no causal guarantee, so they sort after sequenced
      events by ascending `ts`.
    """
    sequenced: List[Tuple[int, float, int, Dict[str, Any]]] = []
    unsequenced: List[Tuple[float, int, Dict[str, Any]]] = []

    for input_index, event in enumerate(events):
        seq = event.get("seq")
        if seq is None:
            unsequenced.append((_event_ts(event), input_index, event))
            continue
        try:
            seq_int = int(seq)
        except (TypeError, ValueError):
            unsequenced.append((_event_ts(event), input_index, event))
            continue
        sequenced.append((seq_int, _event_ts(event), input_index, event))

    sequenced.sort(key=lambda item: (item[0], item[1], item[2]))
    unsequenced.sort(key=lambda item: (item[0], item[1]))

    resolved: List[Dict[str, Any]] = []
    seen_seq = set()
    for seq_int, _ts, _input_index, event in sequenced:
        if seq_int in seen_seq:
            continue
        seen_seq.add(seq_int)
        resolved.append(event)

    resolved.extend(event for _ts, _input_index, event in unsequenced)
    return resolved


# Public alias — enforcement layers (`swarm_time_consensus_guard`) may import
# either name; behavior is identical (pure sort + collapse policy above).
order_events = resolve_causal_sequence


if __name__ == "__main__":
    demo = [
        {"id": "wall-clock-late", "seq": 1, "ts": 100.0},
        {"id": "causally-late", "seq": 2, "ts": 90.0},
    ]
    for row in resolve_causal_sequence(demo):
        print(row)
