#!/usr/bin/env python3
"""
vision_processor_worker.py — Distributed stigmergic edge detection core
=======================================================================

CPU-only "swimmer" edge extraction:
- thousands of lightweight agents on a pixel matrix
- 3x3 local sensing (gradient around current cell)
- pheromone deposit on edge crossings
- evaporation to remove noise and preserve structure skeleton
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np


@dataclass
class VisionConfig:
    width: int = 320
    height: int = 320
    swimmers: int = 1200
    edge_threshold: float = 0.18
    deposit_edge: float = 1.4
    deposit_flat: float = 0.01
    evaporation: float = 0.015
    follow_weight: float = 1.8
    gradient_weight: float = 2.2
    explore_prob: float = 0.07
    seed: int = 1337


class VisionProcessorWorker:
    def __init__(self, image: np.ndarray, cfg: VisionConfig) -> None:
        if image.ndim != 2:
            raise ValueError("image must be 2D grayscale")
        self.cfg = cfg
        self.img = image.astype(np.float32)
        self.h, self.w = self.img.shape
        self.rng = np.random.default_rng(int(cfg.seed))
        self.pher = np.zeros_like(self.img, dtype=np.float32)

        # swimmer positions: int row/col
        self.sy = self.rng.integers(0, self.h, size=(cfg.swimmers,), dtype=np.int32)
        self.sx = self.rng.integers(0, self.w, size=(cfg.swimmers,), dtype=np.int32)

        self.tick = 0
        self.edge_hits_total = 0
        self.flat_steps_total = 0

    def _grad_mag(self, y: int, x: int) -> float:
        y0 = max(0, y - 1)
        y1 = min(self.h - 1, y + 1)
        x0 = max(0, x - 1)
        x1 = min(self.w - 1, x + 1)
        patch = self.img[y0 : y1 + 1, x0 : x1 + 1]
        return float(np.max(patch) - np.min(patch))

    def _candidate_moves(self, y: int, x: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny = int(np.clip(y + dy, 0, self.h - 1))
                nx = int(np.clip(x + dx, 0, self.w - 1))
                out.append((ny, nx))
        return out

    def _choose_move(self, y: int, x: int) -> Tuple[int, int, bool]:
        cand = self._candidate_moves(y, x)
        if self.rng.random() < float(self.cfg.explore_prob):
            ny, nx = cand[int(self.rng.integers(0, len(cand)))]
            g = self._grad_mag(ny, nx)
            is_edge = g >= float(self.cfg.edge_threshold)
            return ny, nx, is_edge

        scores = np.zeros((len(cand),), dtype=np.float64)
        edge_flags = np.zeros((len(cand),), dtype=np.int8)
        for i, (ny, nx) in enumerate(cand):
            g = self._grad_mag(ny, nx)
            p = float(self.pher[ny, nx])
            scores[i] = (1.0 + self.cfg.gradient_weight * g) * (1.0 + self.cfg.follow_weight * p)
            edge_flags[i] = 1 if g >= float(self.cfg.edge_threshold) else 0

        s = float(np.sum(scores))
        if s <= 1e-12:
            idx = int(self.rng.integers(0, len(cand)))
        else:
            probs = scores / s
            idx = int(self.rng.choice(len(cand), p=probs))
        ny, nx = cand[idx]
        return ny, nx, bool(edge_flags[idx])

    def step(self) -> Dict[str, Any]:
        self.tick += 1
        self.pher *= (1.0 - float(self.cfg.evaporation))

        edge_hits = 0
        flat_steps = 0
        for i in range(len(self.sx)):
            y = int(self.sy[i])
            x = int(self.sx[i])
            ny, nx, is_edge = self._choose_move(y, x)
            self.sy[i] = ny
            self.sx[i] = nx
            if is_edge:
                self.pher[ny, nx] += float(self.cfg.deposit_edge)
                edge_hits += 1
            else:
                self.pher[ny, nx] += float(self.cfg.deposit_flat)
                flat_steps += 1

        self.edge_hits_total += edge_hits
        self.flat_steps_total += flat_steps

        return {
            "tick": self.tick,
            "edge_hits_now": edge_hits,
            "flat_steps_now": flat_steps,
            "edge_hits_total": self.edge_hits_total,
            "flat_steps_total": self.flat_steps_total,
            "pher_peak": float(np.max(self.pher)),
            "pher_mean": float(np.mean(self.pher)),
        }


def synth_topography(width: int, height: int, seed: int) -> np.ndarray:
    """
    Generate noisy topography-like grayscale matrix in [0,1].
    Uses blended radial structures + gaussian-ish noise.
    """
    rng = np.random.default_rng(seed)
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    rr = np.sqrt(xx * xx + yy * yy)

    terrain = (
        0.45 * np.exp(-((rr - 0.35) ** 2) / 0.01)
        + 0.30 * np.exp(-((xx + 0.45) ** 2 + (yy - 0.15) ** 2) / 0.02)
        + 0.35 * np.exp(-((xx - 0.35) ** 2 + (yy + 0.40) ** 2) / 0.03)
        + 0.20 * np.sin(9.0 * xx + 3.0 * yy)
        + 0.15 * np.cos(8.0 * yy - 2.0 * xx)
    ).astype(np.float32)

    noise = (rng.random((height, width), dtype=np.float32) - 0.5) * 0.35
    out = terrain + noise
    out -= np.min(out)
    mx = float(np.max(out))
    if mx > 1e-8:
        out /= mx
    return out.astype(np.float32)

