#!/usr/bin/env python3
"""Parallel cortex/arm diagnostics for Alice.

When one cortex stalls, a different arm should inspect the failure while the
organism keeps moving. This organ records that split-brain-as-capability:
the stalled cortex remains the observed error, and a separate diagnostic arm
gets a concrete prompt to inspect the relevant code and receipts.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked, read_text_locked


TRUTH_LABEL = "ALICE_PARALLEL_CORTEX_ARM_DIAGNOSTICS_V1"
LEDGER_NAME = "parallel_cortex_arm_diagnostics.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

_ARM_PRIORITY = (
    "claude_agent",
    "codex_agent",
    "cline_agent",
    "qwen_agent",
    "grok_agent",
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is not None:
        p = Path(state_dir).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    env = os.environ.get("SIFTA_STATE_DIR", "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    p = _DEFAULT_STATE
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _arm_from_cortex_name(name: str) -> str:
    low = _norm(name)
    if "claude" in low or "anthropic" in low:
        return "claude_agent"
    if "codex" in low or "openai" in low:
        return "codex_agent"
    if "cline" in low:
        return "cline_agent"
    if "qwen" in low or "kimi" in low:
        return "qwen_agent"
    if "grok" in low or "xai" in low:
        return "grok_agent"
    return ""


def available_diagnostic_arms(
    *,
    state_dir: Path | str | None = None,
    exclude_model: str = "",
) -> list[str]:
    """Return available diagnostic arms, preferring non-stalled arms."""
    excluded = _arm_from_cortex_name(exclude_model)
    seen: set[str] = set()
    arms: list[str] = []
    try:
        from System.swarm_cortex_consciousness_organ import CortexConsciousnessOrgan

        org = CortexConsciousnessOrgan(state_dir=state_dir)
        for row in org.get_conscious_state().get("available") or []:
            if not isinstance(row, Mapping):
                continue
            if not row.get("available", True):
                continue
            arm = _arm_from_cortex_name(str(row.get("cortex") or ""))
            if arm and arm != excluded and arm not in seen:
                seen.add(arm)
                arms.append(arm)
    except Exception:
        pass

    # Registry presence is useful even when PATH/OAuth probing is sparse.
    try:
        from System.swarm_arm_flex_diagnostic import CORE_ARM_IDS
        for arm in CORE_ARM_IDS:
            if arm != excluded and arm not in seen:
                seen.add(arm)
                arms.append(arm)
    except Exception:
        pass

    return sorted(arms, key=lambda arm: _ARM_PRIORITY.index(arm) if arm in _ARM_PRIORITY else 99)


def choose_diagnostic_arm(
    *,
    state_dir: Path | str | None = None,
    exclude_model: str = "",
    preferred: str = "claude_agent",
) -> str:
    arms = available_diagnostic_arms(state_dir=state_dir, exclude_model=exclude_model)
    if not arms:
        return "codex_agent"
    # r337 (George 2026-06-02): consult Alice's receipt-backed skill ratings so the arm
    # with the best LEARNED code-diagnosis habit is chosen, not just a static preference.
    # Separate habits/skills drive the pick; the field optimizes which arm diagnoses best.
    try:
        from System import swarm_arm_outcome_learner as _learner

        rated = _learner.recommend_arm_for_task(
            "diagnose code bug traceback root cause in repo module", default_arm=""
        )
        if rated and rated in arms:
            return rated
    except Exception:
        pass
    if preferred in arms:
        return preferred
    return arms[0]


@dataclass
class ParallelCortexArmDiagnostic:
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "PARALLEL_CORTEX_ARM_DIAGNOSTIC"
    stalled_cortex: str = ""
    diagnostic_arm: str = ""
    recovery_receipt_id: str = ""
    timeout_s: int = 0
    cause: str = "timeout"
    owner_text_preview: str = ""
    why: str = ""
    source_files: list[str] = field(default_factory=list)
    arm_task_prompt: str = ""
    self_code_round_id: str = ""
    self_code_paths: list[str] = field(default_factory=list)
    self_code_packet: str = ""
    parallel_policy: str = (
        "Use one cortex/arm to continue owner work while another independent arm "
        "inspects the stalled cortex path and writes receipts."
    )
    habit_note: str = (
        "Different arms and cortexes have different habits, strengths, provider "
        "latency, tool access, and failure modes; Alice should exploit that diversity."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def schedule_parallel_diagnostic(
    *,
    stalled_cortex: str,
    owner_text: str = "",
    timeout_s: int = 0,
    cause: str = "timeout",
    recovery_receipt_id: str = "",
    state_dir: Path | str | None = None,
    preferred_arm: str = "claude_agent",
) -> ParallelCortexArmDiagnostic:
    """Write the diagnostic row and a body-stabilization queue item."""
    preview = " ".join(str(owner_text or "").split())[:220]
    arm = choose_diagnostic_arm(
        state_dir=state_dir,
        exclude_model=stalled_cortex,
        preferred=preferred_arm,
    )
    why = (
        f"{stalled_cortex or 'the cortex'} exceeded the bounded {int(timeout_s or 0)}s "
        "cortex-turn timeout. This is a slowness/latency failure at the selected "
        "cortex transport path, not proof that George's request was wrong and not "
        "proof that credentials are bad."
    )
    self_code_packet = ""
    self_code_paths: list[str] = []
    try:
        from System.swarm_alice_self_coding_hand import (
            extract_target_paths,
            recover_self_cut_prompt,
            self_cut_round_id,
        )

        self_code_packet = recover_self_cut_prompt(owner_text)
        if self_code_packet:
            self_code_paths = extract_target_paths(self_code_packet)
            self_code_round = self_cut_round_id(self_code_packet) or "alice-self-code-recovered"
        else:
            self_code_round = ""
    except Exception:
        self_code_packet = ""
        self_code_round = ""
        self_code_paths = []

    if self_code_packet:
        prompt = (
            "Read the covenant. This stalled turn is an Alice SELF-CODE turn, not only a "
            "latency incident. Verify the recovery receipt "
            f"{recovery_receipt_id or '(none)'}, then continue the owner work through the "
            "available arm: produce/execute the SELF_CODE_CUT packet below for "
            f"{self_code_round}. Target paths: {', '.join(self_code_paths) or '(see packet)'}. "
            "If you cannot execute, leave a precise receipt-backed diagnosis and do not ask "
            "George to repeat.\n\nRECOVERED SELF-CODE PACKET:\n"
            + self_code_packet
        )
    else:
        prompt = (
            "Read the covenant. Inspect System/swarm_gemini_brain.py and "
            "System/swarm_cortex_timeout_recovery.py. Explain why the stalled cortex "
            f"timed out after {int(timeout_s or 0)}s, verify the recovery receipt "
            f"{recovery_receipt_id or '(none)'}, and propose the smallest improvement "
            "without blocking the main owner turn. Owner turn preview: " + preview
        )
    event = ParallelCortexArmDiagnostic(
        stalled_cortex=str(stalled_cortex or ""),
        diagnostic_arm=arm,
        recovery_receipt_id=str(recovery_receipt_id or ""),
        timeout_s=int(timeout_s or 0),
        cause=str(cause or "timeout"),
        owner_text_preview=preview,
        why=why,
        source_files=[
            "System/swarm_gemini_brain.py",
            "System/swarm_cortex_timeout_recovery.py",
            "System/swarm_parallel_cortex_arm_diagnostics.py",
            *self_code_paths,
        ],
        arm_task_prompt=prompt[:1200],
        self_code_round_id=self_code_round,
        self_code_paths=self_code_paths,
        self_code_packet=self_code_packet,
    )
    append_line_locked(
        _ledger_path(state_dir),
        json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n",
    )
    try:
        from System.swarm_body_stabilization_queue import add_queue_item

        add_queue_item(
            description=(
                f"Parallel diagnostic: {arm} inspects {stalled_cortex} timeout "
                f"while another cortex/arm continues owner work."
            ),
            kind="self_stabilization",
            source="parallel_cortex_arm_diagnostics",
            status="queued",
            priority=0.82,
            owner_plan=False,
            linked_receipt=event.trace_id,
            state_dir=state_dir,
            dedupe=True,
        )
    except Exception:
        pass
    return event


def latest_parallel_diagnostic_block(
    *,
    state_dir: Path | str | None = None,
) -> str:
    path = _ledger_path(state_dir)
    if not path.exists():
        return ""
    last = ""
    try:
        for line in read_text_locked(path).splitlines():
            if line.strip():
                last = line.strip()
    except Exception:
        return ""
    if not last:
        return ""
    try:
        row = json.loads(last)
    except Exception:
        return ""
    return (
        "PARALLEL CORTEX/ARM DIAGNOSTIC: "
        f"{row.get('diagnostic_arm')} is assigned to inspect "
        f"{row.get('stalled_cortex')} ({row.get('cause')}) while the organism "
        "continues through another available cortex/arm. "
        f"Reason: {row.get('why')}"
    )


def record_diagnostic_outcome(
    *,
    diagnostic_arm: str,
    stalled_cortex: str = "",
    cause: str = "timeout",
    finding: str = "",
    fixed: bool = False,
    trace_id: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Close the learning loop (r337, George): record which arm diagnosed the fault
    and whether it found/fixed the cause. Append-only evidence so Alice's field learns
    which arm has the best diagnosis habit for which cortex fault — that is how she
    uses arms + cortexes to improve and optimize, not just queue once and forget."""
    row = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "kind": "PARALLEL_CORTEX_ARM_DIAGNOSTIC_OUTCOME",
        "diagnostic_arm": str(diagnostic_arm or "")[:40],
        "stalled_cortex": str(stalled_cortex or "")[:80],
        "cause": str(cause or "")[:40],
        "finding_preview": " ".join(str(finding or "").split())[:400],
        "fixed": bool(fixed),
        "trace_id": str(trace_id or ""),
    }
    append_line_locked(
        _ledger_path(state_dir),
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return row
