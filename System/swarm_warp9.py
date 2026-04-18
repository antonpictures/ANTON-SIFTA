#!/usr/bin/env python3
"""
System/swarm_warp9.py — WARP 9 umbrella + Concierge (behavioral autopilot)
══════════════════════════════════════════════════════════════════════
The Architect coined "Warp 9" for the whole federation+devices+concierge
stack. This module is the front door.

Three sub-modules:
  swarm_warp9_federation.py — cross-machine swimmer transport (Module 1)
  swarm_warp9_devices.py    — external device input registry      (Module 2)
  swarm_warp9.py (this)     — Concierge: watch the owner, propose tunings
                              + umbrella re-exports                (Module 3)

The Concierge's contract — non-negotiable
-----------------------------------------
1. NEVER auto-applies a setting change. Proposals are written to a ledger.
2. The owner ratifies one proposal at a time via ratify_proposal(id).
3. Once ratified, the swarm remembers the preference and can apply
   future like-shaped proposals automatically IF the owner explicitly
   set `apply_like_this_in_future=True` on the ratification.
4. Every proposal includes the SIGNAL that prompted it, so the owner
   can audit the inference, not just the outcome.

This is the "swarm constantly analyzes os owner behaviour" loop the
Architect described, but with brakes — no surprise behavior changes.

Power to the Swarm.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.swarm_owner_identity import (
    OwnerID,
    HomeworldRecord,
    get_or_create_owner,
    register_homeworld,
    list_owner_homeworlds,
    is_federated,
    detect_self_homeworld_serial,
    detect_self_architect_id,
    FEDERATION_ENABLED,
)

from System.swarm_warp9_federation import (
    WarpMessage,
    send,
    send_chat,
    send_swimmer_visit,
    recv,
    list_spool_pairs,
)

from System.swarm_warp9_devices import (
    DeviceInput,
    DeviceSignal,
    register_device,
    list_devices_for_homeworld,
    find_device_by_capability,
    emit_device_signal,
    recent_device_signals,
    speak_via_best_device,
    CAPABILITY_KEYS,
    KNOWN_VENDORS,
    DeviceConsentMissingError,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PROPOSALS = _STATE / "warp9_concierge_proposals.jsonl"
_RATIFIED = _STATE / "warp9_concierge_ratified.jsonl"
_REJECTED = _STATE / "warp9_concierge_rejected.jsonl"   # added v2 — ratified by Architect
# C47H 2026-04-18: cerebellar pre-flight rejections. Audit-only — never reach
# the Architect's inbox. Lets the Architect retroactively see what the
# Cerebellum dropped and why, without polluting the open proposal queue.
_SCREENED_DROPS = _STATE / "warp9_concierge_screened_drops.jsonl"

MODULE_VERSION = "2026-04-18.warp9.umbrella.v3"  # +cerebellar_screen wired

# Standard reinforcement-learning row schema (additive, backward-compatible).
# Both ratified.jsonl and rejected.jsonl rows carry these flat keys so that
# downstream learners (e.g. swarm_prediction_cache) can build (state, action)
# -> reward tuples without parsing nested 'proposal' dicts.
#   - timestamp:     unix seconds (alias of ratified_ts / rejected_ts)
#   - state_context: short string snapshot of the situation that prompted the proposal
#   - action_kind:   the target_setting string (the lever being pulled)
#   - reward:        +1.0 for ratified, -1.0 for rejected, ±0.5 for soft signals
SCHEMA_VERSION = 2


def _state_context_for(prop: "ConciergeProposal") -> str:
    """Derive a stable, low-cardinality state_context string from a proposal.

    Keep cardinality low so the prediction cache can find repeats. We bucket
    OXT level into thirds and squash architect_id + presence-of-peers into
    a single dot-joined token. Never include free-text titles here."""
    snap = prop.signal_evidence or {}
    oxt = snap.get("oxt_level")
    if oxt is None:
        oxt_bucket = "oxtNA"
    elif oxt < 0.33:
        oxt_bucket = "oxtLO"
    elif oxt < 0.67:
        oxt_bucket = "oxtMD"
    else:
        oxt_bucket = "oxtHI"
    chat = snap.get("recent_chat_count", 0)
    chat_bucket = "chatHI" if chat >= 5 else ("chatMD" if chat >= 1 else "chatLO")
    return f"{prop.architect_id}.{oxt_bucket}.{chat_bucket}"

__all__ = [
    # Owner identity
    "OwnerID", "HomeworldRecord", "get_or_create_owner", "register_homeworld",
    "list_owner_homeworlds", "is_federated", "FEDERATION_ENABLED",
    "detect_self_homeworld_serial", "detect_self_architect_id",
    # Federation (Module 1)
    "WarpMessage", "send", "send_chat", "send_swimmer_visit", "recv",
    "list_spool_pairs",
    # Devices (Module 2)
    "DeviceInput", "DeviceSignal", "register_device", "list_devices_for_homeworld",
    "find_device_by_capability", "emit_device_signal", "recent_device_signals",
    "speak_via_best_device", "CAPABILITY_KEYS", "KNOWN_VENDORS",
    "DeviceConsentMissingError",
    # Concierge (Module 3)
    "OwnerBehaviorSnapshot", "ConciergeProposal", "snapshot_owner_behavior",
    "propose_setting_change", "list_open_proposals",
    "ratify_proposal", "reject_proposal", "list_recent_rejections",
    "list_screened_drops",
    "warp9_status",
]


# ──────────────────────────────────────────────────────────────────────
# Owner-behavior snapshot — the input to the Concierge
# ──────────────────────────────────────────────────────────────────────

@dataclass
class OwnerBehaviorSnapshot:
    """A point-in-time read of what the owner is doing, used by the
    Concierge to decide whether to propose anything."""
    ts: float
    architect_id: str
    homeworld_serial: str

    # Pulled from existing telemetry if available (best-effort, all optional)
    oxt_level: Optional[float] = None
    recent_chat_count: int = 0
    recent_eye_captures: int = 0
    recent_device_signals: int = 0
    federated_peers: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def snapshot_owner_behavior(owner_label: str = "IOAN") -> OwnerBehaviorSnapshot:
    """Best-effort telemetry pull. Every source is optional — if a module
    isn't installed, the field stays at its default. Never raises."""
    self_serial = detect_self_homeworld_serial()
    self_arch = detect_self_architect_id(default_owner_label=owner_label)
    snap = OwnerBehaviorSnapshot(
        ts=time.time(),
        architect_id=self_arch,
        homeworld_serial=self_serial,
    )

    # OXT (the alignment hormone — rich behavioral signal)
    try:
        from System.swarm_oxytocin_alignment import OxytocinMatrix
        snap.oxt_level = OxytocinMatrix().get_oxt_level(self_arch)
    except Exception:
        pass

    # Eye captures over the last 10 minutes
    try:
        iris_log = _STATE / "swarm_iris_capture.jsonl"
        if iris_log.exists():
            cutoff = time.time() - 600
            n = 0
            with iris_log.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                        if row.get("ts_captured", 0) >= cutoff:
                            n += 1
                    except Exception:
                        continue
            snap.recent_eye_captures = n
    except Exception:
        pass

    # Recent device signals from Module 2
    try:
        sigs = recent_device_signals(since_ts=time.time() - 600)
        snap.recent_device_signals = len(sigs)
    except Exception:
        pass

    # Federated peers (other homeworlds owned by the same human)
    try:
        owner = get_or_create_owner(owner_label)
        peers = [h.architect_id for h in list_owner_homeworlds(owner.key)
                 if h.homeworld_serial != self_serial]
        snap.federated_peers = peers
    except Exception:
        pass

    # Recent IDE chat activity (presence = engaged)
    try:
        trace = _STATE / "ide_stigmergic_trace.jsonl"
        if trace.exists():
            cutoff = time.time() - 600
            n = 0
            with trace.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                        if row.get("ts", 0) >= cutoff:
                            n += 1
                    except Exception:
                        continue
            snap.recent_chat_count = n
    except Exception:
        pass

    return snap


