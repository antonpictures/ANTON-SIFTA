#!/usr/bin/env python3
"""
metabolic_budget.py — Swarm Metabolism stub (energy = compute / API usage).
══════════════════════════════════════════════════════════════════════════════

Biology sketch: organisms allocate finite ATP; Kleiber-style scaling relates
metabolic rate to mass. Here “mass” is session work; “ATP” is abstract units.

Policy (Architect chorum, 2026-04-17): **local IDE synthesis is cheap**;
**centralized API calls are expensive**. This module only *accounts* — it does
not block — so C47H integrations stay opt-in.

Append-only ledger: `.sifta_state/metabolic_ledger.jsonl`
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "metabolic_ledger.jsonl"

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-18.v1"


class SpendKind(str, Enum):
    LOCAL_IDE = "local_ide"           # Cursor / Antigravity chat, no extra vendor
    EXTERNAL_API = "external_api"    # e.g. centralized tab, paid endpoint
    DISK_IO = "disk_io"              # negligible; optional telemetry


# Default unit costs (tunable; not physical dollars).
_DEFAULT_COST = {
    SpendKind.LOCAL_IDE: 1.0,
    SpendKind.EXTERNAL_API: 10.0,
    SpendKind.DISK_IO: 0.1,
}


@dataclass
class MetabolicLine:
    ts: float
    kind: str
    units: float
    cost: float
    note: str
    trigger: str
    schema_version: int = SCHEMA_VERSION


def spend(
    kind: SpendKind,
    *,
    units: float = 1.0,
    note: str = "",
    trigger: str = "CP2F",
    cost_table: Optional[Dict[SpendKind, float]] = None,
) -> Dict[str, Any]:
    """Record one spend event. Returns the row written."""
    table = cost_table or _DEFAULT_COST
    c = float(table.get(kind, 1.0)) * float(units)
    row = {
        "schema_version": SCHEMA_VERSION,
        "module_version": MODULE_VERSION,
        "ts": time.time(),
        "kind": kind.value,
        "units": round(units, 4),
        "cost": round(c, 4),
        "note": note,
        "trigger": trigger,
    }
    append_line_locked(_LEDGER, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def ledger_total(*, since_ts: Optional[float] = None) -> Dict[str, float]:
    """Sum costs by kind (optional time filter)."""
    if not _LEDGER.exists():
        return {}
    out: Dict[str, float] = {}
    raw = read_text_locked(_LEDGER)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since_ts is not None and r.get("ts", 0) < since_ts:
            continue
        k = r.get("kind", "unknown")
        out[k] = out.get(k, 0.0) + float(r.get("cost", 0.0))
    return out


__all__ = ["SpendKind", "spend", "ledger_total", "MODULE_VERSION", "SCHEMA_VERSION"]
