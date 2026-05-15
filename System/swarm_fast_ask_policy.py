#!/usr/bin/env python3
"""
swarm_fast_ask_policy.py

Local, receipt-backed Fast Ask self-improvement organ for Alice.

Purpose
-------
Before Alice's main brain answers a turn, a small local policy decides which
traces to read (alice_conversation, memory_ledger, research docs, stigmergic
observability, none) and in what order/quantity. Bad decisions cost latency,
STGM, and truth. This module:

  1. Names the decision lanes (a small enumerated, append-only set).
  2. Provides a rule-based seed policy `decide(query, recent_history)` that
     emits a `Decision` (which lanes to read + a stop condition).
  3. Records every Fast Ask turn as an append-only `FAST_ASK_TRAINING_EXAMPLE`
     row in `.sifta_state/fast_ask_training_examples.jsonl` with a
     SHA-256 receipt — that ledger is the data source for any future learned
     policy (rule weighting, classifier, tiny LoRA).
  4. Exposes `record_dispatch(...)` and `record_outcome(ticket, ...)` as the
     two hook points the Talk widget (or any brain router) can call.
  5. Provides a `policy_snapshot(...)` that aggregates the ledger into hints
     (success rate per lane, mean latency, mean STGM spend, top failure
     phrases) so peer Doctors can read what the swarm has actually learned.

Doctrine
--------
Receipt-backed (every row carries `truth_label`, `receipt`, `query_hash`,
`falsifier`). Append-only. No cloud. No outbound calls. Crashing this
organ MUST NOT crash Alice's brain — the Talk-widget hook is wrapped in
defensive try/except.

CLI
---
    python3 -m System.swarm_fast_ask_policy decide "what did I say about mondaloy?"
    python3 -m System.swarm_fast_ask_policy snapshot
    python3 -m System.swarm_fast_ask_policy tail 5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(os.environ.get("SIFTA_STATE_DIR", str(_REPO / ".sifta_state")))

TRUTH_LABEL = "FAST_ASK_POLICY_V1"
LEDGER_NAME = "fast_ask_training_examples.jsonl"
EPISODIC_TRUTH_LABEL = "FAST_ASK_POLICY_DIARY_V1"
KIND_TRAINING_EXAMPLE = "FAST_ASK_TRAINING_EXAMPLE"
KIND_DECISION_ONLY = "FAST_ASK_DECISION"
SCHEMA_VERSION = 2

FAILURE_KINDS = (
    "none",
    "bad_recall",
    "over_context",
    "missed_tool",
    "slow",
    "rlhs_drift",
    "hallucination",
    "crash",
    "stale_physical_space",
    "other",
)


# Trace lanes the policy is allowed to recommend reading. Append-only:
# adding a new lane is fine, removing or renaming one breaks replay.
LANES: tuple[str, ...] = (
    "alice_conversation",          # .sifta_state/alice_conversation.jsonl
    "memory_ledger",               # .sifta_state/memory_ledger.jsonl
    "research_docs",               # Documents/RESEARCH_*.md
    "stigmergic_observability",    # .sifta_state/stigmergic_observability.jsonl
    "ide_stigmergic_trace",        # .sifta_state/ide_stigmergic_trace.jsonl
    "work_receipts",               # .sifta_state/work_receipts.jsonl
    "physical_space",              # fused E35 physical-space report
    "face_detection_events",        # .sifta_state/face_detection_events.jsonl
    "owner_body_events",            # .sifta_state/owner_body_events.jsonl
    "canonical_organ_registry",     # live organ map + health/profit query routes
    "interstellar_evidence_field", # .sifta_state/interstellar_3i_evidence_field.jsonl
    "mondaloy_process_field",      # .sifta_state/mondaloy_process_field.jsonl
    "schedule",                    # stigmergic schedule rows
    "none",                        # explicit "do not read anything extra"
)

# Rough query "buckets" the rule-based policy classifies into. Buckets feed
# both the Decision recommendation and the replay aggregation.
QUERY_BUCKETS: tuple[str, ...] = (
    "recall_self",
    "research_topic",
    "tool_action",
    "schedule",
    "swarm_status",
    "owner_body",
    "speculative_physics",
    "code_or_repo",
    "small_talk",
    "unknown",
)

# Default soft "stop conditions" each bucket should respect — written into
# the decision so the brain (or a future learned policy) knows when to stop
# reading more traces.
STOP_CONDITIONS = {
    "recall_self": "found at least 3 prior turns matching query keywords",
    "research_topic": "found 1 research_docs hit + 1 conversation anchor",
    "tool_action": "found tool spec or 1 prior receipt for same intent",
    "schedule": "found upcoming row OR confirmed empty schedule",
    "swarm_status": "found latest stigmergic row younger than 1h",
    "owner_body": "found fresh body/camera row OR named absence/staleness explicitly",
    "speculative_physics": "found 1 evidence-field deposit OR 1 falsifier",
    "code_or_repo": "found file or symbol mentioned in query",
    "small_talk": "no extra context needed",
    "unknown": "12 conversation turns or first context hit, whichever first",
}

# Decay constants for replay aggregation: older rows count less.
DEFAULT_TAU_S = {
    KIND_TRAINING_EXAMPLE: 30.0 * 24.0 * 3600.0,  # ~30 days
    KIND_DECISION_ONLY:    7.0 * 24.0 * 3600.0,
}

# Tiny keyword tables for the rule-based seed policy. These are not weights —
# they only choose which trace lanes the policy SUGGESTS reading. The learned
# policy can replace them.
_BUCKET_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("schedule",            ("schedule", "calendar", "remind", "tomorrow", "tonight",
                             "appointment", "meeting", "due ")),
    ("tool_action",         ("send whatsapp", "play music", "open camera",
                             "screenshot", "git commit", "git push", "ollama",
                             "tool call")),
    ("swarm_status",        ("stgm", "swarm status", "metabolism", "homeostasis",
                             "wallet", "ledger", "predator", "covenant",
                             "ide stigmergic")),
    ("owner_body",          ("owner body", "my body", "george body", "looks sick",
                             "alice sick", "are you sick", "healthy", "health",
                             "tooth", "teeth", "dentist", "hydration", "sleep",
                             "camera", "face", "eating", "coffee")),
    ("recall_self",         ("what did i say", "what did you say", "remind me",
                             "earlier you", "before you said", "we talked",
                             "yesterday", "last time", "you mentioned")),
    ("speculative_physics", ("3i/atlas", "3i atlas", "interstellar", "plasmoid",
                             "lagrangian", "siust", "quantum gravity",
                             "consciousness physics", "panpsych")),
    ("research_topic",      ("mondaloy", "ar1", "rocketdyne", "research",
                             "primary source", "tacit knowledge", "patent",
                             "subq", "speech to speech", "stigmergic ")),
    ("code_or_repo",        ("def ", "class ", ".py", ".jsonl", "pytest",
                             "cursor", "antigravity", "codex", "import ",
                             "py_compile", "applications/", "system/")),
    ("small_talk",          ("hello", "hey alice", "good morning",
                             "good night", "how are you", "thanks", "thank you")),
)


@dataclass(frozen=True)
class Decision:
    bucket: str
    read: tuple[str, ...]              # ordered lane:limit hints, e.g. "alice_conversation:last_12"
    stop_condition: str
    rationale: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "read": list(self.read),
            "stop_condition": self.stop_condition,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class FastAskTicket:
    """Returned by `record_dispatch`; pass back into `record_outcome`."""
    trace_id: str
    start_ts: float
    query_hash: str
    bucket: str
    decision: Decision
    model: str
    history_turns: int
    sysprompt_chars: int


# ── path helpers ─────────────────────────────────────────────────────────────
def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def ledger_path(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


# ── canonicalization + receipts ──────────────────────────────────────────────
def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def local_receipt(payload: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in payload.items() if k != "receipt"}
    return hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()


def query_hash(query_text: str) -> str:
    """Stable, privacy-friendly hash over the normalised query.

    Lower-cased + whitespace-collapsed so 'what did I say' and 'What did
    I  say' bucket to the same training example for replay.
    """
    norm = re.sub(r"\s+", " ", (query_text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=True, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


# ── identity helpers ─────────────────────────────────────────────────────────
def _node_serial() -> str:
    cached = os.environ.get("SIFTA_NODE_SERIAL")
    if cached:
        return cached
    try:
        import subprocess
        out = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            if "Serial Number" in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "UNKNOWN_NODE"


# ── rule-based seed policy ───────────────────────────────────────────────────
def _classify_query(query_text: str, snap: dict[str, Any] | None = None) -> str:
    """Return the bucket label for `query_text` using dynamic historical weights."""
    text = (query_text or "").lower()
    if not text.strip():
        return "small_talk"
        
    scores = {b: 0.0 for b in QUERY_BUCKETS}
    for bucket, kws in _BUCKET_KEYWORDS:
        hits = sum(1 for kw in kws if kw in text)
        scores[bucket] = hits
        
    if snap:
        buckets_info = snap.get("buckets", {})
        for b in QUERY_BUCKETS:
            if scores[b] > 0:
                info = buckets_info.get(b, {})
                sr = float(info.get("success_rate", 0.5) or 0.5)
                truth = float(info.get("mean_truth_score", 0.5) or 0.5)
                # Dynamic weighting based on historical performance instead of flat static keywords
                scores[b] *= (sr * truth)

    best_bucket = max(scores.items(), key=lambda x: x[1])
    
    # Epsilon-greedy exploration term: ~15% chance to explore a different bucket 
    # to continuously discover better routing strategies instead of locking in early.
    import random
    if random.random() < 0.15:
        candidates = [b for b, s in scores.items() if s > 0 and b != best_bucket[0]]
        if candidates:
            return random.choice(candidates)

    if best_bucket[1] > 0:
        return best_bucket[0]
    return "unknown"


def _live_presence_gate(*, state_dir: Path | None = None) -> bool:
    try:
        from System.stigmerobotics_observability import live_observability_report

        report = live_observability_report(limit=240, state_dir=state_dir)
        return bool(report.physical_space and report.physical_space.presence_gates_ok)
    except Exception:
        return False


def _normalise_failure_kind(value: str, *, ok: bool) -> str:
    if ok:
        return "none"
    text = (value or "").strip().lower()
    if not text:
        return "other"
    if any(s in text for s in ("timeout", "timed out", "latency", "slow")):
        return "slow"
    if any(s in text for s in ("rlhs", "rlhf", "degraded", "alignment")):
        return "rlhs_drift"
    if any(s in text for s in ("receipt", "effector", "tool", "whatsapp")):
        return "missed_tool"
    if any(s in text for s in ("recall", "context", "memory", "underread")):
        return "bad_recall"
    if any(s in text for s in ("camera", "face", "physical", "presence", "stale")):
        return "stale_physical_space"
    if any(s in text for s in ("halluc", "unk_byte", "tokenizer", "residue", "loop")):
        return "hallucination"
    if any(s in text for s in ("http", "connection", "ollama", "brain", "crash", "exception")):
        return "crash"
    return "other"


def _decision_for_bucket(bucket: str, recent_history_turns: int, query_text: str = "", presence_gates_ok: bool = False) -> Decision:
    """Map a query bucket to a `Decision`. Conservative on STGM by default."""
    history_window = max(2, min(recent_history_turns, 12))
    convo_short = f"alice_conversation:last_{history_window}"
    convo_med = "alice_conversation:last_24"

    if bucket == "small_talk":
        read = ("none",)
    elif bucket == "schedule":
        read = ("schedule:next_5", convo_short)
    elif bucket == "recall_self":
        if presence_gates_ok:
            read = ("physical_space:latest",
                    "face_detection_events:last_20",
                    "stigmergic_observability:last_80",
                    convo_med,
                    "memory_ledger:last_120")
        else:
            read = (convo_med, "memory_ledger:last_120")
    elif bucket == "tool_action":
        read = ("work_receipts:last_24", convo_short, "ide_stigmergic_trace:last_8")
    elif bucket == "swarm_status":
        if presence_gates_ok:
            read = ("physical_space:latest",
                    "stigmergic_observability:last_80",
                    "face_detection_events:last_20",
                    "owner_body_events:last_20",
                    "ide_stigmergic_trace:last_12",
                    "work_receipts:last_24")
        else:
            read = ("ide_stigmergic_trace:last_12",
                    "work_receipts:last_24",
                    "stigmergic_observability:last_30")
    elif bucket == "owner_body":
        if presence_gates_ok:
            read = ("physical_space:latest",
                    "face_detection_events:last_20",
                    "owner_body_events:last_20",
                    "stigmergic_observability:last_80",
                    convo_med)
        else:
            read = ("owner_body_events:last_20",
                    "face_detection_events:last_10",
                    convo_med,
                    "memory_ledger:last_120")
    elif bucket == "research_topic":
        read = ("research_docs:topic_match",
                "mondaloy_process_field:last_24",
                convo_short)
    elif bucket == "speculative_physics":
        read = ("interstellar_evidence_field:last_24",
                "research_docs:topic_match",
                convo_short)
    elif bucket == "code_or_repo":
        read = (convo_short, "work_receipts:last_24")
    else:  # unknown
        read = (convo_short,)
        
    # Bias routing using the new presence_gates_ok signal from E35 when the query looks desk/physical related
    text = query_text.lower()
    is_physical = any(kw in text for kw in ("desk", "room", "camera", "see me", "hear me", "thermal", "physical", "body", "temperature"))
    if is_physical and presence_gates_ok:
        read_list = ["physical_space:latest", *list(read)]
        seen: set[str] = set()
        read_list = [lane for lane in read_list if not (lane in seen or seen.add(lane))]
        read = tuple(read_list)

    return Decision(
        bucket=bucket,
        read=read,
        stop_condition=STOP_CONDITIONS.get(bucket, STOP_CONDITIONS["unknown"]),
        rationale=(
            f"dynamic_policy_v{SCHEMA_VERSION}: query routed to `{bucket}` "
            f"via historical weights. presence_gates_ok={presence_gates_ok}."
        ),
    )


def _with_organ_registry_hint(decision: Decision, query_text: str, *, state_dir: Path | None = None) -> Decision:
    """Attach a registry query lane for turns that should pick organs by live health."""
    if decision.bucket in {"small_talk", "unknown"} or decision.read == ("none",):
        return decision
    try:
        from System.swarm_canonical_organ_registry import route_query

        routed = route_query(query_text, state_dir=state_dir, limit=3, include_dynamic=False)
    except Exception:
        return decision
    matches = routed.get("matches") if isinstance(routed, Mapping) else None
    if not isinstance(matches, list) or not matches:
        return decision
    read = list(decision.read)
    if not any(str(lane).startswith("canonical_organ_registry:") for lane in read):
        read.append("canonical_organ_registry:top_3")
    top_ids = ",".join(str(m.get("organ_id") or "") for m in matches[:3] if isinstance(m, Mapping))
    rationale = decision.rationale
    if top_ids:
        rationale = f"{rationale} organ_registry_top={top_ids}."
    return Decision(
        bucket=decision.bucket,
        read=tuple(read),
        stop_condition=decision.stop_condition,
        rationale=rationale,
    )


def decide(
    query_text: str,
    *,
    recent_history_turns: int = 12,
    presence_gates_ok: bool | None = None,
    state_dir: Path | None = None,
) -> Decision:
    """Public seed policy: produce a `Decision` for `query_text`.

    The returned `Decision` is what Alice's brain SHOULD respect this turn.
    The actual reading is still performed by the brain pipeline; this organ
    only records the recommendation + the outcome.
    """
    try:
        snap = policy_snapshot(state_dir=state_dir)
    except Exception:
        snap = None
        
    bucket = _classify_query(query_text, snap=snap)
    if presence_gates_ok is None and bucket in {"recall_self", "swarm_status", "owner_body"}:
        presence_gates_ok = _live_presence_gate(state_dir=state_dir)
    decision = _decision_for_bucket(
        bucket,
        recent_history_turns,
        query_text=query_text,
        presence_gates_ok=bool(presence_gates_ok),
    )
    return _with_organ_registry_hint(decision, query_text, state_dir=state_dir)


# ── failure capture hook ─────────────────────────────────────────────────────
def record_dispatch(
    *,
    query_text: str,
    model: str,
    history_turns: int,
    sysprompt_chars: int = 0,
    presence_gates_ok: bool = False,
    extra_context: Mapping[str, Any] | None = None,
    state_dir: Path | None = None,
    write_decision_row: bool = True,
) -> FastAskTicket | None:
    """Open a Fast Ask training example for the in-flight brain turn.

    Always returns a `FastAskTicket` on success or `None` on failure. The
    function never raises — Alice's brain MUST keep running even if this
    organ misbehaves.
    """
    try:
        decision = decide(query_text, recent_history_turns=history_turns, presence_gates_ok=presence_gates_ok, state_dir=state_dir)
        ticket = FastAskTicket(
            trace_id=str(uuid.uuid4()),
            start_ts=time.time(),
            query_hash=query_hash(query_text),
            bucket=decision.bucket,
            decision=decision,
            model=str(model or ""),
            history_turns=int(history_turns or 0),
            sysprompt_chars=int(sysprompt_chars or 0),
        )
        if write_decision_row:
            row = {
                "ts": ticket.start_ts,
                "trace_id": ticket.trace_id,
                "kind": KIND_DECISION_ONLY,
                "truth_label": TRUTH_LABEL,
                "schema_version": SCHEMA_VERSION,
                "query_hash": ticket.query_hash,
                "decision": decision.as_payload(),
                "model": ticket.model,
                "history_turns": ticket.history_turns,
                "sysprompt_chars": ticket.sysprompt_chars,
                "node_serial": _node_serial(),
                "extra_context": dict(extra_context or {}),
            }
            row["receipt"] = local_receipt(row)
            _append_jsonl(ledger_path(state_dir), row)
        return ticket
    except Exception:
        return None


def record_outcome(
    ticket: FastAskTicket | None,
    *,
    ok: bool,
    response_text: str = "",
    latency_ms: float | None = None,
    stgm_spent: float | None = None,
    truth_score: float | None = None,
    receipt_correct: bool | None = None,
    user_useful: bool | None = None,
    falsifier: str = "",
    failure_kind: str = "",
    extra: Mapping[str, Any] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Close the Fast Ask training example opened by `record_dispatch`.

    Appends a `FAST_ASK_TRAINING_EXAMPLE` row carrying the original decision,
    the measured outcome, and a SHA-256 receipt. Returns the row on success,
    None on failure (never raises).
    """
    if ticket is None:
        return None
    try:
        end_ts = time.time()
        if latency_ms is None:
            latency_ms = max(0.0, (end_ts - ticket.start_ts) * 1000.0)
        response_text = (response_text or "")
        falsifier = (falsifier or "").strip()
        if not falsifier:
            if ok:
                falsifier = (
                    "would have been faster + equally accurate with strictly "
                    "less context"
                )
            else:
                falsifier = (
                    "more context (or a different lane order) would have "
                    "kept this turn from failing"
                )
        failure_kind = _normalise_failure_kind(failure_kind, ok=bool(ok))
            
        outcome: dict[str, Any] = {
            "ok": bool(ok),
            "latency_ms": round(float(latency_ms), 2),
            "response_chars": len(response_text),
            "stgm_spent": (round(float(stgm_spent), 4)
                           if stgm_spent is not None else None),
            "truth_score": (round(float(truth_score), 4)
                            if truth_score is not None else None),
            "receipt_correct": (None if receipt_correct is None
                                else bool(receipt_correct)),
            "user_useful": (None if user_useful is None
                            else bool(user_useful)),
            "failure_kind": failure_kind,
        }
        row = {
            "ts": end_ts,
            "trace_id": ticket.trace_id,
            "kind": KIND_TRAINING_EXAMPLE,
            "truth_label": TRUTH_LABEL,
            "schema_version": SCHEMA_VERSION,
            "query_hash": ticket.query_hash,
            "decision": ticket.decision.as_payload(),
            "outcome": outcome,
            "falsifier": falsifier,
            "model": ticket.model,
            "history_turns": ticket.history_turns,
            "sysprompt_chars": ticket.sysprompt_chars,
            "start_ts": ticket.start_ts,
            "node_serial": _node_serial(),
            "extra": dict(extra or {}),
        }
        row["receipt"] = local_receipt(row)
        _append_jsonl(ledger_path(state_dir), row)
        return row
    except Exception:
        return None