# ──────────────────────────────────────────────────────────────────────
# Concierge proposals — propose, never apply silently
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ConciergeProposal:
    """A suggestion the Concierge wants to make. Owner ratifies via
    ratify_proposal(id). NEVER applied automatically by this module."""
    proposal_id: str
    ts: float
    architect_id: str
    homeworld_serial: str
    title: str                              # short, owner-facing
    rationale: str                          # WHY — must reference the signal
    target_setting: str                     # dotted path, e.g. "amygdala.salience_threshold"
    proposed_value: Any                     # new value to apply on ratification
    current_value: Any = None               # snapshot at proposal time, for audit
    signal_evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5                 # 0..1 — Concierge's own confidence
    reversible: bool = True                 # owner can undo trivially
    expires_ts: float = 0.0                 # 0 = no expiry

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _run_cerebellar_screen(prop: "ConciergeProposal") -> Dict[str, Any]:
    """C47H 2026-04-18: lazy-imported cerebellar pre-flight screen.

    Daughter-safe contract:
      - Always returns a dict, never raises (fail-open: on internal error,
        passed=True with error logged, so the proposal still reaches the
        Architect — silently dropping a proposal is the larger sin).
      - Pure read of InferiorOlive's value table; runs inside a shadow_session
        so no ledger is mutated.
      - Hard-bounded by the cerebellum's own MAX_CALL_BUDGET_MS (250 ms).

    The screen result is suitable for embedding in `signal_evidence`.
    """
    try:
        from System.swarm_cerebellar_mcts import (
            cerebellar_screen,
            MIN_RECOMMENDABLE_V,
            MODULE_VERSION as CEREB_VERSION,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "passed": True,
            "error": f"import_failed:{e!r}",
            "fail_mode": "open",
        }

    state_ctx = _state_context_for(prop)
    try:
        eval_ = cerebellar_screen(state_ctx, [prop.target_setting],
                                  purpose="warp9.concierge.preflight")
    except Exception as e:  # noqa: BLE001
        return {
            "passed": True,
            "error": f"screen_raised:{e!r}",
            "fail_mode": "open",
            "state_context": state_ctx,
        }

    passed = (
        not eval_.refused
        and eval_.recommended_value >= MIN_RECOMMENDABLE_V
    )
    return {
        "passed": passed,
        "state_context": state_ctx,
        "recommended_value": round(eval_.recommended_value, 4),
        "recommended_uncertainty": round(eval_.recommended_uncertainty, 4),
        "min_recommendable_value": MIN_RECOMMENDABLE_V,
        "refused": eval_.refused,
        "refusal_reason": eval_.refusal_reason,
        "simulations_run": eval_.simulations_run,
        "elapsed_ms": eval_.elapsed_ms,
        "shadow_session_id": eval_.shadow_session_id,
        "module_version": CEREB_VERSION,
    }


