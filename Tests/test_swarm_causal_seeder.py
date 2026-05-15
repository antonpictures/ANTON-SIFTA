"""Tests for the causal-intervention seeder.

These pin:
  - Audit-pair → intervention mapping preserves direction + magnitude.
  - Governor adaptation rows produce one intervention per adaptation.
  - The peer logger receives every extracted intervention exactly once.
  - Synthetic high-density rows can flip the closure gate.
  - The seeder honours SIFTA_CAUSAL_LOGGER_DISABLE.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_causal_seeder import (  # noqa: E402
    TRUTH_LABEL,
    _audit_pair_to_intervention,
    _collect_interventions,
    _governor_row_to_intervention,
    seed_from_receipts,
)


# ── extraction primitives ────────────────────────────────────────────────


def test_audit_pair_with_correct_prediction_has_positive_effect():
    iv = _audit_pair_to_intervention(
        {
            "predicted_next_route": "DEEP_CORTEX",
            "actual_route": "DEEP_CORTEX",
            "correct": True,
            "confidence": 0.689,
            "dominant_detector": "novelty_pressure",
        }
    )
    assert iv is not None
    assert iv["do_vars"]["predicted_next_route"] == "DEEP_CORTEX"
    assert iv["causal_effect_size"] > 0
    assert iv["observed_shift"]["direction_matches"] is True
    assert iv["confounder_check"]["owner_switch"] is False


def test_audit_pair_with_wrong_prediction_has_negative_effect():
    iv = _audit_pair_to_intervention(
        {
            "predicted_next_route": "FAST_REFLEX",
            "actual_route": "DEEP_CORTEX",
            "correct": False,
            "confidence": 0.4,
        }
    )
    assert iv is not None
    assert iv["causal_effect_size"] < 0
    assert iv["observed_shift"]["direction_matches"] is False


def test_audit_pair_without_predicted_route_returns_none():
    assert _audit_pair_to_intervention({"predicted_next_route": "", "actual_route": "DEEP_CORTEX"}) is None
    assert _audit_pair_to_intervention({"actual_route": "DEEP_CORTEX"}) is None


def test_governor_row_yields_one_intervention_per_adaptation():
    row = {
        "ts": 1778759076.0,
        "adaptations": [
            {
                "name": "novelty_pressure",
                "previous_weight": 1.0,
                "new_weight": 1.05,
                "delta": 0.05,
                "accuracy": 0.8,
                "sample_count": 12,
                "status": "WEIGHT_INCREASED",
            },
            {
                "name": "overload",
                "previous_weight": 1.0,
                "new_weight": 0.95,
                "delta": -0.05,
                "accuracy": 0.3,
                "sample_count": 10,
                "status": "WEIGHT_DECREASED",
            },
        ],
    }
    out = list(_governor_row_to_intervention(row))
    assert len(out) == 2
    assert out[0]["do_vars"]["detector"] == "novelty_pressure"
    assert out[0]["causal_effect_size"] > 0           # acc>0.5 + delta>0 → +
    assert out[1]["do_vars"]["detector"] == "overload"
    assert out[1]["causal_effect_size"] > 0           # acc<0.5 + delta<0 → also +
                                                       # (low accuracy reduced weight; direction confirmed)


# ── full pipeline ────────────────────────────────────────────────────────


def test_seeder_writes_interventions_to_peer_logger(tmp_path):
    # Drop synthetic audit + governor rows
    audit_path = tmp_path / "steering_prediction_audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "predicted_next_route": "DEEP_CORTEX",
                        "actual_route": "DEEP_CORTEX",
                        "correct": True,
                        "confidence": 0.7,
                    },
                    {
                        "predicted_next_route": "FAST_REFLEX",
                        "actual_route": "NORMAL_CORTEX",
                        "correct": False,
                        "confidence": 0.3,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = seed_from_receipts(root=tmp_path, write=True)
    assert out["interventions_extracted"] == 2
    assert out["interventions_written"] == 2
    assert out["ledger_row_count"] == 2

    # Verify peer ledger
    ledger = tmp_path / "causal_intervention_log.jsonl"
    assert ledger.exists()
    rows = [json.loads(ln) for ln in ledger.read_text().splitlines() if ln.strip()]
    assert len(rows) == 2
    assert rows[0]["intervention"]["do"]["predicted_next_route"] == "DEEP_CORTEX"


def test_seeder_extras_can_flip_closure_gate(tmp_path):
    """20 high-quality synthetic interventions should let the closure
    gate (n≥15, |τ̂|>0.12, p<0.05) flip to True."""
    extras = []
    # 20 clean treated rows with consistent +0.5 effect
    for i in range(20):
        extras.append(
            {
                "tick_id": i,
                "do_vars": {"detector": f"d_{i%4}"},
                "expected_effect_on": "accuracy",
                "observed_shift": {"direction_matches": True},
                "causal_effect_size": 0.5,
                "confounder_check": {"owner_switch": False, "metabolic_critical": False},
                "organ": "test_synthetic",
                "truth_label": "CAUSAL_CLOSURE_INTERVENTION_TEST",
            }
        )
    # 10 control rows with effect ~0
    for i in range(10):
        extras.append(
            {
                "tick_id": 100 + i,
                "do_vars": {"detector": "control"},
                "expected_effect_on": "accuracy",
                "observed_shift": {"direction_matches": False},
                "causal_effect_size": 0.02,
                "confounder_check": {"owner_switch": False, "metabolic_critical": False},
                "organ": "test_synthetic",
                "truth_label": "CAUSAL_CLOSURE_INTERVENTION_TEST",
            }
        )

    out = seed_from_receipts(root=tmp_path, extra_interventions=extras, write=True)
    assert out["interventions_written"] >= 30
    # With 20 strong-signal treated + 10 weak control, |τ̂| should be > 0.12
    # and the permutation p-value < 0.05.
    est = out["estimate"]
    assert est["n_treated"] >= 15
    assert abs(est["weighted_effect"]) > 0.12
    assert est["p_value"] < 0.05
    assert out["closure_gate"] is True


def test_seeder_honours_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_CAUSAL_LOGGER_DISABLE", "1")
    audit_path = tmp_path / "steering_prediction_audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "predicted_next_route": "DEEP_CORTEX",
                        "actual_route": "DEEP_CORTEX",
                        "correct": True,
                        "confidence": 0.5,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = seed_from_receipts(root=tmp_path, write=True)
    # Extracted yes, written no
    assert out["interventions_extracted"] == 1
    assert out["interventions_written"] == 0
    assert out["ledger_row_count"] == 0


def test_seeder_flips_agi_frontier_when_evidence_is_strong(tmp_path):
    extras = []
    for i in range(20):
        extras.append(
            {
                "tick_id": i,
                "do_vars": {"detector": f"d_{i%5}"},
                "expected_effect_on": "accuracy",
                "observed_shift": {"direction_matches": True},
                "causal_effect_size": 0.55,
                "confounder_check": {"owner_switch": False, "metabolic_critical": False},
                "organ": "test_synthetic",
                "truth_label": "CAUSAL_CLOSURE_INTERVENTION_TEST",
            }
        )
    for i in range(10):
        extras.append(
            {
                "tick_id": 100 + i,
                "do_vars": {"detector": "ctl"},
                "expected_effect_on": "accuracy",
                "observed_shift": {"direction_matches": False},
                "causal_effect_size": 0.0,
                "confounder_check": {"owner_switch": False, "metabolic_critical": False},
                "organ": "test_synthetic",
                "truth_label": "CAUSAL_CLOSURE_INTERVENTION_TEST",
            }
        )
    seed_from_receipts(root=tmp_path, extra_interventions=extras, write=True)

    from System.swarm_agi_frontier_loop import causal_frontier_stats

    stats = causal_frontier_stats(root=tmp_path)
    assert stats["intervention_count"] >= 30
    assert stats["estimate"]["sufficient_data"] is True
    assert stats["status"] == "EVIDENCED", stats
    assert stats["ready"] is True
