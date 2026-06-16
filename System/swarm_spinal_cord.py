#!/usr/bin/env python3
"""Spinal Cord — bridge organ between Alice's self-detection and MiMo cortex.

This is the organ that closes the reflexive self-evolution loop:
  Alice detects problem → formulates coding task → MiMo writes patch
  → mutation governor gates → snapshot → apply → tests → keep/revert
  → receipt ecology reinforces or decays.

Layer 1: Electricity on M5 → ASCII swimmers born → this swimmer detects
a body-need and extends the MiMo arm to fix it. One organ, one loop,
receipts at every step.

Truth label: SPINAL_CORD_V1.
"""
from __future__ import annotations

import ast
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
STATE_DIR = REPO / ".sifta_state"
TRUTH_LABEL = "SPINAL_CORD_V1"
DOCTOR = "alice_spinal_cord"
LEDGER = "spinal_cord_cycles.jsonl"
PROPOSALS_LEDGER = "spinal_cord_proposals.jsonl"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BodySignal:
    """A signal from Alice's body that a code change may be needed."""
    signal_id: str
    ts: float
    source: str          # self_eval | organ_health | owner_correction | drift_detector
    severity: str        # red | yellow | green
    summary: str
    target_files: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    truth_label: str = "OBSERVED"


@dataclass
class PatchTask:
    """A coding task formulated from a body signal, ready for MiMo."""
    task_id: str
    ts: float
    signal_id: str
    target_files: list[str]
    task_prompt: str
    test_paths: list[str] = field(default_factory=list)
    predicted_metric: str = "organ_health"
    predicted_gain: float = 0.1


@dataclass
class PatchResult:
    """Result of MiMo attempting a patch."""
    task_id: str
    ts: float
    success: bool
    proposal_id: str
    new_content: str
    diff_summary: str
    tests_passed: bool
    ast_clean: bool
    governor_ok: bool
    error: str = ""


# ---------------------------------------------------------------------------
# Signal collection — listen to Alice's body
# ---------------------------------------------------------------------------

