#!/usr/bin/env python3
"""
tests/test_sifta_protein_folding_broker.py

Predator v7.0 — Event 78: Protein Folding Broker Truth Gauntlet
"""

import sys
from pathlib import Path

# Ensure project root is on path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import pytest
from System.sifta_protein_folding_broker import ProteinFoldingBroker, FoldingJob


def test_toy_fold_writes_pdb_and_meta(tmp_path):
    """Test valid toy fold generation and file writing."""
    broker = ProteinFoldingBroker()

    meta = broker.run(
        FoldingJob(
            sequence="ACFLIVGPGKTYL",
            engine="toy",
            out_dir=str(tmp_path),
        )
    )

    assert meta["status"] == "ok"
    assert meta["truth_label"] == "toy_CA_backbone_monte_carlo"
    assert meta["confidence"] == "demo_only"
    assert "energy" in meta
    
    # Verify PDB file actually exists
    pdb_path = Path(meta["pdb_path"])
    assert pdb_path.exists()
    assert pdb_path.stat().st_size > 0
    assert "ATOM" in pdb_path.read_text()

    # Verify metadata JSON actually exists
    meta_path = tmp_path / f"{meta['job_id']}.json"
    assert meta_path.exists()
    assert "toy_CA_backbone_monte_carlo" in meta_path.read_text()


def test_invalid_sequence_rejection():
    """Test that invalid amino acids are rejected before any folding."""
    broker = ProteinFoldingBroker()

    # 'B' and 'Z' are not standard amino acids
    with pytest.raises(ValueError, match="invalid amino acids"):
        broker.run(
            FoldingJob(
                sequence="ACDEFGBXYZ",
                engine="toy",
                out_dir=".sifta_state/protein_folds",
            )
        )

def test_long_sequence_guard():
    """Test that sequences longer than 2000 are rejected."""
    broker = ProteinFoldingBroker()

    # Sequence of length 2001
    seq = "A" * 2001
    with pytest.raises(ValueError, match="sequence too long"):
        broker.run(
            FoldingJob(
                sequence=seq,
                engine="toy",
                out_dir=".sifta_state/protein_folds",
            )
        )

def test_missing_real_backend_truth_label(tmp_path):
    """Test that requesting the real backend returns the correct missing truth label."""
    broker = ProteinFoldingBroker()

    meta = broker.run(
        FoldingJob(
            sequence="MKTFFVLLLCTFTVSES",
            engine="esmfold_cli",
            out_dir=str(tmp_path),
        )
    )

    assert meta["status"] == "missing_backend"
    assert meta["truth_label"] == "real_backend_not_installed"
    assert "hint" in meta

    # Verify metadata JSON exists even for a failed real run
    meta_path = tmp_path / f"{meta['job_id']}.json"
    assert meta_path.exists()
    assert "real_backend_not_installed" in meta_path.read_text()

def test_empty_sequence_rejection():
    """Test that an empty sequence is rejected."""
    broker = ProteinFoldingBroker()

    with pytest.raises(ValueError, match="empty protein sequence"):
        broker.run(
            FoldingJob(
                sequence="   \n  ",
                engine="toy",
                out_dir=".sifta_state/protein_folds",
            )
        )

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
