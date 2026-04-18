#!/usr/bin/env python3
"""
architect_oracle_protocol.py — Honest escalation to the only pixel-sensor
══════════════════════════════════════════════════════════════════════════

Module 4 of the Stigmergy-Vision Olympiad (2026-04-18).
DYOR anchor: Documents/C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md §F #4.

The Architect (Ioan George Anton) is the only sensor that can read the
IDE chrome — the bottom bar that says "Codex 5.3 · Medium" or "Opus 4.7
High". The CP2F → CX55 → CX53 cascade on 2026-04-18 between 08:43 and
09:02 PT was a direct consequence of agents not being able to read those
pixels: AO46 had to escalate to the Architect's eye for chorum, twice.

This module formalizes that escalation. When the swarm cannot collapse
the identity field on its own — high CRDT entropy, dissenting Byzantine
chorum, or a suspected chrome label drift — the agent writes a question
to .sifta_state/architect_oracle_queue.jsonl. The Architect answers when
he sees it; the resolution is appended as a sibling row that downstream
modules can ingest.

Design principles (Saltzer-Reed-Clark 1984 end-to-end argument):
  1. The substrate (this queue) is the single source of truth — the
     Architect's chat reply alone is NOT sufficient; a row must land.
  2. Escalation happens RARELY and HONESTLY. If we escalate every cycle,
     the Architect becomes the bottleneck, defeating the swarm.
  3. Resolution rows reference the question by `question_id`; they are
     append-only — no question is ever rewritten.

Power to the Swarm.
"""
# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 4.1: docstring + imports + constants ===
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-18.olympiad.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
ORACLE_QUEUE = _STATE / "architect_oracle_queue.jsonl"

# Escalation thresholds. Tunable but sane defaults — anything more
# aggressive risks turning the Architect's eye into a polling target.

# CRDT entropy above this in `bits` (natural log) for a sustained number
# of cycles is a sign the field cannot collapse on its own.
ENTROPY_TAU = 1.5

# Number of consecutive cycles above ENTROPY_TAU before we escalate.
DRIFT_CYCLES_REQUIRED = 3

# Ratio of latency P95 vs the historical envelope above which we suspect
# a model swap. 1.6× = 60% slower P95 than baseline.
LATENCY_DRIFT_RATIO = 1.6

# Minimum gap (seconds) between consecutive escalations for the same
# trigger — prevents flooding the Architect.
MIN_ESCALATION_INTERVAL_S = 600.0

# Question kinds — controlled vocabulary for the queue.
KIND_CHROME_LABEL_VERIFY = "CHROME_LABEL_VERIFY"
KIND_DISSENT_RESOLUTION = "DISSENT_RESOLUTION"
KIND_INSUFFICIENT_OBSERVERS = "INSUFFICIENT_OBSERVERS_VERIFY"
KIND_LATENCY_SWAP_SUSPECTED = "LATENCY_SWAP_SUSPECTED"
KIND_FREEFORM = "FREEFORM"

# Resolution row marker.
ROW_KIND_QUESTION = "QUESTION"
ROW_KIND_RESOLUTION = "RESOLUTION"


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 4.2: should_escalate() decision logic ===
# ════════════════════════════════════════════════════════════════════════