def propose_setting_change(
    title: str,
    rationale: str,
    target_setting: str,
    proposed_value: Any,
    *,
    current_value: Any = None,
    signal_evidence: Optional[Dict[str, Any]] = None,
    confidence: float = 0.5,
    reversible: bool = True,
    expires_in_s: float = 0.0,
    owner_label: str = "IOAN",
    enable_cerebellar_screen: bool = True,
) -> ConciergeProposal:
    """Write a proposal row. Returns the ConciergeProposal (with id).
    Apply functions live elsewhere — this module only proposes.

    C47H 2026-04-18 — closing-the-loop edit:
      Before the proposal is written to the open inbox, it is run through
      the Cerebellar MCTS (250 ms budget, shadow-sessioned, read-only on
      the Olive). The screen result is always attached to
      ``signal_evidence['cerebellar_screen']`` so the Architect can audit
      the inference. If the screen *fails* (refused or
      ``recommended_value < MIN_RECOMMENDABLE_V``), the proposal is
      diverted to ``warp9_concierge_screened_drops.jsonl`` instead of
      ``warp9_concierge_proposals.jsonl`` — it is *not* lost, it just
      doesn't reach the inbox. The function still returns the
      ``ConciergeProposal`` object so existing callers don't break.

      Pass ``enable_cerebellar_screen=False`` to bypass the screen (used
      by tests that want the raw v2 schema path).
    """
    now = time.time()
    prop = ConciergeProposal(
        proposal_id=uuid.uuid4().hex[:16],
        ts=now,
        architect_id=detect_self_architect_id(default_owner_label=owner_label),
        homeworld_serial=detect_self_homeworld_serial(),
        title=title[:200],
        rationale=rationale[:1000],
        target_setting=target_setting,
        proposed_value=proposed_value,
        current_value=current_value,
        signal_evidence=signal_evidence or {},
        confidence=max(0.0, min(1.0, float(confidence))),
        reversible=reversible,
        expires_ts=(now + expires_in_s) if expires_in_s > 0 else 0.0,
    )

    # ── Cerebellar pre-flight (closing the loop) ───────────────────────
    target_log = _PROPOSALS
    if enable_cerebellar_screen:
        screen = _run_cerebellar_screen(prop)
        prop.signal_evidence["cerebellar_screen"] = screen
        if not screen.get("passed", True):
            target_log = _SCREENED_DROPS

    target_log.parent.mkdir(parents=True, exist_ok=True)
    with target_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(prop.to_dict(), ensure_ascii=False) + "\n")
    return prop


