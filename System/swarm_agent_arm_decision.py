#!/usr/bin/env python3
"""Decision-side agent-arm prepass for Alice Talk.

This module is the small action habit between "I know an arm exists" and
"I reach for it when the task benefits from another local reasoning pass."
Round 64 makes this opt-in only: automatic read-only evidence gatherers are
waste. If enabled for debugging, the selected arm runs live and receipts carry
the proof.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid
from typing import Any, Callable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ASYNC_LEDGER = "agent_arm_async_results.jsonl"
_DEDUP_WINDOW_S = 600.0
_LEARNED_ROUTE_MIN_ATTEMPTS = 3


@dataclass(frozen=True)
class AgentArmDecision:
    arm_id: str
    prompt: str
    reason: str
    timeout_s: int


@dataclass(frozen=True)
class AgentArmAsyncJob:
    job_id: str
    status: str
    decision: AgentArmDecision
    artifact_path: str
    duplicate_of: str = ""


def agent_arm_prepass_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True only when the async prepass is explicitly enabled.

    Alice's arms are available by default through explicit cortex-authored
    dispatch. The background prepass is not a gate and not a substitute for
    receipts; it stays off unless a developer deliberately debugs that path.
    """
    source = os.environ if env is None else env
    value = str(source.get("SIFTA_AGENT_ARM_PREPASS_ENABLE", "0")).strip().lower()
    return value in {"1", "true", "yes", "on", "enabled"}


_TASK_RE = re.compile(
    r"\b("
    r"research|compare|plan|design|implement|debug|diagnose|investigate|"
    r"analy[sz]e|review|refactor|architecture|tests?|prove|verify|"
    r"real\s+task|solve|decide|strategy|trade-?offs?"
    r")\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(
    r"\b(code|patch|diff|pytest|test\s+failure|bug|stack\s*trace|traceback|"
    r"build|create|implement|module|function|class|repo|file|implementation)\b|```",
    re.IGNORECASE,
)
_EXPLICIT_ARM_RE = re.compile(
    r"\b(?:ask|call|use|tell|send\s+to|query|consult|have|get|make|let)\s+"
    r"(hermes|hemes|claude(?:\s+code)?|codex|grok)\b",
    re.IGNORECASE,
)
_SCOUT_RE = re.compile(
    r"\b("
    r"summari[sz]e|classify|extract|triage|label|route|compress|"
    r"intent|next\s+action|key\s+points?|short\s+read"
    r")\b",
    re.IGNORECASE,
)
_STATUS_RE = re.compile(
    r"\b("
    r"what\s+is\s+(?:hermes|codex|agent\s+arm)|"
    r"status|receipt|ledger|configured|registry|what\s+tools?|"
    r"do\s+you\s+have|explain\s+(?:evidence\s+mode|hermes|codex)"
    r")\b",
    re.IGNORECASE,
)
_DIRECT_EFFECTOR_RE = re.compile(
    r"\b(send|message|whatsapp|schedule|remind|timer|camera|switch\s+camera|"
    r"open\s+(?:app|browser|website)|play\s+music)\b",
    re.IGNORECASE,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line, encoding="utf-8")
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_jsonl_tail(path: Path, *, n: int = 80) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        from System.jsonl_file_lock import read_text_locked

        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        text = path.read_text(encoding="utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-n:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _stability_biased_arm(
    arm_id: str,
    reason: str,
    *,
    state_dir: Path | None = None,
    owner_intent_explicit: bool = False,
) -> tuple[str, str]:
    try:
        from System.swarm_stability_to_homeostasis_bridge import (
            read_latest_clamp_signal,
            should_enter_conserve_repair,
        )
        from System.swarm_arm_skills_catalog import allowed_arm_ids_for_current_stability
        from System.swarm_owner_somatic_state import latest_somatic_signal

        signal = read_latest_clamp_signal(root=state_dir)
        if not should_enter_conserve_repair(signal):
            somatic = latest_somatic_signal(state_dir=state_dir or ".sifta_state", max_age_s=420)
            if somatic.get("ok") and somatic.get("is_fatigued") and not owner_intent_explicit:
                if arm_id != "corvid_scout":
                    return (
                        "corvid_scout",
                        reason
                        + "; owner_fatigue_bias routed heavy builder to cheap local corvid_scout",
                    )
            return arm_id, reason
        allowed = allowed_arm_ids_for_current_stability(
            root=state_dir,
            arm_ids=(arm_id, "corvid_scout"),
        )
        if arm_id in allowed:
            return arm_id, reason
        if "corvid_scout" in allowed:
            return (
                "corvid_scout",
                reason
                + "; stability_conserve_repair_bias routed heavy builder to cheap local corvid_scout",
            )
        return arm_id, reason + "; FIELD_FAILURE: no stability-allowed arm candidate"
    except Exception as exc:
        return arm_id, reason + f"; FIELD_FAILURE: stability arm bias unavailable ({type(exc).__name__})"


