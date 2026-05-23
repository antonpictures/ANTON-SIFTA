"""Urban resilience simulator — invariants and monotonic coverage."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "Applications"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import sifta_urban_resilience_sim as urban  # noqa: E402


class TestUrbanResilience(unittest.TestCase):
    def test_vehicles_stay_on_roads(self) -> None:
        cfg = urban.UrbanConfig(width=48, height=32, n_vehicles=40, n_drones=20, seed=1)
        sim = urban.UrbanResilienceSim(cfg)
        for _ in range(100):
            sim.step()
            self.assertTrue(np.all(sim.vx < sim.split))
            self.assertTrue(np.all(sim.road[sim.vy, sim.vx]))

    def test_drone_coverage_increases_eventually(self) -> None:
        cfg = urban.UrbanConfig(width=56, height=40, n_vehicles=30, n_drones=60, rubble_frac=0.22, seed=2)
        sim = urban.UrbanResilienceSim(cfg)
        c0 = 0.0
        for _ in range(400):
            m = sim.step()
            c0 = m["coverage"]
        c1 = c0
        for _ in range(2000):
            m = sim.step()
            c1 = m["coverage"]
        self.assertGreater(c1, c0)


if __name__ == "__main__":
    unittest.main()