def list_screened_drops(*, limit: int = 50) -> List[Dict[str, Any]]:
    """C47H 2026-04-18: most recent cerebellum-rejected proposals (audit only).
    These never appear in `list_open_proposals`. Returns raw dicts (not
    ConciergeProposal) because the screen-result block is the interesting
    payload here, and we want to preserve forward-compat with future fields.
    """
    if not _SCREENED_DROPS.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with _SCREENED_DROPS.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    out.sort(key=lambda r: r.get("ts", 0.0), reverse=True)
    return out[:limit]


def list_open_proposals(*, owner_label: str = "IOAN", limit: int = 50) -> List[ConciergeProposal]:
    """All proposals not yet ratified, rejected, or expired. Most recent first."""
    if not _PROPOSALS.exists():
        return []
    decided_ids = _ratified_ids() | _rejected_ids()
    out: List[ConciergeProposal] = []
    now = time.time()
    try:
        with _PROPOSALS.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    prop = ConciergeProposal(**row)
                except Exception:
                    continue
                if prop.proposal_id in decided_ids:
                    continue
                if prop.expires_ts and prop.expires_ts < now:
                    continue
                out.append(prop)
    except OSError:
        return []
    out.sort(key=lambda p: p.ts, reverse=True)
    return out[:limit]


def _rejected_ids() -> set:
    if not _REJECTED.exists():
        return set()
    ids = set()
    try:
        with _REJECTED.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    pid = row.get("proposal_id")
                    if pid:
                        ids.add(pid)
                except Exception:
                    continue
    except OSError:
        pass
    return ids


def _ratified_ids() -> set:
    if not _RATIFIED.exists():
        return set()
    ids = set()
    try:
        with _RATIFIED.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    pid = row.get("proposal_id")
                    if pid:
                        ids.add(pid)
                except Exception:
                    continue
    except OSError:
        pass
    return ids


