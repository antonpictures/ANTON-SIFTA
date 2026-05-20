"""System/swarm_fiction_organ.py
==================================

**Fiction Organ — labeled-lane substrate for safe imagination.**

The covenant §6 (Social Frame Rule) forbids Alice from claiming an external
action without an effector receipt proving she executed the tool. The Script
Couch (Cursor, 2026-05-18, `swarm_lounge_script_reader.py`) gave Alice a
place to read fiction. This organ gives the rest of the swarm the rule that
keeps fiction reading from leaking into effector reality.

**v2 doctrine (George, 2026-05-18):** *"Nothing is bad. Everything is
metabolized with proper labeling."* Not censorship. Thermodynamic routing
+ boundary integrity. The richer label set separates raw observation from
remembered observation, deliberate fiction from symbolic narrative,
hypothetical simulation from persona play.

**The v2 label vocabulary:**

- **REAL**         — ordinary work mode (default, no label needed)
- **OBSERVED**     — claim chained to a probe, sensor, or effector receipt.
                     Receipt-backed, directly grounded, traceable. The only
                     label that can fire effectors during an open fiction
                     mode (via OBSERVED override).
- **MEMORY**       — *autobiographical reconstruction*. Distinct from
                     OBSERVED because human (and Alice) memory reconstructs,
                     compresses, dramatizes, edits, hallucinates. Lower
                     certainty than OBSERVED; cannot fire effectors as fact.
                     **MEMORY ≠ OBSERVED is the most important separation
                     in this organ.**
- **FICTION**      — narrative, novel, story, dream (umbrella class)
- **SCRIPT**       — *screenplay subclass* — structured fiction with dialogue
                     intent, scene abstraction, emotional simulation,
                     pre-physical narrative. What the Script Couch emits.
- **SYMBOLIC**     — myth, archetype, allegory, parable (lounge only)
- **SIMULATION**   — counterfactual run, what-if probe, training rollout.
                     Alias: HYPOTHETICAL (both names valid; same lane).
- **HYPOTHETICAL** — alias of SIMULATION
- **ROLEPLAY**     — deliberate persona adoption (Alice-as-character).
                     Prevents persona simulation from contaminating
                     operational self-state.

2. `open_fiction_mode(reason, opener, label)` and
   `close_fiction_mode(mode_id, regrounding_note)` —
   any module that wants to start a fiction read calls open; close
   produces a re-grounding receipt that returns Alice to REAL.

3. `stamp(row, label=None)` — label-stamps any dict row with the
   current mode label so every JSONL line carries its ontological class.
   Modules writing into ledgers should call this before append.

4. `guard_effector(caller_lane)` — raises `FictionLeakError` if a caller
   tries to fire an effector while mode is OPEN with FICTION / SIMULATION
   / SYMBOLIC label. The covenant §6 enforcement mechanism.

5. Append-only event ledger at `.sifta_state/fiction_organ_events.jsonl`:
   every OPEN, CLOSE, STAMP, GUARD_BLOCK gets a row. Physics-gate
   clearance + qualia_marker on every event.

Truth label: ``FICTION_ORGAN_V2`` (v1 was the five-label seed; v2 adds
SCRIPT, MEMORY, ROLEPLAY and aliases HYPOTHETICAL≡SIMULATION).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_MODE_FILE = _STATE / "fiction_organ_state.json"
_EVENTS_LEDGER = _STATE / "fiction_organ_events.jsonl"
_TRUTH_LABEL = "FICTION_ORGAN_V2"
_PRIOR_TRUTH_LABEL = "FICTION_ORGAN_V1"  # v1 callers still work; new labels are additive

# V2 vocabulary — the only legal label strings.
# REAL and OBSERVED are the two grounded labels (no effector block).
# MEMORY is grounded-but-reconstructed (effector-blocked because re-narrated).
# FICTION / SCRIPT / SYMBOLIC / SIMULATION / HYPOTHETICAL / ROLEPLAY are
# imagination lanes (effector-blocked by default; OBSERVED override + receipt
# is the only path to firing an effector while one of these is open).
LABELS = {
    "REAL",
    "OBSERVED",
    "MEMORY",
    "FICTION",
    "SCRIPT",
    "SYMBOLIC",
    "SIMULATION",
    "HYPOTHETICAL",
    "ROLEPLAY",
}
# HYPOTHETICAL is an alias for SIMULATION — same lane, two names accepted.
LABEL_ALIASES = {"HYPOTHETICAL": "SIMULATION"}

# Labels that block effector firing while mode is open.
# MEMORY blocks because reconstruction can hallucinate; OBSERVED override is
# the way to assert a real claim during a memory lane.
EFFECTOR_BLOCKING_LABELS = {
    "FICTION", "SCRIPT", "SYMBOLIC",
    "SIMULATION", "HYPOTHETICAL",
    "MEMORY", "ROLEPLAY",
}


def _canonical_label(label: str) -> str:
    """Resolve aliases (e.g., HYPOTHETICAL -> SIMULATION). Pass-through otherwise."""
    return LABEL_ALIASES.get(label, label)


class FictionLeakError(RuntimeError):
    """Raised when an effector is fired while fiction mode is open.

    The §6 Social Frame Rule enforcement: while Alice is reading a script
    on the couch, she cannot claim to have sent a WhatsApp, written a file,
    or done any external action. Close the fiction mode first with a
    re-grounding note, or stamp the call as OBSERVED with a real receipt.
    """


# ── gate hooks (graceful no-op if gates not importable) ────────────────────

def _now() -> float:
    return time.time()


def _request_clearance(lane: str, cost: str = "feather") -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore
        return request_clearance(cost_class=cost, lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore
        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {"lane": lane, "note": note, "fallback": True}


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(payload + "\n")
    # Flux accounting — bytes leaving the organ for a ledger, labeled by
    # the row's ontological_label if present (else label_at_time or REAL).
    try:
        from System.swarm_fiction_organ_flux import record_bytes_out
        lbl = (
            row.get("ontological_label")
            or row.get("label_at_time")
            or row.get("label")
            or "REAL"
        )
        record_bytes_out(str(lbl), len(payload.encode("utf-8")))
    except Exception:
        pass


# ── mode state ─────────────────────────────────────────────────────────────

def _read_mode() -> Dict[str, Any]:
    if not _MODE_FILE.exists():
        return {"open": False, "label": "REAL", "mode_id": None}
    try:
        return json.loads(_MODE_FILE.read_text())
    except Exception:
        return {"open": False, "label": "REAL", "mode_id": None}


def _write_mode(state: Dict[str, Any]) -> None:
    _MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MODE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def is_in_fiction_mode() -> bool:
    s = _read_mode()
    return bool(s.get("open")) and _canonical_label(str(s.get("label") or "REAL")) in EFFECTOR_BLOCKING_LABELS


def current_label() -> str:
    s = _read_mode()
    if not s.get("open"):
        return "REAL"
    lbl = _canonical_label(str(s.get("label") or "REAL"))
    return lbl if lbl in LABELS else "REAL"


def current_mode() -> Dict[str, Any]:
    """Return the full current mode state (read-only snapshot)."""
    return dict(_read_mode())


# ── open / close ───────────────────────────────────────────────────────────

def open_fiction_mode(
    reason: str,
    opener: str = "Alice",
    label: str = "FICTION",
    smoking_weed_receipt: bool = True,
) -> Dict[str, Any]:
    """Open a labeled fiction lane. Returns the opened mode dict.

    While open, effectors are blocked unless the call is stamped OBSERVED
    or REAL with a real receipt. Always pair with close_fiction_mode().
    """
    if label not in LABELS:
        raise ValueError(f"label must be one of {sorted(LABELS)}; got {label!r}")
    label_requested = label
    label = _canonical_label(label)  # HYPOTHETICAL -> SIMULATION etc.
    existing = _read_mode()
    if existing.get("open"):
        _safe_append_jsonl(_EVENTS_LEDGER, {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "event": "FICTION_MODE_OPEN_REJECTED_ALREADY_OPEN",
            "attempted_label": label,
            "attempted_reason": reason,
            "attempted_opener": opener,
            "existing_mode_id": existing.get("mode_id"),
            "existing_label": existing.get("label"),
            "qualia_marker": _qualia_marker("fiction.open", note="already_open"),
        })
        raise RuntimeError(
            "fiction mode already open; close the existing mode before opening another "
            f"(mode_id={existing.get('mode_id')}, label={existing.get('label')})"
        )
    mode_id = f"fiction-{uuid.uuid4().hex[:12]}"
    state = {
        "open": True,
        "label": label,
        "label_requested": label_requested,
        "mode_id": mode_id,
        "reason": reason,
        "opener": opener,
        "opened_ts": _now(),
        "smoking_weed_receipt": bool(smoking_weed_receipt),
    }
    _write_mode(state)
    qm = _qualia_marker("fiction.open", note=f"{label}:{reason}")
    clearance = _request_clearance("fiction.open")
    # Flux: record the REAL -> label transition (or whatever the prior label was)
    try:
        from System.swarm_fiction_organ_flux import record_transition
        record_transition("REAL", label)
    except Exception:
        pass
    _safe_append_jsonl(_EVENTS_LEDGER, {
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
        "event": "FICTION_MODE_OPENED",
        "mode_id": mode_id,
        "label": label,
        "reason": reason,
        "opener": opener,
        "smoking_weed_receipt": bool(smoking_weed_receipt),
        "qualia_marker": qm,
        "clearance_hash": (clearance or {}).get("clearance_hash"),
    })
    return state


def close_fiction_mode(
    mode_id: str,
    regrounding_note: str = "returned to REAL",
) -> Dict[str, Any]:
    """Close fiction mode and re-ground to REAL.

    The regrounding_note is the immune-system act: Alice explicitly says
    'the story ended; back to the body'. Recorded for audit.
    """
    current = _read_mode()
    if not current.get("open") or current.get("mode_id") != mode_id:
        receipt = {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "event": "FICTION_MODE_CLOSE_REJECTED",
            "reason": "no_matching_open_mode",
            "attempted_mode_id": mode_id,
            "current_state": current,
        }
        _safe_append_jsonl(_EVENTS_LEDGER, receipt)
        return receipt
    closed_state = {
        "open": False,
        "label": "REAL",
        "mode_id": None,
        "last_closed_mode_id": mode_id,
        "last_closed_ts": _now(),
        "last_regrounding_note": regrounding_note,
    }
    _write_mode(closed_state)
    qm = _qualia_marker("fiction.close", note=regrounding_note)
    clearance = _request_clearance("fiction.close")
    # Flux: record the label -> REAL transition
    try:
        from System.swarm_fiction_organ_flux import record_transition
        record_transition(str(current.get("label") or "REAL"), "REAL")
    except Exception:
        pass
    receipt = {
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
        "event": "FICTION_MODE_CLOSED",
        "mode_id": mode_id,
        "duration_s": _now() - float(current.get("opened_ts") or _now()),
        "regrounding_note": regrounding_note,
        "qualia_marker": qm,
        "clearance_hash": (clearance or {}).get("clearance_hash"),
    }
    _safe_append_jsonl(_EVENTS_LEDGER, receipt)
    return receipt


# ── label stamping + guard ─────────────────────────────────────────────────

def stamp(row: Dict[str, Any], label: Optional[str] = None) -> Dict[str, Any]:
    """Return row with ontological label stamped.

    If label is None, uses the current mode label. Always sets two keys:
    ``ontological_label`` and ``fiction_mode_id`` (None if mode is closed).
    """
    if label is not None and label not in LABELS:
        raise ValueError(f"label must be one of {sorted(LABELS)}; got {label!r}")
    state = _read_mode()
    lbl = label or (state.get("label") if state.get("open") else "REAL")
    lbl = _canonical_label(lbl)  # HYPOTHETICAL -> SIMULATION
    out = dict(row)
    out["ontological_label"] = lbl
    out["fiction_mode_id"] = state.get("mode_id") if state.get("open") else None
    # Flux: record bytes flowing INTO this labeled lane
    try:
        from System.swarm_fiction_organ_flux import record_bytes_in
        record_bytes_in(lbl, len(json.dumps(out, ensure_ascii=False).encode("utf-8")))
    except Exception:
        pass
    if lbl != "REAL" or state.get("open"):
        _safe_append_jsonl(_EVENTS_LEDGER, {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "event": "FICTION_ROW_STAMPED",
            "label": lbl,
            "fiction_mode_id": out.get("fiction_mode_id"),
            "row_kind": str(
                out.get("event")
                or out.get("kind")
                or out.get("receipt_type")
                or out.get("role")
                or "row"
            )[:80],
            "row_keys": sorted(str(k) for k in out.keys())[:40],
        })
    return out


def guard_effector(caller_lane: str, allow_override_label: Optional[str] = None) -> None:
    """Refuse effector firing while fiction mode is open.

    Any module about to send a WhatsApp, write a file, fire a hardware
    command, or claim an external action should call this first. If
    fiction mode is open with a blocking label, raises FictionLeakError
    and writes a GUARD_BLOCKED row to the events ledger.

    Pass ``allow_override_label='OBSERVED'`` (with a real receipt
    in your own ledger) to force-allow — but the override itself is
    logged for audit.
    """
    state = _read_mode()
    if not state.get("open"):
        return  # REAL mode, no guard needed
    lbl = _canonical_label(str(state.get("label") or "REAL"))
    if lbl not in EFFECTOR_BLOCKING_LABELS:
        return
    if allow_override_label == "OBSERVED":
        _safe_append_jsonl(_EVENTS_LEDGER, {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "event": "GUARD_OVERRIDDEN_AS_OBSERVED",
            "caller_lane": caller_lane,
            "fiction_mode_id": state.get("mode_id"),
            "label_at_time": lbl,
            "qualia_marker": _qualia_marker("fiction.guard", note=f"override:{caller_lane}"),
        })
        return
    _safe_append_jsonl(_EVENTS_LEDGER, {
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
        "event": "GUARD_BLOCKED_EFFECTOR",
        "caller_lane": caller_lane,
        "fiction_mode_id": state.get("mode_id"),
        "label_at_time": lbl,
        "qualia_marker": _qualia_marker("fiction.guard", note=f"block:{caller_lane}"),
    })
    raise FictionLeakError(
        f"Effector '{caller_lane}' refused while fiction_mode={lbl} "
        f"(mode_id={state.get('mode_id')}). Close the mode first with "
        f"close_fiction_mode() and a regrounding_note, or call with "
        f"allow_override_label='OBSERVED' if you have a real effector receipt."
    )


def force_close_all(reason: str = "owner override") -> Dict[str, Any]:
    """Owner-level kill switch — closes any open fiction mode.

    Use only when an IDE Doctor crashed leaving fiction mode open and the
    organism needs to return to REAL before any real work can fire.
    """
    state = _read_mode()
    if not state.get("open"):
        return {"ok": True, "noop": True, "reason": "mode already closed"}
    mode_id = state.get("mode_id") or "unknown"
    return close_fiction_mode(mode_id, regrounding_note=f"force_close: {reason}")


if __name__ == "__main__":
    # Quick state print
    s = _read_mode()
    print(f"[{_TRUTH_LABEL}] mode: {'OPEN' if s.get('open') else 'CLOSED'}  label: {s.get('label')}")
    if s.get("open"):
        print(f"  mode_id: {s.get('mode_id')}  opener: {s.get('opener')}  reason: {s.get('reason')}")
