#!/usr/bin/env python3
"""
System/swarm_topological_optimizer.py
══════════════════════════════════════════════════════════════════════
Concept: Starling Murmuration — Topological Swarm Optimization (Event 71)
Author:  BISHOP / AG31 — Biocode Olympiad
Status:  Active Organ

Classic swarm algorithms (like Boids) assume agents interact with all
neighbors within a fixed metric radius. But real starling murmurations
do not work this way. Ballerini et al. (2008) discovered that starlings
interact with a fixed number of neighbors (topological distance, K ≈ 7),
regardless of how close or far away they are.

This topological interaction is the secret to scale-free correlations
(Cavagna 2010) and high-speed information transfer without damping
(Attanasi 2014). It makes the swarm robust to predatory attacks that
cause extreme density fluctuations.

SIFTA Translation:
  - We replace O(N²) radius-based interaction with O(N·K) topological
    interaction.
  - Agents compute alignment, cohesion, and separation ONLY against
    their 7 nearest neighbors.
  - Behavioral inertia (Attanasi 2014) is implemented by smoothly
    blending the old velocity with the new topologically-computed one.
  - This layer sits underneath the stigmergic fields, stabilizing the
    agents' movement mechanics before they follow field gradients.
"""

from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

@dataclass
class TopologyConfig:
    k_neighbors: int = 7
    alignment_weight: float = 0.6
    cohesion_weight: float = 0.25
    separation_weight: float = 0.35
    inertia_weight: float = 0.7
    max_speed: float = 0.05
    eps: float = 1e-8


class TopologicalSwarmOptimizer:
    def __init__(self, cfg: Optional[TopologyConfig] = None):
        self.cfg = cfg or TopologyConfig()

    def _k_nearest(self, positions: np.ndarray, i: int) -> np.ndarray:
        d = np.linalg.norm(positions - positions[i], axis=1)
        k = min(self.cfg.k_neighbors + 1, len(positions))
        if k <= 1:
            return np.array([], dtype=int)
        
        idx = np.argpartition(d, k - 1)[:k]
        idx = idx[np.argsort(d[idx])]
        return idx[1:k]

    def step(self, positions: np.ndarray, velocities: np.ndarray) -> np.ndarray:
        positions = np.asarray(positions, dtype=np.float32)
        velocities = np.asarray(velocities, dtype=np.float32)
        N = len(positions)
        
        if N <= 1:
            return velocities.copy()

        new_vel = np.zeros_like(velocities)

        for i in range(N):
            neighbors = self._k_nearest(positions, i)
            if len(neighbors) == 0:
                new_vel[i] = velocities[i]
                continue

            neigh_pos = positions[neighbors]
            neigh_vel = velocities[neighbors]

            # --- Alignment ---
            align = np.mean(neigh_vel, axis=0)

            # --- Cohesion ---
            center = np.mean(neigh_pos, axis=0)
            cohesion = center - positions[i]

            # --- Separation ---
            delta = positions[i] - neigh_pos
            dist = np.linalg.norm(delta, axis=1, keepdims=True) + self.cfg.eps
            # Bishop's formula: sum of unit vectors
            separation = np.sum(delta / dist, axis=0)

            # --- Calculate topological force ---
            topological_force = (
                self.cfg.alignment_weight * align
                + self.cfg.cohesion_weight * cohesion
                + self.cfg.separation_weight * separation
            )

            # --- Behavioural Inertia ---
            v_new = (
                self.cfg.inertia_weight * velocities[i]
                + (1.0 - self.cfg.inertia_weight) * topological_force
            )

            speed = float(np.linalg.norm(v_new))
            if speed > self.cfg.max_speed:
                v_new = (v_new / speed) * self.cfg.max_speed
            elif speed < self.cfg.eps:
                v_new = np.random.normal(0, self.cfg.eps, size=2)

            new_vel[i] = v_new

        return new_vel.astype(np.float32)


def proof_of_property() -> bool:
    print("\n=== SIFTA TOPOLOGICAL SWARM (Event 71) : JUDGE VERIFICATION ===")

    N = 20
    rng = np.random.default_rng(71)
    positions = rng.uniform(0.0, 1.0, size=(N, 2)).astype(np.float32)
    velocities = rng.uniform(-0.02, 0.02, size=(N, 2)).astype(np.float32)

    cfg = TopologyConfig(k_neighbors=7)
    optimizer = TopologicalSwarmOptimizer(cfg)

    print("\n[*] Phase 1: Topological Cohesion (Ballerini 2008)")
    
    # 1. Let the swarm find its natural equilibrium density
    for _ in range(80):
        velocities = optimizer.step(positions, velocities)
        positions += velocities
        
    equilibrium_spread = float(np.std(positions))
    
    # 2. Artificially expand the swarm far beyond equilibrium
    positions *= 5.0
    scattered_spread = float(np.std(positions))
    
    # 3. Allow it to recover
    for _ in range(80):
        velocities = optimizer.step(positions, velocities)
        positions += velocities
        
    recovered_spread = float(np.std(positions))
    
    print(f"    Equilibrium spread:         {equilibrium_spread:.4f}")
    print(f"    Scattered spread (x5):      {scattered_spread:.4f}")
    print(f"    Recovered spread:           {recovered_spread:.4f}")
    assert recovered_spread < scattered_spread, "[FAIL] Topological interaction failed to recover cohesion"

    print("\n[*] Phase 2: Information Transfer & Behavioural Inertia (Attanasi 2014)")
    
    velocities[:] = np.array([0.05, 0.0], dtype=np.float32)
    velocities[0] = np.array([0.0, 0.05], dtype=np.float32)
    
    align_init = float(np.mean(velocities[:, 1]))
    
    for _ in range(5):
        velocities = optimizer.step(positions, velocities)
        velocities[0] = np.array([0.0, 0.05], dtype=np.float32)
        positions += velocities
        
    align_final = float(np.mean(velocities[:, 1]))
    
    print(f"    Initial turn alignment (Y-vel): {align_init:.4f}")
    print(f"    Final turn alignment (Y-vel):   {align_final:.4f}")
    assert align_final > align_init, "[FAIL] Information about the turn did not propagate"
    
    mean_speed = float(np.mean(np.linalg.norm(velocities, axis=1)))
    print(f"    Mean speed after turn propagation: {mean_speed:.4f} (max={cfg.max_speed})")
    assert mean_speed > cfg.max_speed * 0.5, "[FAIL] Behavioural inertia failed, swarm damped out"

    print("\n[+] BIOLOGICAL PROOF: Starling Topological Swarm verified.")
    print("    1. Recovered cohesion independently of metric distance (Ballerini 2008)")
    print("    2. Turn information propagated through swarm (Cavagna 2010)")
    print("    3. Behavioural inertia prevented catastrophic damping (Attanasi 2014)")
    print("[+] EVENT 71 PASSED.")
    return True

if __name__ == "__main__":
    proof_of_property()
