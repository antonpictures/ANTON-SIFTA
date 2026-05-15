"""Honest NVIDIA-facing tournament strings — no fake flex."""

from __future__ import annotations

from System.sifta_vs_nvidia_differentiator import (
    SIFTA_DIFFERENTIATORS,
    animal_mascot_line,
    benchmark_contrast_claims,
    institutional_contrast_line,
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
    assert all(v["truth_label"] for v in SIFTA_DIFFERENTIATORS.values())


def test_taglines_nonempty():
    assert "NVIDIA" in tagline() and "SIFTA" in tagline()
    assert "termite" not in animal_mascot_line().lower()  # mascot line is GPU vs stigmergy
    assert "stigmergic" in animal_mascot_line().lower()
    assert "local receipts" in institutional_contrast_line()


def test_benchmark_contrast_claims_are_truth_labeled():
    rows = benchmark_contrast_claims()
    assert len(rows) >= 3
    assert {row["truth_label"] for row in rows} >= {
        "OBSERVED_VENDOR_DOMAIN",
        "OPERATIONAL",
        "HYPOTHESIS_UNTIL_RECEIPTED",
    }
