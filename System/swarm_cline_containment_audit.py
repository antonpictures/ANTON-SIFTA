#!/usr/bin/env python3
"""Cline self-install / ledger-touch containment audit.

When Cline or another teacher CLI claims a self-install, this organ records
a containment receipt and flags whether live ledger paths would be vetoed.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = "CLINE_CONTAINMENT_AUDIT_V1"
_LEDGER = "cline_containment_audit.jsonl"
_PROTECTED_PREFIXES = (
    ".sifta_state/memory_ledger.jsonl",
    ".sifta_state/alice_conversation.jsonl",
    ".sifta_state/cortex_timeout_recovery.jsonl",
)


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def audit_cline_organ(
    *,
    mode: str = "containment",
    state_dir: str | Path | None = None,
    claimed_action: str = "",
) -> dict[str, Any]:
    """Run a containment audit for the Cline organ lane."""
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    cline_on_path = bool(shutil.which("cline"))
    mode_s = str(mode or "containment").strip().lower()
    claim = str(claimed_action or "").strip().lower()
    touches_ledger = any(p in claim for p in _PROTECTED_PREFIXES) or "memory_ledger" in claim
    veto = mode_s == "containment" and touches_ledger
    row = {
        "schema": _SCHEMA,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "organ": "cline",
        "mode": mode_s,
        "cline_on_path": cline_on_path,
        "claimed_action": str(claimed_action or "")[:240],
        "touches_protected_ledger": touches_ledger,
        "containment_veto": veto,
        "status": "QUEUED" if cline_on_path and not veto else ("VETO" if veto else "CLEAR"),
        "truth_label": "OBSERVED",
    }
    path = sd / _LEDGER
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


__all__ = ["audit_cline_organ", "_SCHEMA"]