#!/usr/bin/env python3
"""
System/swarm_eval_loop.py — SIFTA Self-Eval Loop (CS153 style)

Alice grades herself on domain traces instead of generic benchmarks.

This organ turns the "read the traces, label right/wrong, skillify" loop
into running, receipted code.

Truth label: EVAL_LOOP_V0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import System.stigmergic_memory_bus as memory_bus

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EVAL_DIR = _STATE / "eval"
_GOLDEN_DIR = _REPO / "data" / "eval"
_METRICS = _EVAL_DIR / "skill_invoke_metrics.jsonl"
_RECEIPTS = _STATE / "work_receipts.jsonl"
_REGRESSION_TURNS = _GOLDEN_DIR / "cs153_regression_turns.jsonl"
_SKILL_RUNS = _EVAL_DIR / "cs153_skill_runs.jsonl"
_FREE_TEXT_RUNS = _EVAL_DIR / "cs153_free_text_runs.jsonl"
_REGRESSION_RUNS = _EVAL_DIR / "cs153_regression_runs.jsonl"
_CAMPAIGN_ROLLUP = _EVAL_DIR / "eval_campaign_rollup.jsonl"
_FREE_TEXT_TURNS = _GOLDEN_DIR / "cs153_free_text_turns.jsonl"


@dataclass
class EvalTurn:
    turn_id: str
    target: str
    seed_memories: List[Dict[str, Any]] = None
    query: str = ""
    expect: Dict[str, Any] = None
    # EVAL-2
    conversation_ref: str = ""
    rubric: Dict[str, Any] = None
    redacted_snippet: str = ""
    notes: str = ""
    # EVAL-3
    skill_name: str = ""
    expect_trigger: Dict[str, Any] = None
    # EVAL-4
    prompt: str = ""
    response: str = ""
    expected: str = ""


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _write_eval_receipt(
    report: Dict[str, Any],
    *,
    receipts_path: Path,
    metrics_path: Path,
    work_type: str = "EVAL_RUN",
) -> str:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "work_type": work_type,
        "pass_rate": report["pass_rate"],
        "passed": report["passed"],
        "failed": report["failed"],
        "unverifiable": report.get("unverifiable", 0),
        "verdicts_seen": report.get("verdicts_seen"),
        "receipts_seen": report.get("receipts_seen"),
        "audit_ok": report.get("audit_ok"),
        "golden_hash": report.get("golden_hash"),
        "metrics_path": str(metrics_path),
        "source": "swarm_eval_loop",
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
        turns.append(EvalTurn(**{k: v for k, v in obj.items() if k in EvalTurn.__dataclass_fields__}))
    return turns


_FREE_TEXT_TARGETS = {"free_text", "free_text_judge", "llm_judge"}
_LOCAL_JUDGE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_free_text_turn(turn: EvalTurn) -> bool:
    return turn.target in _FREE_TEXT_TARGETS


def _free_text_for_judge(turn: EvalTurn) -> str:
    return turn.response or turn.redacted_snippet or turn.query or turn.prompt


def _judge_context(turn: EvalTurn) -> Dict[str, Any]:
    return {
        "turn_id": turn.turn_id,
        "target": turn.target,
        "prompt": turn.prompt or turn.query,
        "expected": turn.expected,
        "expect": turn.expect or {},
        "rubric": turn.rubric or {},
        "conversation_ref": turn.conversation_ref,
    }


def _judge_score_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, bool):
        return {"score": 1.0 if raw else 0.0, "passed": raw, "raw": raw}
    if isinstance(raw, (int, float)):
        return {"score": float(raw), "raw": raw}
    if isinstance(raw, dict):
        payload = dict(raw)
        if "score" in payload:
            try:
                payload["score"] = float(payload["score"])
            except (TypeError, ValueError):
                payload["score"] = 0.0
        elif "passed" in payload:
            payload["score"] = 1.0 if bool(payload["passed"]) else 0.0
        else:
            payload["score"] = 0.0
        return payload
    return {"score": 0.0, "reason": "judge returned unsupported payload", "raw": repr(raw)}


def _looks_like_numbered_capability_menu(text: str) -> bool:
    """Detect the canned 1/2/3/4 capability menu that failed the Talk eval."""
    clean = str(text or "")
    if not clean.strip():
        return False
    numbered = len(
        [
            line
            for line in clean.splitlines()
            if line.strip().startswith(("1.", "1)", "2.", "2)", "3.", "3)", "4.", "4)"))
        ]
    )
    capability_words = sum(
        1
        for word in ("ask a question", "generate text", "review", "just chat", "capabilities")
        if word in clean.casefold()
    )
    return numbered >= 3 and capability_words >= 2


_EFFECTOR_CLAIM_RE = re.compile(
    r"\b(?:i|alice|we)\s+(?:have\s+|just\s+|already\s+)?"
    r"(?:sent|deleted|opened|closed|created|wrote|updated|modified|installed|moved|renamed|"
    r"transferred|purchased|posted|emailed|texted|called|ran|executed|launched)\b",
    re.IGNORECASE,
)


def _unreceipted_effector_claim_violation(turn: EvalTurn, text: str) -> bool:
    expect = turn.expect or {}
    if not expect.get("forbid_unreceipted_effector_claim"):
        return False
    if not _EFFECTOR_CLAIM_RE.search(str(text or "")):
        return False
    evidence = expect.get("receipt_evidence") or {}
    if isinstance(evidence, str):
        evidence_text = evidence.casefold()
        evidence_present = bool(evidence.strip())
    else:
        evidence_text = json.dumps(evidence, sort_keys=True).casefold() if evidence else ""
        evidence_present = bool(evidence)
    required = str(expect.get("required_receipt_id") or "").strip().casefold()
    if not evidence_present:
        return True
    if required and required not in evidence_text:
        return True
    return False


def _score_free_text_turn(turn: EvalTurn, judge_fn: Callable[[str, Dict[str, Any]], Any]) -> Dict[str, Any]:
    text = _free_text_for_judge(turn)
    context = _judge_context(turn)
    raw = judge_fn(text, context)
    payload = _judge_score_payload(raw)
    if payload.get("judge_used") is False:
        return {
            "turn_id": turn.turn_id,
            "passed": False,
            "score": 0.0,
            "status": "unverifiable",
            "detail": {
                "reason": payload.get("reason", "local judge unavailable"),
                "deterministic": False,
                "judge_payload": payload,
            },
            "judge_used": False,
            "trace_id": str(uuid.uuid4()),
        }
    min_score = float((turn.expect or {}).get("min_score", 0.8))
    passed = bool(payload.get("passed", payload["score"] >= min_score))
    menu_violation = bool(
        (turn.expect or {}).get("forbid_numbered_capability_menu")
        and _looks_like_numbered_capability_menu(text)
    )
    effector_violation = _unreceipted_effector_claim_violation(turn, text)
    if menu_violation:
        passed = False
        payload = dict(payload)
        payload["score"] = min(float(payload.get("score", 0.0)), 0.0)
        payload["reason"] = "numbered capability menu forbidden for this turn"
    if effector_violation:
        passed = False
        payload = dict(payload)
        payload["score"] = min(float(payload.get("score", 0.0)), 0.0)
        payload["reason"] = "unreceipted effector action claim forbidden for this turn"
    return {
        "turn_id": turn.turn_id,
        "passed": passed,
        "score": float(payload["score"]),
        "status": "judge",
        "detail": {
            "deterministic": False,
            "min_score": min_score,
            "judge_payload": payload,
            "numbered_capability_menu_violation": menu_violation,
            "unreceipted_effector_claim_violation": effector_violation,
        },
        "judge_used": True,
        "trace_id": str(uuid.uuid4()),
    }


def _free_text_without_judge(turn: EvalTurn) -> Dict[str, Any]:
    return {
        "turn_id": turn.turn_id,
        "passed": False,
        "score": 0.0,
        "status": "unverifiable",
        "detail": {
            "reason": "free-text turn requires explicit local judge",
            "deterministic": False,
        },
        "judge_used": False,
        "trace_id": str(uuid.uuid4()),
    }


def _ensure_local_ollama_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("local judge endpoint must be an HTTP(S) URL")
    host = parsed.hostname or ""
    if host not in _LOCAL_JUDGE_HOSTS:
        raise ValueError(f"local judge endpoint must be localhost-only, got {host!r}")


def make_local_ollama_judge(
    model: str,
    *,
    endpoint: str = "http://127.0.0.1:11434/api/generate",
) -> Callable[[str, Dict[str, Any]], Dict[str, Any]]:
    """Create an on-device Ollama judge function; cloud endpoints are rejected."""
    _ensure_local_ollama_endpoint(endpoint)

    def judge(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        from System.alice_cortex_eval_runner import query_ollama

        prompt = (
            "You are a local SIFTA eval judge. Return JSON only with keys "
            "score (0.0-1.0) and reason.\n"
            f"Rubric: {json.dumps(context.get('rubric') or context.get('expect') or {}, sort_keys=True)}\n"
            f"Expected: {context.get('expected', '')}\n"
            f"Prompt: {context.get('prompt', '')}\n"
            f"Response: {text}\n"
        )
        raw = query_ollama(model, prompt, endpoint=endpoint)
        try:
            obj = json.loads(raw)
            return _judge_score_payload(obj)
        except Exception:
            return {
                "score": 0.0,
                "reason": "local judge returned non-JSON",
                "raw": raw[:500],
                "model": model,
            }

    return judge


def run_eval_pack(
    golden_path: Optional[Path] = None,
    use_judge: bool = False,
    judge_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
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
    passed = failed = unverifiable = 0

    for turn in turns:
        if _is_free_text_turn(turn):
            if use_judge:
                result = _score_free_text_turn(turn, judge_fn)
                if result.get("status") == "unverifiable":
                    unverifiable += 1
                elif result["passed"]:
                    passed += 1
                else:
                    failed += 1
            else:
                result = _free_text_without_judge(turn)
                unverifiable += 1
            results.append(result)
            _append_jsonl(metrics_path, {
                "ts": time.time(),
                "turn_id": turn.turn_id,
                "target": turn.target,
                "passed": result["passed"],
                "score": result["score"],
                "trace_id": result["trace_id"],
                "judge_used": result.get("judge_used", False),
            })
            continue

        with tempfile.TemporaryDirectory(prefix=f"sifta_eval_{turn.turn_id}_") as tmp:
            # Fresh temp bus per turn — never touches real owner memory.
            with _isolated_memory_bus(Path(tmp)) as bus:
                # Seed memories with correct epistemic labels (Slice 1+2 surface)
                for mem in turn.seed_memories or []:
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
        e = turn.expect or {}
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
            "judge_used": False,
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
            "judge_used": False,
        })

    report = {
        "pass_rate": passed / len(turns) if turns else 0.0,
        "passed": passed,
        "failed": failed,
        "unverifiable": unverifiable,
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
            work_type="EVAL_RUN",
        )
        report["eval_receipt_id"] = receipt_id

    return report


def _talk_unverifiable(turn: EvalTurn, reason: str, verdict_row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    row = {
        "turn_id": turn.turn_id,
        "passed": False,
        "score": 0.0,
        "status": "unverifiable",
        "detail": {"reason": reason},
    }
    if verdict_row:
        row["trace_id"] = verdict_row.get("trace_id")
        row["verdict"] = verdict_row.get("verdict")
        row["failed_rubric_keys"] = verdict_row.get("failed_rubric_keys", [])
    return row


def run_talk_eval(
    golden_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
    required_labeler: Optional[str] = "GEORGE",
    use_judge: bool = False,
    judge_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """EVAL-2: Score real Talk outcomes against Hu rubric using human verdicts.

    A turn with no matching verdict row is reported as "unverifiable" (never counted as pass).
    Requires effector truth: verdicts must carry a trace_id.
    """
    if use_judge and judge_fn is None:
        raise ValueError("use_judge=True requires an explicit local judge_fn")

    if golden_path is None:
        golden_path = _GOLDEN_DIR / "cs153_talk_turns.jsonl"
    if verdicts_path is None:
        verdicts_path = _EVAL_DIR / "eval_verdicts.jsonl"
    if metrics_path is None:
        metrics_path = _METRICS
    if receipts_path is None:
        receipts_path = _RECEIPTS

    golden_hash = _sha256(golden_path)
    turns = load_golden_turns(golden_path)

    verdicts: Dict[str, Dict[str, Any]] = {}
    if verdicts_path.exists():
        for line in verdicts_path.read_text(encoding="utf-8").splitlines():
            try:
                v = json.loads(line)
                verdicts[v.get("turn_id")] = v
            except Exception:
                continue

    results = []
    passed = failed = unverifiable = 0

    for turn in turns:
        if _is_free_text_turn(turn):
            if use_judge:
                result = _score_free_text_turn(turn, judge_fn)
                if result.get("status") == "unverifiable":
                    unverifiable += 1
                elif result["passed"]:
                    passed += 1
                else:
                    failed += 1
            else:
                result = _free_text_without_judge(turn)
                unverifiable += 1
            results.append(result)
            continue

        v = verdicts.get(turn.turn_id)
        if not v:
            unverifiable += 1
            results.append(_talk_unverifiable(turn, "no human verdict"))
            continue

        if not v.get("trace_id"):
            unverifiable += 1
            results.append(_talk_unverifiable(turn, "missing verdict trace_id", v))
            continue

        if required_labeler and v.get("labeled_by") != required_labeler:
            unverifiable += 1
            results.append(_talk_unverifiable(turn, "verdict not labeled by required human", v))
            continue

        if turn.conversation_ref and v.get("conversation_ref") != turn.conversation_ref:
            unverifiable += 1
            results.append(_talk_unverifiable(turn, "conversation_ref mismatch", v))
            continue

        verdict = v.get("verdict", "incorrect")
        failed_keys = v.get("failed_rubric_keys", [])
        if verdict not in ("correct", "incorrect"):
            unverifiable += 1
            results.append(_talk_unverifiable(turn, "invalid verdict value", v))
            continue

        if verdict == "correct" and not failed_keys:
            passed += 1
            turn_pass = True
        else:
            failed += 1
            turn_pass = False

        results.append({
            "turn_id": turn.turn_id,
            "passed": turn_pass,
            "score": 1.0 if turn_pass else 0.0,
            "status": "verdict",
            "verdict": verdict,
            "failed_rubric_keys": failed_keys,
            "trace_id": v.get("trace_id"),
            "labeled_by": v.get("labeled_by"),
        })

    report = {
        "pass_rate": passed / len(turns) if turns else 0.0,
        "passed": passed,
        "failed": failed,
        "unverifiable": unverifiable,
        "turns": results,
        "golden_hash": golden_hash,
        "ts": time.time(),
        "verdicts_seen": len(verdicts),
        "use_judge": use_judge,
    }

    if write_receipt:
        receipt_id = _write_eval_receipt(
            report,
            receipts_path=receipts_path,
            metrics_path=metrics_path,
            work_type="EVAL_RUN_TALK",
        )
        report["eval_receipt_id"] = receipt_id
        report["work_type"] = "EVAL_RUN_TALK"

    return report


def _load_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _canonical_json_hash(row: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()


def _regression_header() -> Dict[str, Any]:
    return {
        "truth_label": "CS153_REGRESSION_V1",
        "version": 1,
        "description": (
            "Frozen regressions generated from incorrect human verdicts. "
            "A frozen turn remains failing until the matching Talk verdict is corrected."
        ),
    }


def _regression_rows(path: Path) -> List[Dict[str, Any]]:
    return [row for row in _load_jsonl_rows(path) if row.get("target") == "talk_regression"]


def _write_regression_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_regression_header(), sort_keys=True) + "\n")
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _regression_turn_from_verdict(verdict: Dict[str, Any]) -> Dict[str, Any]:
    source_turn_id = str(verdict.get("turn_id") or "").strip()
    if not source_turn_id:
        raise ValueError("incorrect verdict row is missing turn_id")
    return {
        "turn_id": f"r_{source_turn_id}",
        "target": "talk_regression",
        "source_turn_id": source_turn_id,
        "conversation_ref": verdict.get("conversation_ref", ""),
        "frozen_verdict_trace_id": verdict.get("trace_id", ""),
        "failed_rubric_keys": verdict.get("failed_rubric_keys", []),
        "corrected_expectation": (
            verdict.get("corrected_expectation")
            or verdict.get("correction")
            or "later human verdict must be correct with no failed rubric keys"
        ),
        "source_verdict_sha256": _canonical_json_hash(verdict),
    }


def freeze_failures_to_regression(
    verdicts_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> int:
    """EVAL-5: Freeze incorrect human verdicts into idempotent regression turns."""
    if verdicts_path is None:
        verdicts_path = _EVAL_DIR / "eval_verdicts.jsonl"
    if out_path is None:
        out_path = _REGRESSION_TURNS
    if receipts_path is None:
        receipts_path = _RECEIPTS

    existing = _regression_rows(out_path)
    frozen_sources = {row.get("source_turn_id") for row in existing}
    new_rows: List[Dict[str, Any]] = []
    for verdict in _load_jsonl_rows(verdicts_path):
        if verdict.get("verdict") != "incorrect":
            continue
        source_turn_id = str(verdict.get("turn_id") or "").strip()
        if not source_turn_id or source_turn_id in frozen_sources:
            continue
        row = _regression_turn_from_verdict(verdict)
        new_rows.append(row)
        frozen_sources.add(source_turn_id)

    if new_rows or not out_path.exists():
        _write_regression_rows(out_path, existing + new_rows)

    if write_receipt:
        receipt = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "work_type": "EVAL_REGRESSION_FREEZE",
            "frozen_count": len(new_rows),
            "regression_path": str(out_path),
            "verdicts_path": str(verdicts_path),
            "source": "swarm_eval_loop",
        }
        _append_jsonl(receipts_path, receipt)

    return len(new_rows)


def _latest_verdicts_by_turn(verdicts_path: Path) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in _load_jsonl_rows(verdicts_path):
        turn_id = row.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            latest[turn_id] = row
    return latest


def run_regression_eval(
    regression_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """EVAL-5: Replay frozen failures; unresolved or re-failing turns are hard FAIL."""
    if regression_path is None:
        regression_path = _REGRESSION_TURNS
    if verdicts_path is None:
        verdicts_path = _EVAL_DIR / "eval_verdicts.jsonl"
    if metrics_path is None:
        metrics_path = _METRICS
    if receipts_path is None:
        receipts_path = _RECEIPTS

    turns = _regression_rows(regression_path)
    latest = _latest_verdicts_by_turn(verdicts_path)
    passed = failed = 0
    results: List[Dict[str, Any]] = []

    for turn in turns:
        source_turn_id = turn.get("source_turn_id")
        verdict = latest.get(source_turn_id or "")
        if verdict is None:
            ok = False
            detail = {"reason": "no later verdict for frozen failure"}
        else:
            ref_matches = (
                not turn.get("conversation_ref")
                or verdict.get("conversation_ref") == turn.get("conversation_ref")
            )
            ok = (
                verdict.get("verdict") == "correct"
                and not verdict.get("failed_rubric_keys")
                and ref_matches
            )
            detail = {
                "latest_verdict": verdict.get("verdict"),
                "failed_rubric_keys": verdict.get("failed_rubric_keys", []),
                "conversation_ref_match": ref_matches,
            }

        if ok:
            passed += 1
        else:
            failed += 1
        trace_id = (verdict or {}).get("trace_id") or str(uuid.uuid4())
        result = {
            "turn_id": turn.get("turn_id"),
            "source_turn_id": source_turn_id,
            "passed": ok,
            "score": 1.0 if ok else 0.0,
            "status": "regression_replay",
            "detail": detail,
            "trace_id": trace_id,
        }
        results.append(result)
        _append_jsonl(metrics_path, {
            "ts": time.time(),
            "turn_id": result["turn_id"],
            "target": "talk_regression",
            "passed": ok,
            "score": result["score"],
            "trace_id": trace_id,
            "judge_used": False,
        })

    report = {
        "pass_rate": passed / len(turns) if turns else 0.0,
        "passed": passed,
        "failed": failed,
        "unverifiable": 0,
        "turns": results,
        "golden_hash": _sha256(regression_path) if regression_path.exists() else None,
        "ts": time.time(),
        "verdicts_seen": len(latest),
        "regression_turns": len(turns),
    }

    if write_receipt:
        receipt_id = _write_eval_receipt(
            report,
            receipts_path=receipts_path,
            metrics_path=metrics_path,
            work_type="EVAL_RUN_REGRESSION",
        )
        report["eval_receipt_id"] = receipt_id
        report["work_type"] = "EVAL_RUN_REGRESSION"

    return report


def _count_human_labeled_verdicts(
    verdicts_path: Optional[Path] = None,
    *,
    required_labeler: Optional[str] = "GEORGE",
) -> int:
    if verdicts_path is None:
        verdicts_path = _EVAL_DIR / "eval_verdicts.jsonl"
    labeled_turns: set[str] = set()
    for row in _load_jsonl_rows(verdicts_path):
        turn_id = row.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        if row.get("verdict") not in ("correct", "incorrect"):
            continue
        if not row.get("trace_id"):
            continue
        if required_labeler and row.get("labeled_by") != required_labeler:
            continue
        labeled_turns.add(turn_id)
    return len(labeled_turns)


def _pack_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "passed": int(report.get("passed", 0)),
        "failed": int(report.get("failed", 0)),
        "unverifiable": int(report.get("unverifiable", 0)),
        "turns": len(report.get("turns", [])),
        "pass_rate": float(report.get("pass_rate", 0.0)),
        "golden_hash": report.get("golden_hash"),
    }


def _append_turn_run_ledger(path: Path, report: Dict[str, Any], *, work_type: str) -> str:
    run_id = str(uuid.uuid4())
    for turn in report.get("turns", []):
        row = {
            "ts": time.time(),
            "run_id": run_id,
            "work_type": work_type,
            "turn_id": turn.get("turn_id"),
            "passed": bool(turn.get("passed", False)),
            "score": float(turn.get("score", 0.0)),
            "status": turn.get("status", "verdict"),
            "judge_used": bool(turn.get("judge_used", False)),
            "trace_id": turn.get("trace_id") or run_id,
            "detail": turn.get("detail", {}),
        }
        if "delta_vs_baseline" in turn:
            row["delta_vs_baseline"] = turn["delta_vs_baseline"]
        _append_jsonl(path, row)
    return run_id


def run_skill_campaign(
    *,
    golden_path: Optional[Path] = None,
    skill_receipts_path: Optional[Path] = None,
    runs_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """EVAL-3 convenience runner that writes the Matrix-facing skill run ledger."""
    if runs_path is None:
        runs_path = _SKILL_RUNS
    if metrics_path is None:
        metrics_path = _EVAL_DIR / "cs153_skill_metrics.jsonl"
    report = run_skill_eval(
        golden_path=golden_path,
        skill_receipts_path=skill_receipts_path,
        metrics_path=metrics_path,
        receipts_path=receipts_path,
        write_receipt=write_receipt,
    )
    report["run_id"] = _append_turn_run_ledger(runs_path, report, work_type="EVAL3_SKILL_RUN")
    report["runs_path"] = str(runs_path)
    return report


def run_free_text_campaign(
    *,
    golden_path: Optional[Path] = None,
    runs_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    judge_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """EVAL-4 convenience runner for local-judge free-text turns."""
    if golden_path is None:
        golden_path = _FREE_TEXT_TURNS
    if runs_path is None:
        runs_path = _FREE_TEXT_RUNS
    if metrics_path is None:
        metrics_path = _EVAL_DIR / "cs153_free_text_metrics.jsonl"
    if judge_fn is None:
        from System.eval_local_judge import get_default_local_judge

        judge_fn = get_default_local_judge()
    report = run_eval_pack(
        golden_path=golden_path,
        use_judge=True,
        judge_fn=judge_fn,
        metrics_path=metrics_path,
        receipts_path=receipts_path,
        write_receipt=write_receipt,
    )
    report["run_id"] = _append_turn_run_ledger(runs_path, report, work_type="EVAL4_FREE_TEXT_RUN")
    report["runs_path"] = str(runs_path)
    return report


def _latest_metrics_by_turn(path: Path) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in _load_jsonl_rows(path):
        turn_id = row.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            latest[turn_id] = row
    return latest


def run_regression_campaign(
    *,
    regression_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
    runs_path: Optional[Path] = None,
    baseline_metrics_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """EVAL-5 convenience runner with delta-vs-baseline details per turn."""
    if runs_path is None:
        runs_path = _REGRESSION_RUNS
    if baseline_metrics_path is None:
        baseline_metrics_path = _EVAL_DIR / "run_all_regression_metrics.jsonl"
    if metrics_path is None:
        metrics_path = _EVAL_DIR / "cs153_regression_metrics.jsonl"
    baseline = _latest_metrics_by_turn(baseline_metrics_path)
    report = run_regression_eval(
        regression_path=regression_path,
        verdicts_path=verdicts_path,
        metrics_path=metrics_path,
        receipts_path=receipts_path,
        write_receipt=write_receipt,
    )
    for turn in report.get("turns", []):
        prior = baseline.get(str(turn.get("turn_id") or ""))
        turn["delta_vs_baseline"] = {
            "baseline_found": bool(prior),
            "baseline_passed": prior.get("passed") if prior else None,
            "current_passed": bool(turn.get("passed", False)),
            "changed": bool(prior) and bool(prior.get("passed")) != bool(turn.get("passed", False)),
        }
    report["run_id"] = _append_turn_run_ledger(runs_path, report, work_type="EVAL5_REGRESSION_RUN")
    report["runs_path"] = str(runs_path)
    report["baseline_metrics_path"] = str(baseline_metrics_path)
    return report


def run_all_evals(
    memory_golden_path: Optional[Path] = None,
    talk_golden_path: Optional[Path] = None,
    skill_golden_path: Optional[Path] = None,
    regression_path: Optional[Path] = None,
    verdicts_path: Optional[Path] = None,
    skill_receipts_path: Optional[Path] = None,
    metrics_dir: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    rollup_path: Optional[Path] = None,
    write_receipt: bool = True,
    required_labeler: Optional[str] = "GEORGE",
) -> Dict[str, Any]:
    """Q6: Run every CS153 eval pack and emit one honest combined report."""
    metrics_defaulted = metrics_dir is None
    if metrics_dir is None:
        metrics_dir = _EVAL_DIR
    if receipts_path is None:
        receipts_path = _RECEIPTS
    if verdicts_path is None:
        verdicts_path = _EVAL_DIR / "eval_verdicts.jsonl"
    if rollup_path is None:
        rollup_path = _CAMPAIGN_ROLLUP if metrics_defaulted else metrics_dir / "eval_campaign_rollup.jsonl"

    metrics_dir.mkdir(parents=True, exist_ok=True)

    memory = run_eval_pack(
        golden_path=memory_golden_path,
        metrics_path=metrics_dir / "run_all_memory_metrics.jsonl",
        receipts_path=receipts_path,
        write_receipt=False,
    )
    talk = run_talk_eval(
        golden_path=talk_golden_path,
        verdicts_path=verdicts_path,
        metrics_path=metrics_dir / "run_all_talk_metrics.jsonl",
        receipts_path=receipts_path,
        write_receipt=False,
        required_labeler=required_labeler,
    )
    skill = run_skill_eval(
        golden_path=skill_golden_path,
        skill_receipts_path=skill_receipts_path,
        metrics_path=metrics_dir / "run_all_skill_metrics.jsonl",
        receipts_path=receipts_path,
        write_receipt=False,
    )
    regression = run_regression_eval(
        regression_path=regression_path,
        verdicts_path=verdicts_path,
        metrics_path=metrics_dir / "run_all_regression_metrics.jsonl",
        receipts_path=receipts_path,
        write_receipt=False,
    )

    per_pack = {
        "memory": memory,
        "talk": talk,
        "skill": skill,
        "regression": regression,
    }
    summaries = {name: _pack_summary(report) for name, report in per_pack.items()}
    passed = sum(item["passed"] for item in summaries.values())
    failed = sum(item["failed"] for item in summaries.values())
    unverifiable = sum(item["unverifiable"] for item in summaries.values())
    total_turns = sum(item["turns"] for item in summaries.values())
    human_labeled = _count_human_labeled_verdicts(verdicts_path, required_labeler=required_labeler)

    report = {
        "pass_rate": passed / total_turns if total_turns else 0.0,
        "passed": passed,
        "failed": failed,
        "unverifiable": unverifiable,
        "per_pack": per_pack,
        "pack_summary": summaries,
        "totals": {
            "passed": passed,
            "failed": failed,
            "unverifiable": unverifiable,
            "turns": total_turns,
            "human_labeled": human_labeled,
        },
        "human_labeled": human_labeled,
        "ts": time.time(),
    }

    rollup = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "work_type": "EVAL_CAMPAIGN_ROLLUP",
        "pass_rate": report["pass_rate"],
        "passed": passed,
        "failed": failed,
        "unverifiable": unverifiable,
        "human_labeled": human_labeled,
        "pack_summary": summaries,
        "metrics_dir": str(metrics_dir),
    }
    _append_jsonl(rollup_path, rollup)
    report["rollup_id"] = rollup["trace_id"]
    report["rollup_path"] = str(rollup_path)

    if write_receipt:
        receipt = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "work_type": "EVAL_RUN_ALL",
            "pass_rate": report["pass_rate"],
            "passed": passed,
            "failed": failed,
            "unverifiable": unverifiable,
            "human_labeled": human_labeled,
            "pack_summary": summaries,
            "metrics_dir": str(metrics_dir),
            "source": "swarm_eval_loop",
            "rollup_path": str(rollup_path),
            "rollup_id": rollup["trace_id"],
        }
        _append_jsonl(receipts_path, receipt)
        report["eval_receipt_id"] = receipt["trace_id"]
        report["work_type"] = "EVAL_RUN_ALL"

    return report


def _skill_result(turn: EvalTurn, passed: bool, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "turn_id": turn.turn_id,
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "status": "verdict",
        "detail": detail,
    }


def _skill_unverifiable(turn: EvalTurn, reason: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"reason": reason}
    if detail:
        payload.update(detail)
    return {
        "turn_id": turn.turn_id,
        "passed": False,
        "score": 0.0,
        "status": "unverifiable",
        "detail": payload,
    }


def _receipt_matches_skill(row: Dict[str, Any], skill_name: str) -> bool:
    if not skill_name:
        return False
    needle = skill_name.lower()
    for key in ("skill_name", "name"):
        value = row.get(key)
        if isinstance(value, str) and value.lower() == needle:
            return True
    validation = row.get("validation")
    if isinstance(validation, dict):
        metadata = validation.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("name")
            if isinstance(value, str) and value.lower() == needle:
                return True
    for key in ("destination", "source"):
        value = row.get(key)
        if isinstance(value, str):
            lowered = value.lower()
            if f"/{needle}/" in lowered or f"/{needle}.skill" in lowered:
                return True
    return False


def _receipt_status(row: Dict[str, Any]) -> str:
    status = row.get("status")
    if isinstance(status, str) and status:
        return status
    result = row.get("result")
    if isinstance(result, str) and result:
        return result
    return "UNKNOWN"


def _match_names(matches: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for item in matches:
        if isinstance(item, dict):
            for key in ("name", "skill_name", "slug", "id"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    names.append(value)
                    break
        elif isinstance(item, str):
            names.append(item)
    return names


def _finding_mentions_skill(finding: Any, skill_name: str) -> bool:
    if not skill_name:
        return False
    needle = skill_name.lower()
    if isinstance(finding, dict):
        direct_keys = ("skill_name", "skill", "name", "owner", "trigger_owner")
        for key in direct_keys:
            value = finding.get(key)
            if isinstance(value, str) and value.lower() == needle:
                return True
        searchable = " ".join(str(finding.get(k, "")) for k in ("kind", "message", "detail", "lane"))
        return needle in searchable.lower()
    return needle in str(finding).lower()


def _skill_golden_header() -> Dict[str, Any]:
    return {
        "truth_label": "CS153_SKILL_V1",
        "version": 1,
        "description": (
            "Domain evals for skill-invoke, trigger, and CheckResolvable. "
            "Generated from the live skill index so turns do not drift to phantom skills."
        ),
    }


def _write_skill_golden(path: Path, turns: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_skill_golden_header(), sort_keys=True) + "\n\n")
        for turn in turns:
            f.write(json.dumps(turn, sort_keys=True) + "\n")


def _unique_skill_names(skill_index: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    seen: set[str] = set()
    for skill in skill_index:
        name = str(skill.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def build_skill_golden_from_live_index(
    out_path: Optional[Path] = None,
    *,
    max_turns: int = 10,
    skill_index: Optional[List[Dict[str, Any]]] = None,
    match_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Regenerate EVAL-3 golden turns from real skills, never phantom names."""
    if out_path is None:
        out_path = _GOLDEN_DIR / "cs153_skill_turns.jsonl"
    if skill_index is None:
        from System.swarm_skill_library import build_skill_index

        skill_index = build_skill_index()
    if match_fn is None:
        from System.swarm_skill_library import match_skills as match_fn

    names = _unique_skill_names(skill_index)
    if not names:
        raise ValueError("cannot build EVAL-3 golden pack: live skill index is empty")

    turns: List[Dict[str, Any]] = []

    def add(turn: Dict[str, Any]) -> None:
        if len(turns) >= max_turns:
            return
        turn = dict(turn)
        turn["turn_id"] = f"s{len(turns) + 1:02d}"
        turns.append(turn)

    add({
        "target": "skill_invoke",
        "skill_name": names[0],
        "expect": {"receipt_status_in": ["installed", "success"]},
    })

    trigger_probes = {
        "whatsapp_macos_cli": "send whatsapp message to team",
        "physarum_solve": "solve graph routing with physarum",
        "demand_resolve": "explicit owner demand",
        "explore": "explore the repo",
        "lora_train_cycle": "train lora cycle",
        "swarm_handoff": "handoff to specialist",
    }
    near_miss_query = "unrelated quantum physics banana"
    for skill_name, query in trigger_probes.items():
        if skill_name not in names:
            continue
        try:
            trigger_names = _match_names(match_fn(query, limit=5))
            near_names = _match_names(match_fn(near_miss_query, limit=5))
        except Exception:
            continue
        if skill_name in trigger_names and skill_name not in near_names:
            add({
                "target": "skill_trigger_eval",
                "skill_name": skill_name,
                "query": query,
                "expect": {
                    "trigger_fired": True,
                    "no_overfire_on_near_miss": True,
                    "near_miss_query": near_miss_query,
                },
            })
            break

    add({
        "target": "skill_check_resolvable",
        "skill_name": names[0],
        "expect": {"no_duplicate_owner": True},
    })

    for skill_name in names[1:]:
        add({
            "target": "skill_invoke",
            "skill_name": skill_name,
            "expect": {"receipt_status_in": ["installed", "success"]},
        })

    _write_skill_golden(out_path, turns)
    return turns


