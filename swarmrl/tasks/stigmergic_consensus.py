"""swarmrl/tasks/stigmergic_consensus.py
══════════════════════════════════════════════════════════════════════
Stigmergic Consensus Reward — AS46 / AG31 synthesis
══════════════════════════════════════════════════════════════════════

Rewards particles for LOCAL agreement with nearby swarm members,
WITHOUT a central controller, oracle, or global target.

Physics grounding:
  - Vicsek et al. (1995) Phys Rev Lett 75:1226 — local velocity
    alignment as order parameter for self-driven phase transition.
  - Reynolds (1987) SIGGRAPH — Boids: alignment + cohesion + separation.
    Original drop included alignment + cohesion but missing separation.
    AG31 PATCH: added separation_weight to prevent point-collapse.
  - Toner & Tu (1995, 1998) Phys Rev Lett — hydrodynamic theory of
    flocking: local alignment is sufficient for global polar order.
  - Lavergne et al. (2019) Science 364:70 — activity penalty prevents
    the emergent freeze / absorbing-state collapse (entropy trap).

Claim boundary:
  - "alignment" here is cosine similarity of velocity vectors (Vicsek).
    It is NOT a proxy for information-theoretic consensus or vote quorum.
  - cohesion/separation are geometric, NOT social.
  - reward is a dense shaping signal, NOT a sparse terminal reward.

Use cases:
  - Flocking / schooling emergence without programmed leader
  - Lane formation in driven particle systems
  - Collective sorting by activity level
  - Self-organized phase behavior studies

Compatible with:
  - swarmrl >= 0.1.0 (ESPResSo backend)
  - numpy >= 1.22
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

try:
    from swarmrl.components import Colloid
    from swarmrl.tasks.task import Task
    _SWARMRL_AVAILABLE = True
except ImportError:
    # Graceful stub for use in SIFTA without full ESPResSo install
    _SWARMRL_AVAILABLE = False
    Colloid = object  # type: ignore
    class Task:          # type: ignore  # noqa: E302
        def __init__(self, particle_type: int = 0):
            self.particle_type = particle_type
        def get_colloid_indices(self, colloids):
            return list(range(len(colloids)))


class StigmergicConsensus(Task):
    """
    Stigmergic Consensus Reward.

    Rewards particles for local agreement with nearby swarm members
    while penalizing both collapse into immobility AND collapse into
    a geometric point (missing separation rule from original drop).

    Parameters
    ----------
    particle_type:
        Integer species tag. Only this species receives rewards.
    radius:
        Interaction radius (simulation units). Mirrors Vicsek r_0.
    alignment_weight:
        Weight on velocity alignment term ∈ [-1, 1].
        Maps directly to Vicsek order parameter η.
    cohesion_weight:
        Weight on cohesion (center-of-mass attraction).
        Positive = pull toward neighbor center, Reynolds rule 3.
    separation_weight:
        Weight on separation (collision avoidance penalty).
        Positive = penalize being too close. Reynolds rule 1.
        AG31 ADDITION: prevents point-collapse not in original drop.
    separation_radius:
        Distance below which separation penalty activates.
        Defaults to radius / 3 if not specified.
    activity_weight:
        Weight on activity (anti-freeze) term.
        Penalizes falling into the absorbing immobile state.
    reference_speed:
        Normalization for the activity tanh gate.
        AG31 PATCH: original tanh(own_speed) has wrong units when
        simulation box is large; this normalizes to physical meaning.
    min_neighbors:
        Minimum neighbors required; returns -0.1 if below threshold.
    """

    def __init__(
        self,
        particle_type: int = 0,
        radius: float = 3.0,
        alignment_weight: float = 1.0,
        cohesion_weight: float = 0.2,
        separation_weight: float = 0.3,
        separation_radius: Optional[float] = None,
        activity_weight: float = 0.05,
        reference_speed: float = 1.0,
        min_neighbors: int = 1,
    ):
        super().__init__(particle_type)
        self.radius = radius
        self.alignment_weight = alignment_weight
        self.cohesion_weight = cohesion_weight
        self.separation_weight = separation_weight
        self.separation_radius = (
            separation_radius if separation_radius is not None else radius / 3.0
        )
        self.activity_weight = activity_weight
        self.reference_speed = max(reference_speed, 1e-8)
        self.min_neighbors = min_neighbors
        self.previous_positions: Optional[np.ndarray] = None

    def initialize(self, colloids: List[Colloid]) -> None:
        """Seed the velocity estimator on first call."""
        self.previous_positions = np.array(
            [np.array(c.pos, dtype=float) for c in colloids]
        )

    def __call__(self, colloids: List[Colloid]) -> np.ndarray:
        """
        Compute per-particle stigmergic consensus reward.

        Returns
        -------
        rewards : np.ndarray, shape (len(species_indices),)
        """
        species_indices = self.get_colloid_indices(colloids)
        positions = np.array([np.array(c.pos, dtype=float) for c in colloids])

        if self.previous_positions is None:
            self.initialize(colloids)

        # Finite-difference velocity estimate (Vicsek-style, frame-based)
        velocities = positions - self.previous_positions

        rewards = np.zeros(len(species_indices))

        for out_i, i in enumerate(species_indices):
            delta = positions - positions[i]
            distances = np.linalg.norm(delta, axis=1)

            neighbors = [
                j for j in species_indices
                if j != i and distances[j] < self.radius
            ]

            if len(neighbors) < self.min_neighbors:
                rewards[out_i] = -0.1   # isolation penalty
                continue

            own_v = velocities[i]
            neigh_v = velocities[neighbors]

            own_speed = np.linalg.norm(own_v) + 1e-8
            neigh_speed = np.linalg.norm(neigh_v, axis=1) + 1e-8

            # ── Term 1: Vicsek alignment ──────────────────────────────
            # cos(θ) between own velocity and each neighbor's velocity.
            # Mean ∈ [-1, 1]; +1 = perfect flock alignment.
            alignment = float(np.mean(
                np.dot(neigh_v, own_v) / (neigh_speed * own_speed)
            ))

            # ── Term 2: Reynolds cohesion ─────────────────────────────
            # Normalized distance to neighbor center-of-mass.
            # Negative (pull toward center) ∈ [-1, 0].
            center = np.mean(positions[neighbors], axis=0)
            cohesion = -np.linalg.norm(positions[i] - center) / self.radius

            # ── Term 3: Reynolds separation (AG31 addition) ───────────
            # Penalize neighbors inside the hard separation shell.
            # Prevents collapse to a geometric point.
            too_close = [
                j for j in neighbors
                if distances[j] < self.separation_radius
            ]
            if too_close:
                # Mean normalized overlap distance → negative reward
                mean_overlap = float(np.mean([
                    1.0 - distances[j] / self.separation_radius
                    for j in too_close
                ]))
                separation = -mean_overlap  # ∈ [-1, 0]
            else:
                separation = 0.0

            # ── Term 4: Activity anti-freeze (Lavergne 2019) ──────────
            # tanh normalized to reference_speed so it's meaningful
            # across different simulation unit scales.
            # AG31 PATCH: original used raw own_speed, saturated for
            # large box units.
            activity = float(np.tanh(own_speed / self.reference_speed))

            rewards[out_i] = (
                self.alignment_weight  * alignment
                + self.cohesion_weight   * cohesion
                + self.separation_weight * separation
                + self.activity_weight   * activity
            )

        self.previous_positions = positions.copy()
        return rewards

    # ── Introspection ──────────────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"StigmergicConsensus("
            f"radius={self.radius}, "
            f"alignment={self.alignment_weight}, "
            f"cohesion={self.cohesion_weight}, "
            f"separation={self.separation_weight}, "
            f"activity={self.activity_weight})"
        )
