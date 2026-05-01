#!/usr/bin/env python3
"""
tests/test_sifta_protein_folding_broker.py

Predator v7.0 — Event 78: Protein Folding Broker Truth Gauntlet
"""

import json
import sys
from pathlib import Path

# Ensure project root is on path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import pytest
from System.sifta_protein_folding_broker import ProteinFoldingBroker, FoldingJob
from System.alphafold_compliance import (
    alphafold_server_output_policy_metadata,
    policy_for_artifact_family,
)


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


def test_c55m_hp_lattice_fold_writes_pdb_and_meta(tmp_path, monkeypatch):
    """C55M + George deterministic lattice engine writes falsifiable artifacts."""
    monkeypatch.setenv("SIFTA_HP_LATTICE_BEAM", "96")
    broker = ProteinFoldingBroker()

    meta = broker.run(
        FoldingJob(
            sequence="ACFLIVGPGKTYL",
            engine="c55m_hp_lattice",
            out_dir=str(tmp_path),
        )
    )

    assert meta["status"] == "ok"
    assert meta["truth_label"] == "c55m_george_hp_lattice_beam_search"
    assert meta["confidence"] == "deterministic_lattice_baseline"
    assert meta["energy"] <= 0
    assert meta["hydrophobic_contacts"] >= 0
    assert meta["cosigned_by"] == ["C55M-DR-CODEX", "George Anton"]

    pdb_path = Path(meta["pdb_path"])
    assert pdb_path.exists()
    text = pdb_path.read_text()
    assert "SIFTA C55M + George HP lattice" in text
    assert text.count("\nATOM") + int(text.startswith("ATOM")) == len(meta["sequence"])

    meta_path = tmp_path / f"{meta['job_id']}.json"
    assert meta_path.exists()
    assert "c55m_george_hp_lattice_beam_search" in meta_path.read_text()


def test_c55m_hp_lattice_is_deterministic(tmp_path, monkeypatch):
    """Same sequence and beam width must produce the same structure hash."""
    monkeypatch.setenv("SIFTA_HP_LATTICE_BEAM", "96")
    broker = ProteinFoldingBroker()

    meta1 = broker.run(
        FoldingJob(sequence="FVNQHLCGSHLVEALY", engine="c55m_hp_lattice",
                   out_dir=str(tmp_path / "a"))
    )
    meta2 = broker.run(
        FoldingJob(sequence="FVNQHLCGSHLVEALY", engine="c55m_hp_lattice",
                   out_dir=str(tmp_path / "b"))
    )

    assert meta1["structure_hash"] == meta2["structure_hash"]
    assert meta1["energy"] == meta2["energy"]


def test_alphafold_db_receipt_preserves_cc_by_attribution(tmp_path, monkeypatch):
    """AFDB lookups must preserve CC-BY attribution metadata in meta + receipt."""

    class _FakeResponse:
        def __init__(self, payload: bytes):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

    pdb_text = (
        "ATOM      1  CA  ALA A   1      11.104  13.207  14.099  1.00 92.50           C\n"
        "END\n"
    )
    api_payload = json.dumps(
        [
            {
                "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P69905-F1-model_v4.pdb",
                "gene": "HBA1",
                "organismScientificName": "Homo sapiens",
                "globalMetricValue": 95.1,
                "latestVersion": 4,
            }
        ]
    ).encode()
    calls = []

    def _fake_urlopen(req, timeout=None, context=None):
        calls.append(str(getattr(req, "full_url", req)))
        if len(calls) == 1:
            return _FakeResponse(api_payload)
        return _FakeResponse(pdb_text.encode())

    monkeypatch.setattr("System.sifta_protein_folding_broker.urllib.request.urlopen", _fake_urlopen)
    out_dir = tmp_path / "protein_folds"
    broker = ProteinFoldingBroker()

    meta = broker.run(
        FoldingJob(
            sequence="",
            engine="alphafold_db",
            uniprot_id="P69905",
            out_dir=str(out_dir),
        )
    )

    compliance = meta["compliance"]
    assert meta["truth_label"] == "alphafold2_ebi_database"
    assert compliance["license"] == "CC-BY-4.0"
    assert compliance["requires_attribution"] is True
    assert compliance["uniprot_id"] == "P69905"
    assert any(c["id"] == "jumper_2021_alphafold" for c in compliance["citations"])

    receipt = json.loads((tmp_path / "protein_fold_receipts.jsonl").read_text().splitlines()[0])
    assert receipt["engine"] == "alphafold_db"
    assert receipt["pdb_sha256"]
    assert receipt["compliance"]["license"] == "CC-BY-4.0"


def test_alphafold_server_policy_is_noncommercial_and_restrictive():
    """Server output policy is separate from AFDB and must not be treated as CC-BY."""

    afdb = policy_for_artifact_family("alphafold_db")
    server = alphafold_server_output_policy_metadata(output_generated_date="2026-05-01")

    assert afdb["license"] == "CC-BY-4.0"
    assert server["allowed_use"] == "non_commercial_only"
    assert server["requires_terms_notice"] is True
    assert "automated_binding_or_interaction_prediction_systems_including_glide_or_autodock" in server["prohibited_uses"]


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
