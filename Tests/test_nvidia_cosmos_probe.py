#!/usr/bin/env python3
"""Cosmos-Reason1 probe: ONLINE vs REAL tied to inference receipts, not cache alone."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.nvidia_cosmos_probe import (
    COSMOS_REASON1_REPO_ID,
    SCHEMA_INFERENCE,
    SCHEMA_METADATA,
    append_metadata_receipt,
    cosmos_join_truth_row,
    cosmos_truth_probe_dict,
    record_inference_receipt,
)


def test_join_truth_online_without_weights(tmp_path):
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=tmp_path / "c.jsonl")
    assert r.join_truth == "ONLINE"
    assert not r.weights_cached
    assert not r.inference_ok


def test_join_truth_online_with_cache_but_no_inference(tmp_path):
    hub = tmp_path / "hub" / "models--nvidia--Cosmos-Reason1-7B"
    hub.mkdir(parents=True)
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=tmp_path / "c.jsonl")
    assert r.join_truth == "ONLINE"
    assert r.weights_cached
    assert "inference" in r.detail.lower()


def test_join_truth_real_after_inference_receipt(tmp_path):
    rec = tmp_path / "c.jsonl"
    record_inference_receipt(
        ok=True,
        prompt_excerpt="describe",
        image_sha256="abc",
        path=rec,
        writer="pytest",
    )
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=rec)
    assert r.join_truth == "REAL"
    assert r.inference_ok


def test_join_truth_real_after_swarm_cosmos_reason1_receipt(tmp_path):
    """``swarm_cosmos_reason1`` writes SIFTA_COSMOS_REASON1_V1 truth=REAL — join must see it."""
    rec = tmp_path / "c.jsonl"
    rec.write_text(
        json.dumps(
            {
                "schema": "SIFTA_COSMOS_REASON1_V1",
                "truth": "REAL",
                "hf_repo": "nvidia/Cosmos-Reason1-7B",
                "response": "A flat surface under indoor lighting.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=rec)
    assert r.join_truth == "REAL"


def test_join_truth_real_after_swarm_cosmos_reason1_v2_receipt(tmp_path):
    """Current ``swarm_cosmos_reason1`` receipts are V2; Join must still promote REAL."""
    rec = tmp_path / "c.jsonl"
    rec.write_text(
        json.dumps(
            {
                "schema": "SIFTA_COSMOS_REASON1_V2",
                "truth": "REAL",
                "hf_repo": "nvidia/Cosmos-Reason1-7B",
                "response": "The camera frame shows a desk scene.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=rec)
    assert r.join_truth == "REAL"


def test_join_truth_real_after_swarm_cosmos_reason1_v2_real_inference_receipt(tmp_path):
    """The live bridge writes truth=REAL_INFERENCE; Join treats it as inference proof."""
    rec = tmp_path / "c.jsonl"
    rec.write_text(
        json.dumps(
            {
                "schema": "SIFTA_COSMOS_REASON1_V2",
                "truth": "REAL_INFERENCE",
                "hf_repo": "Qwen/Qwen2-VL-2B-Instruct",
                "response": "A man with glasses and a dark shirt.",
                "use_bridge": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    r = cosmos_join_truth_row(cache_root=tmp_path, receipts_path=rec)
    assert r.join_truth == "REAL"


def test_metadata_receipt_row_shape(tmp_path):
    row = append_metadata_receipt(
        {"pipeline_tag": "image-text-to-text", "gated": False},
        path=tmp_path / "c.jsonl",
        writer="pytest",
    )
    assert row["schema"] == SCHEMA_METADATA
    assert row["ok"] is True
    line = (tmp_path / "c.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(line)["model_id"] == COSMOS_REASON1_REPO_ID


def test_truth_probe_dict_keys(tmp_path):
    d = cosmos_truth_probe_dict(
        cache_root=tmp_path,
        receipts_path=tmp_path / "empty.jsonl",
    )
    assert d["truth"] == "ONLINE"
    assert "scanner_line" in d
