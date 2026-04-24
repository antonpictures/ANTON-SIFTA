"""swarmrl/tasks/stigmal_555.py
══════════════════════════════════════════════════════════════════════
Stigmal 555: Multi-channel stigmergic consensus with environmental memory.

Adds a decaying spatial field that agents deposit into, creating indirect,
time-delayed coordination (true stigmergy).
"""
from __future__ import annotations

from typing import List, Optional
import numpy as np

try:
    from swarmrl.components import Colloid
    from swarmrl.tasks.task import Task
except ImportError:
    # Graceful stub for standalone usage
    Colloid = object  # type: ignore
    class Task:       # type: ignore  # noqa: E302
        def __init__(self, particle_type: int = 0):
            self.particle_type = particle_type
        def get_colloid_indices(self, colloids):
            return list(range(len(colloids)))


class Stigmal555(Task):
    """
    Stigmal 555: Multi-Signal Stigmergic Field.
    
    Channels:
      1. Motion alignment (Vicsek velocity agreement)
      2. Spatial patterning (Lennard-Jones style structure sweet-spot)
      3. Environmental trace memory (decaying spatial field)
    """

    def __init__(
        self,
        particle_type: int = 0,
        radius: float = 3.0,
        box_size: float = 100.0,
        grid_size: int = 64,
        field_decay: float = 0.95,
        deposit_strength: float = 0.1,
        alignment_weight: float = 1.0,
        structure_weight: float = 0.3,
        memory_weight: float = 0.5,
    ):
        super().__init__(particle_type)

        self.radius = radius
        self.box_size = box_size
        self.grid_size = grid_size
        self.field_decay = field_decay
        self.deposit_strength = deposit_strength

        self.alignment_weight = alignment_weight
        self.structure_weight = structure_weight
        self.memory_weight = memory_weight

        self.previous_positions: Optional[np.ndarray] = None
        self.field = np.zeros((grid_size, grid_size))

    def initialize(self, colloids: List[Colloid]) -> None:
        self.previous_positions = np.array(
            [np.array(c.pos, dtype=float) for c in colloids]
        )

    def _to_grid(self, pos: np.ndarray) -> tuple[int, int]:
        """
        Convert physical position to 2D grid indices.
        AG31 Patch: handles periodic boundaries and 3D -> 2D projection.
        """
        # Take X and Y (first two dimensions)
        p2d = pos[:2]
        # Periodic boundary normalization [0, 1)
        normalized = (p2d % self.box_size) / self.box_size
        # Map to grid
        grid_coords = np.clip((normalized * self.grid_size).astype(int), 0, self.grid_size - 1)
        return int(grid_coords[0]), int(grid_coords[1])

    def __call__(self, colloids: List[Colloid]) -> np.ndarray:
        species_indices = self.get_colloid_indices(colloids)
        positions = np.array([np.array(c.pos, dtype=float) for c in colloids])

        if self.previous_positions is None:
            self.initialize(colloids)

        velocities = positions - self.previous_positions

        # --- Decay memory field ---
        self.field *= self.field_decay

        # --- Deposit traces ---
        for pos in positions:
            gx, gy = self._to_grid(pos)
            self.field[gx, gy] += self.deposit_strength

        rewards = np.zeros(len(species_indices))

        for out_i, i in enumerate(species_indices):
            delta = positions - positions[i]
            distances = np.linalg.norm(delta, axis=1)

            neighbors = [
                j for j in species_indices
                if j != i and distances[j] < self.radius
            ]

            if not neighbors:
                rewards[out_i] = -0.1
                continue

            # --- 1. Alignment (Velocity agreement) ---
            own_v = velocities[i]
            neigh_v = velocities[neighbors]

            own_speed = np.linalg.norm(own_v) + 1e-8
            neigh_speed = np.linalg.norm(neigh_v, axis=1) + 1e-8

            alignment = float(np.mean(
                np.dot(neigh_v, own_v) / (neigh_speed * own_speed)
            ))

            # --- 2. Structure (Clustering sweet spot) ---
            # Penalize being too close or too far from neighbors (target = radius/2)
            mean_dist = float(np.mean(distances[neighbors]))
            structure = -abs(mean_dist - (self.radius * 0.5))

            # --- 3. Memory field (Pheromone following) ---
            gx, gy = self._to_grid(positions[i])
            memory_signal = float(self.field[gx, gy])

            rewards[out_i] = (
                self.alignment_weight * alignment
                + self.structure_weight * structure
                + self.memory_weight * memory_signal
            )

        self.previous_positions = positions.copy()
        return rewards

    def __repr__(self) -> str:
        return (
            f"Stigmal555("
            f"align={self.alignment_weight}, "
            f"struct={self.structure_weight}, "
            f"mem={self.memory_weight}, "
            f"decay={self.field_decay})"
        )