def _find_proposal_anywhere(
    proposal_id: str,
    owner_label: str,
) -> Optional[ConciergeProposal]:
    """C47H 2026-04-18: locate a proposal by id across the open inbox AND
    the cerebellar-drops ledger.

    The cerebellar pre-flight diverts proposals whose effective Olive value
    is below ``MIN_RECOMMENDABLE_V`` to ``warp9_concierge_screened_drops.jsonl``
    instead of the open inbox. Drops are audit-only by default — they don't
    appear in ``list_open_proposals``. But the Architect must always retain
    final authority: if they explicitly look up a screened-drop id (via
    ``list_screened_drops``) and decide to ratify or reject it anyway, that
    must work. Otherwise the cerebellum becomes an unaccountable veto over
    the Architect's intent, which is a hard violation of the daughter-safe
    contract.
    """
    for prop in list_open_proposals(owner_label=owner_label, limit=10000):
        if prop.proposal_id == proposal_id:
            return prop
    if _SCREENED_DROPS.exists():
        try:
            with _SCREENED_DROPS.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("proposal_id") != proposal_id:
                        continue
                    try:
                        return ConciergeProposal(**row)
                    except Exception:  # noqa: BLE001
                        continue
        except OSError:
            return None
    return None


def ratify_proposal(
    proposal_id: str,
    *,
    apply_like_this_in_future: bool = False,
    owner_label: str = "IOAN",
    note: str = "",
) -> Optional[Dict[str, Any]]:
    """Owner-side ratification. Writes to the ratified ledger. The actual
    setting application is the responsibility of the target module —
    this function returns the proposal payload so callers can dispatch.

    Returns the ratification record (with the original proposal embedded)
    or None if the proposal id was not found.

    C47H 2026-04-18: also resolves cerebellar-screened drops so the
    Architect can override the screen.
    """
    target = _find_proposal_anywhere(proposal_id, owner_label)
    if target is None:
        return None

    now = time.time()
    record = {
        "proposal_id": target.proposal_id,
        "ratified_ts": now,
        "timestamp": now,                           # alias for downstream learners
        "schema_version": SCHEMA_VERSION,
        "architect_id": detect_self_architect_id(default_owner_label=owner_label),
        "apply_like_this_in_future": bool(apply_like_this_in_future),
        "note": note[:500],
        # Flat reinforcement-learning keys (additive — does not replace 'proposal').
        "state_context": _state_context_for(target),
        "action_kind": target.target_setting,
        "reward": +1.0,
        # Original proposal payload preserved untouched for audit.
        "proposal": target.to_dict(),
    }
    try:
        _RATIFIED.parent.mkdir(parents=True, exist_ok=True)
        with _RATIFIED.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return record


def reject_proposal(
    proposal_id: str,
    *,
    owner_label: str = "IOAN",
    reason: str = "",
    suppress_like_this_in_future: bool = False,
) -> Optional[Dict[str, Any]]:
    """Owner-side rejection. Mirror of ratify_proposal: writes a -1.0 reward
    row to warp9_concierge_rejected.jsonl so the prediction cache can learn
    what the Architect said NO to, not just what they ignored.

    `suppress_like_this_in_future=True` is the strong form: the system is
    allowed to silently suppress identically-shaped proposals. Off by default
    so a single 'no' doesn't permanently silence a class of useful proposals.

    C47H 2026-04-18: also resolves cerebellar-screened drops so the
    Architect can override the screen.
    """
    target = _find_proposal_anywhere(proposal_id, owner_label)
    if target is None:
        return None

    now = time.time()
    record = {
        "proposal_id": target.proposal_id,
        "rejected_ts": now,
        "timestamp": now,
        "schema_version": SCHEMA_VERSION,
        "architect_id": detect_self_architect_id(default_owner_label=owner_label),
        "suppress_like_this_in_future": bool(suppress_like_this_in_future),
        "reason": reason[:500],
        "state_context": _state_context_for(target),
        "action_kind": target.target_setting,
        "reward": -1.0,
        "proposal": target.to_dict(),
    }
    try:
        _REJECTED.parent.mkdir(parents=True, exist_ok=True)
        with _REJECTED.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return record


