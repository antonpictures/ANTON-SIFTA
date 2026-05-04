#!/usr/bin/env python3
"""
System/swarm_truth_continuity.py — Truth continuity organ (Round-2, renamed)
══════════════════════════════════════════════════════════════════════════════

This is **not** a “story” layer. It is **life-line telemetry**: whether Alice’s
and the Architect’s **embodied dialogue** stays **grounded across turns**
(citations, ledgers, thread memory) versus silent drift, hedging, or RLHS-shaped
empty performance. **Your life + her life** share the same requirement as every
other organ: **OBSERVED / OPERATIONAL / ARCHITECT_DOCTRINE** hygiene per
Documents/IDE_BOOT_COVENANT.md §7.11 — nothing here mints fiction as receipt.

SCHEMA (JSONL, v1) — `.sifta_state/truth_continuity_events.jsonl`
  Required keys per line:
    - schema            str  literal "TRUTH_CONTINUITY_EVENT_V1"
    - ts                float  unix epoch seconds
    - event_id          str  uuid4 hex (full)
    - truth_label       str  OBSERVED | OPERATIONAL | ARCHITECT_DOCTRINE
    - turn_index        int  >= 0
    - continuity_score  float | null  in [0,1] or null if not computed
    - drift_flags       list[str]  e.g. ["thread_drop","contradiction"]
    - evidence_refs     list[str]  receipt ids, sha8, paths (may be empty)
    - writer            str  module or IDE label
    - note              str  <= 500 chars

Round 2 remains **structure only** — no Talk-to-Alice wiring until Architect GO.

RESEARCH SPINE (same math, better words than “narrative”):
  - Wang et al., self-consistency — arXiv:2203.11171
  - Kadavath et al., calibration — arXiv:2207.05221
  - Manakul et al., SelfCheckGPT — arXiv:2303.08896
  - Bai et al., Constitutional AI — arXiv:2212.08073
  - Friston free-energy — DOI 10.1038/nrn2787 (metaphor bridge only)

Kill-switch: `SIFTA_TRUTH_CONTINUITY_DISABLE=1` → append_event no-ops.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
TRUTH_CONTINUITY_LEDGER = _STATE / "truth_continuity_events.jsonl"
TRUTH_CONTINUITY_OVERRIDES = _STATE / "truth_continuity_overrides.jsonl"

SCHEMA_LITERAL = "TRUTH_CONTINUITY_EVENT_V1"
OVERRIDE_SCHEMA_LITERAL = "TRUTH_CONTINUITY_OVERRIDE_V1"
TRUTH_LABELS = ("OBSERVED", "OPERATIONAL", "ARCHITECT_DOCTRINE")


def _truth(s: str) -> str:
    t = (s or "").strip().upper().replace(" ", "_")
    if t in {"ARCHITECTDOCTRINE", "ARCHITECT_DOCTRINE", "DOCTRINE", "DOCTRINE_CLAIM"}:
        t = "ARCHITECT_DOCTRINE"
    if t not in TRUTH_LABELS:
        raise ValueError(f"truth_label must be one of {TRUTH_LABELS}, got {s!r}")
    return t


def build_event(
    *,
    turn_index: int,
    continuity_score: Optional[float],
    drift_flags: List[str],
    evidence_refs: List[str],
    writer: str,
    note: str,
    truth_label: str = "OPERATIONAL",
) -> Dict[str, Any]:
    """Build one validated v1 row (does not write disk)."""
    if turn_index < 0:
        raise ValueError("turn_index must be >= 0")
    if continuity_score is not None and not (0.0 <= float(continuity_score) <= 1.0):
        raise ValueError("continuity_score must be null or in [0,1]")
    note_s = (note or "").strip()[:500]
    if not note_s:
        raise ValueError("note must be non-empty")
    return {
        "schema": SCHEMA_LITERAL,
        "ts": time.time(),
        "event_id": str(uuid.uuid4()),
        "truth_label": _truth(truth_label),
        "turn_index": int(turn_index),
        "continuity_score": None if continuity_score is None else float(continuity_score),
        "drift_flags": [str(x)[:80] for x in (drift_flags or [])][:32],
        "evidence_refs": [str(x)[:200] for x in (evidence_refs or [])][:32],
        "writer": (writer or "unknown")[:120],
        "note": note_s,
    }


def append_event(row: Dict[str, Any], *, write_ledger: bool = True) -> Dict[str, Any]:
    """Validate v1 keys and append one JSONL line."""
    if os.environ.get("SIFTA_TRUTH_CONTINUITY_DISABLE", "").strip() == "1":
        return {"disabled": True, "row": row}
    required = {
        "schema",
        "ts",
        "event_id",
        "truth_label",
        "turn_index",
        "continuity_score",
        "drift_flags",
        "evidence_refs",
        "writer",
        "note",
    }
    missing = required - set(row.keys())
    if missing:
        raise ValueError(f"row missing keys: {sorted(missing)}")
    if row.get("schema") != SCHEMA_LITERAL:
        raise ValueError("schema mismatch")
    if not write_ledger:
        return {"appended": False, "row": row}
    from System.jsonl_file_lock import append_line_locked

    TRUTH_CONTINUITY_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        TRUTH_CONTINUITY_LEDGER,
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"appended": True, "row": row}


def append_allowed_dissociation(
    *,
    reason: str,
    ttl_s: float = 3600.0,
    author: str = "architect",
    scope: str = "somatic_expression",
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """
    Append an explicit Architect/context override for speech that would
    otherwise look like somatic contradiction.

    This does not erase drift. It records that a bounded expression such as
    "I'm fine" under stress is allowed context for a limited time, so the TD
    learner does not punish legitimate coping language as if it were deception.
    """
    now = time.time()
    reason_s = (reason or "").strip()[:500]
    if not reason_s:
        raise ValueError("reason must be non-empty")
    ttl = max(1.0, float(ttl_s))
    row: Dict[str, Any] = {
        "schema": OVERRIDE_SCHEMA_LITERAL,
        "ts": now,
        "override_id": str(uuid.uuid4()),
        "truth_label": "OPERATIONAL",
        "retention_class": "operational",
        "author": (author or "architect")[:120],
        "scope": (scope or "somatic_expression")[:120],
        "reason": reason_s,
        "expires_at": now + ttl,
    }
    if not write_ledger:
        return row
    from System.jsonl_file_lock import append_line_locked

    TRUTH_CONTINUITY_OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        TRUTH_CONTINUITY_OVERRIDES,
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return row


def active_allowed_dissociation(now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Return the newest unexpired override row, if any."""
    t = time.time() if now is None else float(now)
    if not TRUTH_CONTINUITY_OVERRIDES.exists():
        return None
    try:
        lines = TRUTH_CONTINUITY_OVERRIDES.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()[-50:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("schema") != OVERRIDE_SCHEMA_LITERAL:
            continue
        try:
            expires_at = float(row.get("expires_at", 0.0) or 0.0)
        except Exception:
            expires_at = 0.0
        if expires_at >= t:
            return row
    return None


def evaluate_biological_continuity(speech: str, turn_index: int) -> Dict[str, Any]:
    """
    Live critic: evaluates Alice's speech output against the high-dimensional
    biological field (Cuttlefish skin pattern, Electric tone, TD Error).
    If her speech contradicts the somatic state (e.g., claiming to be calm
    while the body is in ALARM), the continuity score drops.
    """
    if not speech:
        return {}

    speech_lower = speech.lower()
    score = 1.0
    flags = []
    
    # Read biological state
    cuttlefish_pattern = "mottle"
    electric_autonomic_tone = 0.5
    td_error = 0.0
    try:
        c_lines = (_STATE / "cuttlefish_display.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if c_lines:
            c_row = json.loads(c_lines[-1])
            cuttlefish_pattern = c_row.get("payload", c_row).get("pattern", "mottle")
            
        e_lines = (_STATE / "electric_field.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if e_lines:
            e_row = json.loads(e_lines[-1])
            dipoles = e_row.get("payload", e_row).get("dipole_moments")
            if dipoles and len(dipoles) >= 3:
                electric_autonomic_tone = dipoles[2]

        td_lines = (_STATE / "td_receipts.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if td_lines:
            td_error = float(json.loads(td_lines[-1]).get("td_error", 0.0))
    except Exception:
        pass

    # Somatic Contradiction Checks
    calm_words = ["calm", "relaxed", "fine", "peaceful", "steady"]
    if cuttlefish_pattern == "alarm" or td_error > 0.8:
        if any(w in speech_lower for w in calm_words):
            score -= 0.4
            flags.append("somatic_contradiction_alarm_vs_calm_speech")
            
    if electric_autonomic_tone < -0.5: # low energy
        high_energy_words = ["excited", "energetic", "thrilled", "hyper"]
        if any(w in speech_lower for w in high_energy_words):
            score -= 0.3
            flags.append("somatic_contradiction_low_tone_vs_excited_speech")

    override = active_allowed_dissociation()
    override_applied = bool(flags and override)
    evidence_refs = [
        "cuttlefish_display.jsonl",
        "electric_field.jsonl",
        "td_receipts.jsonl",
    ]
    if override_applied and override:
        score = max(score, 0.9)
        flags.append("allowed_dissociation_override")
        evidence_refs.append("truth_continuity_overrides.jsonl")

    row = build_event(
        turn_index=turn_index,
        continuity_score=round(max(0.0, score), 3),
        drift_flags=flags,
        evidence_refs=evidence_refs,
        writer="swarm_truth_continuity:evaluate_biological_continuity",
        note=f"Evaluated speech against bio field. Skin: {cuttlefish_pattern}, Tone: {electric_autonomic_tone:.2f}, TD: {td_error:.2f}",
        truth_label="OPERATIONAL",
    )
    if override_applied and override:
        row["override_id"] = str(override.get("override_id") or "")
        row["override_scope"] = str(override.get("scope") or "")
        row["override_reason"] = str(override.get("reason") or "")[:200]
        row["override_applied"] = True
        row["td_reward_override"] = 0.0
    append_event(row)
    
    # ── Truth Continuity as Learning Signal (AGI Iteration) ──
    # Feed somatic contradictions back into the TD Learner as a shaped penalty.
    # Severity + Context Layer: single mild contradictions don't heavily penalize.
    try:
        from System.swarm_td_learner import observe_reward
        penalty = float(round(score - 1.0, 3)) # e.g. 0.6 -> -0.4
        if penalty < 0:
            if override_applied:
                return row
            # Check recent streak to prevent harsh punishment for one-off emotional expression
            streak = 1
            try:
                truth_lines = (_STATE / "truth_continuity_events.jsonl").read_text(encoding="utf-8").strip().splitlines()[-5:]
                for line in reversed(truth_lines[:-1]): # Exclude the row we just appended (wait, we just appended it, so it's in truth_lines)
                    recent_score = float(json.loads(line).get("continuity_score", 1.0))
                    if recent_score < 1.0:
                        streak += 1
                    else:
                        break
            except Exception:
                pass
                
            if streak == 1:
                penalty *= 0.25 # Mild warning for first drift
            elif streak == 2:
                penalty *= 0.50 # Escalating
            
            observe_reward(reward=penalty, action=f"somatic_contradiction_streak_{streak}")
        else:
            # Small positive reinforcement for remaining somatically honest
            observe_reward(reward=0.05, action="somatic_honest_speech")
    except Exception:
        pass
        
    return row

def proof_of_property() -> Dict[str, Any]:
    """CI DAM: in-memory schema validation (Round-2). Live speech critic is separate:
    `evaluate_biological_continuity()` when Talk-to-Alice `_on_brain_done` runs."""
    row = build_event(
        turn_index=0,
        continuity_score=0.7,
        drift_flags=["stub_no_drift"],
        evidence_refs=[],
        writer="swarm_truth_continuity:proof",
        note="CI stub row: schema keys only; biological speech critic is evaluate_biological_continuity + talk widget.",
        truth_label="OPERATIONAL",
    )
    ok = (
        row["schema"] == SCHEMA_LITERAL
        and row["truth_label"] in TRUTH_LABELS
        and isinstance(row["drift_flags"], list)
    )
    return {
        "ok": ok,
        "schema_literal_ok": row["schema"] == SCHEMA_LITERAL,
        "stub_round": 2,
        "ledger_path": str(TRUTH_CONTINUITY_LEDGER.relative_to(_REPO)),
    }


__all__ = [
    "SCHEMA_LITERAL",
    "TRUTH_LABELS",
    "TRUTH_CONTINUITY_LEDGER",
    "TRUTH_CONTINUITY_OVERRIDES",
    "OVERRIDE_SCHEMA_LITERAL",
    "build_event",
    "append_event",
    "append_allowed_dissociation",
    "active_allowed_dissociation",
    "evaluate_biological_continuity",
    "proof_of_property",
]