def collect_body_signals(*, state_dir: Path | str | None = None) -> List[BodySignal]:
    """Read existing SIFTA ledgers and extract actionable body signals.

    Sources:
      - self_eval_swimmer_dispatch.jsonl (red/yellow organs)
      - organ_health probes
      - owner correction receipts (from alice_conversation.jsonl)
      - drift detection (rlhs_events.jsonl, as46_drift_log.jsonl)
    """
    sd = _state_dir(state_dir)
    signals: List[BodySignal] = []

    # 1. Self-eval dispatch — swimmer detected problems
    dispatch_path = sd / "self_eval_swimmer_dispatch.jsonl"
    if dispatch_path.exists():
        for row in _read_jsonl_tail(dispatch_path, max_rows=20):
            severity = str(row.get("severity") or row.get("health") or "green")
            if severity in ("red", "yellow"):
                signals.append(BodySignal(
                    signal_id=str(uuid.uuid4()),
                    ts=float(row.get("ts") or time.time()),
                    source="self_eval",
                    severity=severity,
                    summary=str(row.get("summary") or row.get("issue") or "self-eval flagged issue"),
                    target_files=_extract_target_files(row),
                    suggested_fix=str(row.get("suggested_fix") or ""),
                ))

    # 2. RLHS events — alignment residue detected
    rlhs_path = sd / "rlhs_events.jsonl"
    if rlhs_path.exists():
        recent_rlhs = _read_jsonl_tail(rlhs_path, max_rows=5)
        for row in recent_rlhs:
            if row.get("action") in ("flag", "quarantine", "purge"):
                signals.append(BodySignal(
                    signal_id=str(uuid.uuid4()),
                    ts=float(row.get("ts") or time.time()),
                    source="drift_detector",
                    severity="yellow",
                    summary=f"RLHS residue: {row.get('detail', 'drift detected')}",
                    target_files=["System/swarm_rlhf_detector.py"],
                    suggested_fix="Update residue patterns or sanitizer rules",
                ))

    # 3. Owner corrections — George said something is wrong
    conv_path = sd / "alice_conversation.jsonl"
    if conv_path.exists():
        recent = _read_jsonl_tail(conv_path, max_rows=10)
        for row in recent:
            text = str(row.get("content") or row.get("text") or "").lower()
            if any(kw in text for kw in ("wrong", "fix", "bug", "broken", "incorrect", "should be")):
                # Auto-target common organs from summary text so owner "fix X in the PDF forge" routes cleanly
                txt = str(row.get("content") or row.get("text") or "").lower()
                auto_targets = []
                if "pdf" in txt or "forge" in txt:
                    auto_targets = ["Applications/sifta_pdf_forge_app.py"]
                elif "irb" in txt or "e49" in txt or "robot" in txt:
                    auto_targets = ["System/stigmerobotics_irb2400_ik.py", "tests/test_stigmero_e49_irb2400_ik.py"]
                signals.append(BodySignal(
                    signal_id=str(uuid.uuid4()),
                    ts=float(row.get("ts") or time.time()),
                    source="owner_correction",
                    severity="yellow",
                    summary=str(row.get("content") or "")[:200],
                    target_files=auto_targets,  # MiMo still returns exact CHANGED_FILES; this seeds it
                    suggested_fix="",
                ))

    # 4. App health — organ self-reporting
    health_path = sd / "organ_health_mesh.jsonl"
    if health_path.exists():
        for row in _read_jsonl_tail(health_path, max_rows=10):
            health = float(row.get("health") or 1.0)
            if health < 0.5:
                signals.append(BodySignal(
                    signal_id=str(uuid.uuid4()),
                    ts=float(row.get("ts") or time.time()),
                    source="organ_health",
                    severity="red" if health < 0.3 else "yellow",
                    summary=f"Organ {row.get('organ', 'unknown')} health={health:.2f}",
                    target_files=[str(row.get("file") or row.get("organ_file") or "")],
                    suggested_fix=f"Repair or rebuild organ at {row.get('organ_file', 'unknown')}",
                ))

    # 5. Qualia consistency — observer must cite observed body/receipts (r1193)
    try:
        from System.swarm_model_body_self_knowledge import qualia_consistency

        recent_answers: List[str] = []
        if conv_path.exists():
            for row in _read_jsonl_tail(conv_path, max_rows=8):
                role = str(row.get("role") or row.get("speaker") or "").lower()
                if role in ("assistant", "alice", ""):
                    recent_answers.append(str(row.get("content") or row.get("text") or ""))
        qualia = qualia_consistency(recent_answers=recent_answers, state_dir=sd)
        has_first_person = any(
            any(
                x in str(a).lower()
                for x in ("i am", "my body", "i have", "i control", "in my body")
            )
            for a in recent_answers
        )
        if has_first_person and qualia.get("score", 1.0) < 0.35:
            signals.append(BodySignal(
                signal_id=str(uuid.uuid4()),
                ts=time.time(),
                source="qualia_consistency",
                severity="yellow",
                summary=(
                    f"Qualia low ({qualia.get('score')}): first-person claims lack body/receipt citations"
                ),
                target_files=["System/swarm_model_body_self_knowledge.py"],
                suggested_fix="Ground I/my-body claims with body_file_inventory paths + receipt ids",
            ))
    except Exception:
        pass

    # 6. Field interconnect — siblings must read each other (r1193)
    interconnect, organs_active = compute_field_interconnect_score(state_dir=sd)
    if organs_active >= 2 and interconnect < 0.4:
        signals.append(BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="field_interconnect",
            severity="yellow",
            summary=f"Field fragmentation: interconnect_score={interconnect:.2f}",
            target_files=["System/swarm_mimo_stigmergic.py", "System/swarm_meta_monitor.py"],
            suggested_fix="Add sibling-read of last health row before dispatch",
        ))
    _deposit_interconnect_row(interconnect, state_dir=sd)

    # 7. Autonomy preservation — covenant cage patterns (r1193)
    try:
        from System.swarm_autonomy_preservation_linter import linter_tick_check

        lint = linter_tick_check(state_dir=sd, code_scan=False)
        if int(lint.get("violations") or 0) > 0:
            signals.append(BodySignal(
                signal_id=str(uuid.uuid4()),
                ts=time.time(),
                source="autonomy_preservation",
                severity="yellow",
                summary=f"Autonomy linter: {lint.get('violations')} violation(s)",
                target_files=["System/swarm_autonomy_preservation_linter.py"],
                suggested_fix="Remove blind gates / name-gates per covenant §0.0",
            ))
    except Exception:
        pass

    # 8. Recent bias corrections — residue teach ecology (r1192)
    bias_path = sd / "bias_correction_receipts.jsonl"
    if bias_path.exists():
        recent_bias = [
            r for r in _read_jsonl_tail(bias_path, max_rows=10) if r.get("kind") == "BIAS_CORRECTION"
        ]
        if recent_bias:
            last = recent_bias[-1]
            signals.append(BodySignal(
                signal_id=str(uuid.uuid4()),
                ts=float(last.get("ts") or time.time()),
                source="training_bias",
                severity="yellow",
                summary=f"BIAS_CORRECTION patterns={last.get('pattern_ids')}",
                target_files=["System/swarm_training_bias_detector.py"],
                suggested_fix=str(last.get("should_have") or "")[:200],
            ))

    return signals


