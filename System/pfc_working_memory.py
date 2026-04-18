#!/usr/bin/env python3
"""
pfc_working_memory.py — Minimal PFC working-memory buffer for novelty / RPE hooks.
══════════════════════════════════════════════════════════════════════════════

Biology sketch: dorsolateral PFC maintains **representational** working memory
(Goldman-Rakic 1995). Here: a finite ring buffer of **numeric state vectors**
(e.g. fingerprint features, embedding summaries) so Claude-tab directives like
“cosine distance to rolling average” are implementable without trusting prose.

This is not a full cognitive model — only the **interface** the motivational
layer needs for novelty and surprise.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Deque, List, Optional, Sequence

MODULE_VERSION = "2026-04-18.v1"


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _mean_vec(vectors: Sequence[Sequence[float]]) -> List[float]:
    if not vectors:
        return []
    d = len(vectors[0])
    acc = [0.0] * d
    for v in vectors:
        if len(v) != d:
            raise ValueError("vector dim mismatch")
        for i, x in enumerate(v):
            acc[i] += x
    n = float(len(vectors))
    return [x / n for x in acc]


class PFCWorkingMemory:
    """
    Ring buffer of state vectors + rolling statistics for novelty.

    `add` appends a vector; oldest dropped when maxlen reached.
    """

    def __init__(self, dim: int, maxlen: int = 32) -> None:
        if dim < 1:
            raise ValueError("dim must be >= 1")
        self.dim = dim
        self.maxlen = maxlen
        self._buf: Deque[List[float]] = deque(maxlen=maxlen)

    def __len__(self) -> int:
        return len(self._buf)

    def add(self, vec: Sequence[float]) -> None:
        v = [float(x) for x in vec]
        if len(v) != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {len(v)}")
        self._buf.append(v)

    def rolling_mean(self) -> List[float]:
        return _mean_vec(list(self._buf))

    def cosine_novelty(self, vec: Sequence[float]) -> float:
        """
        Returns 1 - cos(v, mean) in [0, 2] (higher = more novel vs history).
        """
        if not self._buf:
            return 1.0
        mu = self.rolling_mean()
        c = _cosine(vec, mu)
        return max(0.0, min(2.0, 1.0 - c))

    def discrete_entropy_normalized(self, bins: int = 8) -> float:
        """
        Coarse entropy over per-dimension discretization — proxy for
        'unresolved / diverse patterns' when you lack a full distribution.
        Returns H / log(bins) in [0, 1] if enough samples.
        """
        if len(self._buf) < 2 or bins < 2:
            return 1.0
        # Hash each vector to a bin index (simple fold)
        counts = [0] * bins
        for v in self._buf:
            s = sum(abs(x) for x in v)
            idx = int((s % 1.0) * bins) % bins
            counts[idx] += 1
        tot = sum(counts)
        h = 0.0
        for c in counts:
            if c <= 0:
                continue
            p = c / tot
            h -= p * math.log(p)
        return h / math.log(bins) if bins > 1 else 0.0


__all__ = ["PFCWorkingMemory", "MODULE_VERSION"]
