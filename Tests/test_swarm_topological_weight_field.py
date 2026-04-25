#!/usr/bin/env python3
"""Tests for System/swarm_topological_weight_field.py."""

import json
from pathlib import Path

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_topological_weight_field import TopologicalWeightField


def test_weights_normalize_to_one():
    f = TopologicalWeightField()
    f.record_interaction(["a", "b"], success=True, entropy=0.1)
    f.record_interaction(["a", "c"], success=True, entropy=0.1)
    w = f.generate_merge_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_fingerprint_is_deterministic():
    f = TopologicalWeightField()
    f.record_interaction(["x", "y"], success=True, entropy=0.2)
    assert f.fingerprint() == f.fingerprint()


def test_high_success_low_entropy_beats_high_entropy_same_path():
    """Compare raw node scores — normalized weights can tie when the graph is symmetric."""
    good = TopologicalWeightField()
    bad = TopologicalWeightField()
    for _ in range(10):
        good.record_interaction(["u", "v"], success=True, entropy=0.05)
        bad.record_interaction(["u", "v"], success=True, entropy=2.0)
    wg = good.compute_weight(good.nodes["u"])
    wb = bad.compute_weight(bad.nodes["u"])
    assert wg > wb


def test_paths_observed_counts_interactions_not_edges():
    f = TopologicalWeightField()
    f.record_interaction(["solo"], success=True, entropy=0.1)
    f.record_interaction(["a", "b", "c"], success=True, entropy=0.2)

    assert f.paths_observed() == 2


def test_invalid_interaction_rejected():
    f = TopologicalWeightField()

    try:
        f.record_interaction([], success=True, entropy=0.1)
    except ValueError as exc:
        assert "path" in str(exc)
    else:
        raise AssertionError("empty paths must be rejected")

    try:
        f.record_interaction(["a"], success=True, entropy=-0.1)
    except ValueError as exc:
        assert "entropy" in str(exc)
    else:
        raise AssertionError("negative entropy must be rejected")


def test_ledger_row_matches_canon(tmp_path: Path):
    ledger = tmp_path / "topological_weight_field.jsonl"
    f = TopologicalWeightField()
    f.record_interaction(["lora_reasoning", "lora_style"], success=True, entropy=0.1)
    f.append_ledger_row(ledger_path=ledger, paths_observed=128, entropy_mean=0.42)

    row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert set(row.keys()) == LEDGER_SCHEMAS["topological_weight_field.jsonl"]
    assert row["event"] == "topological_weight_update"
    assert row["paths_observed"] == 128
    assert abs(row["entropy_mean"] - 0.42) < 1e-9
    assert "lora_reasoning" in row["adapters"]