def agent_arm_decision_for_turn(
    user_text: str,
    *,
    state_dir: Path | None = None,
) -> Optional[AgentArmDecision]:
    """Return an arm decision for hard turns that should use an arm."""

    text = (user_text or "").strip()
    if len(text) < 24:
        return None
    if "[TOOL_CALL:" in text or "```tool_call" in text:
        return None
    if _DIRECT_EFFECTOR_RE.search(text):
        return None
    if _STATUS_RE.search(text) and not _TASK_RE.search(text):
        return None
    task_match = bool(_TASK_RE.search(text))
    code_match = bool(_CODE_RE.search(text))
    scout_match = bool(_SCOUT_RE.search(text))
    if not (task_match or code_match or scout_match):
        return None

    registry_context = ""
    try:
        from System.swarm_canonical_organ_registry import route_query

        routed = route_query(text, limit=3, include_dynamic=False)
        matches = routed.get("matches") or []
        if matches:
            registry_context = " Registry organ hints: " + "; ".join(
                f"{m.get('organ_id')}({m.get('layer')},health={(m.get('health') or {}).get('status', 'unknown')})"
                for m in matches[:3]
            )
    except Exception:
        registry_context = ""

    explicit_arm = None
    explicit_match = _EXPLICIT_ARM_RE.search(text)
    if explicit_match:
        named = explicit_match.group(1).casefold().replace(" ", "_")
        explicit_arm = {
            "hermes": "hermes_agent",
            "hemes": "hermes_agent",
            "claude": "claude_agent",
            "claude_code": "claude_agent",
            "codex": "codex_agent",
            "grok": "grok_agent",
        }.get(named)

    arm_id = explicit_arm or "hermes_agent"
    if code_match:
        arm_id = explicit_arm or "codex_agent"
    elif scout_match and len(text) <= 1200:
        arm_id = explicit_arm or "corvid_scout"
    if explicit_arm is None:
        try:
            from System.swarm_arm_outcome_learner import recommend_arm_for_task

            arm_id = recommend_arm_for_task(
                text,
                default_arm=arm_id,
                min_attempts=_LEARNED_ROUTE_MIN_ATTEMPTS,
            )
        except Exception:
            pass

    bounded = text.replace("\n", " ").strip()
    if len(bounded) > 1500:
        bounded = bounded[:1500] + "..."
    reason = (
        "owner explicitly named this registered agent arm"
        if explicit_arm
        else "task benefits from a second local arm pass before Alice answers"
    )
    arm_id, reason = _stability_biased_arm(
        arm_id,
        reason,
        state_dir=state_dir,
        owner_intent_explicit=explicit_arm is not None,
    )
    from System.swarm_swimmer_task_packet import (
        build_task_packet_from_arm_dispatch,
        render_swimmer_task_prompt,
        write_task_packet_ledger,
    )

    if explicit_arm and code_match and arm_id == explicit_arm:
        owner_task = (
            "Alice-owned SIFTA app/build delegation. "
            "Write real files in /Users/ioanganton/Music/ANTON_SIFTA if the task asks for code; "
            "do not only describe. After writing, run relevant compile/runtime/tests and print "
            "files written, compile result, runtime/test output, errors, and receipt. "
            "If writing fails or stalls, emit an honest failure receipt. Owner task: "
            + bounded
            + registry_context
        )
        job = "sifta_build_delegation"
    else:
        owner_task = (
            "Live arm action pass. Do useful work if the task asks for it, "
            "then report the receipt, risks, and next step: "
            + bounded
            + registry_context
        )
        job = "bounded_research_pass"

    packet = build_task_packet_from_arm_dispatch(
        arm_id=arm_id,
        owner_task=owner_task,
        job=job,
        organ="agent_arms",
    )
    write_task_packet_ledger(packet, state_dir=state_dir, extra={"source": "agent_arm_decision"})
    prompt = render_swimmer_task_prompt(packet)
    # Round 100 (2026-05-28): bumped from 150s to 300s for the heavy builder
    # arms (claude/codex/qwen/cline) after Alice's verified complaint that
    # codex+claude were timing out at 150s — receipts f8469daa, 2c636406,
    # d8be46e7 in agent_arm_receipts.jsonl. Decision-layer default is what
    # her autonomous cortex sends when it doesn't supply an explicit
    # timeout_s; the router still clamps to its own per-arm ceiling (1200s).
    # Grok and corvid_scout stay shorter because their tasks are usually
    # one-shot probes, not multi-file builds.
    timeout_s = {"codex_agent": 300, "claude_agent": 300, "grok_agent": 150, "qwen_agent": 300, "cline_agent": 300, "corvid_scout": 30}.get(arm_id, 75)
    return AgentArmDecision(arm_id=arm_id, prompt=prompt, reason=reason, timeout_s=timeout_s)


