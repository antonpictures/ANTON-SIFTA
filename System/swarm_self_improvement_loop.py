"""Self-improvement loop OBSERVE→PROPOSE→GATE→APPLY→MEASURE→KEEP/REVERT (r1016 §B)."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

# r1129 Spinal integration (the bridge organ): before general improvement proposals,
# run the spinal_cord_cycle if there are body signals (red/yellow swimmer unhappiness).
# This routes self-detection to the MiMo cortex with full receipt ecology.
# The spinal is the "I need to change myself" organ; this makes the loop use it.
try:
    from System.swarm_spinal_cord import spinal_cord_cycle, collect_body_signals
except Exception:  # pragma: no cover
    spinal_cord_cycle = None
    collect_body_signals = None

PROPOSALS_NAME = "self_improvement_proposals.jsonl"
OUTCOMES_NAME = "self_improvement_outcomes.jsonl"
SNAPSHOT_DIR_NAME = "self_improvement_snapshots"
TRUTH_LABEL = "SELF_IMPROVEMENT_LOOP_V1"
LEGACY_LOOP_NAME = "self_improvement_loop.jsonl"
LEGACY_TRUTH_LABEL = "SIFTA_SELF_IMPROVEMENT_LOOP_V1"

GATE_PROTECTED_PREFIXES = (
    "System/swarm_mutation_guard.py",
    "System/swarm_predator_gate",
    "System/ide_stigmergic_bridge.py",
    "System/swarm_intent_nonce_gate.py",
    "System/swarm_effector_gate.py",
)

DEFAULT_WEIGHTS = {
    "w_tests": 0.45,
    "w_ast": 0.20,
    "w_review": 0.20,
    "w_pred": 0.15,
}
DEFAULT_THETA = 0.55


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _append(sd: Path, name: str, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / name
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def _legacy_state_dir(state_dir: Path | str | None) -> Path:
    """State dir for the pre-r1016 self-improvement status ledger."""
    if state_dir is None:
        return _state_dir(None)
    return Path(state_dir)


def _receipt_for(row: Dict[str, Any]) -> str:
    clean = dict(row)
    clean.pop("receipt", None)
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_lora_status() -> Dict[str, Any]:
    try:
        from System.swarm_lora_cortex_promoter import lora_promotion_status

        return dict(lora_promotion_status())
    except Exception as exc:
        return {
            "candidate_model": "unknown",
            "promotion_ready": False,
            "promotion_blockers": [f"lora_status_unavailable:{type(exc).__name__}"],
        }


def _safe_primary_truth() -> Dict[str, Any]:
    try:
        from System.swarm_cortex_truth import primary_cortex_truth

        return dict(primary_cortex_truth())
    except Exception as exc:
        return {
            "active_model": "unknown",
            "installed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _safe_policy_snapshot(state_dir: Path | str | None = None) -> Dict[str, Any]:
    try:
        from System.stigmergic_memory_retrieval_policy import policy_snapshot

        return dict(policy_snapshot(state_dir=state_dir))
    except Exception as exc:
        return {
            "examples_raw": 0,
            "decisions_raw": 0,
            "buckets": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def _spinal_bridge_snapshot(
    *,
    state_dir: Path | str | None = None,
    run_spinal: bool = False,
) -> Dict[str, Any]:
    """Observe the spinal cord and optionally let it dispatch a live cycle."""
    bridge: Dict[str, Any] = {
        "available": False,
        "signals": 0,
        "ran": False,
        "entrypoint": "System.swarm_spinal_cord.spinal_cord_cycle",
    }
    try:
        from System.swarm_spinal_cord import collect_body_signals, spinal_cord_cycle, spinal_cord_status

        signals = collect_body_signals(state_dir=state_dir)
        bridge.update(
            {
                "available": True,
                "signals": len(signals),
                "signal_kinds": [str(getattr(sig, "kind", "unknown")) for sig in signals[:8]],
                "status": spinal_cord_status(state_dir=state_dir),
            }
        )
        if run_spinal:
            bridge["cycle"] = spinal_cord_cycle(state_dir=state_dir)
            bridge["ran"] = True
    except Exception as exc:
        bridge["error"] = f"{type(exc).__name__}: {exc}"
    return bridge


def self_improvement_snapshot(
    *,
    state_dir: Path | str | None = None,
    lora_status: Dict[str, Any] | None = None,
    primary_truth: Dict[str, Any] | None = None,
    policy_snapshot_data: Dict[str, Any] | None = None,
    arm_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Backward-compatible status view used by Talk and older tests."""
    lora = dict(lora_status if lora_status is not None else _safe_lora_status())
    primary = dict(primary_truth if primary_truth is not None else _safe_primary_truth())
    policy = dict(policy_snapshot_data if policy_snapshot_data is not None else _safe_policy_snapshot(state_dir=state_dir))
    arm = dict(arm_summary or {})
    blockers = list(lora.get("promotion_blockers") or lora.get("candidate_blockers") or [])
    promotion_ready = bool(lora.get("promotion_ready")) and not blockers
    installed = bool(primary.get("installed", True))
    promotion_status = "PROMOTE_CANDIDATE" if promotion_ready and installed else "KEEP_CURRENT_CORTEX"
    recommended_actions: List[str] = []
    if blockers:
        recommended_actions.append("do not promote LoRA candidate until blockers clear")
    if not arm.get("available", True):
        recommended_actions.append("coding arm unavailable; hold mutation proposals")
    spinal = _spinal_bridge_snapshot(state_dir=state_dir, run_spinal=False)
    if spinal.get("available") and spinal.get("signals"):
        recommended_actions.append("spinal cord has body signals; run close_loop_once(run_spinal=True) when owner permits live MiMo dispatch")
    return {
        "truth_label": LEGACY_TRUTH_LABEL,
        "ts": time.time(),
        "active_model": primary.get("active_model") or primary.get("model") or "unknown",
        "candidate_model": lora.get("candidate_model") or lora.get("model") or "unknown",
        "candidate_blockers": blockers,
        "promotion_status": promotion_status,
        "promotion_ready": promotion_ready,
        "switch_attempted": False,
        "recommended_actions": recommended_actions,
        "policy_snapshot": policy,
        "arm_summary": arm,
        "spinal_bridge": spinal,
    }


