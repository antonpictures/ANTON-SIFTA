"""Honest NVIDIA-facing tournament strings — no fake flex."""

from __future__ import annotations

from System.sifta_vs_nvidia_differentiator import (
    SIFTA_DIFFERENTIATORS,
    animal_mascot_line,
    nvidia_test_claims,
    tagline,
)


def test_nvidia_test_claims_shape():
    claims = nvidia_test_claims()
    assert len(claims) == 4
    assert "Isaac Sim" in claims[0]
    assert "GPU" in claims[1]
    assert "stigmergic" in claims[2]
    assert "REAL" in claims[3]


def test_differentiators_keys():
    assert set(SIFTA_DIFFERENTIATORS) >= {
        "stigmergic_receipts",
        "truth_labeled_organs",
        "animal_sensor_forge",
        "owner_metabolism",
        "protein_referee",
    }


def test_taglines_nonempty():
    assert "NVIDIA" in tagline() and "SIFTA" in tagline()
    assert "termite" not in animal_mascot_line().lower()  # mascot line is GPU vs stigmergy
    assert "stigmergic" in animal_mascot_line().lower()
