#!/usr/bin/env python3
"""
swarm_interaction_borg.py — Mehr-axis BORG for silicon coordination (small slice)

Physical robots solve Nash games in clutter; SIFTA solves truth + memory + credit
on the stigmergic field. This module wires the five minimal adopts from
Documents/MEHR_ROBOTICS_INTERACTIVE_AUTONOMY_SIFTA_AXIS.md:

  1. interaction_mode on memory rows (yield / fiction / locale / dyad)
  2. Learn from George+Alice interaction demos (not monologue-only)
  3. Hippocampus coach — hard task → sub-skills + pytest checklist
  4. Credit assignment — STGM per doctor (economic_attribution_key)
  5. Explicitly NO Nash solver for Talk (policy constant only)
"""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_REPO = Path(__file__).resolve().parent.parent

# Policy: Talk path must not spawn game-theoretic motion planners.
NASH_SOLVER_FOR_TALK = False
BORG_TRUTH_LABEL = "SWARM_INTERACTION_BORG_V1"

INTERACTION_MODES = frozenset({
    "NEUTRAL",
    "YIELD_LEFT",
    "YIELD_RIGHT",
    "FICTION_COWATCH",
    "LOCALE_SG_PASS_LEFT",
    "LOCALE_US_PASS_RIGHT",
    "DYAD_GEORGE_ALICE",
    "OWNER_BODY_MAINTENANCE",
})

_FICTION_CTX = ("fiction", "cowatch", "media", "tv", "movie", "youtube", "show")
_OWNER_CTX = ("owner_body", "restroom", "maintenance", "hygiene", "pacemaker")
_DYAD_CTX = ("talk_to_alice", "alice_talk", "dyad", "george_alice")


def infer_interaction_mode(text: str, *, app_context: str = "") -> str:
    """Map utterance + app context to a stable interaction convention bit."""
    low = (text or "").lower()
    ctx = (app_context or "").lower()

    if any(k in ctx for k in _FICTION_CTX) or any(
        k in low for k in ("cowatch", "youtube", "on tv", "in the movie", "the show said")
    ):
        return "FICTION_COWATCH"
    if any(k in ctx for k in _OWNER_CTX) or any(
        k in low for k in ("restroom", "bathroom break", "owner body", "i need the toilet")
    ):
        return "OWNER_BODY_MAINTENANCE"
    if "yield left" in low or "pass on the left" in low or "keep left" in low:
        return "YIELD_LEFT"
    if "yield right" in low or "pass on the right" in low or "keep right" in low:
        return "YIELD_RIGHT"
    if "singapore" in low and ("left" in low or "pass" in low):
        return "LOCALE_SG_PASS_LEFT"
    if any(k in low for k in ("us driving", "america", "california")) and "right" in low:
        return "LOCALE_US_PASS_RIGHT"
    if any(k in ctx for k in _DYAD_CTX):
        return "DYAD_GEORGE_ALICE"
    if any(k in low for k in ("george", "alice")) and "?" in low:
        return "DYAD_GEORGE_ALICE"
    return "NEUTRAL"


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    d = state_dir or (_REPO / ".sifta_state")
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _memory_bus_state(state_dir: Optional[Path]) -> Iterator[None]:
    """Temporarily redirect memory-bus ledgers for isolated tests/probes."""
    if state_dir is None:
        yield
        return

    state = _state_dir(Path(state_dir))

    import System.stigmergic_memory_bus as memory_bus

    old_paths = (
        memory_bus.LEDGER_DIR,
        memory_bus.LEDGER_FILE,
        memory_bus.STGM_LOG_FILE,
        memory_bus.MEMORY_EPISTEMOLOGY_AUDIT,
    )
    memory_bus.LEDGER_DIR = state
    memory_bus.LEDGER_FILE = state / "memory_ledger.jsonl"
    memory_bus.STGM_LOG_FILE = state / "stgm_memory_rewards.jsonl"
    memory_bus.MEMORY_EPISTEMOLOGY_AUDIT = state / "memory_epistemology_audit.jsonl"

    try:
        import System.proof_of_useful_work as proof

        old_issue_work_receipt = proof.issue_work_receipt
        proof.issue_work_receipt = lambda *args, **kwargs: None
    except Exception:
        proof = None
        old_issue_work_receipt = None

    try:
        yield
    finally:
        (
            memory_bus.LEDGER_DIR,
            memory_bus.LEDGER_FILE,
            memory_bus.STGM_LOG_FILE,
            memory_bus.MEMORY_EPISTEMOLOGY_AUDIT,
        ) = old_paths
        if proof is not None and old_issue_work_receipt is not None:
            proof.issue_work_receipt = old_issue_work_receipt


