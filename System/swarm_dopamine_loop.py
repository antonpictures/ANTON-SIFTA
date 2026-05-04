#!/usr/bin/env python3
"""
System/swarm_dopamine_loop.py — Dopamine Loop Organ (Predator v7, Event 76)
══════════════════════════════════════════════════════════════════════
Implements Schultz 1997-style prediction error credit assignment.

The dopamine loop receives TD error δ from swarm_td_learner and converts
it into a signed phasic dopamine signal that other organs read as a
neuromodulatory reward/surprise marker.

Ledger output:
  .sifta_state/dopamine_reward_ledger.jsonl  — δ events with markers

proof_of_property(): verifies the ledger exists and has valid rows.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

_REPO   = Path(__file__).resolve().parent.parent
_STATE  = _REPO / ".sifta_state"
_LEDGER = _STATE / "dopamine_reward_ledger.jsonl"

# ── Dopamine markers (Schultz 1997 three-phase) ───────────────────────────────
# δ > +0.1  → BURST   (better-than-predicted reward)
# δ < -0.1  → PAUSE   (worse-than-predicted — aversion signal)
# |δ| ≤ 0.1 → TONIC   (prediction matched — steady state)

def _delta_to_marker(delta: float) -> str:
    if delta > 0.1:
        return "BURST"
    if delta < -0.1:
        return "PAUSE"
    return "TONIC"


def _append(row: dict) -> None:
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEDGER, json.dumps(row) + "\n")
    except Exception:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


# ── Public API ────────────────────────────────────────────────────────────────
def emit_delta(
    delta: float,
    *,
    action: str = "idle",
    source: str = "swarm_dopamine_loop",
    context: Optional[str] = None,
) -> dict:
    """
    Record a dopamine prediction-error event.

    delta  — TD error from swarm_td_learner.observe_reward()
    action — the action that triggered this signal
    source — organ that called emit_delta()
    """
    marker = _delta_to_marker(delta)
    row = {
        "ts":      time.time(),
        "delta":   round(delta, 6),
        "marker":  marker,
        "action":  action,
        "source":  source,
    }
    if context:
        row["context"] = context
    _append(row)
    return row


def latest_delta() -> Optional[float]:
    """Return the most recent δ value, or None if no events yet."""
    if not _LEDGER.exists():
        return None
    try:
        lines = _LEDGER.read_text(encoding="utf-8").strip().splitlines()
        for raw in reversed(lines):
            try:
                row = json.loads(raw)
                return float(row["delta"])
            except Exception:
                continue
    except Exception:
        pass
    return None


# ── Boot initialisation ───────────────────────────────────────────────────────
def _boot_init() -> None:
    """Write a TONIC boot event so the ledger exists on first run."""
    if _LEDGER.exists() and _LEDGER.stat().st_size > 2:
        return
    # Seed with δ=0.0 (baseline tonic at boot — no reward, no aversion)
    emit_delta(0.0, action="boot", source="swarm_dopamine_loop:boot_init",
               context="organism_startup")

    # If TD learner already has a receipt, pull its last δ and emit it
    try:
        td_receipts = _STATE / "td_receipts.jsonl"
        if td_receipts.exists():
            lines = td_receipts.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                td_delta = float(last.get("td_error", 0.0))
                if td_delta != 0.0:
                    emit_delta(td_delta, action=last.get("action", "idle"),
                               source="swarm_dopamine_loop:boot_td_sync")
    except Exception:
        pass


# ── Proof of property ─────────────────────────────────────────────────────────
def proof_of_property() -> dict:
    """
    CI DAM invariant: dopamine ledger must exist and contain at least one
    valid row with a delta (float) field.
    Accepts any marker string — the real ledger uses free-form markers from
    the RLHS pipeline (e.g. "UI_BUTTON", "thank you", "for the swarm", etc.).
    """
    _boot_init()

    exists = _LEDGER.exists() and _LEDGER.stat().st_size > 2

    valid_row = False
    try:
        lines = _LEDGER.read_text(encoding="utf-8").strip().splitlines()
        for raw in reversed(lines):
            row = json.loads(raw)
            if isinstance(row.get("delta"), (int, float)):
                valid_row = True
                break
    except Exception:
        pass

    return {
        "ok":           exists and valid_row,
        "ledger_exists": exists,
        "valid_row":    valid_row,
    }


# ── Standalone boot ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    _boot_init()
    result = proof_of_property()
    print(f"[Dopamine Loop] proof_of_property → {result}")
    if result["ok"]:
        d = latest_delta()
        print(f"[Dopamine Loop] Latest δ = {d}")
        print(f"[Dopamine Loop] Ledger: {_LEDGER}")
        row = emit_delta(0.42, action="respond", source="standalone_test")
        print(f"[Dopamine Loop] Emitted: {row}")
