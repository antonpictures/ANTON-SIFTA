#!/usr/bin/env python3
"""
Entropy‑driven adaptive throttle for SIFTA heartbeat.
Computes Shannon entropy over the last N visual frames and returns a scaling factor.
"""

import json
import math
from pathlib import Path
from typing import List

_VISUAL = Path(".sifta_state/visual_stigmergy.jsonl")
_N = 30  # number of recent frames to consider


def _load_recent_frames() -> List[dict]:
    if not _VISUAL.exists():
        return []
    with _VISUAL.open("rb") as f:
        # read last N lines efficiently
        f.seek(0, 2)
        size = f.tell()
        read = min(size, 256 * 1024)
        f.seek(max(0, size - read))
        tail = f.read().splitlines()[-_N:]
    rows = []
    for raw in tail:
        try:
            rows.append(json.loads(raw.decode("utf-8", errors="replace")))
        except json.JSONDecodeError:
            continue
    return rows


def entropy_factor() -> float:
    """Return a multiplier ∈ [0.5, 2.0] for heartbeat interval."""
    rows = _load_recent_frames()
    if not rows:
        return 1.0

    # simple entropy on motion_mean field
    values = [float(r.get("motion_mean", 0.0)) for r in rows]
    # discretize into 10 bins
    bins = [0] * 10
    for v in values:
        idx = min(9, max(0, int((v + 1.0) * 5)))  # map [-1,1] → [0,9]
        bins[idx] += 1
    total = sum(bins)
    if total == 0:
        return 1.0
    ent = -sum((c / total) * math.log2(c / total) for c in bins if c)
    # map entropy ∈ [0, log2(10)] → scaling factor
    max_ent = math.log2(10)
    scale = 1.0 + (max_ent - ent) / max_ent  # high entropy → 1.0, low → up to 2.0
    return max(0.5, min(2.0, scale))


if __name__ == "__main__":
    print(f"Entropy factor: {entropy_factor():.2f}")