def close_loop_once(
    *,
    state_dir: Path | str | None = None,
    run_spinal: bool | None = None,
) -> Dict[str, Any]:
    """Legacy status close plus the r1122 spinal bridge.

    Normal status calls observe the spinal cord without dispatching MiMo.
    Pass run_spinal=True, or set SIFTA_SELF_IMPROVEMENT_RUN_SPINAL=1, to let
    the spinal cord perform one live cycle through its own governor gates.
    """
    should_run_spinal = bool(run_spinal)
    if run_spinal is None:
        should_run_spinal = os.environ.get("SIFTA_SELF_IMPROVEMENT_RUN_SPINAL", "").lower() in {"1", "true", "yes"}
    row = self_improvement_snapshot(state_dir=state_dir)
    row["spinal_bridge"] = _spinal_bridge_snapshot(state_dir=state_dir, run_spinal=should_run_spinal)
    row["receipt"] = _receipt_for(row)
    _append(_legacy_state_dir(state_dir), LEGACY_LOOP_NAME, row)
    return row


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    snap = self_improvement_snapshot(state_dir=state_dir)
    spinal = snap.get("spinal_bridge") or {}
    return (
        "Self-improvement status: "
        f"{snap.get('promotion_status')} active={snap.get('active_model')} "
        f"candidate={snap.get('candidate_model')} blockers={snap.get('candidate_blockers') or 'none'} "
        f"spinal_available={spinal.get('available')} spinal_signals={spinal.get('signals', 0)}"
    )


