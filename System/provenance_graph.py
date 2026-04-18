#!/usr/bin/env python3
"""
provenance_graph.py — Append-only causal edges for state mutations (CP2F / AO46).

Not a full RDF triple store — a **first-class audit log** of who touched what,
with input file hints and optional scalar meta. Aligns with W3C PROV *spirit*
(provenance as explicit records) without requiring SPARQL.

See: Documents/CP2F_DYOR_TURN58_STIGMERGICCODE_LITERATURE_2026-04-18.md
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_LOG = _REPO / ".sifta_state" / "provenance_graph.jsonl"

SCHEMA_VERSION = 1


def record_state_edge(
    *,
    who: str,
    what: str,
    inputs: List[str],
    output: str,
    meta: Optional[Dict[str, Any]] = None,
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Append one provenance edge. Paths in inputs/output are **relative names**
    or repo-relative strings for grep-ability (e.g. `.sifta_state/dopamine_ou_engine.json`).
    """
    edge: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "who": who,
        "what": what,
        "inputs": list(inputs),
        "output": output,
    }
    if meta:
        edge["meta"] = meta
    line = json.dumps(edge, ensure_ascii=False) + "\n"
    path = log_path or _DEFAULT_LOG
    append_line_locked(path, line)
    return edge


__all__ = ["record_state_edge", "SCHEMA_VERSION"]
