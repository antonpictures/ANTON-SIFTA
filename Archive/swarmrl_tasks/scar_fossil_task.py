"""
swarmrl_tasks/scar_fossil_task.py
==================================
SIFTA Scar Fossil as a SwarmRL Task.

Rewards colloids for following the pheromone gradient toward the strongest SCAR.
Issues kill_switch=True when field_is_stable() — the Strogatz sync moment.

Usage:
    from swarmrl_tasks.scar_fossil_task import ScarFossilTask
    task = ScarFossilTask(target="body_state.py", particle_type=0)
    trainer.task = task
"""

import sys
import time
from pathlib import Path
from typing import List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from scar_kernel import Kernel, consensus_field, field_is_stable

try:
    from swarmrl.components.colloid import Colloid
    from swarmrl.tasks.task import Task
    _HAS_SWARMRL = True
except ImportError:
    _HAS_SWARMRL = False

    class Colloid:
        def __init__(self, pos, director, id, velocity=None, type=0):
            self.pos = np.array(pos)
            self.director = np.array(director)
            self.id = id
            self.type = type

    class Task:
        def __init__(self, particle_type=0):
            self.particle_type = particle_type
            self._kill_switch = False

        @property
        def kill_switch(self):
            return self._kill_switch

        @kill_switch.setter
        def kill_switch(self, value):
            self._kill_switch = value

        def get_colloid_indices(self, colloids, p_type=None):
            if p_type is None:
                p_type = self.particle_type
            return [i for i, c in enumerate(colloids) if c.type == p_type]


class ScarFossilTask(Task):
    """
    SwarmRL Task driven by SIFTA pheromone consensus.

    Reward function: pheromone_score of the dominant trail,
    scaled by the number of agents in agreement.

    kill_switch fires when field_is_stable() — the swarm has converged.
    This is the Strogatz synchronization moment coded into the reward loop.
    """

    def __init__(self, target: str, particle_type: int = 0,
                 kernel: Kernel = None, stability_threshold: float = 0.15):
        super().__init__(particle_type=particle_type)
        self.target = target
        self._kernel = kernel or Kernel()
        self.stability_threshold = stability_threshold
        self._cached_reward = 0.0

    def __call__(self, colloids: List["Colloid"]) -> float:
        """
        Compute reward based on current field stability.

        Returns float reward:
          - 0.0  → field unstable, agents should keep exploring
          - 0-1  → partial convergence, field is crystallizing
          - 1.0  → fossil exists, perfect convergence

        Side effect: sets kill_switch=True when field stabilizes.
        """
        scars = [
            s for s in self._kernel.scars.values()
            if s.target == self.target and s.state in ("PROPOSED", "LOCKED")
        ]

        # Fossil = maximum reward, terminate
        if self.target in self._kernel.fossils:
            self.kill_switch = True
            return 1.0

        if not scars:
            return 0.0

        field = consensus_field(scars)
        stable = field_is_stable(field, threshold=self.stability_threshold)

        if stable:
            # Strogatz moment: set kill switch, return top score as reward
            self.kill_switch = True
            reward = float(field[0][1])
        else:
            # Still exploring: partial reward proportional to dominant score
            reward = float(field[0][1]) * 0.5 if field else 0.0

        self._cached_reward = reward
        return reward
