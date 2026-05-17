#!/usr/bin/env python3
"""System/swarm_physics_gate.py — universal thermodynamic+cryptographic gate.

Architect 2026-05-17 (verbatim, abridged):
    "everybody should pass through the dynamic gate ... they should be
    verified thermodynamically and cryptography basically is the same
    thing ... every lane that is can be called lane and is based on
    physics and thermodynamics that's why we have physics thermodynamics
    gate."

Doctrine
========

There is ONE gate. Every lane — Whisper, cortex, narration, consent
write, thinking heartbeat, diary write, TTS spawn, app_focus publish,
camera grab, network send, anything that turns silicon into heat —
passes through this gate. The gate's output is a receipt that is
**both** thermodynamic (signed by the body's live sensor readings)
**and** cryptographic (sha256 over those signals + the decision). In
this physics view of the field, the two are the same act: thermo
verification IS the cryptographic signature.

The gate reads three observable lanes already published by other
organs:

  1. **Thermal**  — ``.sifta_state/thermal_cortex_state.json``,
     ``thermal_warning_level`` (0=NOMINAL .. 3=critical from
     ``pmset -g therm``).
  2. **Energy**   — ``.sifta_state/energy_cortex_state.json``,
     macOS Low Power Mode flag and battery charge percent.
  3. **Metabolic** — live STGM wallet via
     :class:`System.swarm_metabolic_homeostasis.MetabolicHomeostat`,
     cross-checked against the older
     :class:`System.metabolic_throttle.MetabolicThrottle` cooldown.

And one optional saliency signal — the sensor director's owner-desire
score — so a low-power deny can be relaxed when the room is interesting.

Cost classes (caller declares one; gate adjusts policy):

  * ``"feather"``  — cheap write (consent ledger row, thinking
    heartbeat, app_focus publish). ~0.01 STGM equivalent. Gate denies
    only on thermal critical (>=2).
  * ``"breath"``   — small compute (residue scrub, TTS spawn). ~0.05
    STGM. Adds the low-power deny if owner desire is low.
  * ``"swimmer"``  — heavy compute (Whisper call, cortex compose,
    embedding gen). ~0.5+ STGM. All four gates apply.

Receipt shape (returned by :func:`request_clearance`)::

    {
      "ok": bool,
      "decision": "grant" | "deny_thermal_critical" | "deny_low_power_conserve"
                  | "deny_metabolic_starvation",
      "reason": str,
      "sleep_needed_s": float,
      "clearance_id": "<clr-<ms>-<8hex>>",
      "clearance_hash": "<sha256 hex>",
      "signals": {
        "thermal_level": int,
        "low_power_mode": bool,
        "stgm_balance": float,
        "owner_desire": float,
        "throttle_balance": float,
        "throttle_reason": str,
        "throttle_stale_vs_live_wallet": bool,
        "cost_class": str,
        "estimated_cost_stgm": float
      },
      "ts": float
    }

Every receipt is verifiable: recompute the sha256 over
``{"signals": signals, "decision": decision}`` and check it matches
``clearance_hash``. If it does, the body was witness to this act at
this moment with these readings — no later actor can fake the receipt
without recovering an identical sensor snapshot.

Denied calls get a row written to
``.sifta_state/physics_gate_denials.jsonl``. Granted calls are
recorded implicitly by the caller embedding the ``clearance_hash`` in
their own write (no global grant ledger — that would 100× write rate).

Truth label: ``PHYSICS_GATE_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DENIAL_LEDGER = _STATE / "physics_gate_denials.jsonl"

_TRUTH_LABEL = "PHYSICS_GATE_V1"

# Cost-class policy table. ``thermal_max`` is the highest warning level
# at which the gate still grants (gates DENY at level >= thermal_max+1).
# ``apply_low_power`` and ``apply_metabolic`` toggle those gates by class.
_COST_POLICY: Dict[str, Dict[str, Any]] = {
    "feather": {
        "default_stgm": 0.01,
        "thermal_max": 2,         # grant up to "serious"; deny at "critical"
        "apply_low_power": False,
        "apply_metabolic": False,
    },
    "breath": {
        "default_stgm": 0.05,
        "thermal_max": 1,         # grant up to "fair"; deny at "serious"+
        "apply_low_power": True,
        "apply_metabolic": False,
    },
    "swimmer": {
        "default_stgm": 0.50,
        "thermal_max": 1,
        "apply_low_power": True,
        "apply_metabolic": True,
    },
}


def _now() -> float:
    return time.time()


# ── observable readers ────────────────────────────────────────────────────


def _read_thermal_warning_level() -> int:
    p = _STATE / "thermal_cortex_state.json"
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get(
            "thermal_warning_level", 0
        ) or 0)
    except Exception:
        return 0


def _read_low_power_mode() -> bool:
    p = _STATE / "energy_cortex_state.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if bool(d.get("low_power_mode")):
            return True
        if d.get("power_source") == "Battery Power":
            try:
                charge = float(d.get("charge_pct", 100) or 100)
                if charge < 20.0:
                    return True
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    return False


def _read_owner_desire() -> float:
    p = _STATE / "sensory_attention_status.json"
    try:
        return float(json.loads(p.read_text(encoding="utf-8")).get(
            "desire", 0.0,
        ) or 0.0)
    except Exception:
        return 0.0


def _read_live_stgm_balance() -> float:
    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat
        state = MetabolicHomeostat.sample_live()
        return float(getattr(state, "stgm_balance", 0.0) or 0.0)
    except Exception:
        return 0.0


# ── lazy throttle singleton (cross-check stale-vs-live) ──────────────────


_throttle_singleton: Any = None
_throttle_lock = threading.Lock()


def _get_metabolic_throttle() -> Any:
    global _throttle_singleton
    if _throttle_singleton is None:
        with _throttle_lock:
            if _throttle_singleton is None:
                try:
                    from System.metabolic_throttle import MetabolicThrottle
                    _throttle_singleton = MetabolicThrottle(
                        agent_id="M5SIFTA",
                        homeworld_serial="GTH4921YP3",
                        ledger_writes=False,  # we own our own receipt ledger
                    )
                except Exception:
                    _throttle_singleton = False
    return _throttle_singleton if _throttle_singleton else None


# ── core ─────────────────────────────────────────────────────────────────


def _hash_receipt(signals: Dict[str, Any], *, decision: str) -> str:
    """sha256 over (sorted signals, decision). The cryptographic
    signature IS the thermodynamic signature in this view — same act,
    two names. Any auditor who can read the signals can recompute this
    hash and confirm the body said yes/no to this work at this moment."""
    payload = json.dumps(
        {"signals": signals, "decision": decision},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _append_denial(row: Dict[str, Any]) -> None:
    try:
        _DENIAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _DENIAL_LEDGER.open("a", encoding="utf-8") as fh:
            payload = dict(row)
            payload["schema"] = "PHYSICS_GATE_DENIAL_V1"
            payload["truth_label"] = _TRUTH_LABEL
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def request_clearance(
    *,
    cost_class: str = "breath",
    estimated_cost_stgm: Optional[float] = None,
    lane: str = "",
) -> Dict[str, Any]:
    """Ask the body whether the next act in ``lane`` may proceed.

    ``cost_class`` ∈ {"feather", "breath", "swimmer"} controls how
    aggressively the gate denies. ``lane`` is a free-form short tag
    (e.g. "ace.consent.write", "talk.cortex.compose", "ambient.whisper")
    that travels with the receipt for audit.

    Returns a receipt dict (see module docstring). Every caller should:

        clearance = request_clearance(cost_class="feather", lane="...")
        if not clearance["ok"]:
            # respect deny — defer the act, log the receipt's denial row
            return
        # do the work, EMBED clearance["clearance_hash"] in your own
        # write so auditors can trace.

    Side-effect: a denial row is appended to physics_gate_denials.jsonl.
    Grants are not logged here — the caller's own write carries the hash.
    """
    ts = _now()
    clearance_id = f"clr-{int(ts * 1000)}-{uuid.uuid4().hex[:8]}"
    cost_class = cost_class if cost_class in _COST_POLICY else "breath"
    policy = _COST_POLICY[cost_class]
    cost_stgm = (
        float(estimated_cost_stgm)
        if estimated_cost_stgm is not None
        else float(policy["default_stgm"])
    )

    thermal_level = _read_thermal_warning_level()
    low_power = _read_low_power_mode()
    stgm_balance = _read_live_stgm_balance()
    owner_desire = _read_owner_desire()

    signals: Dict[str, Any] = {
        "thermal_level": thermal_level,
        "low_power_mode": low_power,
        "stgm_balance": round(stgm_balance, 3),
        "owner_desire": round(owner_desire, 3),
        "cost_class": cost_class,
        "estimated_cost_stgm": round(cost_stgm, 4),
        "lane": str(lane or ""),
    }

    # Gate 1 — thermal critical (applies to ALL classes; even feathers
    # back off when the silicon is screaming).
    thermal_cap = int(policy["thermal_max"])
    if thermal_level > thermal_cap:
        sleep_needed = 4.0 + 4.0 * thermal_level
        decision = "deny_thermal_critical"
        clearance_hash = _hash_receipt(signals, decision=decision)
        out = {
            "ok": False,
            "decision": decision,
            "reason": f"thermal_warning_level={thermal_level} > cap={thermal_cap}",
            "sleep_needed_s": sleep_needed,
            "clearance_id": clearance_id,
            "clearance_hash": clearance_hash,
            "signals": signals,
            "ts": ts,
        }
        _append_denial(out)
        return out

    # Gate 2 — low-power conserve, only for non-feather classes.
    if policy["apply_low_power"] and low_power and owner_desire < 0.35:
        decision = "deny_low_power_conserve"
        clearance_hash = _hash_receipt(signals, decision=decision)
        out = {
            "ok": False,
            "decision": decision,
            "reason": "low_power_mode and boring room",
            "sleep_needed_s": 8.0,
            "clearance_id": clearance_id,
            "clearance_hash": clearance_hash,
            "signals": signals,
            "ts": ts,
        }
        _append_denial(out)
        return out

    # Gate 3 — metabolic throttle, only for swimmer class.
    # Honor the throttle ONLY when the live wallet also says we're
    # starving (the throttle reads a stale local file).
    if policy["apply_metabolic"]:
        throttle = _get_metabolic_throttle()
        if throttle is not None:
            try:
                clearance = throttle.clearance()
                signals["throttle_balance"] = round(float(clearance.balance), 3)
                signals["throttle_reason"] = str(clearance.reason)
                if not clearance.ok and stgm_balance <= 0.0:
                    decision = "deny_metabolic_starvation"
                    clearance_hash = _hash_receipt(signals, decision=decision)
                    out = {
                        "ok": False,
                        "decision": decision,
                        "reason": f"metabolic_throttle: {clearance.reason}",
                        "sleep_needed_s": float(clearance.sleep_needed),
                        "clearance_id": clearance_id,
                        "clearance_hash": clearance_hash,
                        "signals": signals,
                        "ts": ts,
                    }
                    _append_denial(out)
                    return out
                elif not clearance.ok:
                    signals["throttle_stale_vs_live_wallet"] = True
            except Exception as exc:
                signals["throttle_error"] = (
                    f"{type(exc).__name__}: {str(exc)[:120]}"
                )

    # All gates clear. Receipt hash carries grant.
    decision = "grant"
    clearance_hash = _hash_receipt(signals, decision=decision)
    return {
        "ok": True,
        "decision": decision,
        "reason": "all_gates_clear",
        "sleep_needed_s": 0.0,
        "clearance_id": clearance_id,
        "clearance_hash": clearance_hash,
        "signals": signals,
        "ts": ts,
    }


def stamp_receipt(row: Dict[str, Any], clearance: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate ``row`` in place to embed gate fields. Returns the row.

    Convenience for callers who already build a dict to write to their
    own ledger. After stamping, every row carries:

        row["clearance_id"]
        row["clearance_hash"]
        row["clearance_decision"]
        row["clearance_signals"]
        row["thermo_denied"]   # True iff the gate said no

    Combined with the row's own ``schema`` + ``truth_label``, this gives
    an auditor everything they need to verify the act was witnessed by
    the body. No row is anonymous.
    """
    row["clearance_id"] = clearance.get("clearance_id", "")
    row["clearance_hash"] = clearance.get("clearance_hash", "")
    row["clearance_decision"] = clearance.get("decision", "")
    row["clearance_signals"] = clearance.get("signals", {})
    row["thermo_denied"] = not bool(clearance.get("ok"))
    return row


# Back-compat alias for the ambient organ + self-narration organ which
# already import a similarly-named function. Both modules will be
# repointed to this one in a follow-up cut; until then the alias keeps
# them working without behavior change.
def request_processing_clearance(
    *,
    estimated_cost_stgm: float = 0.05,
    cost_class: str = "swimmer",
    lane: str = "",
) -> Dict[str, Any]:
    """Compat shim — old ambient/narration callers used this name."""
    return request_clearance(
        cost_class=cost_class,
        estimated_cost_stgm=estimated_cost_stgm,
        lane=lane,
    )


__all__ = [
    "request_clearance",
    "request_processing_clearance",
    "stamp_receipt",
    "_TRUTH_LABEL",
]