def _tool_call_for_decision(decision: AgentArmDecision):
    from System.swarm_tool_router import ParsedToolCall

    return ParsedToolCall(
        tool_name="agent_arm_research",
        params={
            "arm": decision.arm_id,
            "prompt": decision.prompt,
            "timeout_s": str(decision.timeout_s),
            "cost_justification": (
                "Alice chose a registered arm because this task needs "
                "a second local work pass before her final answer."
            ),
        },
        raw_match="[AUTO_AGENT_ARM_PREPASS]",
    )


def _execute_decision(decision: AgentArmDecision, *, owner_present: bool = True):
    from System.swarm_tool_router import execute_tool_call

    return execute_tool_call(
        _tool_call_for_decision(decision),
        owner_present=owner_present,
        autonomous=True,
    )


def run_agent_arm_decision_prepass(
    user_text: str,
    *,
    owner_present: bool = True,
    force: bool = False,
    env: dict[str, str] | None = None,
):
    """Execute the selected arm through the receipted tool router."""

    if not force and not agent_arm_prepass_enabled(env):
        return None, None
    decision = agent_arm_decision_for_turn(user_text)
    if decision is None:
        return None, None

    return decision, _execute_decision(decision, owner_present=owner_present)


def _result_row(
    *,
    job_id: str,
    decision: AgentArmDecision,
    user_sha256: str,
    tool_result: Any,
    status: str,
) -> dict[str, Any]:
    result = getattr(tool_result, "result", {}) or {}
    if not isinstance(result, dict):
        result = {}
    return {
        "ts": time.time(),
        "truth_label": "AGENT_ARM_ASYNC_RESULT",
        "job_id": job_id,
        "status": status,
        "ok": bool(getattr(tool_result, "executed", False)),
        "arm_id": decision.arm_id,
        "reason": decision.reason,
        "timeout_s": decision.timeout_s,
        "user_sha256": user_sha256,
        "tool_status": getattr(tool_result, "status", ""),
        "arm_status": result.get("status"),
        "receipt_id": result.get("receipt_id"),
        "artifact_path": result.get("artifact_path"),
        "feedback_tail": str(getattr(tool_result, "feedback_for_alice", ""))[-5000:],
    }


