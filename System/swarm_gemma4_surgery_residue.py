"""Append-only surgery examples for Gemma4 cleanup.

These rows are not prompt text. They are receipts for model-level cleanup:
when a detector strips a bad completion or a channel gate prevents a loop, the
pattern is preserved as training/eval material instead of being normalized in
Alice's live prompt.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def surgery_residue_path(root: Optional[Path] = None) -> Path:
    base = Path(root) if root is not None else _repo_root()
    return base / ".sifta_state" / "gemma4_surgery_residues.jsonl"


def log_surgery_residue(
    *,
    kind: str,
    source: str,
    pattern: str,
    sample: str = "",
    action: str,
    root: Optional[Path] = None,
    truth_label: str = "OBSERVED",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "schema": "GEMMA4_SURGERY_RESIDUE_V1",
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": truth_label,
        "kind": str(kind or "unknown"),
        "source": str(source or "unknown"),
        "pattern": str(pattern or "unknown"),
        "sample": str(sample or "")[:1000],
        "action": str(action or "record"),
    }
    if meta:
        row["meta"] = dict(meta)

    path = surgery_residue_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    if append_line_locked:
        append_line_locked(path, line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return row
