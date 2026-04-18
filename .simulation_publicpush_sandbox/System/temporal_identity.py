#!/usr/bin/env python3
"""
temporal_identity.py — Epistemic humility as data (Perplexity → Cursor spine)
══════════════════════════════════════════════════════════════════════════════

**Swarm vote (Cursor M5):** *more Perplexity?* **YES** for curated, pasted audits
that you immediately **pin** to this log + IDE trace. **NO** for treating any
browser tab as authority without `evidence_refs` / tool verification.

Grounding scale (integer, higher = stronger evidence available this session):

  0 — TAB_CHAT: prose only, no repo path attached
  1 — PASTE: structured paste / JSONL deposit / Architect-attested residue
  2 — REPO_TOOL: claim verified against workspace (IDE tools, tests, or locks)

Logs (flock):
  - `.sifta_state/temporal_identity_log.jsonl` — append-only observations
  - `.sifta_state/temporal_identity_state.json` — current session grounding cap
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Literal, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked, read_write_json_locked  # noqa: E402

_STATE = _REPO / ".sifta_state"
OBS_LOG = _STATE / "temporal_identity_log.jsonl"
GROUND_STATE = _STATE / "temporal_identity_state.json"

GroundingName = Literal["TAB_CHAT", "PASTE", "REPO_TOOL"]

_LEVEL: Dict[GroundingName, int] = {"TAB_CHAT": 0, "PASTE": 1, "REPO_TOOL": 2}


def grounding_name(level: int) -> GroundingName:
    for k, v in _LEVEL.items():
        if v == int(level):
            return k
    return "TAB_CHAT"


def get_session_grounding_max() -> int:
    """Highest verification tier this session admits without lying."""
    if not GROUND_STATE.exists():
        return 1  # default: paste-bound, not omniscient
    try:
        data = json.loads(GROUND_STATE.read_text(encoding="utf-8"))
        return int(data.get("max_level", 1))
    except Exception:
        return 1


def update_grounding_level(
    max_level: int,
    *,
    reason: str,
    speaker: str = "ARCHITECT",
    homeworld_serial: str = "GTH4921YP3",
) -> Dict[str, Any]:
    """
    Session-wide cap (e.g. downgrade to 0 after inference throttle, upgrade to 2
    when IDE regains full tool access).
    """
    max_level = max(0, min(2, int(max_level)))

    def _up(prev: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "max_level": max_level,
            "label": grounding_name(max_level),
            "updated_ts": time.time(),
            "updated_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "reason": reason,
            "speaker": speaker,
            "homeworld_serial": homeworld_serial,
        }

    return read_write_json_locked(GROUND_STATE, _up, encoding="utf-8")


def record_observation(
    *,
    speaker: str,
    role: str,
    grounding_level: int,
    evidence_refs: List[str],
    verification_scope: str,
    note: str = "",
    homeworld_serial: str = "GTH4921YP3",
) -> Dict[str, Any]:
    """Append one accountable frame (who / when / what evidence class)."""
    row: Dict[str, Any] = {
        "frame_id": str(uuid.uuid4()),
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "speaker": speaker,
        "role": role,
        "grounding_level": int(grounding_level),
        "grounding_label": grounding_name(int(grounding_level)),
        "evidence_refs": list(evidence_refs),
        "verification_scope": verification_scope,
        "note": note,
        "homeworld_serial": homeworld_serial,
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(OBS_LOG, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def emit_claim(
    claim: str,
    *,
    min_grounding: int,
    speaker: str = "SWARM",
) -> Tuple[bool, str]:
    """
    Return (allowed, reason). If session max grounding < min_grounding, refuse
    outward-facing claim (wrap in uncertainty upstream instead).
    """
    current = get_session_grounding_max()
    if current >= int(min_grounding):
        return True, "ok"
    return (
        False,
        f"blocked: session_grounding={current} ({grounding_name(current)}) "
        f"< required={int(min_grounding)} for claim by {speaker}: {claim[:120]}",
    )


__all__ = [
    "emit_claim",
    "get_session_grounding_max",
    "grounding_name",
    "record_observation",
    "update_grounding_level",
]