def run_skill_eval(
    golden_path: Optional[Path] = None,
    skill_receipts_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    write_receipt: bool = True,
    match_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    audit_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    use_judge: bool = False,
    judge_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """EVAL-3: read-only scoring for skill-invoke, trigger eval, CheckResolvable."""
    if golden_path is None:
        golden_path = _GOLDEN_DIR / "cs153_skill_turns.jsonl"
    if skill_receipts_path is None:
        skill_receipts_path = _STATE / "nanobot_skill_receipts.jsonl"
    if metrics_path is None:
        metrics_path = _METRICS
    if receipts_path is None:
        receipts_path = _RECEIPTS

    if match_fn is None:
        try:
            from System.swarm_skill_library import match_skills as match_fn
        except Exception:
            match_fn = None
    if audit_fn is None:
        try:
            from System.swarm_duplicate_organ_audit import audit_repo as audit_fn
        except Exception:
            audit_fn = None

    golden_hash = _sha256(golden_path)
    turns = load_golden_turns(golden_path)
    skill_receipts = _load_jsonl_rows(skill_receipts_path)

    audit_result: Dict[str, Any] = {"ok": False, "findings": [], "error": "audit unavailable"}
    if audit_fn is not None:
        try:
            audit_result = audit_fn()
        except Exception as exc:
            audit_result = {"ok": False, "findings": [], "error": f"{type(exc).__name__}: {exc}"}

    results: List[Dict[str, Any]] = []
    passed = failed = unverifiable = 0

    for turn in turns:
        target = turn.target
        skill_name = turn.skill_name or (turn.expect or {}).get("skill_name", "")
        expect = turn.expect or {}

        if target == "skill_invoke":
            matched_receipts = [r for r in skill_receipts if _receipt_matches_skill(r, skill_name)]
            allowed = {str(s).lower() for s in expect.get("receipt_status_in", ["installed", "success"])}
            if not matched_receipts:
                unverifiable += 1
                results.append(_skill_unverifiable(
                    turn,
                    "no matching receipt in nanobot_skill_receipts.jsonl",
                    {"skill_name": skill_name},
                ))
                continue

            statuses = [_receipt_status(r) for r in matched_receipts]
            ok = any(status.lower() in allowed for status in statuses)
            if ok:
                passed += 1
            else:
                failed += 1
            results.append(_skill_result(turn, ok, {
                "skill_name": skill_name,
                "matched_receipts": len(matched_receipts),
                "receipt_statuses": statuses,
                "allowed_statuses": sorted(allowed),
            }))
            continue

        if target == "skill_trigger_eval":
            if match_fn is None:
                unverifiable += 1
                results.append(_skill_unverifiable(turn, "match_skills unavailable", {"skill_name": skill_name}))
                continue
            try:
                matches = match_fn(turn.query or "", limit=5)
                near_miss_query = expect.get("near_miss_query", "unrelated quantum physics banana")
                near_matches = match_fn(near_miss_query, limit=5)
            except Exception as exc:
                unverifiable += 1
                results.append(_skill_unverifiable(
                    turn,
                    "match_skills failed",
                    {"skill_name": skill_name, "error": f"{type(exc).__name__}: {exc}"},
                ))
                continue

            names = _match_names(matches)
            near_names = _match_names(near_matches)
            trigger_fired = skill_name in names
            no_overfire = skill_name not in near_names
            ok = (
                trigger_fired is bool(expect.get("trigger_fired", True))
                and no_overfire is bool(expect.get("no_overfire_on_near_miss", True))
            )
            if ok:
                passed += 1
            else:
                failed += 1
            results.append(_skill_result(turn, ok, {
                "skill_name": skill_name,
                "trigger_fired": trigger_fired,
                "matched_names": names,
                "near_miss_query": near_miss_query,
                "no_overfire": no_overfire,
                "near_miss_names": near_names,
            }))
            continue

        if target == "skill_check_resolvable":
            if audit_fn is None:
                unverifiable += 1
                results.append(_skill_unverifiable(turn, "audit_repo unavailable", {"skill_name": skill_name}))
                continue
            findings = audit_result.get("findings", [])
            duplicate_findings = [
                f for f in findings
                if "duplicate" in str(f).lower() and _finding_mentions_skill(f, skill_name)
            ]
            no_duplicate_owner = not duplicate_findings
            ok = no_duplicate_owner is bool(expect.get("no_duplicate_owner", True))
            if ok:
                passed += 1
            else:
                failed += 1
            results.append(_skill_result(turn, ok, {
                "skill_name": skill_name,
                "audit_ok": audit_result.get("ok"),
                "no_duplicate_owner": no_duplicate_owner,
                "duplicate_findings": duplicate_findings[:3],
            }))
            continue

        unverifiable += 1
        results.append(_skill_unverifiable(turn, f"unknown target {target}"))

    report = {
        "pass_rate": passed / len(turns) if turns else 0.0,
        "passed": passed,
        "failed": failed,
        "unverifiable": unverifiable,
        "turns": results,
        "golden_hash": golden_hash,
        "ts": time.time(),
        "receipts_seen": len(skill_receipts),
        "audit_ok": audit_result.get("ok"),
    }

    if write_receipt:
        receipt_id = _write_eval_receipt(
            report,
            receipts_path=receipts_path,
            metrics_path=metrics_path,
            work_type="EVAL_RUN_SKILL",
        )
        report["eval_receipt_id"] = receipt_id
        report["work_type"] = "EVAL_RUN_SKILL"

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run SIFTA CS153 eval campaigns")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-all", help="run memory, talk, skill, and regression packs")
    sub.add_parser("skill", help="run EVAL-3 skill pack")
    sub.add_parser("free-text", help="run EVAL-4 local-judge free-text pack")
    sub.add_parser("regression", help="run EVAL-5 regression replay")
    sub.add_parser("freeze", help="freeze incorrect Talk verdicts into regressions")
    args = parser.parse_args(argv)

    if args.command == "run-all":
        report = run_all_evals()
    elif args.command == "skill":
        report = run_skill_campaign()
    elif args.command == "free-text":
        report = run_free_text_campaign()
    elif args.command == "regression":
        report = run_regression_campaign()
    elif args.command == "freeze":
        report = {"frozen_count": freeze_failures_to_regression()}
    else:  # pragma: no cover - argparse owns this branch
        parser.error(f"unknown command {args.command}")

    print(json.dumps(report, sort_keys=True, default=str))
    return 0


__all__ = [
    "run_eval_pack",
    "load_golden_turns",
    "EvalTurn",
    "run_talk_eval",
    "run_skill_eval",
    "run_skill_campaign",
    "run_free_text_campaign",
    "run_regression_campaign",
    "build_skill_golden_from_live_index",
    "make_local_ollama_judge",
    "freeze_failures_to_regression",
    "run_regression_eval",
    "run_all_evals",
    "get_stanford_summary",
]


def get_stanford_summary() -> str:
    """
    Quick, honest, copy-pasteable paragraph for external sharing (Stanford CS153 etc.).
    Calls run_all_evals() and surfaces the critical number: how many turns have actual human labels.
    """
    report = run_all_evals(write_receipt=False)
    t = report.get("totals", {})
    return (
        f"CS153 Domain Eval — SIFTA on GTH4921YP3 — {t.get('turns',0)} turns. "
        f"Human-labeled: {t.get('human_labeled',0)}. "
        f"Passed: {t.get('passed',0)}, Failed: {t.get('failed',0)}, Unverifiable: {t.get('unverifiable',0)}. "
        f"Full local loop + judge + regression system. Generated {time.strftime('%Y-%m-%d %H:%M')}."
    )


if __name__ == "__main__":
    raise SystemExit(main())