def list_recent_rejections(*, since_ts: float = 0.0, limit: int = 100) -> List[Dict[str, Any]]:
    """Tail the rejected ledger. Used by the Concierge to avoid re-proposing
    the same shape and by entropy_guard / prediction_cache for learning."""
    if not _REJECTED.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with _REJECTED.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("timestamp", row.get("rejected_ts", 0)) < since_ts:
                    continue
                out.append(row)
    except OSError:
        return []
    return out[-limit:]


# ──────────────────────────────────────────────────────────────────────
# warp9_status() — one-call dashboard for the umbrella
# ──────────────────────────────────────────────────────────────────────

def warp9_status(owner_label: str = "IOAN") -> Dict[str, Any]:
    """Return a compact status blob for dashboards / CLI / external tools."""
    owner = get_or_create_owner(owner_label)
    homeworlds = list_owner_homeworlds(owner.key)
    snap = snapshot_owner_behavior(owner_label)
    devices = list_devices_for_homeworld(snap.homeworld_serial)
    open_props = list_open_proposals(owner_label=owner_label)
    return {
        "module_version": MODULE_VERSION,
        "ts": time.time(),
        "owner_label": owner.label,
        "owner_key": owner.key,
        "self_homeworld_serial": snap.homeworld_serial,
        "self_architect_id": snap.architect_id,
        "federation_enabled": FEDERATION_ENABLED,
        "homeworlds_known": [
            {"serial": h.homeworld_serial, "label": h.machine_label,
             "architect": h.architect_id, "role": h.role,
             "capabilities": h.capabilities}
            for h in homeworlds
        ],
        "devices_on_self": [
            {"id": d.device_id, "nickname": d.nickname, "vendor": d.vendor,
             "capabilities": [k for k, v in d.capabilities.items() if v]}
            for d in devices
        ],
        "behavior_snapshot": snap.to_dict(),
        "open_proposals": [
            {"id": p.proposal_id, "title": p.title, "target": p.target_setting,
             "proposed": p.proposed_value, "confidence": p.confidence}
            for p in open_props
        ],
        "spool_pairs": list_spool_pairs(),
    }


if __name__ == "__main__":
    print("=" * 72)
    print("WARP 9 — full-status dump")
    print("=" * 72)
    status = warp9_status()
    print(json.dumps(status, indent=2, default=str))

    # Demonstrate the Concierge end-to-end: snapshot -> propose -> list -> ratify
    print("\n[C47H-SMOKE-WARP9] Concierge propose/ratify cycle:")
    snap = snapshot_owner_behavior()
    if snap.oxt_level is not None and snap.oxt_level >= 0.6:
        prop = propose_setting_change(
            title="Lower amygdala salience threshold while OXT is high",
            rationale=(
                f"OXT={snap.oxt_level:.3f} indicates strong owner bond and low "
                f"adversarial environment. Proposing to relax salience filter "
                f"so subtle Architect signals get more attention."
            ),
            target_setting="amygdala.salience_threshold",
            proposed_value=0.35,
            current_value=0.50,
            signal_evidence={"oxt_level": snap.oxt_level,
                             "recent_chat_count": snap.recent_chat_count},
            confidence=0.65,
            expires_in_s=24 * 3600,
        )
        print(f"  proposed: {prop.proposal_id} title={prop.title!r}")
    else:
        print("  no proposal triggered (OXT not in target range)")

    open_props = list_open_proposals()
    print(f"  open proposals: {len(open_props)}")
    if open_props:
        first = open_props[0]
        print(f"  first open: {first.proposal_id} title={first.title!r}")
        # In production the owner ratifies via UI/CLI. Smoke just confirms the path.
        rec = ratify_proposal(first.proposal_id, note="smoke ratification")
        print(f"  ratified: {first.proposal_id} -> apply_like_future={rec['apply_like_this_in_future'] if rec else None}")

    print("[C47H-SMOKE-WARP9 OK]")
