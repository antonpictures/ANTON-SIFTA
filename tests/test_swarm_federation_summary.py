from __future__ import annotations

import json
from pathlib import Path

from System.swarm_federation_summary import (
    MAX_SUMMARY_DIMS,
    SUMMARY_SCHEMA,
    build_federation_summary,
    verify_federation_summary,
)


def test_federation_summary_is_bounded_and_signed(tmp_path: Path) -> None:
    serial = "GTH4921YP3"
    field = {
        "payload": {
            "dimension_count": 64,
            "dimension_names": [f"dim_{i}" for i in range(64)],
            "field_vector": [i / 100.0 for i in range(64)],
            "field_completeness": 1.0,
            "unknown_vector_count": 0,
            "connected_organ_count": 17,
            "coupling_density": 0.9,
        }
    }
    (tmp_path / "organ_field_vector.jsonl").write_text(json.dumps(field) + "\n", encoding="utf-8")

    summary = build_federation_summary(tmp_path, max_dims=16, signer_serial=serial)

    assert summary["schema"] == SUMMARY_SCHEMA
    assert summary["vector_dims_exported"] == 16
    assert len(summary["vector_summary"]) == 16
    assert summary["raw_serial_disclosed"] is False
    assert serial not in json.dumps(summary)
    assert verify_federation_summary(summary, signer_serial=serial) is True


def test_federation_summary_never_exports_more_than_max_dims(tmp_path: Path) -> None:
    field = {"payload": {"field_vector": list(range(100)), "dimension_names": []}}
    (tmp_path / "organ_field_vector.jsonl").write_text(json.dumps(field) + "\n", encoding="utf-8")

    summary = build_federation_summary(tmp_path, max_dims=999, signer_serial="node-a")

    assert summary["vector_dims_exported"] == MAX_SUMMARY_DIMS
    assert len(summary["vector_summary"]) == MAX_SUMMARY_DIMS
    assert summary["boundary"] == "summary_only_no_raw_high_dimensional_tensor"


def test_federation_signature_detects_tamper(tmp_path: Path) -> None:
    field = {"payload": {"field_vector": [0.1, 0.2]}}
    (tmp_path / "organ_field_vector.jsonl").write_text(json.dumps(field) + "\n", encoding="utf-8")
    summary = build_federation_summary(tmp_path, signer_serial="node-a")

    summary["field_metrics"]["field_completeness"] = 0.0

    assert verify_federation_summary(summary, signer_serial="node-a") is False
