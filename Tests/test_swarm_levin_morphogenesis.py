from __future__ import annotations

import numpy as np

from System.swarm_levin_morphogenesis import (
    BioelectricGapJunctionRegenerator,
    proof_of_gap_junction_regeneration,
)


def test_gap_junction_regenerates_corrupted_file_bytes_exactly():
    original = b"window:x=10,y=20,w=300,h=180;title=SIFTA;field=unified"
    tissue = BioelectricGapJunctionRegenerator(original, width=12)

    tissue.corrupt_bytes(8, 35, value=0)
    damaged = tissue.to_bytes()
    assert damaged != original
    assert tissue.integrity() < 1.0

    tissue.regenerate(max_steps=240)

    assert tissue.to_bytes() == original
    assert tissue.integrity() == 1.0


def test_gap_junction_regenerates_2d_window_geometry_pattern():
    target = np.zeros((12, 12), dtype=np.float32)
    target[2:10, 3:9] = 180.0
    target[5, 5] = 255.0
    tissue = BioelectricGapJunctionRegenerator(target)

    tissue.damage_rect(3, 9, 4, 8, value=0.0)
    assert tissue.integrity() < 1.0

    tissue.regenerate(max_steps=240)

    assert np.array_equal(tissue.V, target)


def test_gap_junction_proof_passes():
    assert proof_of_gap_junction_regeneration() is True