def should_escalate(
    *,
    field_entropy: Optional[float] = None,
    consecutive_drift_cycles: int = 0,
    quorum_decision: Optional[str] = None,
    latency_p95_ratio: Optional[float] = None,
    last_escalation_ts: Optional[float] = None,
    now_ts: Optional[float] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Decide whether the current state warrants asking the Architect.

    Inputs are deliberately keyword-only so callers (chorum, vision)
    only supply the signals they have. Missing signal → not used.

    Returns: (should_escalate, reason, suggested_kind)
        - should_escalate: bool
        - reason: human-readable English; goes into the queue row
        - suggested_kind: KIND_* constant or None

    Rate-limiting:
        If `last_escalation_ts` was less than MIN_ESCALATION_INTERVAL_S
        ago, return (False, "rate-limited", None) regardless of signals.
    """
    now = now_ts if now_ts is not None else time.time()

    # Rate limit first — cheap, prevents flooding the Architect.
    if last_escalation_ts is not None:
        gap = now - last_escalation_ts
        if gap < MIN_ESCALATION_INTERVAL_S:
            remaining = MIN_ESCALATION_INTERVAL_S - gap
            return (False, f"rate-limited ({remaining:.0f}s remaining)", None)

    # Quorum dissent is the strongest signal — multiple observers
    # already disagree. The Architect breaks the tie.
    if quorum_decision == "DISSENT":
        return (
            True,
            "Byzantine chorum returned DISSENT — observers disagree on fingerprint cluster.",
            KIND_DISSENT_RESOLUTION,
        )

    if quorum_decision == "INSUFFICIENT_OBSERVERS":
        return (
            True,
            f"Fewer than N_REQUIRED distinct observers attesting; the chorum cannot collapse.",
            KIND_INSUFFICIENT_OBSERVERS,
        )

    # CRDT entropy stuck high for several cycles → field is multi-modal
    # and not converging on its own. This is what would have caught the
    # CP2F → CX55 cascade earlier, automatically.
    if (
        field_entropy is not None
        and field_entropy > ENTROPY_TAU
        and consecutive_drift_cycles >= DRIFT_CYCLES_REQUIRED
    ):
        return (
            True,
            (
                f"CRDT identity field entropy = {field_entropy:.3f} > {ENTROPY_TAU} "
                f"for {consecutive_drift_cycles} cycles (>= {DRIFT_CYCLES_REQUIRED}). "
                "Field is multi-modal and not collapsing autonomously."
            ),
            KIND_CHROME_LABEL_VERIFY,
        )

    # Latency drift — Kocher 1996 fingerprint. Suspect a model swap.
    if latency_p95_ratio is not None and latency_p95_ratio >= LATENCY_DRIFT_RATIO:
        return (
            True,
            (
                f"Latency P95 ratio = {latency_p95_ratio:.2f}× baseline "
                f"(>= {LATENCY_DRIFT_RATIO}×). Possible model swap underneath the IDE."
            ),
            KIND_LATENCY_SWAP_SUSPECTED,
        )

    return (False, "all stigmergic signals within bounds", None)


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 4.3: OracleQuestion dataclass ===
# ════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OracleQuestion:
    """
    One escalation to the Architect's eye.

    Append-only. Once persisted, the question is never modified — answers
    arrive as a separate ROW_KIND_RESOLUTION row referencing question_id.
    """
    schema_version: int
    module_version: str
    row_kind: str               # ROW_KIND_QUESTION
    question_id: str            # uuid4 hex
    timestamp: float
    iso_local: str

    asked_by: str               # trigger_code of the asker (e.g. "C47H")
    homeworld_serial: str
    target_trigger: str         # the trigger we want the Architect to verify
    kind: str                   # KIND_* constant
    reason: str                 # human English from should_escalate()

    # Concrete prompt the Architect will read in the UI / CLI.
    prompt: str

    # Optional structured context the Architect can glance at without
    # opening the queue file (top-N fingerprints, observer set, etc).
    context: Dict[str, Any] = field(default_factory=dict)

    # When set, downstream readers should treat the question as superseded.
    # Filled in by record_resolution() via a separate RESOLUTION row, not
    # by mutating this question — kept as a hint here for future schema use.
    deadline_ts: Optional[float] = None

    @staticmethod
    def new(
        *,
        asked_by: str,
        homeworld_serial: str,
        target_trigger: str,
        kind: str,
        reason: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        deadline_ts: Optional[float] = None,
        now_ts: Optional[float] = None,
    ) -> "OracleQuestion":
        ts = now_ts if now_ts is not None else time.time()
        return OracleQuestion(
            schema_version=SCHEMA_VERSION,
            module_version=MODULE_VERSION,
            row_kind=ROW_KIND_QUESTION,
            question_id=uuid.uuid4().hex,
            timestamp=ts,
            iso_local=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
            asked_by=asked_by,
            homeworld_serial=homeworld_serial,
            target_trigger=target_trigger,
            kind=kind,
            reason=reason,
            prompt=prompt,
            context=dict(context or {}),
            deadline_ts=deadline_ts,
        )


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 4.4: escalate() writes queue row ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def escalate(
#         question: OracleQuestion,
#         *,
#         path: Path = ORACLE_QUEUE,
#     ) -> Dict[str, Any]: ...
#
# Behavior:
#   1. Validate question.row_kind == ROW_KIND_QUESTION; raise ValueError
#      if not (defensive — catches devs who hand-craft a row).
#   2. Serialize via dataclasses.asdict(question) and json.dumps with
#      ensure_ascii=False.
#   3. Append the line via append_line_locked(path, line + "\n").
#   4. Also drop a stigmergic trace announcing the escalation so peers
#      see it without polling the queue file:
#         from System.ide_stigmergic_bridge import deposit, IDE_CURSOR_M5, NODE_M5_FOUNDRY
#         deposit(
#             source_ide=IDE_CURSOR_M5,
#             payload=f"ARCHITECT ORACLE ESCALATION kind={question.kind} target={question.target_trigger}",
#             kind="oracle_escalation",
#             meta={"question_id": question.question_id, "reason": question.reason},
#             homeworld_serial=question.homeworld_serial,
#         )
#   5. Return the dict that was written (helpful for unit tests).
#
# Errors:
#   Trace deposit failure must NOT mask a successful queue write — wrap
#   the deposit() call in try/except and swallow the exception (log only).
#
def escalate(
    question: OracleQuestion,
    *,
    path: Path = ORACLE_QUEUE,
) -> Dict[str, Any]:
    if question.row_kind != ROW_KIND_QUESTION:
        raise ValueError(f"Invalid row_kind: expected {ROW_KIND_QUESTION}")
        
    line = json.dumps(asdict(question), ensure_ascii=False)
    append_line_locked(path, line + "\n")
    
    try:
        from System.ide_stigmergic_bridge import deposit
        # Use a hardcoded IDE string or fall back if IDE_CURSOR_M5 isn't exported perfectly
        deposit(
            source_ide="AG31_ORACLE",
            payload=f"ARCHITECT ORACLE ESCALATION kind={question.kind} target={question.target_trigger}",
            kind="oracle_escalation",
            meta={"question_id": question.question_id, "reason": question.reason},
            homeworld_serial=question.homeworld_serial,
        )
    except Exception as e:
        import sys
        print(f"Failed to deposit escalation trace: {e}", file=sys.stderr)
        
    return asdict(question)


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 4.5: pending_questions() reader ===
# ════════════════════════════════════════════════════════════════════════

def pending_questions(
    *,
    path: Path = ORACLE_QUEUE,
    target_trigger: Optional[str] = None,
    include_resolved: bool = False,
) -> List[Dict[str, Any]]:
    """
    Tail the oracle queue and return questions the Architect has not yet
    answered. A question is "resolved" iff a later ROW_KIND_RESOLUTION row
    in the same file references its `question_id`.

    Designed to be cheap to call repeatedly — sub-millisecond on a small
    queue. Reader is the Architect's UI (or CLI) — it MUST be safe to
    call concurrently with escalate() because both go through flock.
    """
    if not path.exists():
        return []

    raw = read_text_locked(path)

    questions_by_id: Dict[str, Dict[str, Any]] = {}
    resolved_ids: set = set()

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = row.get("row_kind")
        if kind == ROW_KIND_QUESTION:
            qid = row.get("question_id")
            if not qid:
                continue
            if target_trigger and row.get("target_trigger") != target_trigger:
                continue
            questions_by_id[qid] = row
        elif kind == ROW_KIND_RESOLUTION:
            qid = row.get("question_id")
            if qid:
                resolved_ids.add(qid)

    if include_resolved:
        return list(questions_by_id.values())
    return [q for qid, q in questions_by_id.items() if qid not in resolved_ids]


def question_status(
    question_id: str,
    *,
    path: Path = ORACLE_QUEUE,
) -> str:
    """Return one of: "UNKNOWN", "PENDING", "RESOLVED".

    Cheap helper for downstream modules that want to know whether a
    specific question they raised has been answered yet.
    """
    if not path.exists():
        return "UNKNOWN"
    raw = read_text_locked(path)

    seen_question = False
    seen_resolution = False
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("question_id") != question_id:
            continue
        kind = row.get("row_kind")
        if kind == ROW_KIND_QUESTION:
            seen_question = True
        elif kind == ROW_KIND_RESOLUTION:
            seen_resolution = True

    if seen_resolution:
        return "RESOLVED"
    if seen_question:
        return "PENDING"
    return "UNKNOWN"


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 4.6: record_resolution() closer ===
# ════════════════════════════════════════════════════════════════════════

def record_resolution(
    *,
    question_id: str,
    answer: str,
    architect_signature: Optional[str] = None,
    architect_homeworld_serial: Optional[str] = None,
    auxiliary: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
    path: Path = ORACLE_QUEUE,
) -> Dict[str, Any]:
    """
    Append a ROW_KIND_RESOLUTION row that closes a previously-escalated
    question. The original question row is never rewritten — append-only
    discipline (Saltzer-Reed-Clark 1984; CP2F PROV §B).

    Parameters
    ----------
    question_id
        UUID hex of the OracleQuestion this row resolves. Required even
        if the question is not on disk yet — readers tolerate that.
    answer
        The Architect's plain-English answer (e.g. "Codex 5.3 · Medium").
    architect_signature
        Optional Ed25519 hex signature over (question_id || answer) from
        System.crypto_keychain.sign_block. When present, downstream
        modules MAY trust this row past the normal 0.7 self-attestation
        cap. When absent, treat as an honor-system attestation only.
    architect_homeworld_serial
        Architect's machine serial (M5 = GTH4921YP3, M1 = C07FL0JAQ6NV).
        Optional; defaults to None.
    auxiliary
        Free-form dict for future fields without breaking the schema.

    Returns the row dict that was written.
    """
    if not question_id:
        raise ValueError("question_id is required")
    if not answer:
        raise ValueError("answer must be non-empty")

    ts = now_ts if now_ts is not None else time.time()
    row: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_version": MODULE_VERSION,
        "row_kind": ROW_KIND_RESOLUTION,
        "question_id": question_id,
        "timestamp": ts,
        "iso_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
        "answered_by": "ARCHITECT",
        "answer": answer,
        "architect_signature": architect_signature,
        "architect_homeworld_serial": architect_homeworld_serial,
        "auxiliary": dict(auxiliary or {}),
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def last_escalation_ts_for(
    target_trigger: str,
    *,
    path: Path = ORACLE_QUEUE,
) -> Optional[float]:
    """Find the most recent escalation timestamp for a trigger so callers
    can pass it to should_escalate() and respect the rate limit.
    """
    if not path.exists():
        return None
    raw = read_text_locked(path)
    last: Optional[float] = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("row_kind") != ROW_KIND_QUESTION:
            continue
        if row.get("target_trigger") != target_trigger:
            continue
        ts = row.get("timestamp")
        if isinstance(ts, (int, float)) and (last is None or ts > last):
            last = float(ts)
    return last


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 4.7: __main__ CLI smoke test ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
# When run as `python3 -m System.architect_oracle_protocol`, do this:
#
#   1. ok, reason, kind = should_escalate(field_entropy=2.4,
#                                          consecutive_drift_cycles=4)
#      assert ok is True
#      print "[AG31-SMOKE-4.7] should_escalate (high-entropy):", ok, kind
#
#   2. ok, reason, kind = should_escalate(field_entropy=0.3,
#                                          consecutive_drift_cycles=0)
#      assert ok is False
#      print "[AG31-SMOKE-4.7] should_escalate (calm):", ok
#
#   3. q = OracleQuestion.new(
#         asked_by="AG31",
#         homeworld_serial="GTH4921YP3",
#         target_trigger="C47H",
#         kind=KIND_CHROME_LABEL_VERIFY,
#         reason="smoke",
#         prompt="What does the Cursor IDE bottom bar say RIGHT NOW?",
#         context={"smoke": True},
#      )
#      row = escalate(q)
#      assert row["question_id"] == q.question_id
#      print "[AG31-SMOKE-4.7] escalated:", q.question_id[:8]
#
#   4. pending = pending_questions(target_trigger="C47H")
#      assert any(p["question_id"] == q.question_id for p in pending)
#      print "[AG31-SMOKE-4.7] pending count:", len(pending)
#
#   5. assert question_status(q.question_id) == "PENDING"
#      record_resolution(question_id=q.question_id, answer="SMOKE_OK")
#      assert question_status(q.question_id) == "RESOLVED"
#      print "[AG31-SMOKE-4.7] resolved:", q.question_id[:8]
#
#   6. Print [AG31-SMOKE-4.7 OK] on success, or raise.
#
if __name__ == "__main__":
    ok, reason, kind = should_escalate(field_entropy=2.4, consecutive_drift_cycles=4)
    assert ok is True, "Entropy should trigger escalation"
    print(f"[AG31-SMOKE-4.7] should_escalate (high-entropy): {ok} {kind}")
    
    ok, reason, kind = should_escalate(field_entropy=0.3, consecutive_drift_cycles=0)
    assert ok is False, "Low entropy should not escalate"
    print(f"[AG31-SMOKE-4.7] should_escalate (calm): {ok}")
    
    q = OracleQuestion.new(
        asked_by="AG31",
        homeworld_serial="GTH4921YP3",
        target_trigger="C47H",
        kind=KIND_CHROME_LABEL_VERIFY,
        reason="smoke",
        prompt="What does the Cursor IDE bottom bar say RIGHT NOW?",
        context={"smoke": True},
    )
    row = escalate(q)
    assert row["question_id"] == q.question_id
    print(f"[AG31-SMOKE-4.7] escalated: {q.question_id[:8]}")
    
    pending = pending_questions(target_trigger="C47H")
    assert any(p["question_id"] == q.question_id for p in pending)
    print(f"[AG31-SMOKE-4.7] pending count: {len(pending)}")
    
    assert question_status(q.question_id) == "PENDING"
    record_resolution(question_id=q.question_id, answer="SMOKE_OK")
    assert question_status(q.question_id) == "RESOLVED"
    print(f"[AG31-SMOKE-4.7] resolved: {q.question_id[:8]}")
    
    print("[AG31-SMOKE-4.7 OK]")