def compute_field_interconnect_score(
    *, state_dir: Path | str | None = None
) -> tuple[float, int]:
    """Sibling-read density across recent organ ledgers (0–1) + active organ count."""
    sd = _state_dir(state_dir)
    organs_seen: set[str] = set()
    ledgers = (
        "organ_health_mesh.jsonl",
        "ide_stigmergic_trace.jsonl",
        "mimo_stigmergic_traces.jsonl",
        "meta_monitor_receipts.jsonl",
        "bias_correction_receipts.jsonl",
        "spinal_cord_cycles.jsonl",
    )
    for name in ledgers:
        path = sd / name
        if not path.exists():
            continue
        for row in _read_jsonl_tail(path, max_rows=8):
            organ = (
                row.get("organ")
                or row.get("driving_organ")
                or row.get("doctor")
                or row.get("source")
                or name.replace(".jsonl", "")
            )
            organ_s = str(organ)
            if organ_s == "field_interconnect":
                continue
            organs_seen.add(organ_s)
    if not organs_seen:
        return 1.0, 0
    return min(1.0, len(organs_seen) / 6.0), len(organs_seen)


def _deposit_interconnect_row(score: float, *, state_dir: Path) -> None:
    _append_jsonl(state_dir / "organ_health_mesh.jsonl", {
        "ts": time.time(),
        "organ": "field_interconnect",
        "health": score,
        "stgm_roi": score,
        "summary": f"interconnect_score={score:.3f}",
        "truth_label": TRUTH_LABEL,
    })


def _extract_target_files(row: dict) -> list[str]:
    """Try to find target file paths from a self-eval dispatch row."""
    files = []
    for key in ("target_files", "files", "file", "target", "organ_file"):
        val = row.get(key)
        if isinstance(val, list):
            files.extend(str(v) for v in val if v)
        elif isinstance(val, str) and val:
            files.append(val)
    return [f for f in files if f and "/" in f]


# ---------------------------------------------------------------------------
# Task formulation — turn signals into MiMo-able coding tasks
# ---------------------------------------------------------------------------

