"""
Event 124 - Multi-gate replay policy.

Event 123 wrote one scalar replay-policy receipt. This module expands that into
several bounded gate values that can be consumed independently by sensory,
dialogue, research, and persistence paths.

Truth label: MULTI_GATE_REPLAY_POLICY. This is deterministic receipt policy,
not learned weights. Kill-switch: SIFTA_MULTI_GATE_REPLAY_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_kernel_identity import owner_display_name, owner_name
from System.swarm_persistent_owner_history import state_dir

MULTI_GATE_LOG_NAME = "multi_gate_policy.jsonl"

BASE_GATES: Dict[str, float] = {
    "co_watch_suggestion": 0.0,
    "question_followup": 0.0,
    "session_persistence": 0.0,
    "research_depth": 0.0,
    "owner_continuity": 0.0,
    "media_context_sensitivity": 0.0,
}


def multi_gate_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / MULTI_GATE_LOG_NAME


def _clamp(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = 0.0
    return round(min(1.0, max(0.0, f)), 4)


def _owner_tokens() -> List[str]:
    out: List[str] = []
    for bit in (owner_name(), owner_display_name()):
        s = (bit or "").strip().lower()
        if len(s) >= 2:
            out.append(s)
    return out


def _normalized_prior(prior_gates: Optional[Dict[str, Any]], decay: float) -> Dict[str, float]:
    prior = prior_gates or {}
    decay_f = min(1.0, max(0.0, float(decay)))
    return {k: _clamp(_clamp(prior.get(k, 0.0)) - decay_f) for k in BASE_GATES}


def compute_multi_gate_bias(
    current_context: str,
    replay_summary: str,
    *,
    prior_gates: Optional[Dict[str, Any]] = None,
    decay: float = 0.05,
) -> Dict[str, float]:
    """
    Bounded deterministic gates from replay + current context.

    Prior state decays first, then current replay evidence can raise one or more
    gates. No hardcoded owner name; local identity comes from kernel helpers.
    """
    gates = _normalized_prior(prior_gates, decay)
    replay_l = (replay_summary or "").lower()
    ctx_l = (current_context or "").lower()
    blob = f"{replay_l} {ctx_l}"

    media_terms = ("youtube", "youtu.be", "video", "cowatch", "co-watch", "media", "audio")
    if any(w in blob for w in media_terms):
        gates["media_context_sensitivity"] = max(gates["media_context_sensitivity"], 0.55)
    if any(w in replay_l for w in ("youtube", "youtu.be", "video", "cowatch", "co-watch")):
        gates["co_watch_suggestion"] = max(gates["co_watch_suggestion"], 0.35)
        if any(w in blob for w in ("together", "shared", "joint", "with you", "watching with")):
            gates["co_watch_suggestion"] = max(gates["co_watch_suggestion"], 0.70)
            gates["session_persistence"] = max(gates["session_persistence"], 0.55)

    if any(w in ctx_l for w in ("?", "question", "asked", "can you", "who am i", "who are you")):
        gates["question_followup"] = max(gates["question_followup"], 0.50)
    if any(w in replay_l for w in ("question", "followup", "follow-up", "asked")):
        gates["question_followup"] = max(gates["question_followup"], 0.45)

    if any(w in replay_l for w in ("long session", "hours", "marathon", "overnight", "sleep", "woke")):
        gates["session_persistence"] = max(gates["session_persistence"], 0.65)

    for tok in _owner_tokens():
        if tok and tok in blob:
            gates["owner_continuity"] = max(gates["owner_continuity"], 0.80)
    if gates["owner_continuity"] < 0.1 and ("architect" in blob or "owner" in blob):
        gates["owner_continuity"] = max(gates["owner_continuity"], 0.50)

    if any(w in blob for w in ("research", "paper", "doi", "arxiv", "pubmed", "review", "study")):
        gates["research_depth"] = max(gates["research_depth"], min(1.0, 0.55 + 0.08 * blob.count("paper")))

    return {k: _clamp(v) for k, v in gates.items()}


def tail_gate_rows(max_lines: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = multi_gate_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []
    for ln in lines[-max(1, min(max_lines, 200)) :]:
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def current_gate_state(*, root: Optional[Path] = None) -> Dict[str, float]:
    rows = tail_gate_rows(1, root=root)
    if not rows:
        return BASE_GATES.copy()
    gates = rows[-1].get("gate_biases") or {}
    return {k: _clamp(gates.get(k, 0.0)) for k in BASE_GATES}


def gate_value(name: str, *, root: Optional[Path] = None) -> float:
    return _clamp(current_gate_state(root=root).get(name, 0.0))


def apply_multi_gate_bias(
    current_context: str,
    replay_summary: str,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    min_seconds_between_writes: float = 120.0,
    force_write: bool = False,
    decay: float = 0.05,
) -> Dict[str, float]:
    """Compute multi-gate replay policy and append one locked receipt."""
    if os.environ.get("SIFTA_MULTI_GATE_REPLAY_DISABLE", "").strip() == "1":
        return BASE_GATES.copy()

    prior = current_gate_state(root=root)
    gates = compute_multi_gate_bias(
        current_context,
        replay_summary,
        prior_gates=prior,
        decay=decay,
    )
    strength = round(sum(gates.values()) / max(1, len(gates)), 4)

    if write_ledger and not force_write and min_seconds_between_writes > 0:
        rows = tail_gate_rows(1, root=root)
        if rows:
            try:
                last_ts = float(rows[-1].get("ts") or rows[-1].get("timestamp") or 0.0)
                if time.time() - last_ts < min_seconds_between_writes:
                    write_ledger = False
            except (TypeError, ValueError):
                pass

    if write_ledger:
        row: Dict[str, Any] = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "MULTI_GATE_REPLAY_POLICY",
            "context_preview": " ".join((current_context or "").split())[:200],
            "gate_biases": gates,
            "total_adaptation_strength": strength,
        }
        append_line_locked(
            multi_gate_log_path(root),
            json.dumps(row, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return gates


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_gate_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    gates = row.get("gate_biases") or {}
    parts = [f"{k}={_clamp(gates.get(k, 0.0)):.2f}" for k in BASE_GATES]
    return "MULTI-GATE REPLAY POLICY (Event 124 - bounded gate receipts): " + ", ".join(parts)


class MultiGateReplayPolicy:
    """Compatibility facade for app/tests that prefer class-style calls."""

    GATES = BASE_GATES

    @staticmethod
    def apply_multi_gate_bias(
        replay_patterns: List[str],
        *,
        root: Optional[Path] = None,
        force_write: bool = False,
    ) -> Dict[str, float]:
        replay_summary = " ".join(replay_patterns)
        return apply_multi_gate_bias(
            "",
            replay_summary,
            root=root,
            force_write=force_write,
        )

    @staticmethod
    def get_current_gate_state(*, root: Optional[Path] = None) -> Dict[str, float]:
        return current_gate_state(root=root)


__all__ = [
    "BASE_GATES",
    "MULTI_GATE_LOG_NAME",
    "MultiGateReplayPolicy",
    "apply_multi_gate_bias",
    "compute_multi_gate_bias",
    "current_gate_state",
    "gate_value",
    "multi_gate_log_path",
    "summary_for_prompt",
    "tail_gate_rows",
]
