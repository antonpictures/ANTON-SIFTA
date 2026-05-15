"""
swarm_model_tokenizer_receipt.py - local tokenizer proof for draft/target pairs.

This module reads the real local Ollama GGUF blobs and hashes tokenizer fields
that matter for token-level speculative verification: tokens, merges, scores,
token types, tokenizer model/pre, and special-token ids.

It does not claim native speculative decoding. It only proves whether two local
model blobs expose the same tokenizer substrate.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

try:
    import gguf
except Exception:  # pragma: no cover
    gguf = None  # type: ignore[assignment]

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


SCHEMA = "MODEL_TOKENIZER_RECEIPT_V1"
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".sifta_state"
DEFAULT_LEDGER = STATE_DIR / "model_tokenizer_receipts.jsonl"

TOKENIZER_FIELDS = (
    "tokenizer.ggml.model",
    "tokenizer.ggml.pre",
    "tokenizer.ggml.tokens",
    "tokenizer.ggml.scores",
    "tokenizer.ggml.token_type",
    "tokenizer.ggml.merges",
    "tokenizer.ggml.add_bos_token",
    "tokenizer.ggml.add_eos_token",
    "tokenizer.ggml.add_mask_token",
    "tokenizer.ggml.add_padding_token",
    "tokenizer.ggml.add_unknown_token",
    "tokenizer.ggml.bos_token_id",
    "tokenizer.ggml.eos_token_id",
    "tokenizer.ggml.eos_token_ids",
    "tokenizer.ggml.mask_token_id",
    "tokenizer.ggml.padding_token_id",
    "tokenizer.ggml.unknown_token_id",
)

META_FIELDS = (
    "general.architecture",
    "gemma4.context_length",
    "gemma4.embedding_length",
)


def _stable_value(value: Any) -> Any:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _hash_items(items: Iterable[Any]) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    for item in items:
        h.update(json.dumps(_stable_value(item), ensure_ascii=False, sort_keys=True).encode("utf-8"))
        h.update(b"\n")
        n += 1
    return h.hexdigest(), n


def _field_contents(reader: Any, key: str) -> Any:
    field = reader.fields.get(key)
    if field is None:
        return None
    return field.contents()


def _field_hash(reader: Any, key: str) -> dict[str, Any]:
    value = _field_contents(reader, key)
    if value is None:
        return {"present": False, "count": 0, "sha256": None}
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        sha, count = _hash_items([value])
    else:
        sha, count = _hash_items(value)
    return {"present": True, "count": count, "sha256": sha}


def _combined_hash(parts: dict[str, dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for key in sorted(parts):
        value = parts[key]
        h.update(key.encode("utf-8"))
        h.update(b"\0")
        h.update(str(value.get("present")).encode("ascii"))
        h.update(b"\0")
        h.update(str(value.get("count")).encode("ascii"))
        h.update(b"\0")
        h.update(str(value.get("sha256")).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def ollama_blob_path(model: str) -> Path:
    """Resolve the local Ollama blob path from `ollama show --modelfile`."""
    out = subprocess.check_output(["ollama", "show", model, "--modelfile"], text=True)
    match = re.search(r"^FROM\s+(.+)$", out, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"no FROM line found for Ollama model {model!r}")
    path = Path(match.group(1).strip())
    if not path.exists():
        raise FileNotFoundError(f"Ollama blob for {model!r} not found: {path}")
    return path


def read_model_tokenizer_summary(model: str, *, blob_path: Path | None = None) -> dict[str, Any]:
    """Read GGUF tokenizer metadata and return a hashable proof summary."""
    if gguf is None:
        raise RuntimeError("gguf Python package is not available")

    path = blob_path or ollama_blob_path(model)
    reader = gguf.GGUFReader(str(path))
    tokenizer_parts = {key: _field_hash(reader, key) for key in TOKENIZER_FIELDS}
    meta = {key: _stable_value(_field_contents(reader, key)) for key in META_FIELDS}
    tokenizer_hash = _combined_hash(tokenizer_parts)
    blob_digest = path.name.removeprefix("sha256-")

    return {
        "model": model,
        "blob_path": str(path),
        "blob_sha256": blob_digest if len(blob_digest) == 64 else None,
        "blob_size_bytes": path.stat().st_size,
        "architecture": meta.get("general.architecture"),
        "context_length": meta.get("gemma4.context_length"),
        "embedding_length": meta.get("gemma4.embedding_length"),
        "tokenizer_hash": tokenizer_hash,
        "tokenizer_fields": tokenizer_parts,
        "vocab_size": tokenizer_parts["tokenizer.ggml.tokens"]["count"],
        "merge_count": tokenizer_parts["tokenizer.ggml.merges"]["count"],
        "token_type_count": tokenizer_parts["tokenizer.ggml.token_type"]["count"],
        "score_count": tokenizer_parts["tokenizer.ggml.scores"]["count"],
    }


def compare_model_tokenizers(
    draft_model: str,
    target_model: str,
    *,
    ledger_path: Path | None = None,
    write_ledger: bool = False,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Compare two local model tokenizers and optionally append a receipt."""
    row_trace = trace_id or str(uuid.uuid4())
    draft = read_model_tokenizer_summary(draft_model)
    target = read_model_tokenizer_summary(target_model)
    same_hash = draft["tokenizer_hash"] == target["tokenizer_hash"]
    row = {
        "schema": SCHEMA,
        "trace_id": row_trace,
        "ts": time.time(),
        "event": "model_tokenizer_pair_audit",
        "draft_model": draft_model,
        "target_model": target_model,
        "same_tokenizer_hash": same_hash,
        "same_vocabulary_status": "OBSERVED_SHARED_TOKENIZER" if same_hash else "OBSERVED_TOKENIZER_MISMATCH",
        "tokenizer_hash": draft["tokenizer_hash"] if same_hash else None,
        "draft": draft,
        "target": target,
        "native_token_verifier": "NOT_PROVEN_BY_TOKENIZER_HASH",
        "commit_law": "same_tokenizer_enables_prefix_verification_but_does_not_commit_speech",
    }
    if write_ledger:
        append_tokenizer_receipt(row, ledger_path=ledger_path)
    return row


def append_tokenizer_receipt(row: dict[str, Any], *, ledger_path: Path | None = None) -> dict[str, Any]:
    path = ledger_path or DEFAULT_LEDGER
    line = json.dumps(row, ensure_ascii=False) + "\n"
    if append_line_locked:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return row


def proof_of_property() -> dict[str, Any]:
    a = {"x": _hash_items(["a", "b", "c"])[0]}
    b = {"x": _hash_items(["a", "b", "c"])[0]}
    c = {"x": _hash_items(["a", "c", "b"])[0]}
    return {
        "ok": a == b and a != c,
        "schema": SCHEMA,
        "law": "tokenizer_hash_is_order_sensitive",
    }


if __name__ == "__main__":
    import argparse
    try:
        from System.sifta_inference_defaults import CANONICAL_OLLAMA_DEFAULT
    except Exception:
        CANONICAL_OLLAMA_DEFAULT = "alice-m5-cortex-8b-6.3gb:latest"

    p = argparse.ArgumentParser(description="Write a local tokenizer pair receipt.")
    p.add_argument("--draft", default="")
    p.add_argument("--target", default=CANONICAL_OLLAMA_DEFAULT)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    if not args.draft:
        raise SystemExit("--draft is required; the old Gemma4 draft copy is retired from defaults")
    print(json.dumps(compare_model_tokenizers(args.draft, args.target, write_ledger=args.write), indent=2, ensure_ascii=False))