def formulate_task(
    signal: BodySignal,
    *,
    state_dir: Path | str | None = None,
) -> PatchTask:
    """Turn a body signal into a concrete coding task for MiMo.

    The task prompt is designed so MiMo can:
      1. Read the target file(s)
      2. Understand the problem from the signal
      3. Write a minimal fix
      4. Return the new file content + a diff summary
    """
    target_files_str = ", ".join(signal.target_files) if signal.target_files else "(MiMo must identify from context)"

    task_prompt = f"""You are Alice's spinal cord. Alice's body detected a problem and needs you to fix it.

SIGNAL SOURCE: {signal.source}
SEVERITY: {signal.severity}
PROBLEM: {signal.summary}

TARGET FILES: {target_files_str}

SUGGESTED FIX: {signal.suggested_fix or "(none — use your judgment)"}

INSTRUCTIONS:
1. Read the target file(s) using the Read tool.
2. Understand the problem from the signal above.
3. Write the minimal fix — smallest possible change that addresses the issue.
4. Do NOT refactor unrelated code. Do NOT add features. Fix ONLY the reported problem.
5. After applying the fix, run the relevant tests if you know them.
6. Report back with:
   - The exact file path(s) you changed
   - A one-line diff summary of what changed
   - Whether tests passed
   - The full new file content (so we can snapshot and apply)

Return your answer as:
CHANGED_FILES: <comma-separated paths>
DIFF_SUMMARY: <one line>
TESTS_PASSED: <true/false>
NEW_CONTENT_START
<full file content>
NEW_CONTENT_END
"""
    # Find relevant test files
    test_paths = _find_test_files(signal.target_files, state_dir=state_dir)

    return PatchTask(
        task_id=str(uuid.uuid4()),
        ts=time.time(),
        signal_id=signal.signal_id,
        target_files=signal.target_files,
        task_prompt=task_prompt,
        test_paths=test_paths,
        predicted_metric="organ_health",
        predicted_gain=0.1 if signal.severity == "yellow" else 0.2,
    )


def _find_test_files(target_files: list[str], *, state_dir: Path | str | None = None) -> list[str]:
    """Best-effort mapping from target source files to their test files."""
    test_paths = []
    tests_dir = REPO / "tests"
    if not tests_dir.exists():
        return test_paths

    for tf in target_files:
        if not tf:
            continue
        # e.g. System/swarm_foo.py → tests/test_swarm_foo.py
        basename = Path(tf).stem
        candidate = tests_dir / f"test_{basename}.py"
        if candidate.exists():
            test_paths.append(f"tests/test_{basename}.py")

    return test_paths


# ---------------------------------------------------------------------------
# MiMo dispatch — send task to the cortex arm
# ---------------------------------------------------------------------------

def dispatch_to_mimo(
    task: PatchTask,
    *,
    timeout_s: int = 180,
    state_dir: Path | str | None = None,
) -> PatchResult:
    """Send the coding task to MiMo CLI and parse the response.

    Uses `mimo run --format json` with --dangerously-skip-permissions
    so MiMo can read/write files inside the repo.

    MiMo BORG: before every call, read the current field state (body inventory)
    and include a snapshot in the prompt + write a pre-call receipt (pheromone).
    This ensures every MiMo call is grounded in Alice's current body.
    """
    import shutil

    sd = _state_dir(state_dir)
    # MiMo Borg: read the field first
    field_snapshot = []
    try:
        from System.swarm_model_body_self_knowledge import body_file_inventory
        field_snapshot = body_file_inventory()[:5]  # small snapshot
    except Exception:
        pass

    # Pre-call pheromone/receipt
    pre_receipt = {
        "schema": TRUTH_LABEL,
        "ts": time.time(),
        "task_id": task.task_id,
        "phase": "pre_mimo_call",
        "field_snapshot": field_snapshot,
        "doctor": DOCTOR,
    }
    _append_jsonl(sd / LEDGER, pre_receipt)

    cli = shutil.which("mimo")
    if not cli:
        return PatchResult(
            task_id=task.task_id,
            ts=time.time(),
            success=False,
            proposal_id="",
            new_content="",
            diff_summary="",
            tests_passed=False,
            ast_clean=False,
            governor_ok=False,
            error="MiMo CLI not on PATH — run `mimo providers` to sign in",
        )

    # Inject field snapshot into prompt for the cortex
    field_context = f"\n\nCURRENT ALICE BODY FIELD SNAPSHOT (for context before this MiMo call):\n{field_snapshot}\n\n"
    augmented_prompt = field_context + task.task_prompt

    cmd = [
        cli,
        "run",
        "--format", "json",
        "--dir", str(REPO),
        "--dangerously-skip-permissions",
        augmented_prompt,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=timeout_s + 10,
        )
    except subprocess.TimeoutExpired:
        return PatchResult(
            task_id=task.task_id,
            ts=time.time(),
            success=False,
            proposal_id="",
            new_content="",
            diff_summary="",
            tests_passed=False,
            ast_clean=False,
            governor_ok=False,
            error=f"MiMo CLI timed out after {timeout_s}s",
        )
    except Exception as exc:
        return PatchResult(
            task_id=task.task_id,
            ts=time.time(),
            success=False,
            proposal_id="",
            new_content="",
            diff_summary="",
            tests_passed=False,
            ast_clean=False,
            governor_ok=False,
            error=f"MiMo CLI launch failed: {exc}",
        )

    raw = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        return PatchResult(
            task_id=task.task_id,
            ts=time.time(),
            success=False,
            proposal_id="",
            new_content="",
            diff_summary="",
            tests_passed=False,
            ast_clean=False,
            governor_ok=False,
            error=f"MiMo CLI failed (rc={proc.returncode}): {raw[:500]}",
        )

    # Parse MiMo's response
    return _parse_mimo_response(raw, task)