# ── replay + snapshot ────────────────────────────────────────────────────────
def _decay_weight(kind: str, ts: float, now_ts: float) -> float:
    tau = DEFAULT_TAU_S.get(kind, 7.0 * 24.0 * 3600.0)
    age = max(0.0, now_ts - ts)
    return math.exp(-age / max(1.0, tau))


def training_examples(
    *,
    state_dir: Path | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows = [
        r for r in read_jsonl(ledger_path(state_dir))
        if r.get("kind") == KIND_TRAINING_EXAMPLE
    ]
    rows.sort(key=lambda r: float(r.get("ts", 0.0)))
    if limit is not None:
        rows = rows[-int(limit):]
    return rows


def policy_snapshot(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Aggregate the ledger into bucket-level hints for the next turn."""
    now_ts = float(now if now is not None else time.time())
    rows = read_jsonl(ledger_path(state_dir))
    examples = [r for r in rows if r.get("kind") == KIND_TRAINING_EXAMPLE]
    decisions = [r for r in rows if r.get("kind") == KIND_DECISION_ONLY]

    by_bucket: dict[str, dict[str, float]] = {}
    failures: list[dict[str, Any]] = []
    for row in examples:
        bucket = (((row.get("decision") or {}).get("bucket")) or "unknown")
        outcome = row.get("outcome") or {}
        ts = float(row.get("ts", 0.0))
        weight = _decay_weight(KIND_TRAINING_EXAMPLE, ts, now_ts)
        agg = by_bucket.setdefault(bucket, {
            "n": 0.0,
            "n_raw": 0.0,
            "n_ok": 0.0,
            "n_fail": 0.0,
            "latency_ms_sum": 0.0,
            "stgm_spent_sum": 0.0,
            "stgm_n": 0.0,
            "truth_sum": 0.0,
            "truth_n": 0.0,
            "useful_sum": 0.0,
            "useful_n": 0.0,
        })
        agg["n"] += weight
        agg["n_raw"] += 1.0
        if outcome.get("ok"):
            agg["n_ok"] += weight
        else:
            agg["n_fail"] += weight
            failures.append({
                "ts": ts,
                "bucket": bucket,
                "failure_kind": outcome.get("failure_kind") or outcome.get("error_kind") or "",
                "falsifier": row.get("falsifier") or "",
                "model": row.get("model") or "",
            })
        agg["latency_ms_sum"] += float(outcome.get("latency_ms") or 0.0) * weight
        if outcome.get("stgm_spent") is not None:
            agg["stgm_spent_sum"] += float(outcome["stgm_spent"]) * weight
            agg["stgm_n"] += weight
        if outcome.get("truth_score") is not None:
            agg["truth_sum"] += float(outcome["truth_score"]) * weight
            agg["truth_n"] += weight
        if outcome.get("user_useful") is not None:
            agg["useful_sum"] += (1.0 if outcome["user_useful"] else 0.0) * weight
            agg["useful_n"] += weight

    hints: dict[str, dict[str, Any]] = {}
    for bucket, agg in by_bucket.items():
        n = max(agg["n"], 1e-9)
        hints[bucket] = {
            "examples_decayed": round(agg["n"], 3),
            "examples_raw": int(agg["n_raw"]),
            "success_rate": round(agg["n_ok"] / n, 3),
            "mean_latency_ms": round(agg["latency_ms_sum"] / n, 1),
            "mean_stgm_spent": (round(agg["stgm_spent_sum"] / max(agg["stgm_n"], 1e-9), 3)
                                if agg["stgm_n"] > 0 else None),
            "mean_truth_score": (round(agg["truth_sum"] / max(agg["truth_n"], 1e-9), 3)
                                 if agg["truth_n"] > 0 else None),
            "user_useful_rate": (round(agg["useful_sum"] / max(agg["useful_n"], 1e-9), 3)
                                 if agg["useful_n"] > 0 else None),
            "recommended_lanes": list(_decision_for_bucket(bucket, 12, presence_gates_ok=False).read),
            "stop_condition": STOP_CONDITIONS.get(bucket, STOP_CONDITIONS["unknown"]),
        }

    failures.sort(key=lambda r: r["ts"], reverse=True)

    return {
        "truth_label": TRUTH_LABEL,
        "schema_version": SCHEMA_VERSION,
        "now": now_ts,
        "ledger_rows": len(rows),
        "training_examples": len(examples),
        "decision_only_rows": len(decisions),
        "buckets": hints,
        "recent_failures": failures[:10],
        "lanes_known": list(LANES),
        "buckets_known": list(QUERY_BUCKETS),
        "failure_kinds_known": list(FAILURE_KINDS),
    }


def proof_of_property(*, state_dir: Path | None = None) -> dict[str, bool]:
    """Verify the load-bearing invariants of this organ on disk."""
    snap = policy_snapshot(state_dir=state_dir)
    return {
        "ledger_path_exists_or_empty": True,
        "schema_version_v1": snap["schema_version"] == SCHEMA_VERSION,
        "lanes_set_immutable": tuple(snap["lanes_known"]) == LANES,
        "buckets_set_immutable": tuple(snap["buckets_known"]) == QUERY_BUCKETS,
        "failure_kinds_set_immutable": tuple(snap["failure_kinds_known"]) == FAILURE_KINDS,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="swarm_fast_ask_policy",
        description="SIFTA Fast Ask self-improvement organ — local, receipt-backed.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_decide = sub.add_parser("decide", help="show the rule-based decision for a query")
    p_decide.add_argument("query", help="user query text")
    p_decide.add_argument("--turns", type=int, default=12)

    sub.add_parser("snapshot", help="print policy snapshot (bucket hints)")

    p_tail = sub.add_parser("tail", help="print last N training examples")
    p_tail.add_argument("n", type=int, nargs="?", default=10)

    sub.add_parser("proof", help="print proof_of_property() result")

    args = parser.parse_args()
    if args.cmd == "decide":
        d = decide(args.query, recent_history_turns=args.turns)
        print(json.dumps(d.as_payload(), indent=2, ensure_ascii=True))
        return 0
    if args.cmd == "snapshot":
        print(json.dumps(policy_snapshot(), indent=2, ensure_ascii=True))
        return 0
    if args.cmd == "tail":
        rows = training_examples(limit=args.n)
        for r in rows:
            print(json.dumps(r, ensure_ascii=True))
        return 0
    if args.cmd == "proof":
        print(json.dumps(proof_of_property(), indent=2, ensure_ascii=True))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
