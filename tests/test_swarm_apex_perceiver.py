from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from System.swarm_apex_perceiver import SwarmApexPerceiver


def test_summary_hydrates_from_existing_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "apex.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "schema": "SIFTA_APEX_PERCEIVER_TRACE_V2",
                "stats": {
                    "raw_N": 100,
                    "gate_N": 12,
                    "latent_L": 32,
                    "active_slots": 3,
                    "compression_pct": 88.0,
                    "raw_entropy_bits": 4.2,
                    "survivor_entropy_bits": 1.7,
                    "attention_sparsity_pct": 93.5,
                },
                "top_focus": [
                    {
                        "slot_id": 0,
                        "salience": 0.91,
                        "dominant_modality": "vision",
                        "magnitude": 12.0,
                    }
                ],
                "focus_hash": "abc123def4567890",
            }
        )
        + "\n"
    )

    perceiver = SwarmApexPerceiver(ledger=ledger)
    summary = perceiver.summary_for_alice()

    assert "raw_tokens=100" in summary
    assert "attention_zero=93.5%" in summary
    assert "VISION" in summary
    assert "proof_hash=abc123def456" in summary


def test_sparse_attention_handles_flat_signal_without_nan(tmp_path: Path) -> None:
    perceiver = SwarmApexPerceiver(
        num_latents=4,
        latent_dim=8,
        sparsity=0.85,
        ledger=tmp_path / "apex.jsonl",
    )

    signal = np.zeros((80, 8), dtype=np.float32)
    results = perceiver.observe(vision=signal)
    stats = perceiver.get_stats()

    assert results
    assert np.isfinite(perceiver.latents).all()
    assert stats["math_contract"] == "deterministic_sparsemax_cross_attention"
    assert 0.0 <= stats["attention_sparsity_pct"] <= 100.0
    assert "proof_hash=" in perceiver.summary_for_alice()


def test_apex_focus_hash_changes_when_signal_changes(tmp_path: Path) -> None:
    ledger = tmp_path / "apex.jsonl"
    perceiver = SwarmApexPerceiver(
        num_latents=4,
        latent_dim=8,
        sparsity=0.85,
        ledger=ledger,
    )

    baseline = np.zeros((80, 8), dtype=np.float32)
    perceiver.observe(vision=baseline)
    first_hash = json.loads(ledger.read_text().splitlines()[-1])["focus_hash"]

    prey = baseline.copy()
    prey[7] = 20.0
    perceiver.observe(vision=prey)
    second_hash = json.loads(ledger.read_text().splitlines()[-1])["focus_hash"]

    assert first_hash != second_hash
