"""
Event 123 - Replay -> policy hook (Stage 2 *stub*).

Turns **textual** replay digest + current context into **scalar biases** and logs
each application as an append-only receipt. This is **not** learned cortical
weights - it is a **measurable** bridge so behavior can later read the same
numbers (co-watch prior, RLHS knobs, motor policy mass - follow-on wiring).

Kill-switch: ``SIFTA_REPLAY_POLICY_DISABLE=1``.
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

POLICY_LOG_NAME = "replay_policy_adaptations.jsonl"

_BIAS_KEYS = (
    "co_watch_suggestion",
    "owner_continuity",
    "research_depth",
    "action_patience",
)


def policy_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / POLICY_LOG_NAME


def _owner_tokens() -> List[str]:
    out: List[str] = []
    for bit in (owner_name(), owner_display_name()):
        s = (bit or "").strip()
        if len(s) >= 2:
            out.append(s.lower())
    return out


def compute_replay_bias(current_context: str, replay_summary: str) -> Dict[str, float]:
    """
    Deterministic hand policy from replay + context substrings.
    Values in [0, 1]. No network; no LLM.
    """
    replay_l = (replay_summary or "").lower()
    ctx_l = (current_context or "").lower()
    blob = f"{replay_l} {ctx_l}"

    bias: Dict[str, float] = {k: 0.0 for k in _BIAS_KEYS}

    if any(w in replay_l for w in ("youtube", "youtu.be", "video", "cowatch", "co-watch")):
        bias["co_watch_suggestion"] = 0.35
        if any(w in replay_l for w in ("together", "collab", "joint", "shared", "with you")):
            bias["co_watch_suggestion"] = min(1.0, bias["co_watch_suggestion"] + 0.28)

    for tok in _owner_tokens():
        if tok and tok in blob:
            bias["owner_continuity"] = min(1.0, max(bias["owner_continuity"], 0.72))
    if bias["owner_continuity"] < 0.1 and ("architect" in blob or "owner" in blob):
        bias["owner_continuity"] = 0.45

    if any(w in replay_l for w in ("research", "paper", "doi", "arxiv", "pubmed", "review")):
        bias["research_depth"] = min(1.0, 0.55 + 0.1 * blob.count("paper"))

    if any(w in replay_l for w in ("long session", "hours", "marathon", "deep work")):
        bias["action_patience"] = 0.58
    elif "bash" in ctx_l or "pytest" in ctx_l:
        bias["action_patience"] = min(1.0, bias["action_patience"] + 0.22)

    return bias


def apply_replay_bias(
    current_context: str,
    replay_summary: str,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    min_seconds_between_writes: float = 120.0,
    force_write: bool = False,
) -> Dict[str, float]:
    """
    Compute bias and optionally append one locked JSONL receipt.
    Throttles rapid re-writes so Talk does not stamp the log every token.
    """
    if os.environ.get("SIFTA_REPLAY_POLICY_DISABLE", "").strip() == "1":
        return {k: 0.0 for k in _BIAS_KEYS}

    bias = compute_replay_bias(current_context, replay_summary)
    mean_bias = round(sum(bias.values()) / max(1, len(_BIAS_KEYS)), 4)

    if (
        write_ledger
        and not force_write
        and min_seconds_between_writes > 0
    ):
        prev = tail_policy_rows(1, root=root)
        if prev:
            try:
                last_ts = float(prev[-1].get("ts") or 0.0)
                if time.time() - last_ts < min_seconds_between_writes:
                    write_ledger = False
            except (TypeError, ValueError):
                pass

    if write_ledger:
        row: Dict[str, Any] = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "REPLAY_POLICY_BIAS",
            "context_preview": " ".join((current_context or "").split())[:200],
            "replay_influence": bias,
            "mean_bias": mean_bias,
        }
        append_line_locked(
            policy_log_path(root),
            json.dumps(row, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    try:
        from System.swarm_multi_gate_replay_policy import apply_multi_gate_bias

        apply_multi_gate_bias(
            current_context,
            replay_summary,
            root=root,
            write_ledger=write_ledger,
            min_seconds_between_writes=min_seconds_between_writes,
            force_write=force_write,
        )
    except Exception:
        pass
    return bias


def tail_policy_rows(max_lines: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = policy_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []
    for ln in lines[-max(1, min(max_lines, 200)) :]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def summary_for_prompt(*, root: Optional[Path] = None, max_rows: int = 5) -> str:
    """Compact block for system prompt - recent bias receipts only."""
    rows = tail_policy_rows(max_rows, root=root)
    multi_gate = ""
    try:
        from System.swarm_multi_gate_replay_policy import summary_for_prompt as _multi_summary

        multi_gate = _multi_summary(root=root).strip()
    except Exception:
        multi_gate = ""
    if not rows and not multi_gate:
        return ""
    lines = []
    if rows:
        lines.append(
            "REPLAY->POLICY HOOK (Event 123 - scalar biases from replay digest; hand policy, not learned weights):"
        )
    for row in rows:
        mb = row.get("mean_bias")
        prev = str(row.get("context_preview") or "")[:72]
        lines.append(f"- mean_bias={mb} preview={prev!r}")
    if multi_gate:
        lines.append(multi_gate)
    return "\n".join(lines)


__all__ = [
    "apply_replay_bias",
    "compute_replay_bias",
    "policy_log_path",
    "summary_for_prompt",
    "tail_policy_rows",
]