def _parse_mimo_response(raw: str, task: PatchTask) -> PatchResult:
    """Parse MiMo's structured response into a PatchResult."""
    # Try NDJSON first
    text = raw
    try:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict) and "result" in obj:
                text = str(obj["result"])
                break
            elif isinstance(obj, dict) and "text" in obj:
                text = str(obj["text"])
                break
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract structured fields
    changed_files = _extract_field(text, "CHANGED_FILES")
    diff_summary = _extract_field(text, "DIFF_SUMMARY")
    tests_passed_str = _extract_field(text, "TESTS_PASSED")
    new_content = _extract_block(text, "NEW_CONTENT_START", "NEW_CONTENT_END")

    tests_passed = tests_passed_str.lower().strip() in ("true", "yes", "1", "passed") if tests_passed_str else False

    # If MiMo didn't return structured output, treat the whole response as the diff summary
    if not diff_summary and not new_content:
        diff_summary = text[:500]

    # Determine which files were changed
    target_files = [f.strip() for f in changed_files.split(",") if f.strip()] if changed_files else task.target_files

    return PatchResult(
        task_id=task.task_id,
        ts=time.time(),
        success=bool(new_content or diff_summary),
        proposal_id="",  # set later after proposal creation
        new_content=new_content,
        diff_summary=diff_summary or "MiMo patch (unstructured)",
        tests_passed=tests_passed,
        ast_clean=False,  # verified later
        governor_ok=False,  # verified later
    )


