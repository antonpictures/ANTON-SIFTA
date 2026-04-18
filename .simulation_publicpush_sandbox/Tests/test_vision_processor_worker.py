"""Unit tests for stigmergic vision / edge worker."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
SYS = REPO / "System"
if str(SYS) not in sys.path:
    sys.path.insert(0, str(SYS))

from vision_processor_worker import VisionConfig, VisionProcessorWorker, synth_topography  # noqa: E402


class TestVisionProcessorWorker(unittest.TestCase):
    def test_synth_topography_shape_and_range(self) -> None:
        im = synth_topography(64, 48, seed=42)
        self.assertEqual(im.shape, (48, 64))
        self.assertGreaterEqual(float(np.min(im)), 0.0)
        self.assertLessEqual(float(np.max(im)), 1.0)

    def test_step_increases_pheromone_on_activity(self) -> None:
        im = synth_topography(32, 32, seed=1)
        cfg = VisionConfig(width=32, height=32, swimmers=80, seed=7)
        w = VisionProcessorWorker(im, cfg)
        p0 = float(np.sum(w.pher))
        for _ in range(50):
            w.step()
        p1 = float(np.sum(w.pher))
        self.assertGreater(p1, p0)
        self.assertGreater(w.edge_hits_total, 0)


if __name__ == "__main__":
    unittest.main()
