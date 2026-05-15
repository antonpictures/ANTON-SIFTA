#!/usr/bin/env python3
"""swarm_mammal_weight_manager.py — local MAMMAL weight proof.

MAMMAL is the IBM / npj Drug Discovery multi-align biomedical model:
`ibm-research/biomed.omics.bl.sm.ma-ted-458m`.

This organ does not claim clinical reasoning. It proves whether the model
artifact is physically present on this SIFTA node and writes an append-only
receipt with the exact files, byte counts, commit SHA, and local path.

Truth label: MAMMAL_LOCAL_WEIGHTS_V1.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "MAMMAL_LOCAL_WEIGHTS_V1"
LEDGER_NAME = "mammal_weight_receipts.jsonl"
MAMMAL_REPO_ID = "ibm-research/biomed.omics.bl.sm.ma-ted-458m"
MAMMAL_LOCAL_DIR = _STATE / "mammal_weights" / "biomed.omics.bl.sm.ma-ted-458m"
REQUIRED_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer/bpe_tokenizer_trained_on_chembl_zinc_with_aug_4272372_samples_balanced_1_1.json",
    "tokenizer/cell_attributes_tokenizer.json",
    "tokenizer/config.yaml",
    "tokenizer/gene_tokenizer.json",
    "tokenizer/t5_tokenizer_AA_special.json",
)
TRUTH_BOUNDARY = (
    "Local artifact proof only. This confirms MAMMAL weights/tokenizers are "
    "on disk for research use. It is not clinical advice, not a medical "
    "diagnosis tool, and not proof that SIFTA reproduces paper benchmarks."
)


@dataclass(frozen=True)
class MammalFileProof:
    path: str
    bytes: int
    sha256: str
    present: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _metadata_revision(local_dir: Path) -> str | None:
    """Read the HF snapshot commit from the metadata sidecar if present."""
    meta = local_dir / ".cache" / "huggingface" / "download" / "model.safetensors.metadata"
    if not meta.exists():
        parts = local_dir.parts
        if "snapshots" in parts:
            idx = parts.index("snapshots")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None
    try:
        first = meta.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
    except Exception:
        return None
    return first or None


def _hf_cache_root() -> Path:
    if "HF_HOME" in os.environ:
        return Path(os.environ["HF_HOME"])
    if "TRANSFORMERS_CACHE" in os.environ:
        return Path(os.environ["TRANSFORMERS_CACHE"]).parent
    return Path.home() / ".cache" / "huggingface"


def _hf_snapshot_roots() -> list[Path]:
    cache_dir = _hf_cache_root() / "hub" / "models--ibm-research--biomed.omics.bl.sm.ma-ted-458m"
    snapshots = cache_dir / "snapshots"
    if not snapshots.exists():
        return []
    return sorted((p for p in snapshots.iterdir() if p.is_dir()), reverse=True)


def _status_for_root(root: Path, *, hash_files: bool) -> tuple[dict[str, Any], list[str]]:
    files: list[MammalFileProof] = []
    total_bytes = 0
    missing: list[str] = []
    for rel in REQUIRED_FILES:
        path = root / rel
        if path.exists() and path.is_file():
            size = path.stat().st_size
            total_bytes += size
            digest = _sha256(path) if hash_files else ""
            files.append(MammalFileProof(rel, size, digest, True))
        else:
            missing.append(rel)
            files.append(MammalFileProof(rel, 0, "", False))
    installed = not missing and total_bytes > 0
    status = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "OBSERVED_LOCAL_ARTIFACTS" if installed else "MISSING_LOCAL_ARTIFACTS",
        "truth_boundary": TRUTH_BOUNDARY,
        "repo_id": MAMMAL_REPO_ID,
        "local_dir": str(root),
        "revision": _metadata_revision(root),
        "installed": installed,
        "missing": missing,
        "n_required_files": len(REQUIRED_FILES),
        "n_present_files": len(REQUIRED_FILES) - len(missing),
        "total_bytes": total_bytes,
        "files": [f.to_dict() for f in files],
    }
    return status, missing


def mammal_weight_status(
    local_dir: str | Path | None = None,
    *,
    hash_files: bool = True,
) -> dict[str, Any]:
    """Return a receipt-friendly proof of the local MAMMAL artifact state.

    Default probe order is SIFTA-local body storage first, then the Hugging Face
    cache snapshot. That keeps Alice's own `.sifta_state` copy canonical while
    preventing a false negative on nodes where the owner pulled the model with
    `huggingface-cli download` into `~/.cache/huggingface/hub`.
    """
    explicit_root = Path(local_dir) if local_dir is not None else None
    candidates = [explicit_root] if explicit_root is not None else [MAMMAL_LOCAL_DIR, *_hf_snapshot_roots()]
    probed: list[str] = []
    first_status: dict[str, Any] | None = None
    for idx, root in enumerate(candidates):
        if root is None:
            continue
        probed.append(str(root))
        status, _missing = _status_for_root(root, hash_files=hash_files)
        if first_status is None:
            first_status = status
        if status["installed"]:
            status["source"] = (
                "explicit_path" if explicit_root is not None
                else "sifta_state" if idx == 0
                else "huggingface_cache_snapshot"
            )
            status["probed_roots"] = probed
            return status
    status = first_status or _status_for_root(explicit_root or MAMMAL_LOCAL_DIR, hash_files=hash_files)[0]
    status["source"] = "explicit_path" if explicit_root is not None else "missing"
    status["probed_roots"] = probed
    return status


def ensure_mammal_weights(
    local_dir: str | Path | None = None,
    *,
    download: bool = False,
) -> dict[str, Any]:
    """Ensure MAMMAL exists locally.

    With download=False this is a pure probe. With download=True it pulls the
    official Hugging Face snapshot into the local SIFTA state directory.
    """
    root = Path(local_dir) if local_dir is not None else MAMMAL_LOCAL_DIR
    status = mammal_weight_status(root, hash_files=False)
    if status["installed"] or not download:
        return mammal_weight_status(root, hash_files=True)
    from huggingface_hub import snapshot_download

    root.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=MAMMAL_REPO_ID, local_dir=str(root))
    return mammal_weight_status(root, hash_files=True)


def write_mammal_weight_receipt(
    status: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = Path(state_root) if state_root is not None else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(status, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "MAMMAL_LOCAL_WEIGHT_PROOF",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": status,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def prove_mammal_weights(
    *,
    local_dir: str | Path | None = None,
    download: bool = False,
    write: bool = True,
) -> dict[str, Any]:
    status = ensure_mammal_weights(local_dir, download=download)
    if write:
        receipt = write_mammal_weight_receipt(status)
        status = {**status, "receipt_trace_id": receipt["trace_id"], "receipt_sha256": receipt["sha256"]}
    return status


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--download", action="store_true", help="download the HF snapshot if missing")
    p.add_argument("--no-write", action="store_true", help="do not write receipt")
    args = p.parse_args()
    result = prove_mammal_weights(download=args.download, write=not args.no_write)
    print(json.dumps(result, indent=2, sort_keys=True))
