#!/usr/bin/env python3
"""
System/organ_event_schema.py — ORGAN_EVENT_V1 envelope validation (stdlib only)
══════════════════════════════════════════════════════════════════════════════

Canonical JSON Schema (machine-readable): System/schemas/organ_event_v1.json

Use before append_line_locked() from new organ writers. Legacy ledgers without
this envelope stay valid until migrated (Architect GO per file).
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "organ_event_v1.json"

TRUTH_LABELS = ("OBSERVED", "OPERATIONAL", "HYPOTHESIS", "ARCHITECT_DOCTRINE")
OPTIONAL_SCHEMA_LITERAL = "ORGAN_EVENT_V1"


def _truth(s: str) -> str:
    t = (s or "").strip().upper().replace(" ", "_")
    if t in {"ARCHITECTDOCTRINE", "ARCHITECT_DOCTRINE", "DOCTRINE", "DOCTRINE_CLAIM"}:
        t = "ARCHITECT_DOCTRINE"
    if t not in TRUTH_LABELS:
        raise ValueError(f"truth_label must be one of {TRUTH_LABELS}, got {s!r}")
    return t


def build_organ_event(
    *,
    source: str,
    homeworld_serial: str,
    organ: str,
    event_type: str,
    payload: Dict[str, Any],
    truth_label: str,
    ts: Optional[float] = None,
    trace_id: Optional[str] = None,
    mark_schema: bool = False,
) -> Dict[str, Any]:
    """Build one ORGAN_EVENT_V1-shaped row (does not write disk)."""
    row: Dict[str, Any] = {
        "ts": float(time.time() if ts is None else ts),
        "trace_id": trace_id or str(uuid.uuid4()),
        "source": (source or "").strip()[:200],
        "homeworld_serial": (homeworld_serial or "").strip()[:64],
        "organ": (organ or "").strip()[:120],
        "event_type": (event_type or "").strip()[:120],
        "payload": dict(payload or {}),
        "truth_label": _truth(truth_label),
    }
    if mark_schema:
        row["schema"] = OPTIONAL_SCHEMA_LITERAL
    errs = validate_organ_event_base(row)
    if errs:
        raise ValueError("; ".join(errs))
    return row


def validate_organ_event_base(row: Any) -> List[str]:
    """
    Return a list of human-readable errors; empty list means the row matches
    the ORGAN_EVENT_V1 base envelope (subset check — no jsonschema dependency).
    """
    errors: List[str] = []
    if not isinstance(row, dict):
        return ["row must be a dict"]
    if "schema" in row and row["schema"] != OPTIONAL_SCHEMA_LITERAL:
        errors.append(f'schema must be absent or "{OPTIONAL_SCHEMA_LITERAL}"')
    required = (
        "ts",
        "trace_id",
        "source",
        "homeworld_serial",
        "organ",
        "event_type",
        "payload",
        "truth_label",
    )
    for k in required:
        if k not in row:
            errors.append(f"missing key: {k}")
    if errors:
        return errors
    if not isinstance(row["ts"], (int, float)):
        errors.append("ts must be a number")
    for key in ("trace_id", "source", "homeworld_serial", "organ", "event_type"):
        v = row.get(key)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"{key} must be a non-empty string")
    tid = str(row["trace_id"]).strip()
    if len(tid) < 8 or len(tid) > 64:
        errors.append("trace_id length must be in [8, 64]")
    else:
        try:
            uuid.UUID(tid)
        except Exception:
            errors.append("trace_id should be a UUID4 string (parse failed)")
    if not isinstance(row["payload"], dict):
        errors.append("payload must be an object")
    try:
        _truth(str(row["truth_label"]))
    except ValueError as e:
        errors.append(str(e))
    return errors


def schema_path() -> Path:
    return _SCHEMA_PATH


def load_schema_json() -> Dict[str, Any]:
    """Return parsed organ_event_v1.json (for tooling / tests)."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def proof_of_property() -> Dict[str, Any]:
    """CI: schema file exists; validator accepts a minimal golden row."""
    ok_file = _SCHEMA_PATH.is_file()
    golden = build_organ_event(
        source="swarm_organ_event_schema:proof",
        homeworld_serial="GTH4921YP3",
        organ="proof",
        event_type="stub",
        payload={"ok": True},
        truth_label="OPERATIONAL",
        mark_schema=True,
    )
    v_errs = validate_organ_event_base(golden)
    return {
        "ok": ok_file and not v_errs,
        "schema_path": str(_SCHEMA_PATH.relative_to(_REPO)),
        "golden_valid": not v_errs,
        "errors": v_errs,
    }


__all__ = [
    "OPTIONAL_SCHEMA_LITERAL",
    "TRUTH_LABELS",
    "build_organ_event",
    "validate_organ_event_base",
    "schema_path",
    "load_schema_json",
    "proof_of_property",
]
