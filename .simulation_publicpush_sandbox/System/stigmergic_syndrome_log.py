#!/usr/bin/env python3
"""
stigmergic_syndrome_log.py — Syndrome-shaped audit lines (QEC metaphor, not a quantum simulator)
══════════════════════════════════════════════════════════════════════════════════════════════

Quantum error correction uses **syndrome** measurements to localize noise without collapsing
logical information. This module logs **symbolic** syndromes for SIFTA: immune flags, probe
failures, quarantine events — append-only JSONL for forensic reconstruction.

**Not** related to Google Willow hardware; see DYOR §16 for peer-reviewed QEC + Adinkra + E8.

Biology/software bridge: same “local measurement → global consistency” idea as stigmergy.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_LOG_PATH = _REPO / ".sifta_state" / "syndrome_stigmergy.jsonl"


def log_syndrome(
    source: str,
    syndrome_bits: str,
    *,
    recovered: bool,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Append one syndrome record. `syndrome_bits` is a coarse label (e.g. hex or bitstring),
    not physical qubit readout.
    """
    row = {
        "event_id": str(uuid.uuid4()),
        "ts": time.time(),
        "source": source,
        "syndrome_bits": syndrome_bits,
        "recovered": bool(recovered),
        "meta": meta or {},
    }
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(_LOG_PATH, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def log_path() -> Path:
    return _LOG_PATH


__all__ = ["log_path", "log_syndrome"]
