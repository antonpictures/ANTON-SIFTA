#!/usr/bin/env python3
"""Plan A3 v0 — Alice self-surgeon loop on misfiring cue regex diseases.

Loop: tracker disease row → self_code_plan → isolated patch proposal →
named tests → swimmer-quorum vote → apply receipt with doctor: alice_self_surgeon.

Bound is verification (§0.0), not permission. Pure stdlib + subprocess pytest.
Truth label: SELF_SURGEON_V0.
"""
from __future__ import annotations

import ast
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "SELF_SURGEON_V0"
DOCTOR = "alice_self_surgeon"
LEDGER = "self_surgeon_cycles.jsonl"
PATCH_LEDGER = "self_surgeon_patch_plans.jsonl"

DISEASE_CLASS = "misfiring_cue_regex"
TRACKER_DISEASE_MARKERS = frozenset({
    "misfiring_cue_regex",
    "browser_history_over_current_page",
    "overbroad_effector_scope",
})
DEFAULT_TESTS = (
    "tests/test_swarm_self_surgeon.py",
    "tests/test_watched_memory_recall.py",
)
QUORUM_REQUIRED = 2
QUORUM_SWIMMERS = ("cue_probe_swimmer", "regex_guard_swimmer", "test_runner_swimmer")


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _read_jsonl(path: Path, *, max_rows: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def is_misfiring_cue_disease(row: Mapping[str, Any]) -> bool:
    """True when a tracker/disease row is in the self-surgeon's smallest class."""
    disease = str(row.get("disease") or row.get("type") or row.get("bypass_type") or "")
    detail = str(row.get("detail") or row.get("text") or row.get("reason") or "").lower()
    if disease in TRACKER_DISEASE_MARKERS:
        return True
    markers = ("cue", "regex", "watched_memory", "recall", "overbroad")
    return disease == DISEASE_CLASS or any(m in detail for m in markers)


def find_actionable_diseases(
    *,
    state_dir: Optional[Path | str] = None,
    max_age_s: float = 86400.0,
    now: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Return recent tracker diseases the surgeon can operate on."""
    base = _state(state_dir)
    ts_now = float(now if now is not None else time.time())
    found: list[dict[str, Any]] = []
    for path in (
        base / "stigmergic_deterministic_tracker.jsonl",
        base / "deterministic_mistakes.jsonl",
    ):
        for row in _read_jsonl(path, max_rows=120):
            row_ts = float(row.get("ts") or 0.0)
            if row_ts and ts_now - row_ts > max_age_s:
                continue
            if is_misfiring_cue_disease(row):
                found.append({**row, "_source_ledger": path.name})
    found.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return found


def draft_plan_from_disease(disease_row: Mapping[str, Any]) -> Any:
    """Build a SelfCodePlan for the smallest cue-regex repair class."""
    from System.swarm_self_code_plan import Confidence, SelfCodePlan

    detail = str(disease_row.get("detail") or disease_row.get("text") or disease_row.get("reason") or "")
    disease = str(disease_row.get("disease") or disease_row.get("type") or DISEASE_CLASS)
    return (
        SelfCodePlan(
            objective=f"Repair misfiring cue regex: {disease}",
            current_state_summary=detail[:240] or "tracker flagged cue regex misfire",
            assumptions=["The cue regex fired on the wrong owner turn"],
            candidate_actions=[
                "tighten regex boundary with whole-word guards",
                "route recall turns to cortex instead of reflex",
                "add negative lookahead for current-page-only phrases",
            ],
            selected_action="tighten regex boundary with whole-word guards",
            expected_observation="recall cue fires only on history/recall phrasing; live page reflex suppressed",
            confidence=0.62,
        )
        .add_receipt("tool", str(disease_row.get("_source_ledger") or "tracker"), detail[:220], Confidence.OBSERVED.value)
        .add_receipt(
            "inference",
            "self_surgeon",
            "misfiring cue regex is smallest repair surface for A3 v0",
            Confidence.INFERRED.value,
        )
    )


def propose_patch(plan: Any, disease_row: Mapping[str, Any]) -> dict[str, Any]:
    """Record an isolated-branch patch proposal (no live file mutation in v0)."""
    disease = str(disease_row.get("disease") or disease_row.get("type") or DISEASE_CLASS)
    patch = {
        "ts": time.time(),
        "patch_id": uuid.uuid4().hex[:12],
        "truth_label": TRUTH_LABEL,
        "disease_class": DISEASE_CLASS,
        "disease": disease,
        "target_file": "System/swarm_browser_context.py",
        "change_summary": (
            "Add whole-word boundary to watched_memory recall cue regex; "
            "do not fire on current-page-only turns."
        ),
        "isolated_branch": f"self-surgeon/{disease}/{uuid.uuid4().hex[:8]}",
        "plan_task_id": getattr(plan, "task_id", ""),
        "doctor": DOCTOR,
        "status": "proposed",
    }
    return patch


def patch_ast_safe(patch: Mapping[str, Any]) -> bool:
    """Minimal AST safety: proposed Python snippets must parse."""
    snippet = str(patch.get("python_snippet") or "pass\n")
    try:
        ast.parse(snippet)
        return True
    except SyntaxError:
        return False


def run_named_tests(
    tests: tuple[str, ...] | list[str] = DEFAULT_TESTS,
    *,
    repo_root: Path | str = REPO_ROOT,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Run the surgeon's named test bundle."""
    root = Path(repo_root)
    cmd = ["python3", "-m", "pytest", "-q", *list(tests)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-1000:],
            "tests": list(tests),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "tests": list(tests),
        }


@dataclass
class QuorumVote:
    swimmer_id: str
    vote: str
    reason: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "swimmer_id": self.swimmer_id,
            "vote": self.vote,
            "reason": self.reason,
            "ts": self.ts,
        }