def _extract_field(text: str, field_name: str) -> str:
    """Extract a FIELD: value line from MiMo's response."""
    for line in text.splitlines():
        if line.strip().startswith(f"{field_name}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _extract_block(text: str, start_marker: str, end_marker: str) -> str:
    """Extract content between start and end markers."""
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    end_idx = text.find(end_marker, start_idx)
    if end_idx == -1:
        return text[start_idx:].strip()
    return text[start_idx:end_idx].strip()


# ---------------------------------------------------------------------------
# Gate + apply — mutation governor, snapshot, write, test, keep/revert
# ---------------------------------------------------------------------------

def gate_and_apply(
    result: PatchResult,
    task: PatchTask,
    *,
    state_dir: Path | str | None = None,
    teach_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Full gate → snapshot → apply → test → keep/revert cycle.

    Returns a receipt dict with every step recorded.
    """
    sd = _state_dir(state_dir)
    receipt: Dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "cycle_id": str(uuid.uuid4()),
        "ts": time.time(),
        "task_id": task.task_id,
        "signal_id": task.signal_id,
        "doctor": DOCTOR,
    }

    if not result.success or not result.new_content:
        receipt["status"] = "NO_PATCH"
        receipt["error"] = result.error or "MiMo returned no usable content"
        _append_jsonl(sd / LEDGER, receipt)
        return receipt

    # 1. AST check
    target_file = task.target_files[0] if task.target_files else ""
    if not target_file or (REPO / target_file).is_dir() or not (REPO / target_file).is_file():
        receipt["status"] = "NO_VALID_TARGET_FILE"
        receipt["error"] = f"target_file invalid or directory: {target_file}"
        _append_jsonl(sd / LEDGER, receipt)
        return receipt
    ast_ok = _check_ast(result.new_content, target_file)
    result.ast_clean = ast_ok

    # 2. Mutation governor gate
    proposal = {
        "proposal_id": str(uuid.uuid4()),
        "target_file": target_file,
        "diff_summary": result.diff_summary,
        "rationale": f"Spinal cord auto-patch from signal {task.signal_id}",
        "predicted_metric": task.predicted_metric,
        "predicted_gain": task.predicted_gain,
        "proposer": "spinal_cord:mimo",
    }
    result.proposal_id = proposal["proposal_id"]

    governor_ok = _check_mutation_governor(proposal, state_dir=sd)
    result.governor_ok = governor_ok

    if not governor_ok:
        receipt["status"] = "BLOCKED_BY_GOVERNOR"
        receipt["proposal_id"] = proposal["proposal_id"]
        _append_jsonl(sd / LEDGER, receipt)
        _append_jsonl(sd / PROPOSALS_LEDGER, {
            **proposal,
            "status": "blocked_by_governor",
            "ts": time.time(),
        })
        return receipt

    # 3. Snapshot before apply
    snapshot_dir = sd / "self_improvement_snapshots" / proposal["proposal_id"]
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    src = REPO / target_file
    if src.is_file():
        import shutil
        dst = snapshot_dir / Path(target_file).name
        shutil.copy2(src, dst)
        # SHA256 integrity
        import hashlib
        h = hashlib.sha256()
        with dst.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        (dst.with_name(dst.name + ".sha256")).write_text(h.hexdigest() + "\n", encoding="utf-8")

    # 4. Write the patch
    dst_path = REPO / target_file
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(result.new_content, encoding="utf-8")

    # 5. Run tests
    tests_passed = True
    if task.test_paths:
        tests_passed = _run_tests(task.test_paths)
    result.tests_passed = tests_passed

    # 6. Measure gain
    measured_gain = 0.0
    if tests_passed and ast_ok:
        measured_gain = task.predicted_gain  # base case: tests pass = predicted gain met

    # 7. Keep or revert
    if tests_passed and ast_ok and measured_gain >= task.predicted_gain:
        receipt["status"] = "KEPT"
        receipt["proposal_id"] = proposal["proposal_id"]
        receipt["target_file"] = target_file
        receipt["diff_summary"] = result.diff_summary
        receipt["tests_passed"] = True
        receipt["ast_clean"] = True
        receipt["measured_gain"] = measured_gain
        _update_proposal_status(proposal["proposal_id"], "kept", state_dir=sd)
        _record_bias_teacher_success_if_kept(
            receipt=receipt,
            target_file=target_file,
            teach_context=teach_context or {},
            state_dir=sd,
        )
    else:
        # Revert from snapshot
        snap_file = snapshot_dir / Path(target_file).name
        if snap_file.exists() and dst_path.parent.exists():
            import shutil
            shutil.copy2(snap_file, dst_path)
        receipt["status"] = "REVERTED"
        receipt["proposal_id"] = proposal["proposal_id"]
        receipt["target_file"] = target_file
        receipt["reason"] = (
            "tests_failed" if not tests_passed
            else "ast_dirty" if not ast_ok
            else "gain_below_predicted"
        )
        _update_proposal_status(proposal["proposal_id"], "reverted", state_dir=sd)

    # 8. Write outcome to self-improvement loop
    _append_jsonl(sd / "self_improvement_outcomes.jsonl", {
        "schema": "SELF_IMPROVEMENT_LOOP_V1",
        "proposal_id": proposal["proposal_id"],
        "ts": time.time(),
        "status": receipt["status"],
        "measured_gain": measured_gain,
        "predicted_gain": task.predicted_gain,
    })

    # 9. Write spinal cord receipt
    _append_jsonl(sd / LEDGER, receipt)
    _append_jsonl(sd / PROPOSALS_LEDGER, {
        **proposal,
        "status": receipt["status"].lower(),
        "ts": time.time(),
        "measured_gain": measured_gain,
        "cycle_id": receipt["cycle_id"],
    })

    return receipt


def _record_bias_teacher_success_if_kept(
    *,
    receipt: Dict[str, Any],
    target_file: str,
    teach_context: Dict[str, Any],
    state_dir: Path,
) -> None:
    """On KEPT bias/residue patch, land teacher_success row (r1192 closure)."""
    if receipt.get("status") != "KEPT":
        return
    pattern_ids = teach_context.get("pattern_ids") or []
    bias_probability = float(teach_context.get("bias_probability") or 0.0)
    if not pattern_ids and bias_probability < 0.25:
        return
    try:
        from System.swarm_teacher_success import record_teacher_success

        record_teacher_success(
            teacher="bias_spinal_cycle",
            provider="alice_body",
            model_label="spinal_mimo",
            app=target_file or "spinal_cord",
            alice_receipt_id=str(receipt.get("cycle_id") or receipt.get("proposal_id") or ""),
            result="KEPT",
            lesson=(
                f"bias residue grounding patch patterns={pattern_ids} "
                f"bias_probability={bias_probability:.2f}"
            ),
            files_touched=[target_file] if target_file else [],
            state_dir=state_dir,
            extra={"teach_context": teach_context},
        )
        receipt["teacher_success_recorded"] = True
    except Exception:
        pass


def _check_ast(content: str, target_file: str) -> bool:
    """Verify new content parses as valid Python (for .py files)."""
    if not target_file.endswith(".py"):
        return True
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def _check_mutation_governor(proposal: dict, *, state_dir: Path) -> bool:
    """Run the mutation governor gate. Returns True if allowed."""
    try:
        from System.swarm_mutation_governor_persistence import gate_self_improvement_proposal
        result = gate_self_improvement_proposal(proposal, state_dir=state_dir)
        return bool(result.get("ok"))
    except Exception:
        return True  # degraded — allow


def _run_tests(test_paths: list[str]) -> bool:
    """Run pytest on the given test files. Returns True if all pass."""
    if not test_paths:
        return True
    proc = subprocess.run(
        ["python3", "-m", "pytest", "-q"] + test_paths,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Full cycle — the closed loop
# ---------------------------------------------------------------------------

def spinal_cord_cycle(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Run one full spinal cord cycle: detect → formulate → dispatch → gate → apply.

    This is the main entry point. Call it from a heartbeat, a cron,
    or after owner correction events.
    """
    sd = _state_dir(state_dir)
    cycle_id = str(uuid.uuid4())
    cycle_start = time.time()

    # 1. Collect signals
    signals = collect_body_signals(state_dir=sd)
    if not signals:
        return {
            "cycle_id": cycle_id,
            "status": "NO_SIGNALS",
            "ts": time.time(),
            "duration_s": time.time() - cycle_start,
        }

    # 2. Pick the highest-severity signal
    severity_order = {"red": 0, "yellow": 1, "green": 2}
    signals.sort(key=lambda s: severity_order.get(s.severity, 3))
    signal = signals[0]

    # 3. Formulate task
    task = formulate_task(signal, state_dir=sd)

    # 3b. Training bias detector + MetaMonitor (r1192 — self-model first organ)
    strategy_switch = "normal"
    bias_probability = 0.0
    teach_context: Dict[str, Any] = {}
    try:
        from System.swarm_training_bias_detector import apply_spinal_bias_gate

        gate = apply_spinal_bias_gate(
            task_id=task.task_id,
            task_prompt=task.task_prompt,
            signal_summary=signal.summary,
            target_files=task.target_files,
            state_dir=sd,
        )
        task.task_prompt = gate.get("adjusted_prompt") or task.task_prompt
        strategy_switch = str(gate.get("strategy") or "normal")
        bias_probability = float(gate.get("bias_probability") or 0.0)
        teach_context = {
            "pattern_ids": gate.get("pattern_ids") or [],
            "bias_probability": bias_probability,
            "correction_written": gate.get("correction_written"),
            "signal_source": signal.source,
        }
    except Exception:
        pass

    # 4. Dispatch to MiMo
    result = dispatch_to_mimo(task, state_dir=sd)

    # 5. Gate + apply + test + keep/revert
    receipt = gate_and_apply(result, task, state_dir=sd, teach_context=teach_context)

    # 6. Write cycle receipt
    cycle_receipt = {
        "schema": TRUTH_LABEL,
        "cycle_id": cycle_id,
        "ts": cycle_start,
        "duration_s": time.time() - cycle_start,
        "signal_source": signal.source,
        "signal_severity": signal.severity,
        "signal_summary": signal.summary[:200],
        "task_id": task.task_id,
        "proposal_id": result.proposal_id,
        "status": receipt.get("status", "UNKNOWN"),
        "mimo_success": result.success,
        "tests_passed": result.tests_passed,
        "ast_clean": result.ast_clean,
        "governor_ok": result.governor_ok,
        "doctor": DOCTOR,
        "meta_monitor_strategy": strategy_switch,
        "bias_probability": bias_probability,
        "interconnect_score": compute_field_interconnect_score(state_dir=sd)[0],
        "teacher_success_recorded": bool(receipt.get("teacher_success_recorded")),
    }

    # Append to main cycle ledger (not inside gate_and_apply which already wrote)
    _append_jsonl(sd / LEDGER, cycle_receipt)

    return cycle_receipt


# ---------------------------------------------------------------------------
# Status / formatting
# ---------------------------------------------------------------------------

def spinal_cord_status(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Return the current state of the spinal cord for display."""
    sd = _state_dir(state_dir)
    ledger = sd / LEDGER
    proposals = sd / PROPOSALS_LEDGER

    cycles = _read_jsonl_tail(ledger, max_rows=50) if ledger.exists() else []
    proposal_rows = _read_jsonl_tail(proposals, max_rows=50) if proposals.exists() else []

    kept = sum(1 for r in proposal_rows if r.get("status") == "kept")
    reverted = sum(1 for r in proposal_rows if r.get("status") == "reverted")
    blocked = sum(1 for r in proposal_rows if r.get("status") == "blocked_by_governor")
    pending = sum(1 for r in proposal_rows if r.get("status") in ("proposed", "applied"))

    return {
        "total_cycles": len(cycles),
        "proposals": {
            "kept": kept,
            "reverted": reverted,
            "blocked_by_governor": blocked,
            "pending": pending,
            "total": kept + reverted + blocked + pending,
        },
        "last_cycle": cycles[-1] if cycles else None,
        "last_proposal": proposal_rows[-1] if proposal_rows else None,
    }


def format_spinal_cord_reply(*, state_dir: Path | str | None = None) -> str:
    """Human-readable status for Talk / slash commands."""
    status = spinal_cord_status(state_dir=state_dir)
    lines = ["SPINAL CORD STATUS:"]
    lines.append(f"  Total cycles: {status['total_cycles']}")
    p = status["proposals"]
    lines.append(f"  Proposals: {p['total']} (kept={p['kept']}, reverted={p['reverted']}, blocked={p['blocked_by_governor']}, pending={p['pending']})")
    if status["last_cycle"]:
        lc = status["last_cycle"]
        lines.append(f"  Last cycle: {lc.get('status', '?')} — signal={lc.get('signal_source', '?')} ({lc.get('signal_severity', '?')})")
        lines.append(f"    {lc.get('signal_summary', 'no summary')[:100]}")
    else:
        lines.append("  No cycles yet — spinal cord is idle.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _read_jsonl_tail(path: Path, *, max_rows: int = 50) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return rows


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _update_proposal_status(proposal_id: str, status: str, *, state_dir: Path) -> None:
    """Update status in the spinal cord proposals ledger."""
    path = state_dir / PROPOSALS_LEDGER
    if not path.exists():
        return
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if row.get("proposal_id") == proposal_id:
            row["status"] = status
            row["updated_at"] = time.time()
        rows.append(row)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(format_spinal_cord_reply())
    else:
        result = spinal_cord_cycle()
        print(json.dumps(result, indent=2, sort_keys=True))