def remember_interaction_turn(
    text: str,
    *,
    architect_id: str = "IOAN_M5",
    app_context: str = "talk_to_alice",
    role: str = "user",
    stt_confidence: float = 0.0,
    alice_model: str = "",
    epistemic_label: Optional[str] = None,
    links: Optional[List[str]] = None,
    interaction_mode: Optional[str] = None,
    force: bool = False,
    state_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Store a George+Alice (or high-value) turn on the memory bus — not monologue-only.

    Skips phatic noise unless force=True. Returns receipt dict or None if skipped.
    """
    from System.swarm_interaction_importance import classify_interaction_importance
    from System.stigmergic_memory_bus import StigmergicMemoryBus

    classification = classify_interaction_importance(
        text,
        role=role,
        stt_confidence=stt_confidence,
        model=alice_model,
    )
    mode = interaction_mode or infer_interaction_mode(text, app_context=app_context)
    band = str(classification.get("importance_band") or "low")
    if not force and band in ("noise", "low") and mode not in {
        "FICTION_COWATCH",
        "OWNER_BODY_MAINTENANCE",
    }:
        return None

    if band in ("critical", "high") and mode == "NEUTRAL" and role in ("user", "alice"):
        mode = "DYAD_GEORGE_ALICE"

    label = epistemic_label
    if label is None and mode == "FICTION_COWATCH":
        label = "FICTION"

    with _memory_bus_state(state_dir):
        bus = StigmergicMemoryBus(architect_id=architect_id)
        trace = bus.remember(
            text,
            app_context,
            epistemic_label=label,
            links=links or [],
            interaction_mode=mode,
        )

    receipt = {
        "truth_label": BORG_TRUTH_LABEL,
        "ts": time.time(),
        "trace_id": trace.trace_id,
        "interaction_mode": trace.interaction_mode,
        "epistemic_label": trace.epistemic_label,
        "importance_band": band,
        "role": role,
        "app_context": app_context,
        "text_preview": (text or "")[:120],
    }
    path = _state_dir(state_dir) / "borg_interaction_receipts.jsonl"
    from System.jsonl_file_lock import append_line_locked  # noqa: PLC0415

    append_line_locked(path, json.dumps(receipt) + "\n", encoding="utf-8")
    return receipt


def deposit_talk_interaction_turn(
    text: str,
    *,
    conf: float = 0.0,
    app_context: Optional[str] = None,
    alice_model: str = "",
    state_dir: Optional[Path] = None,
) -> bool:
    """PyQt6-free canonical entry point for Talk-surface interaction deposits.

    This is the function the real widget calls (thin non-fatal wrapper) and
    the wire tests call directly. It owns the early guard, focus context
    resolution, and the call into remember_interaction_turn under isolation
    when state_dir is supplied.

    Returns True only on successful high-band deposit.
    Never raises — Talk turns must not be lost to memory wiring.
    """
    stripped = (text or "").strip()
    if len(stripped) <= 8 or float(conf or 0.0) <= 0.35:
        return False

    final_context = app_context or "talk_to_alice"
    if app_context is None:
        try:
            from System.swarm_app_focus import get_focus_context

            focus = get_focus_context()
            if focus and isinstance(focus, dict):
                final_context = str(
                    focus.get("app_name") or focus.get("app") or "talk_to_alice"
                ).strip().lower().replace(" ", "_") or "talk_to_alice"
        except Exception:
            pass

    try:
        receipt = remember_interaction_turn(
            stripped,
            architect_id="IOAN_M5",
            app_context=final_context,
            role="user",
            stt_confidence=float(conf or 0.0),
            alice_model=alice_model or "",
            state_dir=state_dir,
        )
        return receipt is not None
    except Exception:
        return False


def credit_assign_doctor(
    *,
    organ_id: str,
    trace_id: str,
    source_ledger: str,
    tick_id: Any,
    amount_stgm: float,
    reason: str,
    doctor_label: str = "",
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Per-doctor STGM credit — no blended blame across IDE bodies."""
    from System.stgm_economy import make_economic_attribution_key

    key = make_economic_attribution_key(
        organ_id=organ_id,
        trace_id=trace_id,
        source_ledger=source_ledger,
        tick_id=tick_id,
    )
    row = {
        "truth_label": BORG_TRUTH_LABEL,
        "ts": time.time(),
        "economic_attribution_key": key,
        "organ_id": organ_id,
        "trace_id": trace_id,
        "source_ledger": source_ledger,
        "tick_id": tick_id,
        "amount_stgm": round(float(amount_stgm), 6),
        "reason": reason,
        "doctor_label": doctor_label or organ_id,
        "nash_solver_for_talk": NASH_SOLVER_FOR_TALK,
    }
    path = _state_dir(state_dir) / "borg_credit_attribution.jsonl"
    from System.jsonl_file_lock import append_line_locked  # noqa: PLC0415

    append_line_locked(path, json.dumps(row) + "\n", encoding="utf-8")
    return row


def coach_decompose_task(
    parent_task: str,
    sub_skills: List[Dict[str, Any]],
    *,
    coach_id: str = "hippocampus_coach",
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Hippocampus-as-coach: break a hard task into sub-skills each with a pytest hook.

    sub_skills items: {"name": str, "pytest_target": str, "done": bool (optional)}
    """
    normalized = []
    for item in sub_skills:
        normalized.append({
            "name": str(item.get("name") or "unnamed"),
            "pytest_target": str(item.get("pytest_target") or ""),
            "done": bool(item.get("done", False)),
        })

    plan_id = hashlib.sha256(
        f"{parent_task}:{time.time()}".encode("utf-8")
    ).hexdigest()[:12]

    row = {
        "truth_label": BORG_TRUTH_LABEL,
        "ts": time.time(),
        "plan_id": plan_id,
        "coach_id": coach_id,
        "parent_task": parent_task,
        "sub_skills": normalized,
        "pytest_gate": "all sub_skills pass before parent_task closed",
    }
    path = _state_dir(state_dir) / "hippocampus_coach_tasks.jsonl"
    from System.jsonl_file_lock import append_line_locked  # noqa: PLC0415

    append_line_locked(path, json.dumps(row) + "\n", encoding="utf-8")
    return row


def talk_coordination_policy() -> Dict[str, Any]:
    """Receipt that Talk uses stigmergy + memory modes, not Nash motion planning."""
    return {
        "truth_label": BORG_TRUTH_LABEL,
        "nash_solver_for_talk": NASH_SOLVER_FOR_TALK,
        "coordination": "stigmergic_memory_bus + interaction_mode + per_doctor_credit",
        "physical_frontier": "orthogonal (Mehr/ICON) — not duplicated here",
    }