def schedule_async_agent_arm_prepass(
    user_text: str,
    *,
    owner_present: bool = True,
    state_dir: Path | None = None,
    executor: Callable[[AgentArmDecision, bool], Any] | None = None,
    start_thread: bool = True,
    run_inline: bool = False,
    force: bool = False,
    env: dict[str, str] | None = None,
) -> AgentArmAsyncJob | None:
    """Schedule an opt-in arm result pass without blocking Alice's Talk turn.

    The scheduled row is written immediately. The result row lands later in
    ``agent_arm_async_results.jsonl`` and is surfaced through
    ``summary_for_prompt`` on subsequent turns.
    """

    if not force and not agent_arm_prepass_enabled(env):
        return None
    decision = agent_arm_decision_for_turn(user_text, state_dir=state_dir)
    if decision is None:
        return None

    state = Path(state_dir or _STATE)
    ledger = state / _ASYNC_LEDGER
    user_sha = _sha256_text((user_text or "").strip())
    now = time.time()
    for row in reversed(_read_jsonl_tail(ledger, n=120)):
        if row.get("user_sha256") != user_sha:
            continue
        if now - float(row.get("ts", 0.0) or 0.0) > _DEDUP_WINDOW_S:
            continue
        prior_job = str(row.get("job_id") or "")
        if prior_job:
            return AgentArmAsyncJob(
                job_id=prior_job,
                status="DUPLICATE_RECENT",
                decision=decision,
                artifact_path=str(ledger),
                duplicate_of=prior_job,
            )

    job_id = str(uuid.uuid4())
    scheduled = {
        "ts": now,
        "truth_label": "AGENT_ARM_ASYNC_SCHEDULED",
        "job_id": job_id,
        "status": "SCHEDULED",
        "arm_id": decision.arm_id,
        "reason": decision.reason,
        "timeout_s": decision.timeout_s,
        "user_sha256": user_sha,
        "prompt_sha256": _sha256_text(decision.prompt),
    }
    _append_jsonl(ledger, scheduled)

    def _worker() -> None:
        run = executor or (lambda dec, present: _execute_decision(dec, owner_present=present))
        try:
            tool_result = run(decision, owner_present)
            feedback = str(getattr(tool_result, "feedback_for_alice", "") or "").strip()
            if bool(getattr(tool_result, "executed", False)):
                status = "ARM_RESULT_CAPTURED"
            elif feedback:
                status = "PARTIAL_ARM_RESULT"
            else:
                status = "NO_ARM_RESULT"
            _append_jsonl(
                ledger,
                _result_row(
                    job_id=job_id,
                    decision=decision,
                    user_sha256=user_sha,
                    tool_result=tool_result,
                    status=status,
                ),
            )
        except Exception as exc:
            _append_jsonl(
                ledger,
                {
                    "ts": time.time(),
                    "truth_label": "AGENT_ARM_ASYNC_ERROR",
                    "job_id": job_id,
                    "status": "ERROR",
                    "arm_id": decision.arm_id,
                    "reason": decision.reason,
                    "user_sha256": user_sha,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )

    if run_inline:
        _worker()
    elif start_thread:
        thread = threading.Thread(
            target=_worker,
            name=f"sifta-agent-arm-{decision.arm_id}-{job_id[:8]}",
            daemon=True,
        )
        thread.start()

    return AgentArmAsyncJob(
        job_id=job_id,
        status="SCHEDULED",
        decision=decision,
        artifact_path=str(ledger),
    )


def summary_for_prompt(
    *,
    state_dir: Path | None = None,
    max_rows: int = 3,
    max_age_s: float = 1800.0,
) -> str:
    """Return recent async arm results for Alice's next cortex turn."""

    ledger = Path(state_dir or _STATE) / _ASYNC_LEDGER
    now = time.time()
    rows = []
    seen_jobs: set[str] = set()
    for row in reversed(_read_jsonl_tail(ledger, n=160)):
        job_id = str(row.get("job_id") or "")
        if not job_id or job_id in seen_jobs:
            continue
        if now - float(row.get("ts", 0.0) or 0.0) > max_age_s:
            continue
        seen_jobs.add(job_id)
        rows.append(row)
        if len(rows) >= max_rows:
            break
    if not rows:
        return ""
    lines = [
        "ASYNC AGENT ARM RESULT BUFFER:",
        "These rows are receipted results from my arms. They are not my voice; I synthesize them in first person.",
    ]
    for row in rows:
        receipt = row.get("receipt_id") or row.get("job_id") or "pending"
        lines.append(
        f"- arm={row.get('arm_id')} status={row.get('status')} receipt={receipt} "
            f"result={str(row.get('feedback_tail') or row.get('error') or '')[:1200]}"
        )
    return "\n".join(lines)


def format_agent_arm_prepass_context(decision: AgentArmDecision, tool_result) -> str:
    """Build the system context Alice sees after the arm returns."""

    receipt = ""
    status = getattr(tool_result, "status", "")
    feedback = getattr(tool_result, "feedback_for_alice", "")
    result = getattr(tool_result, "result", {}) or {}
    if isinstance(result, dict):
        receipt = str(result.get("receipt_id") or "")
        status = str(result.get("status") or status)
    return (
        "AGENT ARM DECISION PREPASS (receipted arm result, not final voice):\n"
        f"- selected_arm={decision.arm_id}\n"
        f"- reason={decision.reason}\n"
        f"- status={status}\n"
        f"- receipt={receipt or 'tool_router_trace'}\n"
        "- Alice must now synthesize this result in first person and cite the receipt if she claims the arm ran.\n"
        f"{feedback}"
    )
