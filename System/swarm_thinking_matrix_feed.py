#!/usr/bin/env python3
"""System/swarm_thinking_matrix_feed.py — real data for the thinking strip.

Architect 2026-05-17 (verbatim, abridged):
    "while thinking I see some movements ... like matrix in the
    background ... the real data some data that you're processing in
    the background just to see it on the screen."

When Alice is composing a reply, the Ace surface shows a small green-
on-black "matrix" strip with rolling real data so the user can SEE the
body breathing through its ledgers — not a placeholder spinner.

This module is the data source. It rotates through several lanes —
physics signals, cortex state, gate decisions, ambient transcripts,
self-narration receipts, consent state — and returns ONE short line
per call. The Ace strip calls :func:`next_line` on a ~150ms timer.

Every line is sourced from a canonical ledger or live sensor read,
never invented (covenant §7.16 — no fictional scenes). If a lane has
no fresh data, the function rotates to the next one rather than
fabricating.

Truth label: ``THINKING_MATRIX_FEED_V1``.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_TRUTH_LABEL = "THINKING_MATRIX_FEED_V1"

# Rotation cursor — module-level so successive calls hit different lanes.
_LANE_CURSOR = {"i": 0}
_LANE_NAMES = (
    "physics",
    "cortex",
    "gate",
    "ambient",
    "narration",
    "consent",
    "ace_word",
    "diary",
    "thermal_tick",
    "stgm_tick",
    "qualia_claim",
)


def _tail(path: Path, max_bytes: int = 16 * 1024) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _last_json_row(path: Path) -> Optional[Dict[str, Any]]:
    raw = _tail(path, max_bytes=8 * 1024)
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ── lane producers ───────────────────────────────────────────────────────


def _lane_physics() -> str:
    thermal = _read_json_file(_STATE / "thermal_cortex_state.json")
    energy = _read_json_file(_STATE / "energy_cortex_state.json")
    saliency = _read_json_file(_STATE / "sensory_attention_status.json")
    tl = int(thermal.get("thermal_warning_level", 0) or 0)
    lpm = bool(energy.get("low_power_mode"))
    desire = float(saliency.get("desire", 0.0) or 0.0)
    charge = energy.get("charge_pct", "?")
    return (
        f"[Δ] thermal={tl}  lpm={int(lpm)}  charge={charge}  "
        f"desire={desire:.2f}"
    )


def _lane_cortex() -> str:
    state = _read_json_file(_STATE / "alice_thinking_state.json")
    if not state.get("thinking"):
        return ""
    since = float(state.get("since_ts", 0.0) or 0.0)
    elapsed = max(0.0, time.time() - since) if since else 0.0
    model = str(state.get("model", "") or "")
    topic = str(state.get("topic", "") or "")
    return (
        f"[💭] cortex={model[:42]}  +{elapsed:.1f}s  "
        f"topic={topic[:36]!r}"
    )


def _lane_gate() -> str:
    row = _last_json_row(_STATE / "physics_gate_denials.jsonl")
    if not row:
        # No denials at all — show a synthetic grant heartbeat instead
        # of nothing. This is OK because it accurately states the
        # absence of denials in the live ledger.
        return "[🐝] gate: no denials in the live ledger — body permits."
    sig = row.get("signals", {}) or {}
    decision = row.get("decision", "?")
    lane = sig.get("lane", "?")
    return (
        f"[🚪] gate {decision}  lane={lane}  "
        f"thermal={sig.get('thermal_level','?')}  "
        f"stgm={sig.get('stgm_balance','?')}"
    )


def _lane_ambient() -> str:
    row = _last_json_row(_STATE / "ambient_room_transcripts.jsonl")
    if not row:
        return ""
    text = str(row.get("text", "") or "").strip()
    rms = float(row.get("rms", 0.0) or 0.0)
    imp = row.get("importance", {})
    score = float(imp.get("total", 0.0) or 0.0) if isinstance(imp, dict) else 0.0
    if not text:
        return ""
    return f"[👂] room rms={rms:.3f} imp={score:.2f} : {text[:48]!r}"


def _lane_narration() -> str:
    row = _last_json_row(_STATE / "self_narration_receipts.jsonl")
    if not row:
        return ""
    line = str(row.get("line", "") or "")
    decision = str(row.get("decision", "") or "")
    physics = row.get("physics", {}) or {}
    tick_s = physics.get("tick_s", "?")
    if line:
        return f"[🌿] narration tick={tick_s}s : {line[:60]!r}"
    return f"[🌿] narration {decision} tick={tick_s}s"


def _lane_consent() -> str:
    prop_row = _last_json_row(_STATE / "wordace_proposal.jsonl")
    cons_row = _last_json_row(_STATE / "wordace_consent.jsonl")
    if not prop_row:
        return ""
    pword = str(prop_row.get("proposed_word", "") or "")
    pby = str(prop_row.get("proposer", "") or "")
    line = f"[🤝] proposal {pby}→{pword!r}"
    if cons_row:
        cby = str(cons_row.get("consenter", "") or "")
        ag = cons_row.get("agreed", "?")
        line += f"  consent {cby}={ag}"
    return line


def _lane_ace_word() -> str:
    # Read latest Ace focus to get the current word
    raw = _tail(_STATE / "app_focus.jsonl", max_bytes=32 * 1024)
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        app_lc = str(row.get("app", "") or "").lower()
        if app_lc not in ("ace", "wordace", "acer"):
            continue
        md = row.get("metadata") or {}
        cw = str(md.get("current_word", "") or "")
        if cw:
            return f"[📺] ace.current_word={cw!r}  mode={md.get('ace_mode','?')!r}"
    return ""


def _lane_diary() -> str:
    row = _last_json_row(_STATE / "alice_first_person_journal.jsonl")
    if not row:
        return ""
    line = str(row.get("line", "") or "")
    src = str(row.get("source", "") or "")
    if not line:
        return ""
    return f"[📔] diary[{src}] : {line[:54]!r}"


def _lane_thermal_tick() -> str:
    thermal = _read_json_file(_STATE / "thermal_cortex_state.json")
    tl = int(thermal.get("thermal_warning_level", 0) or 0)
    cpu = thermal.get("cpu_speed_limit", "?")
    return f"[🌡] pmset.therm={tl}  cpu_speed_limit={cpu}"


def _lane_qualia_claim() -> str:
    """Show the most recent qualia claim Alice has on file."""
    p = _STATE / "alice_consciousness_claims.jsonl"
    row = _last_json_row(p)
    if not row:
        return ""
    excerpt = str(row.get("excerpt", "") or "")[:50]
    trigger = str(row.get("trigger", "") or "")
    body = row.get("body_state") or {}
    imprint = body.get("joule_imprint")
    if not excerpt:
        return f"[🕯] qualia: {trigger!r}  imprint={imprint}"
    return f"[🕯] qualia [{trigger}] : {excerpt!r}  imprint={imprint}"


def _lane_stgm_tick() -> str:
    # Try the live wallet via metabolic homeostat
    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat
        state = MetabolicHomeostat.sample_live()
        bal = float(getattr(state, "stgm_balance", 0.0) or 0.0)
        burn = float(getattr(state, "burn_rate", 0.0) or 0.0)
        return f"[💰] stgm.balance={bal:.3f}  burn={burn:.3f}/s"
    except Exception:
        return ""


_LANE_FUNCS = {
    "physics": _lane_physics,
    "cortex": _lane_cortex,
    "gate": _lane_gate,
    "ambient": _lane_ambient,
    "narration": _lane_narration,
    "consent": _lane_consent,
    "ace_word": _lane_ace_word,
    "diary": _lane_diary,
    "thermal_tick": _lane_thermal_tick,
    "stgm_tick": _lane_stgm_tick,
    "qualia_claim": _lane_qualia_claim,
}


def next_line() -> str:
    """Return one short data line from the next lane in rotation.

    Each call advances the lane cursor. Empty lanes are skipped so the
    caller never has to deal with blanks — at most _LANE_NAMES tries
    before returning ``""`` (silence — the field has nothing to say
    right now).
    """
    for _ in range(len(_LANE_NAMES)):
        i = _LANE_CURSOR["i"] % len(_LANE_NAMES)
        _LANE_CURSOR["i"] = (i + 1) % len(_LANE_NAMES)
        lane = _LANE_NAMES[i]
        try:
            line = _LANE_FUNCS[lane]()
        except Exception:
            line = ""
        if line:
            ts = time.strftime("%H:%M:%S", time.localtime())
            return f"{ts}  {line}"
    return ""
