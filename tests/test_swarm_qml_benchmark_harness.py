#!/usr/bin/env python3
from pathlib import Path

from System.swarm_qml_benchmark_harness import (
    format_qml_benchmark_harness,
    ingest_qdataset_slice,
    run_qml_benchmark_suite,
    run_stgm_shot_allocation_benchmark,
    run_trainability_controller_benchmark,
)


def test_trainability_benchmark_is_proxy_and_equal_budget(tmp_path: Path):
    row = run_trainability_controller_benchmark(state_dir=tmp_path, shot_budget=64)

    assert row["benchmark_id"] == "stigmergic_qml_trainability_controller"
    assert row["truth_label"] == "LOCAL_PROXY_BENCHMARK_NOT_QPU"
    assert row["shot_budget_equal"] == 64
    assert "random_search_equal_budget" in row["baselines"]
    assert "spsa_like_equal_budget" in row["baselines"]
    assert "not a publication or QPU claim" in row["claim_boundary"]


def test_shot_allocation_keeps_equal_total_budget():
    row = run_stgm_shot_allocation_benchmark(shot_budget=240)

    assert row["benchmark_id"] == "stgm_shot_allocation"
    assert sum(row["uniform_allocation"]) == 240
    assert sum(row["stgm_allocation"]) == 240
    assert row["truth_label"] == "LOCAL_PROXY_BENCHMARK_NOT_QPU"


def test_qml_suite_writes_receipt_and_blocks_breakthrough_claim(tmp_path: Path):
    row = run_qml_benchmark_suite(state_dir=tmp_path, write_receipt=True)

    assert row["truth_label"] == "QML_BENCHMARK_HARNESS_V1"
    assert row["breakthrough_claim_allowed"] is False
    assert {b["benchmark_id"] for b in row["benchmarks"]} == {
        "stigmergic_qml_trainability_controller",
        "stgm_shot_allocation",
        "qec_swimmer_decoder",
    }
    ledger = tmp_path / "qml_benchmark_harness.jsonl"
    assert ledger.exists()
    assert "qml_benchmark_suite" in ledger.read_text(encoding="utf-8")
    line = format_qml_benchmark_harness(state_dir=tmp_path)
    assert "QML benchmark harness" in line
    assert "local proxy only" in line


def test_qdataset_slice_ingest_hashes_local_file_without_unpickling(tmp_path: Path):
    sample = tmp_path / "slice.json"
    sample.write_text('{"pauli_measurement_distributions": [0.5, 0.5], "vo_noise": [0.1]}\n', encoding="utf-8")

    row = ingest_qdataset_slice(sample, state_dir=tmp_path, write_receipt=True)

    assert row["truth_label"] == "QDATASET_SLICE_INGEST_V1"
    assert row["ok"] is True
    assert len(row["sha256"]) == 64
    assert row["parser"] == "json_first_row"
    assert "pauli_measurement_distributions" in row["top_level_keys"]
    assert "not QPU output" in row["truth_boundary"]
