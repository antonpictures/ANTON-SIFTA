#!/usr/bin/env python3
"""
Differential privacy wrapper for API egress entries.
Adds Laplace noise to numeric fields (e.g., token cost, latency).
"""

import json
import random
import math
from pathlib import Path

_EGRESS = Path(".sifta_state/api_egress_log.jsonl")
_EPSILON = 0.5  # privacy budget per batch


def _laplace(scale: float) -> float:
    u = random.random() - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


def privatize_batch(batch: list) -> list:
    """Apply Laplace noise to each numeric field in the batch."""
    noisy = []
    for entry in batch:
        noisy_entry = entry.copy()
        for key, val in entry.items():
            if isinstance(val, (int, float)):
                scale = 1.0 / _EPSILON
                noisy_entry[key] = val + _laplace(scale)
        noisy.append(noisy_entry)
    return noisy


def write_private(batch: list) -> None:
    """Append a DP‑noised batch to the egress ledger."""
    noisy = privatize_batch(batch)
    with _EGRESS.open("a", encoding="utf-8") as f:
        for rec in noisy:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    # Demo: read first 5 rows, privatize, and rewrite to a temp file
    try:
        from System.swarm_microbiome_digestion import _tail_jsonl
        rows = _tail_jsonl(_EGRESS, 5)
        write_private(rows)
    except Exception:
        pass
