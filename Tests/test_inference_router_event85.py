import json
from pathlib import Path

import pytest

from System.inference_router import (
    InferenceRouteCandidate,
    append_event85_route_decision,
    choose_event85_cost_vector_route,
    event85_metabolic_cost,
)


def test_event85_cost_vector_prefers_lowest_latency_plus_weight_penalty():
    candidates = [
        {
            "candidate_id": "corvid_remote",
            "model": "corvid",
            "latency_ms": 480,
            "file_weight_mb": 800,
            "token_usage": 0,
            "utility": 1000,
        },
        {
            "candidate_id": "gemma_heavy",
            "model": "gemma4",
            "latency_ms": 250,
            "file_weight_mb": 9600,
            "token_usage": 0,
            "utility": 1000,
        },
        InferenceRouteCandidate(
            candidate_id="qwen_local",
            model="qwen3.5:2b",
            latency_ms=300,
            file_weight_mb=2700,
            token_usage=0,
            utility=1000,
        ),
    ]

    choice = choose_event85_cost_vector_route(
        candidates,
        weights={"latency_ms": 1.0, "file_weight_mb": 0.05, "token_usage": 0.0},
    )

    assert choice["candidate_id"] == "qwen_local"
    assert choice["metabolic_cost"] == pytest.approx(435.0)
    assert choice["decision_path"] == ["qwen_local", "corvid_remote", "gemma_heavy"]
    assert choice["cost_weights"]["file_weight_mb"] == 0.05


def test_event85_cost_vector_skips_unavailable_and_tie_breaks_stably():
    choice = choose_event85_cost_vector_route(
        [
            {"candidate_id": "zeta", "model": "z", "latency_ms": 10, "available": False},
            {"candidate_id": "beta", "model": "b", "latency_ms": 5, "utility": 50},
            {"candidate_id": "alpha", "model": "a", "latency_ms": 5, "utility": 50},
        ],
        weights={"latency_ms": 1.0, "file_weight_mb": 0.0, "token_usage": 0.0},
    )

    assert choice["candidate_id"] == "alpha"
    assert choice["decision_path"] == ["alpha", "beta"]


def test_event85_cost_vector_rejects_invalid_or_empty_candidates():
    with pytest.raises(ValueError, match="no available"):
        choose_event85_cost_vector_route([{"candidate_id": "x", "available": False}])

    with pytest.raises(ValueError, match="finite and non-negative"):
        event85_metabolic_cost({"candidate_id": "x", "latency_ms": -1})

    with pytest.raises(ValueError, match="candidate_id"):
        choose_event85_cost_vector_route([{"latency_ms": 1}])


def test_append_event85_route_decision_writes_one_jsonl_row(tmp_path: Path):
    choice = choose_event85_cost_vector_route(
        [
            {"candidate_id": "a", "model": "qwen", "latency_ms": 20, "file_weight_mb": 1000},
            {"candidate_id": "b", "model": "gemma", "latency_ms": 5, "file_weight_mb": 9600},
        ]
    )
    ledger = tmp_path / "event85_router.jsonl"

    row = append_event85_route_decision(choice, ledger_path=ledger, trace_id="trace-test")

    stored = json.loads(ledger.read_text(encoding="utf-8"))
    assert stored["schema"] == "SIFTA_EVENT85_INFERENCE_ROUTE_DECISION_V1"
    assert stored["trace_id"] == "trace-test"
    assert stored["selected_candidate_id"] == row["selected_candidate_id"] == "a"
    assert stored["no_global_mesh_scalar"] is True