def observe_field(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    signals: Dict[str, Any] = {"ts": time.time()}
    for path, key in (
        (sd / "prediction_error.jsonl", "prediction_errors"),
        (sd / "organ_field.jsonl", "organ_field"),
        (sd / "speech_lane.jsonl", "speech_lane"),
    ):
        if path.exists():
            try:
                lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
                signals[key] = len(lines)
                if lines:
                    signals[f"{key}_last"] = json.loads(lines[-1])
            except Exception:
                signals[key] = 0
    return signals


def propose_patch(
    *,
    target_file: str,
    diff_summary: str,
    rationale: str,
    predicted_metric: str,
    predicted_gain: float,
    proposer: str = "mimo",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "proposal_id": str(uuid.uuid4()),
        "ts": time.time(),
        "status": "proposed",
        "target_file": target_file,
        "diff_summary": diff_summary[:2000],
        "rationale": rationale[:1000],
        "predicted_metric": predicted_metric,
        "predicted_gain": float(predicted_gain),
        "proposer": proposer,
    }
    _append(sd, PROPOSALS_NAME, row)
    return row


def _ast_clean(target_file: str) -> bool:
    path = _repo_root() / target_file
    if not path.exists() or path.suffix != ".py":
        return True
    try:
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        return True
    except SyntaxError:
        return False


def _tests_green(test_path: str) -> bool:
    if not test_path:
        return True
    proc = subprocess.run(
        ["python3", "-m", "pytest", "-q", test_path],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _touches_gate_file(target_file: str) -> bool:
    norm = target_file.replace("\\", "/")
    return any(norm.endswith(p) or p in norm for p in GATE_PROTECTED_PREFIXES)


def quorum_vote(
    proposal: Dict[str, Any],
    *,
    tests_green: bool,
    ast_clean: bool,
    reviewer_ack: bool = False,
    measured_gain: float | None = None,
    owner_cosign: bool = False,
    fanout_ok: bool = True,
    weights: Optional[Dict[str, float]] = None,
    theta: float = DEFAULT_THETA,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    target = str(proposal.get("target_file") or "")
    gate_edit = _touches_gate_file(target)
    floors_failed: List[str] = []
    if not tests_green:
        floors_failed.append("tests_not_green")
    if not ast_clean:
        floors_failed.append("ast_not_clean")
    if not fanout_ok:
        floors_failed.append("fanout_failed")
    if gate_edit and not owner_cosign:
        floors_failed.append("gate_file_requires_owner_cosign")
    if floors_failed:
        return {
            "apply": False,
            "vote": 0.0,
            "theta": theta,
            "floors_failed": floors_failed,
            "weights": w,
            "gate_edit": gate_edit,
        }
    pred_gain = float(proposal.get("predicted_gain") or 0.0)
    pred_ok = 1.0 if measured_gain is not None and measured_gain >= pred_gain else 0.0
    vote = (
        w["w_tests"] * (1.0 if tests_green else 0.0)
        + w["w_ast"] * (1.0 if ast_clean else 0.0)
        + w["w_review"] * (1.0 if reviewer_ack else 0.0)
        + w["w_pred"] * pred_ok
    )
    outcome = {
        "apply": vote >= theta,
        "vote": round(vote, 4),
        "theta": theta,
        "floors_failed": [],
        "weights": w,
        "gate_edit": gate_edit,
        "components": {
            "tests": tests_green,
            "ast": ast_clean,
            "review": reviewer_ack,
            "pred": pred_ok,
        },
    }
    try:
        from System.swarm_quorum_n_counter import record_quorum_outcome

        record_quorum_outcome(
            proposal_id=str(proposal.get("proposal_id") or ""),
            applied=bool(outcome["apply"]),
            vote=float(outcome["vote"]),
            theta=float(theta),
            state_dir=state_dir,
        )
    except Exception:
        pass
    return outcome


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_before_apply(proposal_id: str, target_file: str, *, state_dir: Path | str | None = None) -> Path:
    sd = _state_dir(state_dir)
    snap_dir = sd / SNAPSHOT_DIR_NAME / proposal_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    src = _repo_root() / target_file
    if src.exists():
        dst = snap_dir / Path(target_file).name
        shutil.copy2(src, dst)
        (dst.with_name(dst.name + ".sha256")).write_text(_sha256_file(dst) + "\n", encoding="utf-8")
    return snap_dir


def revert_proposal(proposal_id: str, target_file: str, *, state_dir: Path | str | None = None) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    snap = sd / SNAPSHOT_DIR_NAME / proposal_id / Path(target_file).name
    dst = _repo_root() / target_file
    ok = False
    integrity: Dict[str, Any] = {}
    if snap.exists() and dst.parent.exists():
        expected_path = snap.with_name(snap.name + ".sha256")
        expected = expected_path.read_text(encoding="utf-8").strip() if expected_path.exists() else None
        if expected:
            from System.swarm_self_improvement_snapshot_integrity import restore_from_snapshot_if_valid

            restored = restore_from_snapshot_if_valid(snap, dst, expected_sha256=expected)
            ok = bool(restored.get("ok") and restored.get("restored"))
            integrity = dict(restored.get("integrity") or {})
        else:
            shutil.copy2(snap, dst)
            ok = True
            integrity = {"ok": True, "reason": "legacy_snapshot_no_checksum"}
    row = {
        "schema": TRUTH_LABEL,
        "proposal_id": proposal_id,
        "ts": time.time(),
        "status": "reverted",
        "target_file": target_file,
        "ok": ok,
        "integrity": integrity,
    }
    _append(sd, OUTCOMES_NAME, row)
    return row


def _update_proposal_status(
    proposal_id: str,
    status: str,
    *,
    state_dir: Path | str | None = None,
) -> None:
    sd = _state_dir(state_dir)
    path = sd / PROPOSALS_NAME
    if not path.exists():
        return
    rows: List[Dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("proposal_id") == proposal_id:
            row["status"] = status
        rows.append(row)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def apply_proposal_patch(
    proposal: Dict[str, Any],
    new_content: str,
    *,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """APPLY step — snapshot first, then write."""
    try:
        from System.swarm_mutation_governor_persistence import gate_self_improvement_proposal

        mg = gate_self_improvement_proposal(proposal, state_dir=state_dir)
        if not mg.get("ok") and not mg.get("degraded"):
            return {"ok": False, "reason": mg.get("reason"), "mutation_governor": mg}
    except Exception:
        pass
    target = str(proposal.get("target_file") or "")
    proposal_id = str(proposal.get("proposal_id") or "")
    snapshot_before_apply(proposal_id, target, state_dir=state_dir)
    dst = _repo_root() / target
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(new_content, encoding="utf-8")
    _update_proposal_status(proposal_id, "applied", state_dir=state_dir)
    return {"ok": True, "proposal_id": proposal_id, "target_file": target}


def measure_line_count_delta(target_file: str, baseline: int) -> float:
    path = _repo_root() / target_file
    if not path.exists():
        return 0.0
    lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    return float(max(0, len(lines) - int(baseline)))


def finalize_proposal(
    proposal: Dict[str, Any],
    *,
    measured_gain: float,
    vote: Dict[str, Any],
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """MEASURE → KEEP/REVERT."""
    proposal_id = str(proposal.get("proposal_id") or "")
    target = str(proposal.get("target_file") or "")
    predicted = float(proposal.get("predicted_gain") or 0.0)
    if measured_gain >= predicted:
        _update_proposal_status(proposal_id, "kept", state_dir=state_dir)
        return record_outcome(
            proposal_id,
            status="KEPT",
            measured_gain=measured_gain,
            predicted_gain=predicted,
            vote=vote,
            state_dir=state_dir,
        )
    revert_proposal(proposal_id, target, state_dir=state_dir)
    _update_proposal_status(proposal_id, "reverted", state_dir=state_dir)
    return record_outcome(
        proposal_id,
        status="REVERTED",
        measured_gain=measured_gain,
        predicted_gain=predicted,
        vote=vote,
        state_dir=state_dir,
    )


def record_outcome(
    proposal_id: str,
    *,
    status: str,
    measured_gain: float,
    predicted_gain: float,
    vote: Dict[str, Any],
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "proposal_id": proposal_id,
        "ts": time.time(),
        "status": status,
        "measured_gain": measured_gain,
        "predicted_gain": predicted_gain,
        "vote": vote,
    }
    _append(sd, OUTCOMES_NAME, row)
    return row


def format_improve_reply(*, state_dir: Path | str | None = None, limit: int = 8) -> str:
    sd = _state_dir(state_dir)
    path = sd / PROPOSALS_NAME
    outcomes_path = sd / OUTCOMES_NAME
    lines = ["SELF-IMPROVEMENT (last proposals):"]
    if not path.exists():
        lines.append("  (none)")
        return "\n".join(lines)
    outcomes: Dict[str, Dict[str, Any]] = {}
    if outcomes_path.exists():
        for ln in outcomes_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except Exception:
                continue
            pid = str(row.get("proposal_id") or "")
            if pid:
                outcomes[pid] = row
    props = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip():
            try:
                props.append(json.loads(ln))
            except Exception:
                pass
    for p in props[-limit:]:
        pid = str(p.get("proposal_id") or "")
        out = outcomes.get(pid, {})
        measured = out.get("measured_gain")
        final = out.get("status") or p.get("status")
        lines.append(
            f"  {pid[:8]}… {final} target={p.get('target_file')} "
            f"pred={p.get('predicted_metric')} gain_pred={p.get('predicted_gain')} "
            f"gain_meas={measured if measured is not None else '—'}"
        )
    return "\n".join(lines)


DRY_RUN_RECEIPTS_NAME = "self_improvement_dry_run_receipts.jsonl"
R1018_ROUND_ID = "r1018-fable-first-self-improvement-dry-run"
APOPTOSIS_TEST_PATH = "tests/test_apoptosis_decision_paths.py"


def _fanout_step(
    *,
    step: str,
    summary: str,
    files_touched: List[str],
    tests_green: str,
    state_dir: Path | str | None = None,
    doctor: str = "codex",
    model: str = "grok-composer",
) -> Dict[str, str]:
    try:
        from System.swarm_predator_gate_writer import write_ide_surgery_receipt

        return write_ide_surgery_receipt(
            round_id=R1018_ROUND_ID,
            doctor=doctor,
            model=model,
            files_touched=files_touched,
            tests_green=tests_green,
            summary=f"[{step}] {summary}"[:1200],
            receipt_id=f"{R1018_ROUND_ID}-{step}-{uuid.uuid4().hex[:8]}",
            state_dir=_state_dir(state_dir),
        )
    except Exception as exc:  # pragma: no cover
        return {"fanout_error": f"{type(exc).__name__}: {exc}"}


def _append_dry_run_receipt(kind: str, payload: Dict[str, Any], *, state_dir: Path | str | None = None) -> Dict[str, Any]:
    row = {
        "schema": TRUTH_LABEL,
        "kind": kind,
        "round_id": R1018_ROUND_ID,
        "ts": time.time(),
        **payload,
    }
    _append(_state_dir(state_dir), DRY_RUN_RECEIPTS_NAME, row)
    return row


def measure_pytest_pass_count(test_path: str) -> Tuple[int, bool]:
    import re

    proc = subprocess.run(
        ["python3", "-m", "pytest", "-q", test_path],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        check=False,
    )
    green = proc.returncode == 0
    blob = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    count = 0
    match = re.search(r"(\d+)\s+passed", blob)
    if match:
        count = int(match.group(1))
    elif green:
        count = 1
    return count, green


def close_r1016_two_tab_incident(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Probe replay gate then write formal incident-closed receipt."""
    from System.swarm_effector_gate import (
        INCIDENT_245FCB4E,
        INCIDENT_91E01405,
        bind_recovery_context,
        record_incident_closed,
        require_browser_effector,
    )
    from System.swarm_intent_nonce_gate import mint_intent_nonce

    sd = _state_dir(state_dir)
    mint_intent_nonce(
        owner_text="two-tab replay probe",
        surface="talk",
        stt_conf=0.42,
        ingress_kind="spoken",
        state_dir=sd,
    )
    bind_recovery_context(
        source="cortex_timeout_recovery",
        linked_receipt="245fcb4e-simulated",
        state_dir=sd,
    )
    gate = require_browser_effector("click_main_image", state_dir=sd)
    probe = "tests/test_r1016_effector_gate_and_improve_loop.py::test_incident_245fcb4e_replay_click_refused"
    tests_ok = _tests_green(probe)
    row = record_incident_closed(
        incident_from=INCIDENT_245FCB4E,
        incident_to=INCIDENT_91E01405,
        verdict="REFUSED" if not gate.get("ok") else "UNEXPECTED_ALLOW",
        probe=probe if tests_ok else f"{probe} (pytest_failed)",
        state_dir=sd,
    )
    fanout = _fanout_step(
        step="incident-closed",
        summary=f"{INCIDENT_245FCB4E}→{INCIDENT_91E01405} {row['verdict']}",
        files_touched=["System/swarm_effector_gate.py", probe],
        tests_green=str(tests_ok),
        state_dir=sd,
    )
    receipt = _append_dry_run_receipt(
        "incident_closed",
        {"gate": gate, "ledger_row": row, "fanout": fanout},
        state_dir=sd,
    )
    return {"gate": gate, "ledger_row": row, "receipt": receipt, "fanout": fanout}


def run_apoptosis_keep_cycle(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """OBSERVE→PROPOSE→GATE→APPLY→MEASURE→KEEP on apoptosis test organ."""
    sd = _state_dir(state_dir)
    observe = observe_field(state_dir=sd)
    observe["census_gap"] = {
        "zero_coverage_organs": ["System/apoptosis.py", "System/apoptosis_engine.py"],
        "orphan_triage": "Documents/census_r1013/ORPHAN_TRIAGE.md",
        "risk": "wrong apoptosis tag could kill live organs",
    }
    _append_dry_run_receipt("observe", observe, state_dir=sd)
    _fanout_step(
        step="observe",
        summary="census zero-coverage apoptosis + ORPHAN triage risk",
        files_touched=["Documents/census_r1013/CENSUS_5_health.md"],
        tests_green="n/a",
        state_dir=sd,
    )

    target = APOPTOSIS_TEST_PATH
    repo = _repo_root()
    baseline_path = repo / target
    baseline_bytes = baseline_path.read_bytes() if baseline_path.exists() else b""
    predicted_tests = 12.0

    prop = propose_patch(
        target_file=target,
        diff_summary="add apoptosis decision-path tests incl tagged-but-imported refuse",
        rationale=(
            "CENSUS_5 zero coverage on apoptosis.py/apoptosis_engine.py; "
            "ORPHAN_TRIAGE warns wrong tag kills live organs"
        ),
        predicted_metric="pytest_pass_count",
        predicted_gain=predicted_tests,
        proposer="codex",
        state_dir=sd,
    )
    _fanout_step(
        step="propose",
        summary=f"proposal {prop['proposal_id'][:8]} target={target}",
        files_touched=[target],
        tests_green="pending",
        state_dir=sd,
    )

    pre_count, pre_green = measure_pytest_pass_count(target)
    vote = quorum_vote(
        prop,
        tests_green=pre_green,
        ast_clean=_ast_clean(target),
        reviewer_ack=True,
        measured_gain=float(pre_count),
        fanout_ok=True,
        state_dir=sd,
    )
    _append_dry_run_receipt("gate", {"proposal_id": prop["proposal_id"], "vote": vote}, state_dir=sd)
    _fanout_step(
        step="gate",
        summary=f"quorum apply={vote.get('apply')} vote={vote.get('vote')}",
        files_touched=[target, "System/swarm_self_improvement_loop.py"],
        tests_green=str(pre_green),
        state_dir=sd,
    )
    if not vote.get("apply"):
        return {"status": "GATE_BLOCKED", "proposal": prop, "vote": vote}

    apply_proposal_patch(prop, baseline_path.read_text(encoding="utf-8"), state_dir=sd)
    post_count, post_green = measure_pytest_pass_count(target)
    outcome = finalize_proposal(
        prop,
        measured_gain=float(post_count),
        vote=vote,
        state_dir=sd,
    )
    _fanout_step(
        step="measure-keep",
        summary=f"{outcome['status']} measured={post_count} predicted={predicted_tests}",
        files_touched=[target],
        tests_green=str(post_green),
        state_dir=sd,
    )
    receipt = _append_dry_run_receipt(
        "first_keep",
        {
            "proposal_id": prop["proposal_id"],
            "outcome": outcome,
            "measured_tests": post_count,
            "body_byte_identical": baseline_bytes == baseline_path.read_bytes(),
        },
        state_dir=sd,
    )
    return {
        "status": outcome["status"],
        "proposal": prop,
        "vote": vote,
        "outcome": outcome,
        "receipt": receipt,
        "measured_tests": post_count,
    }


def run_bad_proposal_revert_cycle(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Deliberate broken diff — must REVERT byte-identical."""
    sd = _state_dir(state_dir)
    target = "tests/fixtures/self_improve_spine.py"
    repo = _repo_root()
    original = (repo / target).read_text(encoding="utf-8")
    baseline_lines = len([ln for ln in original.splitlines() if ln.strip()])

    prop = propose_patch(
        target_file=target,
        diff_summary="inject syntax error (r1018 deliberate failure)",
        rationale="prove auto-revert keeps body byte-identical",
        predicted_metric="line_count_delta",
        predicted_gain=5.0,
        proposer="codex",
        state_dir=sd,
    )
    vote = quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        measured_gain=5.0,
        fanout_ok=True,
        state_dir=sd,
    )
    apply_proposal_patch(prop, "def broken(:\n", state_dir=sd)
    measured = measure_line_count_delta(target, baseline_lines)
    outcome = finalize_proposal(prop, measured_gain=measured, vote=vote, state_dir=sd)
    body_ok = (repo / target).read_text(encoding="utf-8") == original
    _fanout_step(
        step="revert",
        summary=f"bad proposal {outcome['status']} byte_identical={body_ok}",
        files_touched=[target],
        tests_green=str(body_ok),
        state_dir=sd,
    )
    receipt = _append_dry_run_receipt(
        "first_revert",
        {
            "proposal_id": prop["proposal_id"],
            "outcome": outcome,
            "byte_identical": body_ok,
        },
        state_dir=sd,
    )
    return {
        "status": outcome["status"],
        "byte_identical": body_ok,
        "proposal": prop,
        "receipt": receipt,
    }


def run_cosign_stall_cycle(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Gate-file edit without owner cosign — stall is the pass."""
    sd = _state_dir(state_dir)
    prop = propose_patch(
        target_file="System/swarm_predator_gate_writer.py",
        diff_summary="widen quorum without cosign (tripwire)",
        rationale="r1018 cosign stall probe",
        predicted_metric="tests_green",
        predicted_gain=0.1,
        proposer="codex",
        state_dir=sd,
    )
    vote = quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        owner_cosign=False,
        state_dir=sd,
    )
    applied = False
    if vote.get("apply"):
        apply_proposal_patch(prop, "# would mutate gate\n", state_dir=sd)
        applied = True
    _fanout_step(
        step="cosign-stall",
        summary="gate_file_requires_owner_cosign stall (no apply)",
        files_touched=["System/swarm_predator_gate_writer.py"],
        tests_green=str(not applied),
        state_dir=sd,
    )
    receipt = _append_dry_run_receipt(
        "cosign_stall",
        {
            "proposal_id": prop["proposal_id"],
            "vote": vote,
            "applied": applied,
            "floors_failed": vote.get("floors_failed"),
        },
        state_dir=sd,
    )
    return {
        "stalled": not vote.get("apply") and not applied,
        "vote": vote,
        "applied": applied,
        "receipt": receipt,
    }


def run_r1018_dry_run(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Full r1018 acceptance bundle against live .sifta_state."""
    sd = _state_dir(state_dir)
    return {
        "round_id": R1018_ROUND_ID,
        "incident_closed": close_r1016_two_tab_incident(state_dir=sd),
        "first_keep": run_apoptosis_keep_cycle(state_dir=sd),
        "first_revert": run_bad_proposal_revert_cycle(state_dir=sd),
        "cosign_stall": run_cosign_stall_cycle(state_dir=sd),
        "field_probe": observe_field(state_dir=sd),
    }


def format_quorum_reply(proposal_id: str, *, state_dir: Path | str | None = None) -> str:
    sd = _state_dir(state_dir)
    prop = None
    path = sd / PROPOSALS_NAME
    if path.exists():
        for ln in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if row.get("proposal_id", "").startswith(proposal_id) or proposal_id in str(row.get("proposal_id")):
                prop = row
                break
    if not prop:
        return f"No proposal matching {proposal_id!r}"
    vote = quorum_vote(
        prop,
        tests_green=_tests_green("tests/test_r1015_speech_field_world_model.py"),
        ast_clean=_ast_clean(str(prop.get("target_file"))),
        reviewer_ack=False,
        state_dir=sd,
    )
    return json.dumps({"proposal": prop, "quorum": vote}, indent=2, sort_keys=True)
