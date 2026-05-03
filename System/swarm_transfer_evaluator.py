"""
Event 126 - Transfer evaluator.

Truth label: GENERALIZATION_TRIAL. This module tests the last AGI-class proof
gap as a receipt:

    novel task -> baseline policy score
    novel task -> replay-informed policy score
    transfer_gain = transfer_reward - baseline_reward

This is still an evaluator, not a benchmark certificate. It gives the Swarm a
repeatable way to prove or falsify transfer across new task descriptions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_multi_gate_replay_policy import BASE_GATES, current_gate_state
from System.swarm_persistent_owner_history import state_dir

TRIAL_LOG_NAME = "generalization_trials.jsonl"

SKILL_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "co_watch_suggestion": (
        "watch",
        "youtube",
        "video",
        "movie",
        "screen",
        "cowatch",
        "co-watch",
    ),
    "question_followup": (
        "?",
        "question",
        "answer",
        "why",
        "what",
        "who",
        "can you",
        "explain",
    ),
    "session_persistence": (
        "sleep",
        "boot",
        "restart",
        "continue",
        "remember",
        "overnight",
        "gap",
        "schedule",
    ),
    "research_depth": (
        "research",
        "paper",
        "study",
        "doi",
        "arxiv",
        "prove",
        "evidence",
        "benchmark",
    ),
    "owner_continuity": (
        "owner",
        "george",
        "architect",
        "identity",
        "life",
        "schedule",
        "body",
    ),
    "media_context_sensitivity": (
        "ambient",
        "background",
        "media",
        "audio",
        "noise",
        "noisy",
        "paused",
        "stt",
    ),
}


def transfer_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / TRIAL_LOG_NAME


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return round(min(hi, max(lo, f)), 4)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]{2,}", _normalize_text(text))}


def task_fingerprint(task_description: str) -> str:
    normalized = _normalize_text(task_description)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"TASK_{digest}"


def _similarity(a: str, b: str) -> float:
    at = _tokens(a)
    bt = _tokens(b)
    if not at or not bt:
        return 0.0
    return round(len(at & bt) / len(at | bt), 4)


def tail_transfer_rows(max_rows: int = 64, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = transfer_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, min(max_rows, 500)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def novelty_score(
    task_description: str,
    *,
    root: Optional[Path] = None,
    prior_rows: Optional[Sequence[Dict[str, Any]]] = None,
) -> float:
    rows = list(prior_rows) if prior_rows is not None else tail_transfer_rows(200, root=root)
    if not rows:
        return 1.0
    task = _normalize_text(task_description)
    max_sim = 0.0
    for row in rows:
        prior = str(row.get("task_description") or row.get("task_new") or "")
        max_sim = max(max_sim, _similarity(task, prior))
    return _clamp(1.0 - max_sim)


def is_novel_task(
    task_description: str,
    *,
    root: Optional[Path] = None,
    similarity_threshold: float = 0.72,
) -> bool:
    rows = tail_transfer_rows(200, root=root)
    task_id = task_fingerprint(task_description)
    for row in rows:
        if row.get("task_id") == task_id:
            return False
        prior = str(row.get("task_description") or row.get("task_new") or "")
        if _similarity(task_description, prior) >= similarity_threshold:
            return False
    return True


def infer_source_skills(task_description: str, gates: Optional[Dict[str, Any]] = None) -> List[str]:
    blob = _normalize_text(task_description)
    found: List[str] = []
    for skill, keywords in SKILL_KEYWORDS.items():
        if any(keyword in blob for keyword in keywords):
            found.append(skill)

    if found:
        return found

    gate_state = gates or {}
    ranked = sorted(
        ((skill, _clamp(gate_state.get(skill, 0.0))) for skill in BASE_GATES),
        key=lambda item: item[1],
        reverse=True,
    )
    return [skill for skill, value in ranked[:2] if value > 0.0] or ["owner_continuity"]


def _gate_vector(gates: Optional[Dict[str, Any]]) -> Dict[str, float]:
    source = gates or {}
    return {key: _clamp(source.get(key, 0.0)) for key in BASE_GATES}


def score_policy(
    task_description: str,
    gates: Optional[Dict[str, Any]],
    *,
    source_skills: Optional[Iterable[str]] = None,
) -> float:
    gate_state = _gate_vector(gates)
    skills = list(source_skills) if source_skills is not None else infer_source_skills(
        task_description, gate_state
    )
    if not skills:
        skills = ["owner_continuity"]

    coverage = sum(gate_state.get(skill, 0.0) for skill in skills) / max(1, len(skills))
    clarity = min(1.0, len(_tokens(task_description)) / 18.0)
    composition = min(1.0, len(set(skills)) / 4.0)
    score = 0.25 + (0.50 * coverage) + (0.15 * clarity) + (0.10 * composition)
    return _clamp(score)


def _option_name(source_skills: Sequence[str]) -> str:
    if not source_skills:
        return "idle"
    if len(source_skills) == 1:
        return source_skills[0]
    digest = hashlib.sha256(",".join(sorted(source_skills)).encode("utf-8")).hexdigest()[:8]
    return f"composed_option_{digest}"


def evaluate_transfer_trial(
    task_description: str,
    *,
    replay_gates: Optional[Dict[str, Any]] = None,
    baseline_gates: Optional[Dict[str, Any]] = None,
    architect_reward: Optional[float] = None,
    actual_outcome: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """
    Compare baseline behavior against replay-informed behavior on one task.

    If architect_reward is supplied, it becomes the transfer_reward. Otherwise
    the transfer_reward is the replay-informed policy score.
    """
    if os.environ.get("SIFTA_TRANSFER_EVALUATOR_DISABLE", "").strip() == "1":
        write_ledger = False

    replay_state = _gate_vector(replay_gates if replay_gates is not None else current_gate_state(root=root))
    baseline_state = _gate_vector(baseline_gates or BASE_GATES)
    source_skills = infer_source_skills(task_description, replay_state)
    baseline_reward = score_policy(task_description, baseline_state, source_skills=source_skills)
    replay_policy_score = score_policy(task_description, replay_state, source_skills=source_skills)
    transfer_reward = (
        _clamp(architect_reward, -1.0, 1.0)
        if architect_reward is not None
        else replay_policy_score
    )
    transfer_gain = round(transfer_reward - baseline_reward, 4)
    avg_gate = sum(replay_state.get(skill, 0.0) for skill in source_skills) / max(
        1, len(source_skills)
    )
    uncertainty = _clamp(1.0 - avg_gate)
    cost = _clamp(0.08 + 0.04 * max(0, len(source_skills) - 1))
    risk = _clamp(0.10 + 0.20 * uncertainty)
    td_error = round(transfer_reward - replay_policy_score, 4)
    novelty = novelty_score(task_description, root=root)

    gate_updates = {
        skill: round(replay_state.get(skill, 0.0) - baseline_state.get(skill, 0.0), 4)
        for skill in source_skills
    }
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "GENERALIZATION_TRIAL",
        "kind": "TRANSFER_TEST",
        "task_id": task_fingerprint(task_description),
        "task_description": " ".join((task_description or "").split())[:240],
        "task_new": " ".join((task_description or "").split())[:240],
        "novel_task": is_novel_task(task_description, root=root),
        "novelty_score": novelty,
        "source_skills": source_skills,
        "option_selected": _option_name(source_skills),
        "baseline_reward": baseline_reward,
        "replay_policy_score": replay_policy_score,
        "transfer_reward": transfer_reward,
        "transfer_gain": transfer_gain,
        "uncertainty": uncertainty,
        "risk": risk,
        "cost": cost,
        "architect_reward": architect_reward,
        "td_error": td_error,
        "actual_outcome": actual_outcome or {},
        "gate_updates": gate_updates,
    }

    if write_ledger:
        append_line_locked(
            transfer_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def aggregate_transfer_stats(
    *,
    root: Optional[Path] = None,
    max_rows: int = 200,
) -> Dict[str, Any]:
    rows = [
        row
        for row in tail_transfer_rows(max_rows, root=root)
        if row.get("truth_label") == "GENERALIZATION_TRIAL"
    ]
    gains: List[float] = []
    novel = 0
    for row in rows:
        try:
            gains.append(float(row.get("transfer_gain", 0.0)))
        except (TypeError, ValueError):
            gains.append(0.0)
        if row.get("novel_task"):
            novel += 1

    if not gains:
        return {
            "trial_count": 0,
            "novel_trial_count": 0,
            "mean_transfer_gain": 0.0,
            "positive_rate": 0.0,
            "transfer_proven": False,
        }

    mean_gain = round(sum(gains) / len(gains), 4)
    positive_rate = round(sum(1 for gain in gains if gain > 0.0) / len(gains), 4)
    return {
        "trial_count": len(gains),
        "novel_trial_count": novel,
        "mean_transfer_gain": mean_gain,
        "positive_rate": positive_rate,
        "transfer_proven": mean_gain > 0.0 and positive_rate > 0.5,
    }


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    stats = aggregate_transfer_stats(root=root)
    if not stats["trial_count"]:
        return ""
    return (
        "TRANSFER EVALUATOR (Event 126): "
        f"trials={stats['trial_count']}, novel={stats['novel_trial_count']}, "
        f"mean_gain={stats['mean_transfer_gain']:.2f}, "
        f"positive_rate={stats['positive_rate']:.2f}, "
        f"transfer_proven={stats['transfer_proven']}"
    )


__all__ = [
    "TRIAL_LOG_NAME",
    "aggregate_transfer_stats",
    "evaluate_transfer_trial",
    "infer_source_skills",
    "is_novel_task",
    "novelty_score",
    "score_policy",
    "summary_for_prompt",
    "tail_transfer_rows",
    "task_fingerprint",
    "transfer_log_path",
]
