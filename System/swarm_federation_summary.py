#!/usr/bin/env python3
"""Bounded cross-node summaries for the high-dimensional organ field.

Raw organ tensors stay local by default. Federation exports a small signed
summary so another node can reason about coarse state without receiving the
full local field or raw hardware serial.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

SUMMARY_SCHEMA = "SWARM_FEDERATION_SUMMARY_V1"
MAX_SUMMARY_DIMS = 32


def _serial_hash(serial: str) -> str:
    clean = str(serial or "").strip()
    if not clean or clean.upper() == "UNKNOWN":
        return "UNKNOWN"
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _read_last_jsonl(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, Mapping) else row


def _signature_payload(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if key not in {"signature_sha256", "signature_scope"}
    }


def _sign(summary: Mapping[str, Any], signer_serial: str) -> str:
    canonical = json.dumps(_signature_payload(summary), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canonical + "|" + str(signer_serial or "")).encode("utf-8")).hexdigest()


def build_federation_summary(
    state_dir: Path = _STATE,
    *,
    max_dims: int = MAX_SUMMARY_DIMS,
    signer_serial: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a signed, bounded summary of the latest organ field row."""
    if signer_serial is None:
        try:
            from System.swarm_kernel_identity import owner_silicon
            signer_serial = owner_silicon()
        except Exception:
            signer_serial = "UNKNOWN"
    limit = max(1, min(MAX_SUMMARY_DIMS, int(max_dims)))
    row = _read_last_jsonl(state_dir / "organ_field_vector.jsonl")
    payload = _payload(row)
    vector = payload.get("field_vector", [])
    if not isinstance(vector, list):
        vector = []
    names = payload.get("dimension_names", [])
    if not isinstance(names, list):
        names = []
    vector_summary = []
    for idx, value in enumerate(vector[:limit]):
        try:
            numeric = round(float(value), 6)
        except Exception:
            numeric = 0.0
        vector_summary.append({
            "index": idx,
            "name": str(names[idx] if idx < len(names) else f"dim_{idx}")[:80],
            "value": numeric,
        })

    summary: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "ts": time.time(),
        "truth_label": "OPERATIONAL",
        "retention_class": "operational",
        "source": "swarm_federation_summary:build",
        "source_homeworld_serial_hash": _serial_hash(str(signer_serial or "")),
        "raw_serial_disclosed": False,
        "max_dims": limit,
        "vector_dims_exported": len(vector_summary),
        "vector_summary": vector_summary,
        "field_metrics": {
            "dimension_count": int(payload.get("dimension_count") or len(vector)),
            "field_completeness": payload.get("field_completeness"),
            "unknown_vector_count": payload.get("unknown_vector_count"),
            "low_resolution_vector_count": payload.get("low_resolution_vector_count"),
            "connected_organ_count": payload.get("connected_organ_count"),
            "coupling_edge_count": payload.get("coupling_edge_count"),
            "coupling_density": payload.get("coupling_density"),
            "field_homeostasis_state": payload.get("field_homeostasis_state"),
        },
        "boundary": "summary_only_no_raw_high_dimensional_tensor",
    }
    summary["signature_scope"] = "canonical_json_sha256_with_local_serial"
    summary["signature_sha256"] = _sign(summary, str(signer_serial or ""))
    return summary


def verify_federation_summary(summary: Mapping[str, Any], *, signer_serial: str) -> bool:
    if summary.get("schema") != SUMMARY_SCHEMA:
        return False
    expected = _sign(summary, signer_serial)
    return str(summary.get("signature_sha256") or "") == expected


__all__ = [
    "SUMMARY_SCHEMA",
    "MAX_SUMMARY_DIMS",
    "build_federation_summary",
    "verify_federation_summary",
]
