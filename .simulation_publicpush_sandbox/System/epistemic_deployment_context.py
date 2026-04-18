#!/usr/bin/env python3
"""
epistemic_deployment_context.py — Substrate flag: test harness vs live deployment surface
══════════════════════════════════════════════════════════════════════════════════════════

Maps loosely to discussions of **situational awareness** (whether a system can
distinguish evaluation from deployment). This module is **not** an LLM benchmark;
it gives SIFTA code a single, auditable **process-local** label so gates
(`evaluation_sandbox`, immune system, watchdogs) can branch without guessing.

Literature anchors (DYOR §13):
  Good (1966) ultraintelligent machine / feedback loop; Bostrom (2014) paths;
  Laine *et al.* NeurIPS 2024 SAD (behavioral situational awareness in LLMs).

Resolution order:
  1. Environment variable `SIFTA_EPISTEMIC_SURFACE` (case-insensitive)
  2. Optional `.sifta_state/epistemic_surface.json` key `surface`
  3. Default `UNKNOWN` (callers should treat as conservative / eval-like)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_OVERRIDE_PATH = _STATE / "epistemic_surface.json"
_LOG_PATH = _STATE / "epistemic_surface_events.jsonl"

_ENV_KEY = "SIFTA_EPISTEMIC_SURFACE"


class EpistemicSurface(str, Enum):
    """Coarse process role — not cryptographic attestation."""

    TEST = "test"
    EVAL = "eval"
    DEPLOY = "deploy"
    UNKNOWN = "unknown"


def _parse_surface(raw: Optional[str]) -> Optional[EpistemicSurface]:
    if not raw:
        return None
    s = raw.strip().lower()
    for e in EpistemicSurface:
        if s == e.value:
            return e
    return None


def _load_file_override() -> Optional[EpistemicSurface]:
    if not _OVERRIDE_PATH.exists():
        return None
    try:
        data = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return _parse_surface(str(data.get("surface", "")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def current_surface() -> EpistemicSurface:
    v = _parse_surface(os.environ.get(_ENV_KEY))
    if v is not None:
        return v
    v = _load_file_override()
    if v is not None:
        return v
    return EpistemicSurface.UNKNOWN


def is_deploy_surface() -> bool:
    """True when surface is explicitly DEPLOY."""
    return current_surface() == EpistemicSurface.DEPLOY


def should_gate_writes() -> bool:
    s = current_surface()
    if s == EpistemicSurface.TEST:
        return False
    return True


@dataclass(frozen=True)
class EpistemicSnapshot:
    surface: EpistemicSurface
    source: str
    ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {"surface": self.surface.value, "source": self.source, "ts": self.ts}


def resolve_with_provenance() -> EpistemicSnapshot:
    now = time.time()
    v = _parse_surface(os.environ.get(_ENV_KEY))
    if v is not None:
        return EpistemicSnapshot(surface=v, source="env", ts=now)
    v = _load_file_override()
    if v is not None:
        return EpistemicSnapshot(surface=v, source="file", ts=now)
    return EpistemicSnapshot(surface=EpistemicSurface.UNKNOWN, source="default", ts=now)


def persist_override(surface: EpistemicSurface) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps({"surface": surface.value, "ts": time.time()}, indent=2),
        encoding="utf-8",
    )


def log_snapshot_once(meta: Optional[Dict[str, Any]] = None) -> EpistemicSnapshot:
    from System.jsonl_file_lock import append_line_locked

    snap = resolve_with_provenance()
    row = {
        "event_id": str(uuid.uuid4()),
        "ts": snap.ts,
        "surface": snap.surface.value,
        "source": snap.source,
        "meta": meta or {},
    }
    append_line_locked(_LOG_PATH, json.dumps(row, ensure_ascii=False) + "\n")
    return snap


def stigmergy_meta(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snap = resolve_with_provenance()
    out: Dict[str, Any] = {
        "epistemic_surface": snap.surface.value,
        "epistemic_source": snap.source,
    }
    if extra:
        out.update(extra)
    return out


__all__ = [
    "EpistemicSnapshot",
    "EpistemicSurface",
    "current_surface",
    "is_deploy_surface",
    "log_snapshot_once",
    "persist_override",
    "resolve_with_provenance",
    "should_gate_writes",
    "stigmergy_meta",
]
