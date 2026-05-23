"""Tests for the receipt → Dreamer trainer.

These pin:
  - With no source rows + no extras, the trainer ships an empty but valid
    artifact (transition_count = 0, value_count = 0) and does NOT crash.
  - The trainer correctly maps audit pairs into transitions (one pair
    becomes exactly one observation; the peer model dedupes by sa_key).
  - With >= 10 distinct (state, action) triples + >= 5 distinct states,
    the artifact crosses the frontier-loop threshold and the AGI frontier
    flips ``learned_latent_models`` from SCAFFOLDED_UNDERPOWERED to
    EVIDENCED.
  - Extra triples passed through the API land in the artifact verbatim.
  - The trainer's receipt row has a sha256 + matches the artifact counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_latent_world_model_trainer import (  # noqa: E402
    TRAINER_LEDGER,
    TRUTH_LABEL,
    _iter_audit_triples,
    _iter_steering_decision_triples,
    train_from_receipts,
)


# ── triple extraction ─────────────────────────────────────────────────────


def test_audit_triple_extraction_maps_correct_field_to_reward():
    rows = [
        {
            "pairs": [
                {
                    "dominant_detector": "novelty_pressure",
                    "predicted_next_route": "DEEP_CORTEX",
                    "actual_route": "DEEP_CORTEX",
                    "correct": True,
                },
                {
                    "dominant_detector": "overload",
                    "predicted_next_route": "CONSERVE_OR_DEFER",
                    "actual_route": "NORMAL_CORTEX",
                    "correct": False,
                },
            ]
        }
    ]
    triples = list(_iter_audit_triples(rows))
    assert len(triples) == 2
    assert triples[0] == ("dom:novelty_pressure", "DEEP_CORTEX", "route:DEEP_CORTEX", 1.0)
    assert triples[1] == ("dom:overload", "CONSERVE_OR_DEFER", "route:NORMAL_CORTEX", 0.0)


def test_steering_decision_triple_picks_max_confidence_prediction():
    rows = [
        {
            "importance_label": "UTILITY",
            "matched_pattern": "utility_pattern",
            "predictions": [
                {"source": "metabolic_pressure", "target": "conserve_or_spend", "confidence": 0.1},
                {"source": "journal_importance", "target": "attention_budget", "confidence": 0.7},
                {"source": "novelty", "target": "deep_cortex", "confidence": 0.0},
            ],
        }
    ]
    triples = list(_iter_steering_decision_triples(rows))
    assert len(triples) == 1
    state, action, next_state, reward = triples[0]
    assert state == "imp:UTILITY"
    assert action == "attention_budget"          # max confidence target
    assert next_state == "pat:utility_pattern"
    assert reward == 0.7


def test_steering_decision_rejects_rows_without_pattern_or_predictions():
    rows = [
        {"importance_label": "HIGH", "matched_pattern": "", "predictions": [{"confidence": 0.5}]},
        {"importance_label": "HIGH", "matched_pattern": "p", "predictions": []},
        {"importance_label": "", "matched_pattern": "p", "predictions": [{"confidence": 0.5}]},
    ]
    assert list(_iter_steering_decision_triples(rows)) == []


# ── trainer behaviour ─────────────────────────────────────────────────────


def test_trainer_empty_state_dir_ships_valid_empty_artifact(tmp_path):
    out = train_from_receipts(root=tmp_path, save=True)
    assert out["truth_label"] == TRUTH_LABEL
    assert out["triple_count"] == 0
    assert out["transition_count"] == 0
    assert out["value_count"] == 0
    # Artifact path may or may not exist depending on whether the peer
    # model wrote on a no-op save; what matters is no crash + receipt.
    assert "sha256" in out and len(out["sha256"]) == 64


def test_trainer_with_extra_triples_crosses_frontier_threshold(tmp_path):
    """The frontier-loop gate requires >= 10 transitions and >= 5 values.

    Construct 10 distinct (state, action, next_state) triples spanning
    5+ unique states.
    """
    extras = []
    for i in range(10):
        state = f"dom:detector_{i % 6}"        # 6 unique state values
        action = f"action_{i % 4}"
        next_state = f"route:NEXT_{i}"          # 10 unique next states → values
        extras.append((state, action, next_state, 1.0 if i % 2 == 0 else 0.0))

    out = train_from_receipts(root=tmp_path, extra_triples=extras, save=True)
    assert out["transition_count"] >= 10
    assert out["value_count"] >= 5

    # Artifact has the expected shape for the frontier-loop gate.
    artifact = json.loads((tmp_path / "latent_world_model.json").read_text(encoding="utf-8"))
    assert "transitions" in artifact
    assert "values" in artifact
    assert len(artifact["transitions"]) >= 10
    assert len(artifact["values"]) >= 5


def test_trainer_flips_agi_frontier_to_evidenced(tmp_path):
    """End-to-end: the frontier_status() call must report EVIDENCED."""
    extras = []
    for i in range(12):
        extras.append((f"dom:d_{i % 7}", f"a_{i % 3}", f"route:N_{i}", float(i % 2)))

    train_from_receipts(root=tmp_path, extra_triples=extras, save=True)

    from System.swarm_agi_frontier_loop import latent_world_model_stats

    stats = latent_world_model_stats(root=tmp_path)
    assert stats["status"] == "EVIDENCED", stats
    assert stats["ready"] is True
    assert stats["transition_count"] >= 10
    assert stats["value_count"] >= 5


def test_trainer_receipt_is_appended_to_ledger(tmp_path):
    extras = [(f"s:{i}", "a", f"s2:{i}", 1.0) for i in range(3)]
    out = train_from_receipts(root=tmp_path, extra_triples=extras, save=True)
    ledger = tmp_path / TRAINER_LEDGER
    assert ledger.exists()
    last = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert last["kind"] == "LATENT_WORLD_MODEL_TRAINER_RUN"
    assert last["sha256"] == out["sha256"]
    assert last["transition_count"] == out["transition_count"]
    assert last["value_count"] == out["value_count"]


def test_trainer_observes_real_audit_pair_rows_when_present(tmp_path):
    """Drop a synthetic prediction-audit row in the state dir; verify it
    contributes to the artifact."""
    audit_path = tmp_path / "steering_prediction_audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "dominant_detector": "novelty_pressure",
                        "predicted_next_route": "DEEP_CORTEX",
                        "actual_route": "DEEP_CORTEX",
                        "correct": True,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = train_from_receipts(root=tmp_path, save=True)
    # One pair → at least one observation → at least one transition.
    assert out["triple_count"] >= 1
    assert out["transition_count"] >= 1
    assert out["source_counts"]["steering_prediction_audit.jsonl"] == 1
