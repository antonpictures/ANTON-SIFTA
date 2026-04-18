#!/usr/bin/env python3
"""
glymphatic_pulse_gate.py — Stigmergic “gate” log when CSF-like flushes complete (metaphor)
══════════════════════════════════════════════════════════════════════════════════════════

Swimmer nanobots **do not** exist here — this is a **substrate audit**: each successful
glymphatic / sleep flush (or manual heal) appends a JSONL row so other IDEs see the pulse.

Peer anchors (DYOR §20):
  Iliff *et al.* 2012 — paravascular CSF–ISF exchange (glymphatic).
  Fultz *et al.* 2019 — NREM sleep, slow waves, hemodynamics, **CSF oscillations** coupled.

**Epistemic line:** wellness videos that tie **pineal breathing** to guaranteed CSF “mystical”
circulation are **not** interchangeable with the papers above; pineal **melatonin** physiology
is separate (Endotext / reviews).

Call `record_pulse()` from `swarm_sleep_cycle.glymphatic_flush` when wiring the organism.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_GATE_LOG = _STATE / "glymphatic_pulse_gate.jsonl"


def record_pulse(
    kind: str,
    *,
    source: str = "cp2f",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append one gate event (flock-safe JSONL)."""
    from System.jsonl_file_lock import append_line_locked

    row = {
        "event_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": kind,
        "source": source,
        "meta": meta or {},
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(_GATE_LOG, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def gate_log_path() -> Path:
    return _GATE_LOG


__all__ = ["gate_log_path", "record_pulse"]
