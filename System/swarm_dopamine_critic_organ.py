"""
Event 125 - Dopamine / critic organ.

Truth label: OBSERVED. This is a deterministic owner-feedback proxy, not
midbrain spike trains. It closes the practical proof loop:

    action -> owner signal -> bounded outcome score -> multi-gate bias nudge

The output is deliberately written into the same Event 124 multi-gate ledger
that Alice's prompt and sensory gates already consume.

Covenant: locked append-only JSONL, no secrets in previews.
Kill-switch: SIFTA_DOPAMINE_CRITIC_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "dopamine_critic_log.jsonl"

_POS = ("good", "yes", "thanks", "great", "perfect", "nice", "love", "helpful", "works")
_NEG = ("no", "stop", "wrong", "bad", "ignore", "useless", "worse", "annoying")
_NEG_PHRASES = (
    "not good",
    "not helpful",
    "does not work",
    "doesn't work",
    "did not work",
    "didn't work",
    "not right",
    "not ok",
    "not okay",
)


def _clamp(value: Any, lo: float = -1.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = 0.0
    return round(min(hi, max(lo, f)), 4)


def critic_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _marker_count(blob: str, markers: tuple[str, ...]) -> int:
    count = 0
    for marker in markers:
        if re.search(rf"(?<![a-z0-9_]){re.escape(marker)}(?![a-z0-9_])", blob):
            count += 1
    return count


def score_owner_outcome_heuristic(
    owner_response: str,
    *,
    expected_positive: bool = True,
) -> float:
    """
    Map free-text owner feedback to [-1, 1].

    This is intentionally conservative. It uses word/phrase boundaries so
    words such as "now" and "know" do not count as the negative marker "no".
    Explicit UI scores should be passed as structured_score when available.
    """
    blob = " ".join((owner_response or "").lower().split())
    pos = _marker_count(blob, _POS)
    neg = _marker_count(blob, _NEG)
    for phrase in _NEG_PHRASES:
        if phrase in blob:
            neg += 1
            if "good" in phrase or "helpful" in phrase or "work" in phrase:
                pos = max(0, pos - 1)
    denom = max(1, pos + neg)
    raw = (pos - neg) / denom
    if not expected_positive:
        raw = -raw
    return _clamp(raw)


def _complete_gate_vector(previous_bias: Dict[str, float]) -> Dict[str, float]:
    try:
        from System.swarm_multi_gate_replay_policy import BASE_GATES
    except Exception:
        BASE_GATES = {}

    keys = list(BASE_GATES.keys()) or list(previous_bias.keys())
    complete: Dict[str, float] = {}
    for key in keys:
        complete[key] = _clamp(previous_bias.get(key, 0.0), 0.0, 1.0)
    return complete


def apply_critic_to_bias_vector(
    action: str,
    owner_response: str,
    previous_bias: Dict[str, float],
    *,
    expected_positive: bool = True,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    learning_rate: float = 0.12,
    structured_score: Optional[float] = None,
) -> Dict[str, float]:
    """
    Nudge each multi-gate value by learning_rate * outcome_score.

    This is the missing proof leg:
        gate change -> better/worse owner outcome -> reinforced/reversed gate.
    """
    base_vector = _complete_gate_vector(previous_bias)
    if os.environ.get("SIFTA_DOPAMINE_CRITIC_DISABLE", "").strip() == "1":
        return base_vector

    if structured_score is not None:
        outcome = _clamp(structured_score)
    else:
        outcome = score_owner_outcome_heuristic(
            owner_response, expected_positive=expected_positive
        )
    lr = _clamp(learning_rate, 0.0, 1.0)

    updated: Dict[str, float] = {}
    for key, base in base_vector.items():
        updated[key] = _clamp(base + lr * outcome, 0.0, 1.0)

    if write_ledger:
        row: Dict[str, Any] = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "DOPAMINE_CRITIC_PROXY",
            "action": (action or "")[:160],
            "owner_response_preview": " ".join((owner_response or "").split())[:200],
            "outcome_score": outcome,
            "learning_rate": lr,
            "expected_positive": bool(expected_positive),
            "previous_bias": base_vector,
            "updated_bias": updated,
        }
        append_line_locked(
            critic_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        from System.swarm_multi_gate_replay_policy import multi_gate_log_path

        mg_row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "MULTI_GATE_REPLAY_POLICY",
            "source_truth_label": "DOPAMINE_CRITIC_PROXY",
            "context_preview": f"DOPAMINE_CRITIC_UPDATE:{(action or '')[:96]}",
            "gate_biases": updated,
            "outcome_score": outcome,
            "total_adaptation_strength": round(sum(updated.values()) / max(1, len(updated)), 4),
        }
        append_line_locked(
            multi_gate_log_path(root),
            json.dumps(mg_row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return updated


def learning_summary(*, root: Optional[Path] = None, max_lines: int = 800) -> Dict[str, Any]:
    """Aggregate recent critic rows for dashboard / prompt stubs."""
    path = critic_log_path(root)
    if not path.exists():
        return {"total_feedback": 0, "avg_outcome_score": 0.0, "learning_active": False}

    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()][-max_lines:]
    total = 0
    ssum = 0.0
    for ln in lines:
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if e.get("truth_label") != "DOPAMINE_CRITIC_PROXY":
            continue
        total += 1
        try:
            ssum += float(e.get("outcome_score", 0.0))
        except (TypeError, ValueError):
            continue
    avg = round(ssum / total, 4) if total else 0.0
    return {
        "total_feedback": total,
        "avg_outcome_score": avg,
        "learning_active": total >= 3,
    }


def tail_critic_rows(max_rows: int = 16, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = critic_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out[-max(1, min(max_rows, 200)) :]


__all__ = [
    "apply_critic_to_bias_vector",
    "critic_log_path",
    "learning_summary",
    "score_owner_outcome_heuristic",
    "tail_critic_rows",
]
