#!/usr/bin/env python3
"""
NVIDIA Cosmos-Reason1 truth organ — NPPL / covenant-honest labels.

**Truth contract (stricter than “weights on disk = REAL”):**
  ONLINE — official Cosmos / HF surface is reachable **or** local HF weight cache exists,
           but **no** successful ``COSMOS_REASON1_INFERENCE_V1`` receipt on this node.
  REAL   — at least one **successful** inference receipt (Alice camera frame or approved
           fixture) exists in ``.sifta_state/cosmos_reason1_receipts.jsonl``.
  BROKEN — metadata fetch or receipt IO failed in a probed path (optional).

Vendor anchors (verify before ship):
  https://developer.nvidia.com/cosmos
  https://huggingface.co/nvidia/Cosmos-Reason1-7B
  https://github.com/nvidia-cosmos/cosmos-reason1

Predict 2.5 is **not** the first local target (gated, video-heavy); see ``sifta_nvidia_join`` asset note.

Research — *why “dissect Cosmos” for training / deployment hygiene* (not medical advice):
  - Mitchell, M. et al. (2019). Model Cards for Model Reporting. FAccT / ACM.
    https://doi.org/10.1145/3287560.3287596 — structured disclosure before “REAL”.
  - Geirhos, R. et al. (2020). Shortcut learning in deep neural networks. *Nature Machine Intelligence* **2**, 665–673.
    https://doi.org/10.1038/s42256-020-00257-z — failure modes when synthetic / VLM pipelines **look** grounded.
  - Zhang, C. et al. (2017). Understanding deep learning requires rethinking generalization. *ICLR*.
    https://arxiv.org/abs/1611.03530 — train-set “memorization” vs true generalization (``training cancer`` metaphor).
  - Lipton, Z. C. et al. (2018). The Mythos of Model Interpretability. *ACM Queue* / *CACM* framing of evidence vs narrative.
  - Rajpurkar, P. et al. (2017). CheXNet: radiologist-level pneumonia detection on chest X-rays. *arXiv:1711.05225*
    — **contrast only**: VLM + frame receipts must **not** be relabeled as regulated clinical truth without trials.

**NPPL:** simulation / research posture; Cosmos output is **evidence**, not a sensor or a diagnostic device.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_RECEIPTS = _REPO / ".sifta_state" / "cosmos_reason1_receipts.jsonl"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

COSMOS_REASON1_REPO_ID = "nvidia/Cosmos-Reason1-7B"
HF_API_MODEL = f"https://huggingface.co/api/models/{COSMOS_REASON1_REPO_ID}"

SCHEMA_METADATA = "COSMOS_REASON1_METADATA_V1"
SCHEMA_INFERENCE = "COSMOS_REASON1_INFERENCE_V1"
# Written by ``swarm_cosmos_reason1.probe_and_infer`` on successful forward pass:
SCHEMA_SWARM_COSMOS_V1 = "SIFTA_COSMOS_REASON1_V1"
SCHEMA_SWARM_COSMOS_V2 = "SIFTA_COSMOS_REASON1_V2"
SCHEMA_SWARM_COSMOS_REAL = {SCHEMA_SWARM_COSMOS_V1, SCHEMA_SWARM_COSMOS_V2}
SWARM_COSMOS_REAL_TRUTHS = {"REAL", "REAL_INFERENCE"}

# Join row vocabulary (matches sifta_nvidia_join.LocalTruth subset used here)
JOIN_ONLINE = "ONLINE"
JOIN_REAL = "REAL"
JOIN_BROKEN = "BLOCKED"


@dataclass(frozen=True)
class CosmosReason1Row:
    join_truth: str
    detail: str
    scanner_line: str
    weights_cached: bool
    metadata_ok: bool
    inference_ok: bool


def _hf_models_cache_dir(repo_id: str, *, cache_root: Path | None = None) -> Path:
    root = cache_root or Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    if root.name != "hub":
        root = root / "hub"
    return root / f"models--{repo_id.replace('/', '--')}"


def fetch_hf_model_metadata(
    *,
    timeout_s: float = 12.0,
    url: str = HF_API_MODEL,
) -> dict[str, Any] | None:
    """GET public HF model JSON — no token. Returns None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "SIFTA-nvidia-cosmos-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def append_metadata_receipt(
    meta: Mapping[str, Any] | None,
    *,
    path: Path | None = None,
    writer: str = "nvidia_cosmos_probe",
) -> dict[str, Any]:
    """Write one ONLINE-grade receipt from HF API payload (or failure row)."""
    path = path or _DEFAULT_RECEIPTS
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    ok = meta is not None
    row: dict[str, Any] = {
        "schema": SCHEMA_METADATA,
        "ts": ts,
        "writer": writer,
        "ok": ok,
        "model_id": COSMOS_REASON1_REPO_ID,
        "pipeline_tag": (meta or {}).get("pipeline_tag"),
        "library_name": (meta or {}).get("library_name"),
        "gated": (meta or {}).get("gated"),
        "downloads": (meta or {}).get("downloads"),
        "truth_note": "ONLINE: HF metadata or cache only — REAL requires inference receipt.",
    }
    from System.ledger_append import append_jsonl_line

    append_jsonl_line(path, row)
    return row


