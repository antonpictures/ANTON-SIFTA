#!/usr/bin/env python3
"""
tests/test_sifta_protein_referee.py

Predator v7.0 — Event 81: Multi-Axis Scientific Referee Tests
Validates TM-score and Contact Map Precision logic.
"""

import sys
import json
import numpy as np
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.sifta_protein_referee import kabsch_align, multi_metric_compare, referee_judgment, referee_triangulate


def test_tm_score_identical_structures():
    """Verify TM-score == 1.0 for identical structures (even if translated/rotated)."""
    P = np.random.rand(10, 3) * 10.0
    
    translation = np.array([5.0, -3.0, 12.0])
    theta = np.pi / 2
    R = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0, 0, 1]
    ])
    
    Q = np.dot(P, R.T) + translation
    
    metrics = multi_metric_compare(P, Q)
    assert metrics["tm_score"] == pytest.approx(1.0, abs=1e-3)
    assert metrics["rmsd_angstroms"] == pytest.approx(0.0, abs=1e-3)
    assert metrics["contact_precision"] == pytest.approx(1.0, abs=1e-3)


def test_contact_map_overlap():
    """Verify contact maps detect precision/recall effectively."""
    # Build a linear CA chain
    P = np.array([[i * 3.8, 0, 0] for i in range(10)], dtype=float)
    # Build the same chain, but the end folds back (residue 0 and 9 touch)
    Q = np.array([[i * 3.8, 0, 0] for i in range(10)], dtype=float)
    Q[-1] = [0.0, 3.8, 0.0]  # Fold residue 9 to touch residue 0
    
    metrics = multi_metric_compare(P, Q)
    # The fold creates new contacts in Q that don't exist in P.
    assert metrics["contact_precision"] < 1.0
    assert metrics["tm_score"] < 1.0


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


def test_referee_true_consensus(tmp_path):
    """Identical geometry should yield TRUE_CONSENSUS."""
    coords = np.random.rand(10, 3) * 10.0
    m1 = create_dummy_job(tmp_path, "job1", "AAAAAAAAAA", "toy", "ok", coords)
    m2 = create_dummy_job(tmp_path, "job2", "AAAAAAAAAA", "esmfold", "ok", coords)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["status"] == "completed"
    assert judgment["epistemic_flag"] == "TRUE_CONSENSUS"
    assert judgment["metrics"]["tm_score"] > 0.7


def test_referee_contradiction(tmp_path):
    """Completely different geometry should yield STRUCTURAL_CONTRADICTION."""
    coords1 = np.array([[i*3.8, 0, 0] for i in range(10)], dtype=float) # straight line
    coords2 = np.random.rand(10, 3) * 50.0 # huge random scatter
    
    m1 = create_dummy_job(tmp_path, "job3", "AAAAAAAAAA", "toy", "ok", coords1)
    m2 = create_dummy_job(tmp_path, "job4", "AAAAAAAAAA", "alphafold", "ok", coords2)
    
    judgment = referee_judgment(m1, m2)
    assert judgment["epistemic_flag"] == "STRUCTURAL_CONTRADICTION"
    assert judgment["metrics"]["tm_score"] < 0.5


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


def test_referee_triangulation_outlier(tmp_path):
    """Triangulation should detect consensus via TM-score and flag the outlier."""
    coords_base = np.random.rand(10, 3) * 10.0
    
    # Engine 1 and 2 agree perfectly
    m1 = create_dummy_job(tmp_path, "job_t1", "AAAAAAAAAA", "alphafold", "ok", coords_base)
    m2 = create_dummy_job(tmp_path, "job_t2", "AAAAAAAAAA", "esmfold", "ok", coords_base)
    
    # Engine 3 hallucinates wildly
    coords_hallucinated = coords_base + np.random.rand(10, 3) * 100.0
    m3 = create_dummy_job(tmp_path, "job_t3", "AAAAAAAAAA", "toy", "ok", coords_hallucinated)
    
    judgment = referee_triangulate([m1, m2, m3])
    
    assert judgment["status"] == "completed"
    assert judgment["epistemic_flag"] == "CONSENSUS_WITH_OUTLIER"
    assert "alphafold" in judgment["consensus_cluster"]
    assert "esmfold" in judgment["consensus_cluster"]
    assert "toy" in judgment["outliers_ejected"]
    
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
