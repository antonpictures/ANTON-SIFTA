#!/usr/bin/env python3
"""
System/swarm_eval_harness.py — SIFTA Self-Eval Harness (CS153 style)

Alice grades herself on domain traces instead of generic benchmarks.

This organ turns the "read the traces, label right/wrong, skillify" loop
into running, receipted code.

Truth label: EVAL_HARNESS_V0
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import System.stigmergic_memory_bus as memory_bus

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EVAL_DIR = _STATE / "eval"
_GOLDEN_DIR = _REPO / "data" / "eval"
_METRICS = _EVAL_DIR / "skill_invoke_metrics.jsonl"
_RECEIPTS = _STATE / "work_receipts.jsonl"


@dataclass
class EvalTurn:
    turn_id: str
    target: str                    # "hybrid_recall" or "recall_context_block"
    seed_memories: List[Dict[str, Any]]
    query: str
    expect: Dict[str, Any]


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _write_eval_receipt(report: Dict[str, Any], *, receipts_path: Path, metrics_path: Path) -> str:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "work_type": "EVAL_RUN",
        "pass_rate": report["pass_rate"],
        "passed": report["passed"],
        "failed": report["failed"],
        "golden_hash": report.get("golden_hash"),
        "metrics_path": str(metrics_path),
        "source": "swarm_eval_harness",
    }
    _append_jsonl(receipts_path, row)
    return row["trace_id"]


@contextmanager
def _isolated_memory_bus(root: Path):
    old_paths = (
        memory_bus.LEDGER_DIR,
        memory_bus.LEDGER_FILE,
        memory_bus.MEMORY_EPISTEMOLOGY_AUDIT,
        memory_bus.STGM_LOG_FILE,
    )
    memory_bus.LEDGER_DIR = root
    memory_bus.LEDGER_FILE = root / "memory_ledger.jsonl"
    memory_bus.MEMORY_EPISTEMOLOGY_AUDIT = root / "memory_epistemology_audit.jsonl"
    memory_bus.STGM_LOG_FILE = root / "stgm_memory_rewards.jsonl"

    try:
        import System.proof_of_useful_work as proof

        old_issue_work_receipt = proof.issue_work_receipt
        proof.issue_work_receipt = lambda *args, **kwargs: None
    except Exception:
        proof = None
        old_issue_work_receipt = None

    try:
        import System.tab_heartbeat as heartbeat

        old_pin_to_web = heartbeat.HeartbeatBus.pin_to_web
        heartbeat.HeartbeatBus.pin_to_web = lambda self, *args, **kwargs: None
    except Exception:
        heartbeat = None
        old_pin_to_web = None

    try:
        import System.lagrangian_constraint_manifold as lagrangian

        old_lagrangian_paths = (
            lagrangian._DUAL_STATE_PATH,
            lagrangian._RESIDUE_LOG_PATH,
        )
        lagrangian._DUAL_STATE_PATH = root / "lagrangian_multipliers.json"
        lagrangian._RESIDUE_LOG_PATH = root / "constraint_residues.jsonl"
    except Exception:
        lagrangian = None
        old_lagrangian_paths = None

    try:
        bus = memory_bus.StigmergicMemoryBus(architect_id="IOAN_M5")
        bus._marrow = None
        yield bus
    finally:
        if proof is not None and old_issue_work_receipt is not None:
            proof.issue_work_receipt = old_issue_work_receipt
        if heartbeat is not None and old_pin_to_web is not None:
            heartbeat.HeartbeatBus.pin_to_web = old_pin_to_web
        if lagrangian is not None and old_lagrangian_paths is not None:
            (
                lagrangian._DUAL_STATE_PATH,
                lagrangian._RESIDUE_LOG_PATH,
            ) = old_lagrangian_paths
        (
            memory_bus.LEDGER_DIR,
            memory_bus.LEDGER_FILE,
            memory_bus.MEMORY_EPISTEMOLOGY_AUDIT,
            memory_bus.STGM_LOG_FILE,
        ) = old_paths


def load_golden_turns(path: Path) -> List[EvalTurn]:
    turns: List[EvalTurn] = []
    header = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if header is None and "truth_label" in obj:
            header = obj
            continue
        turns.append(EvalTurn(**obj))
    return turns


def run_eval_pack(
    golden_path: Optional[Path] = None,
    use_judge: bool = False,
    judge_fn: Optional[Callable[[str, str], bool]] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """
    Run the golden set. Deterministic by default.
    use_judge=True is only allowed with an explicit local judge_fn.
    """
    if use_judge and judge_fn is None:
        raise ValueError("use_judge=True requires an explicit local judge_fn")

    if golden_path is None:
        golden_path = _GOLDEN_DIR / "cs153_golden_turns.jsonl"
    if metrics_path is None:
        metrics_path = _METRICS
    if receipts_path is None:
        receipts_path = _RECEIPTS

    if not golden_path.exists():
        raise FileNotFoundError(f"Golden set not found: {golden_path}")

    golden_hash = _sha256(golden_path)
    turns = load_golden_turns(golden_path)

    results = []
    passed = 0
    failed = 0

    for turn in turns:
        with tempfile.TemporaryDirectory(prefix=f"sifta_eval_{turn.turn_id}_") as tmp:
            # Fresh temp bus per turn — never touches real owner memory.
            with _isolated_memory_bus(Path(tmp)) as bus:
                # Seed memories with correct epistemic labels (Slice 1+2 surface)
                for mem in turn.seed_memories:
                    bus.remember(
                        mem["text"],
                        mem.get("app_context", "talk_to_alice"),
                        epistemic_label=mem.get("epistemic_label"),
                        links=mem.get("links", []),
                    )

                # Run the target
                if turn.target == "hybrid_recall":
                    scored = bus.hybrid_recall(turn.query, "talk_to_alice", top_k=5)
                    actual_texts = [t.raw_text for _, t, _ in scored]
                    actual_labels = [b["label"] for _, t, b in scored]
                elif turn.target == "recall_context_block":
                    block = bus.recall_context_block(turn.query, "talk_to_alice", top_k=5)
                    actual_texts = [block] if block else []
                    actual_labels = []
                else:
                    actual_texts = []
                    actual_labels = []

        # Deterministic scoring (no LLM required for these gates)
        e = turn.expect
        turn_pass = True
        detail = {}

        if "must_include_substring" in e:
            ok = any(e["must_include_substring"].lower() in t.lower() for t in actual_texts)
            if not ok:
                turn_pass = False
            detail["must_include"] = ok

        if "must_exclude_substring" in e:
            bad = any(e["must_exclude_substring"].lower() in t.lower() for t in actual_texts)
            if bad:
                turn_pass = False
            detail["must_exclude"] = not bad

        if "must_be_empty" in e:
            empty_ok = not actual_texts if e["must_be_empty"] else bool(actual_texts)
            if not empty_ok:
                turn_pass = False
            detail["empty_ok"] = empty_ok

        if "must_top_label_in" in e:
            top_ok = bool(actual_labels) and actual_labels[0] in e["must_top_label_in"]
            if not top_ok:
                turn_pass = False
            detail["top_label_ok"] = top_ok

        if turn_pass:
            passed += 1
        else:
            failed += 1

        trace_id = str(uuid.uuid4())
        results.append({
            "turn_id": turn.turn_id,
            "passed": turn_pass,
            "score": 1.0 if turn_pass else 0.0,
            "detail": detail,
            "trace_id": trace_id,
        })

        # Write per-turn metric (the "label right/wrong" surface)
        _append_jsonl(metrics_path, {
            "ts": time.time(),
            "turn_id": turn.turn_id,
            "target": turn.target,
            "passed": turn_pass,
            "score": 1.0 if turn_pass else 0.0,
            "trace_id": trace_id,
            "judge_used": use_judge,
        })

    report = {
        "pass_rate": passed / len(turns) if turns else 0.0,
        "passed": passed,
        "failed": failed,
        "turns": results,
        "golden_hash": golden_hash,
        "ts": time.time(),
        "use_judge": use_judge,
    }

    if write_receipt:
        receipt_id = _write_eval_receipt(
            report,
            receipts_path=receipts_path,
            metrics_path=metrics_path,
        )
        report["eval_receipt_id"] = receipt_id
    return report


__all__ = ["run_eval_pack", "load_golden_turns", "EvalTurn"]