def record_inference_receipt(
    *,
    ok: bool,
    prompt_excerpt: str = "",
    image_sha256: str | None = None,
    model_id: str = COSMOS_REASON1_REPO_ID,
    response_excerpt: str = "",
    error: str | None = None,
    path: Path | None = None,
    writer: str = "alice_cosmos_bridge",
) -> dict[str, Any]:
    """
    Call after a real Cosmos-Reason1 forward pass (Alice frame or fixture).

    ``ok=True`` is required for the join probe to promote Cosmos to REAL.
    """
    path = path or _DEFAULT_RECEIPTS
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": SCHEMA_INFERENCE,
        "ts": time.time(),
        "writer": writer,
        "ok": bool(ok),
        "model_id": model_id,
        "prompt_excerpt": (prompt_excerpt or "")[:500],
        "response_excerpt": (response_excerpt or "")[:500],
        "image_sha256": image_sha256,
        "error": (error or "")[:500] if error else None,
        "nppl": "sim_only_evidence_not_sensor",
    }
    from System.ledger_append import append_jsonl_line

    append_jsonl_line(path, row)
    return row


def _last_inference_ok(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        sch = o.get("schema")
        if sch == SCHEMA_INFERENCE and o.get("ok") is True:
            return o
        if sch in SCHEMA_SWARM_COSMOS_REAL and str(o.get("truth", "")).upper() in SWARM_COSMOS_REAL_TRUTHS:
            return o
    return None


def cosmos_join_truth_row(
    *,
    cache_root: Path | None = None,
    receipts_path: Path | None = None,
) -> CosmosReason1Row:
    """
    Row for ``sifta_nvidia_join`` Cosmos asset: REAL only after inference receipt.
    """
    receipts_path = receipts_path or _DEFAULT_RECEIPTS
    r1 = _hf_models_cache_dir(COSMOS_REASON1_REPO_ID, cache_root=cache_root)
    weights_cached = r1.exists()
    inf = _last_inference_ok(receipts_path)
    inference_ok = inf is not None

    if inference_ok:
        return CosmosReason1Row(
            join_truth=JOIN_REAL,
            detail=(
                "Cosmos-Reason1 inference receipt ok (id="
                f"{repr(inf.get('model_id') or inf.get('hf_repo') or COSMOS_REASON1_REPO_ID)})"
            ),
            scanner_line="Cosmos-Reason1: REAL (inference receipt)",
            weights_cached=weights_cached,
            metadata_ok=True,
            inference_ok=True,
        )

    parts = []
    if weights_cached:
        parts.append(f"weights cached at {r1}")
    else:
        parts.append("weights not in HF hub cache layout")
    parts.append("no COSMOS_REASON1_INFERENCE_V1 ok=true or SIFTA_COSMOS_REASON1 truth=REAL row yet")
    return CosmosReason1Row(
        join_truth=JOIN_ONLINE,
        detail="; ".join(parts) + ". Use fetch_hf_model_metadata + append_metadata_receipt for ONLINE proof without download.",
        scanner_line="Cosmos-Reason1: ONLINE (no inference receipt)",
        weights_cached=weights_cached,
        metadata_ok=False,
        inference_ok=False,
    )


def cosmos_truth_probe_dict(
    *,
    cache_root: Path | None = None,
    receipts_path: Path | None = None,
) -> dict[str, Any]:
    row = cosmos_join_truth_row(cache_root=cache_root, receipts_path=receipts_path)
    return {
        "truth": row.join_truth,
        "detail": row.detail,
        "scanner_line": row.scanner_line,
        "weights_cached": row.weights_cached,
        "inference_ok": row.inference_ok,
        "model_id": COSMOS_REASON1_REPO_ID,
    }


def probe_metadata_and_receipt(
    *,
    receipts_path: Path | None = None,
    writer: str = "nvidia_cosmos_probe",
) -> dict[str, Any]:
    """Fetch HF model JSON and append metadata receipt — ONLINE evidence, no weights."""
    meta = fetch_hf_model_metadata()
    rec = append_metadata_receipt(meta, path=receipts_path, writer=writer)
    return {"metadata": meta, "receipt": rec}


__all__ = [
    "COSMOS_REASON1_REPO_ID",
    "HF_API_MODEL",
    "SCHEMA_METADATA",
    "SCHEMA_INFERENCE",
    "SCHEMA_SWARM_COSMOS_V1",
    "SCHEMA_SWARM_COSMOS_V2",
    "CosmosReason1Row",
    "append_metadata_receipt",
    "cosmos_join_truth_row",
    "cosmos_truth_probe_dict",
    "fetch_hf_model_metadata",
    "probe_metadata_and_receipt",
    "record_inference_receipt",
]
