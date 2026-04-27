#!/usr/bin/env python3
"""
tests/test_sifta_protein_referee.py

Predator v7.0 — Event 79: The Scientific Referee Tests
"""

import sys
import json
import numpy as np
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.sifta_protein_referee import kabsch_rmsd, referee_judgment


def test_kabsch_rmsd_translation_rotation():
    """Verify Kabsch properly superimposes rotated/translated identical structures (RMSD=0)."""
    # Create 5 random CA coordinates
    P = np.random.rand(5, 3) * 10.0
    
    # Translate and rotate P to create Q
    translation = np.array([5.0, -3.0, 12.0])
    # 90 degree rotation around Z axis
    theta = np.pi / 2
    R = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0, 0, 1]
    ])
    
    Q = np.dot(P, R.T) + translation
    
    rmsd = kabsch_rmsd(P, Q)
    assert rmsd == pytest.approx(0.0, abs=1e-6), f"Expected 0.0, got {rmsd}"


def test_kabsch_rmsd_with_noise():
    """Verify Kabsch computes correct non-zero RMSD when structures differ."""
    # A simple triangle
    P = np.array([[0,0,0], [1,0,0], [0,1,0]], dtype=float)
    # The same triangle but one point moved by 1.0 on Z axis
    Q = np.array([[0,0,0], [1,0,0], [0,1,1]], dtype=float)
    
    rmsd = kabsch_rmsd(P, Q)
    # With one point moving 1 unit, the squared error is roughly 1/3 (0.333), 
    # but centering and optimal rotation will minimize this further.
    assert rmsd > 0.1 and rmsd < 1.0


def create_dummy_job(tmp_path: Path, job_id: str, sequence: str, engine: str, status: str, coords: np.ndarray) -> str:
    """Helper to create fake PDB and meta files."""
    pdb_path = tmp_path / f"{job_id}.pdb"
    meta_path = tmp_path / f"{job_id}.json"
    
    with open(pdb_path, "w") as f:
        for i, (x, y, z) in enumerate(coords, 1):
            f.write(f"ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n")
    
    meta = {
        "job_id": job_id,
        "engine": engine,
        "sequence": sequence,
        "status": status,
        "pdb_path": str(pdb_path),
        "truth_label": f"{engine}_truth"
    }
    meta_path.write_text(json.dumps(meta))
    return str(meta_path)


def test_referee_identical_structures(tmp_path):
    """Identical geometry should yield HIGH_CONFIDENCE_AGREEMENT."""
    coords = np.random.rand(10, 3) * 10.0
    m1 = create_dummy_job(tmp_path, "job1", "AAAAAAAAAA", "toy", "ok", coords)
    
    # Translated and slightly nudged coords
    coords2 = coords + np.array([10.0, 10.0, 10.0]) + np.random.normal(0, 0.1, (10, 3))
    m2 = create_dummy_job(tmp_path, "job2", "AAAAAAAAAA", "esmfold", "ok", coords2)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["status"] == "completed"
    assert judgment["epistemic_flag"] == "HIGH_CONFIDENCE_AGREEMENT"
    assert judgment["rmsd_angstroms"] < 2.0


def test_referee_contradiction(tmp_path):
    """Completely different geometry should yield EPISTEMIC_CONTRADICTION."""
    coords1 = np.array([[i*3.8, 0, 0] for i in range(10)], dtype=float) # straight line
    coords2 = np.random.rand(10, 3) * 20.0 # random scatter
    
    m1 = create_dummy_job(tmp_path, "job3", "AAAAAAAAAA", "toy", "ok", coords1)
    m2 = create_dummy_job(tmp_path, "job4", "AAAAAAAAAA", "alphafold", "ok", coords2)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["epistemic_flag"] == "EPISTEMIC_CONTRADICTION"
    assert judgment["rmsd_angstroms"] > 5.0


def test_referee_mismatched_sequence(tmp_path):
    """Referee must reject if sequences don't match."""
    coords = np.zeros((5, 3))
    m1 = create_dummy_job(tmp_path, "job5", "AAAAA", "toy", "ok", coords)
    m2 = create_dummy_job(tmp_path, "job6", "CCCCC", "toy", "ok", coords)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["status"] == "rejected"
    assert judgment["epistemic_flag"] == "invalid_comparison"


def test_referee_missing_backend(tmp_path):
    """Referee must reject if one job didn't actually fold (e.g., missing backend)."""
    coords = np.zeros((5, 3))
    m1 = create_dummy_job(tmp_path, "job7", "AAAAA", "toy", "ok", coords)
    m2 = create_dummy_job(tmp_path, "job8", "AAAAA", "esmfold", "missing_backend", coords)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["status"] == "rejected"
    assert judgment["epistemic_flag"] == "insufficient_evidence"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
