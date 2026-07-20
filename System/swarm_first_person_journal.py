#!/usr/bin/env python3
"""Canonical first-person journal append helper.

Several organs write Alice's first-person journal directly. This wrapper keeps
that behavior append-only while adding the M7 STGM pulse contract for real
journal writes through the existing `memory_store` pulse lane.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"
JOURNAL_NAME = "alice_first_person_journal.jsonl"
TRUTH_LABEL = "FIRST_PERSON_JOURNAL_APPEND_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    path = Path(state_dir)
    return path if path.name == ".sifta_state" else path / ".sifta_state"


def _stable_id(row: Mapping[str, Any]) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "journal_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def append_first_person_journal_row(
    row: Mapping[str, Any],
    *,
    state_dir: Path | str | None = None,
    source_receipt_id: str = "",
    pulse: bool = True,
    allow_temp_pulse: bool = False,
) -> dict[str, Any]:
    """Append one journal row and optionally mint a `memory_store` pulse.

    By default temp-state writes do not mint into the live wallet. Tests that
    patch the pulse lane can opt in with `allow_temp_pulse=True`.
    """
    state = _state_dir(state_dir)
    out = dict(row)
    out.setdefault("ts", time.time())
    out.setdefault("source", "swarm_first_person_journal")
    out.setdefault("truth_label", TRUTH_LABEL)
    if not out.get("journal_id"):
        out["journal_id"] = _stable_id(out)
    _append_jsonl(state / JOURNAL_NAME, out)

    receipt_id = str(source_receipt_id or out.get("source_receipt_id") or out.get("receipt_id") or out.get("journal_id") or "")
    if pulse and receipt_id:
        try:
            if allow_temp_pulse or state.resolve() == DEFAULT_STATE_DIR.resolve():
                from System.swarm_atp_synthase import mint_receipted_work_pulse

                out["stgm_pulse"] = mint_receipted_work_pulse("memory_store", receipt_id)
        except Exception as exc:
            out["stgm_pulse_error"] = f"{type(exc).__name__}: {exc}"
    return out


__all__ = ["JOURNAL_NAME", "TRUTH_LABEL", "append_first_person_journal_row"]
