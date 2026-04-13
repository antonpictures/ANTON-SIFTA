"""
swarmrl_observables/pheromone_field.py
======================================
SIFTA Pheromone Field as a SwarmRL Observable.

Drop-in replacement / extension for SwarmRL's ConcentrationField.
Maps SIFTA's live pheromone gradient (from scar_kernel.consensus_field)
into the (n_colloids, 1) float array expected by SwarmRL's actor-critic networks.

No JAX required in SIFTA's kernel. Numpy is used internally and the result
is returned as a standard numpy array — SwarmRL converts it at the boundary.

Usage (SwarmRL trainer setup):
    from swarmrl_observables.pheromone_field import PheromoneFieldObservable
    observable = PheromoneFieldObservable(target="body_state.py", particle_type=0)
    trainer.observable = observable
"""

import sys
import time
from pathlib import Path
from typing import List

import numpy as np

# Allow imports from parent SIFTA directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from scar_kernel import Kernel, consensus_field, field_is_stable

# SwarmRL Observable base — imported lazily so SIFTA works without SwarmRL installed
try:
    from swarmrl.components.colloid import Colloid
    from swarmrl.observables.observable import Observable
    _HAS_SWARMRL = True
except ImportError:
    # Standalone mode: define minimal stubs so the module loads regardless
    _HAS_SWARMRL = False

    class Colloid:
        def __init__(self, pos, director, id, velocity=None, type=0):
            self.pos = np.array(pos)
            self.director = np.array(director)
            self.id = id
            self.velocity = velocity
            self.type = type

    class Observable:
        def __init__(self, particle_type=0):
            self.particle_type = particle_type
            self._shape = None

        def get_colloid_indices(self, colloids, p_type=None):
            if p_type is None:
                p_type = self.particle_type
            return [i for i, c in enumerate(colloids) if c.type == p_type]

        def compute_observable(self, colloids):
            raise NotImplementedError


class PheromoneFieldObservable(Observable):
    """
    SIFTA Pheromone Gradient as a SwarmRL Observable.

    Each colloid "senses" the pheromone field for a given SIFTA target.
    A score near 1.0 = fossil territory — the consensus is locked here.
    A score near 0.0 = unexplored — agents should explore freely.

    The field gradient drives colloid movement without a central coordinator.
    This is the exact mathematical analog of chemotaxis in bacterial swarms.
    """

    def __init__(self, target: str, particle_type: int = 0, kernel: Kernel = None):
        """
        Parameters
        ----------
        target : str
            The SIFTA target (file or resource) to observe. Colloids navigate
            toward the highest pheromone score for this target.
        particle_type : int
            SwarmRL particle type index.
        kernel : Kernel (optional)
            Pass an existing Kernel instance for shared-state simulations.
            If None, creates its own instance.
        """
        super().__init__(particle_type=particle_type)
        self.target = target
        self._kernel = kernel or Kernel()
        self._shape = (1,)
        self._cached_field = []
        self._last_refresh = 0.0
        self._refresh_interval = 2.0  # Re-read kernel every 2 seconds

    def _refresh_field(self):
        """Pull the live pheromone gradient from the SIFTA kernel."""
        now = time.time()
        if now - self._last_refresh > self._refresh_interval:
            scars = [
                s for s in self._kernel.scars.values()
                if s.target == self.target and s.state in ("PROPOSED", "LOCKED")
            ]
            self._cached_field = consensus_field(scars)
            self._last_refresh = now

    def dominant_score(self) -> float:
        """Return the current dominant pheromone score (0 to 1)."""
        self._refresh_field()
        if not self._cached_field:
            return 0.0
        return float(self._cached_field[0][1])

    def is_stable(self, threshold: float = 0.15) -> bool:
        """True when the field has converged — the Strogatz sync moment."""
        self._refresh_field()
        return field_is_stable(self._cached_field, threshold=threshold)

    def compute_single_observable(self, colloid: "Colloid") -> float:
        """
        Compute pheromone field strength for a single colloid.

        In the physical interpretation, colloid position in [0,1]^3 maps
        onto the SIFTA field: colloids near (1,1,1) are in maximum-pheromone
        territory (fossil zone). Colloids near (0,0,0) are in unexplored space.

        For software agents (no real physics), we use the global dominant score
        as the field value — all colloids sense the same global gradient.
        """
        self._refresh_field()
        if not self._cached_field:
            return 0.0

        # Global pheromone score — all agents feel the same consensus field
        dominant_score = self._cached_field[0][1]

        # If fossil exists for this target, signal maximum saturation
        if self.target in self._kernel.fossils:
            return 1.0

        return float(dominant_score)

    def compute_observable(self, colloids: List["Colloid"]) -> np.ndarray:
        """
        Compute pheromone field for all colloids of the matching type.

        Returns
        -------
        np.ndarray of shape (n_colloids, 1)
            Pheromone strength for each colloid. Compatible with SwarmRL actor-critic.
        """
        indices = self.get_colloid_indices(colloids)
        observables = [
            self.compute_single_observable(colloids[i])
            for i in indices
        ]
        return np.array(observables, dtype=np.float32).reshape(-1, 1)