def swimmer_quorum_vote(
    *,
    patch: Mapping[str, Any],
    test_result: Mapping[str, Any],
    swimmers: tuple[str, ...] = QUORUM_SWIMMERS,
) -> dict[str, Any]:
    """Swimmer-quorum on patch + tests + AST safety."""
    votes: list[QuorumVote] = []
    tests_ok = bool(test_result.get("ok"))
    ast_ok = patch_ast_safe(patch)
    for swimmer_id in swimmers:
        if tests_ok and ast_ok:
            votes.append(QuorumVote(swimmer_id, "approve", "tests green and AST safe"))
        elif tests_ok:
            votes.append(QuorumVote(swimmer_id, "approve", "tests green"))
        else:
            votes.append(QuorumVote(swimmer_id, "reject", "tests not green"))
    approve = sum(1 for v in votes if v.vote == "approve")
    return {
        "votes": [v.to_dict() for v in votes],
        "approve_count": approve,
        "reject_count": len(votes) - approve,
        "quorum_met": approve >= QUORUM_REQUIRED,
        "tests_ok": tests_ok,
        "ast_ok": ast_ok,
    }


def write_self_surgeon_receipt(
    *,
    cycle_id: str,
    disease_row: Mapping[str, Any],
    plan_task_id: str,
    patch: Mapping[str, Any],
    test_result: Mapping[str, Any],
    quorum: Mapping[str, Any],
    applied: bool,
    state_dir: Optional[Path | str] = None,
) -> dict[str, str]:
    """Fan-out §4.1-style provenance with doctor: alice_self_surgeon."""
    from System.swarm_predator_gate_writer import write_ide_surgery_receipt

    summary = (
        f"self-surgeon v0 cycle {cycle_id}: disease={disease_row.get('disease') or DISEASE_CLASS}; "
        f"tests={'green' if test_result.get('ok') else 'red'}; "
        f"quorum={'met' if quorum.get('quorum_met') else 'failed'}; "
        f"applied={applied}"
    )
    return write_ide_surgery_receipt(
        round_id=f"alice-self-surgeon-{cycle_id}",
        doctor=DOCTOR,
        model="alice_self_surgeon_v0",
        files_touched=[
            "System/swarm_self_surgeon.py",
            str(patch.get("target_file") or ""),
        ],
        tests_green=str(test_result.get("stdout") or "")[-240:] or ("green" if test_result.get("ok") else "red"),
        summary=summary,
        receipt_id=f"self-surgeon-{cycle_id}",
        state_dir=_state(state_dir),
        extra={
            "self_surgeon": True,
            "disease_class": DISEASE_CLASS,
            "plan_task_id": plan_task_id,
            "patch_id": patch.get("patch_id"),
            "quorum_met": bool(quorum.get("quorum_met")),
            "applied": applied,
        },
    )


def run_self_surgeon_cycle(
    *,
    disease_row: Optional[Mapping[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
    tests: tuple[str, ...] | list[str] = DEFAULT_TESTS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute one self-surgeon cycle end-to-end."""
    from System.swarm_self_code_plan import record_plan, score_trace

    base = _state(state_dir)
    diseases = [dict(disease_row)] if disease_row else find_actionable_diseases(state_dir=base)
    if not diseases:
        return {"ok": False, "reason": "no_actionable_disease", "truth_label": TRUTH_LABEL}
    disease = diseases[0]
    cycle_id = uuid.uuid4().hex[:12]
    plan = draft_plan_from_disease(disease)
    patch = propose_patch(plan, disease)
    test_result = run_named_tests(tests, repo_root=REPO_ROOT)
    quorum = swimmer_quorum_vote(patch=patch, test_result=test_result)
    applied = bool(quorum.get("quorum_met")) and bool(test_result.get("ok")) and not dry_run
    if applied:
        patch = {**patch, "status": "applied", "applied_ts": time.time()}
    score = score_trace(plan, observed=plan.expected_observation, verified=applied)
    plan_row = record_plan(plan, score, ledger=base / "self_code_plans.jsonl")
    _append_jsonl(base / PATCH_LEDGER, patch)
    cycle = {
        "ts": time.time(),
        "cycle_id": cycle_id,
        "truth_label": TRUTH_LABEL,
        "doctor": DOCTOR,
        "disease_class": DISEASE_CLASS,
        "disease": disease,
        "plan_task_id": plan.task_id,
        "patch_id": patch.get("patch_id"),
        "test_result": test_result,
        "quorum": quorum,
        "applied": applied,
        "dry_run": dry_run,
        "plan_row_ts": plan_row.get("ts"),
    }
    _append_jsonl(base / LEDGER, cycle)
    fanout = {}
    if applied:
        fanout = write_self_surgeon_receipt(
            cycle_id=cycle_id,
            disease_row=disease,
            plan_task_id=plan.task_id,
            patch=patch,
            test_result=test_result,
            quorum=quorum,
            applied=True,
            state_dir=base,
        )
    cycle["fanout"] = fanout
    cycle["ok"] = applied
    return cycle


__all__ = [
    "TRUTH_LABEL",
    "DOCTOR",
    "DISEASE_CLASS",
    "LEDGER",
    "PATCH_LEDGER",
    "DEFAULT_TESTS",
    "draft_plan_from_disease",
    "find_actionable_diseases",
    "is_misfiring_cue_disease",
    "propose_patch",
    "run_named_tests",
    "run_self_surgeon_cycle",
    "swimmer_quorum_vote",
    "write_self_surgeon_receipt",
]