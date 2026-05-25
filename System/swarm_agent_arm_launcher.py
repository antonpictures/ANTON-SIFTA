#!/usr/bin/env python3
"""Receipt-first launcher for SIFTA governed agent arms.

The exact/test path is disabled unless the arm's registry env flag is set.
Evidence mode is Alice's native read-only arm path: it accepts messy output as
evidence, but still writes prompt/output hashes and result receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from typing import Any, Callable, Mapping

from System.swarm_agent_arm_registry import AgentArmSpec, get_agent_arm

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS = "agent_arm_receipts.jsonl"


@dataclass(frozen=True)
class AgentArmResult:
    ok: bool
    receipt_id: str
    arm_id: str
    status: str
    mode: str = "exact"
    output: str = ""
    stderr: str = ""
    returncode: int | None = None
    artifact_path: str = ""


Runner = Callable[[list[str], int], Any]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _arm_receipt_path(state_dir: Path | None = None) -> Path:
    return Path(state_dir or _STATE) / _RECEIPTS


def _kernel_arm_heartbeat(
    arm: AgentArmSpec,
    *,
    state_dir: Path | None,
    receipt_id: str,
    current_job: str,
    status: str,
    ok: bool | None = None,
    evidence_mode: bool = False,
    cortex_metrics: dict[str, Any] | None = None,
) -> None:
    """Mirror every arm launch into the kernel process table.

    Agent arms are organs, not side channels. This helper is deliberately
    best-effort so an unhealthy kernel ledger cannot block Alice's evidence
    collection path.
    """
    try:
        from System.swarm_kernel_process_table import OrganProcess, get_kernel_process_table

        table = get_kernel_process_table(state_root=Path(state_dir or _STATE))
        pid = f"agent_arm:{arm.arm_id}"
        table.ensure_registered(
            OrganProcess(
                pid=pid,
                organ_id=arm.arm_id,
                ring=2,
                health=1.0,
                stgm_balance=0.0,
                current_job=current_job,
                last_receipt_id=receipt_id,
                failure_count=0,
                last_heartbeat_ts=time.time(),
                location="unknown",
                bodies_present=[],
                metadata={
                    "display_name": arm.display_name,
                    "model": arm.model,
                    "provider_base_url": arm.provider_base_url,
                    "source": "swarm_agent_arm_launcher",
                },
            ),
            receipt_id=receipt_id,
        )
        if ok is None:
            health = None
            stgm_delta = 0.0
            failure_delta = 0
        else:
            health = 1.0 if ok else 0.45
            stgm_delta = 0.2 if ok else -0.1
            failure_delta = 0 if ok else 1
        metrics = cortex_metrics or {}
        table.heartbeat(
            pid,
            health=health,
            stgm_delta=stgm_delta,
            current_job=current_job,
            receipt_id=receipt_id,
            failure_delta=failure_delta,
            metadata={
                "arm_status": status,
                "evidence_mode": str(bool(evidence_mode)),
                "tokens_per_sec": str(metrics.get("tokens_per_sec", 0.0)),
                "latency_ms": str(metrics.get("latency_ms", 0.0)),
                "used_mtp": str(bool(metrics.get("used_mtp", False))),
            },
        )
    except Exception:
        return


def hermes_cortex_override(state_dir: Path | None = None) -> str | None:
    """Owner/Alice-settable cortex for the Hermes arm.

    Returns the model string written to ``.sifta_state/hermes_cortex.json``
    (``{"model": "..."}``), or ``None`` if no explicit switch has been made.

    This is HOW "Alice changes the Hermes cortex" without a code edit: write the
    file, the next ``ask_hermes`` call carries the new model. Truth discipline
    (covenant §6 / §7.2): the registry ``model`` field was only ever *recorded*
    in receipts, never passed to the ``hermes chat`` CLI — so the receipt could
    claim one cortex while Hermes ran its own default. We close that gap by
    appending ``--model`` to the command *only* when an override is set, so:
      • no override  → command is byte-for-byte the working default (no regression);
      • override set → the model is REAL (carried on argv, visible in the receipt's
                        ``command`` field) and Hermes is actually asked to use it.
    """
    try:
        path = Path(state_dir or _STATE) / "hermes_cortex.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        model = str(data.get("model") or "").strip()
        return model or None
    except Exception:
        return None


_COVENANT_BOOT_PREFIX = (
    "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md first — "
    "boot by reading it so you understand the SIFTA OS (one Alice, one global chat, "
    "receipts/effector truth §6, no fake actions, file paths under "
    "/Users/ioanganton/Music/ANTON_SIFTA). Then do this for the SIFTA OS:\n\n"
)


def _build_command(arm: AgentArmSpec, prompt: str) -> list[str]:
    # Owner standing order (George 2026-05-24): the external SIFTA-context cortexes
    # (Grok, Claude, Hermes) must ALWAYS be told to read the covenant first, or they
    # have no idea what SIFTA is when asked to modify code or build apps. Prefix it
    # here so every delegation boots them with context. (corvid is internal/local;
    # codex is a read-only reviewer — they don't get the boot prefix.)
    if arm.arm_id in {"grok_agent", "claude_agent", "hermes_agent", "codex_agent"}:
        prompt = _COVENANT_BOOT_PREFIX + (prompt or "")
    if arm.arm_id == "corvid_scout":
        return [arm.command[0], "--task", "evidence", "--query", prompt]
    if arm.arm_id == "grok_agent":
        # External xAI Grok via the repo wrapper, one-shot (real grok-4, no hallucination).
        # Owner 2026-05-24: Grok runs from global chat like Hermes.
        import sys as _sys
        return [_sys.executable, str(_REPO / "grok_chat.py"), "--one-shot", prompt]
    if arm.arm_id == "claude_agent":
        # External Claude Code CLI, headless print mode. Run in _REPO (default cwd of
        # the runner) so Claude can read the codebase AND write app files for the
        # build tournament. Owner standing order (George 2026-05-24): ALWAYS ALLOW all
        # permissions, never choose otherwise — so pass --dangerously-skip-permissions
        # (the headless equivalent of Grok's Ctrl+O yolo). Without it, `claude -p`
        # defaults to NOT auto-accepting edits, so it can produce code as text but
        # never write the files — a build that "ran" yet left nothing on disk. This is
        # the owner's sovereign choice for HIS node; the build verifier + git diff are
        # the audit trail of exactly what Claude wrote.
        return [arm.command[0], "-p", "--dangerously-skip-permissions", prompt]
    command = list(arm.command)
    if arm.arm_id == "codex_agent":
        command += [prompt]
        return command
    command += ["--max-turns", str(arm.max_turns)]
    if arm.default_toolsets:
        command += ["--toolsets", ",".join(arm.default_toolsets)]
    # Hermes cortex switch (opt-in, truthful). Only when the owner/Alice has
    # explicitly written hermes_cortex.json — otherwise the default command is
    # unchanged and the currently-working path is never broken.
    if arm.arm_id == "hermes_agent":
        _override = hermes_cortex_override()
        if _override:
            command += ["--model", _override]
    command += ["--query", prompt]
    return command


def _default_runner(command: list[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(_REPO),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_s,
    )


def _append_arm_live_row(*, text: str, action: str, focused_cli: str, payload: dict[str, Any]) -> None:
    """Mirror one live line from an agent-arm subprocess into the shared
    process-trace ledger (covenant §1.A pt.3: 'visible tool scrollback, readable
    like a real terminal, never hidden').

    George 2026-05-24: "I can't tell if anything is happening." Hermes runs through
    this launcher as a blocking subprocess — unlike Grok's visible PTY — so until
    now its work was a black box for up to the whole timeout. The Talk widget
    already tails matrix_terminal_process_trace.jsonl into its live thinking panel;
    writing here makes the arm's output stream there in real time. Best-effort;
    never raises (visibility must never break the actual call)."""
    clean = (text or "").rstrip()
    if not clean:
        return
    try:
        path = _STATE / "matrix_terminal_process_trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "source": "agent_arm_launcher",
            "kind": "agent_arm_live",
            "action": action,
            "focused_cli": focused_cli,
            "text": clean,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _streaming_runner(command: list[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    """Run an agent-arm CLI with LIVE visibility instead of buffering to the end.

    Popens the process, streams each stdout line into the shared process-trace
    ledger as it arrives, and emits an elapsed heartbeat during silent stretches
    (e.g. a large cortex cold-loading into RAM). Returns a CompletedProcess so the
    rest of ask_agent_arm is unchanged, and raises TimeoutExpired on the deadline
    exactly like subprocess.run, so the existing timeout receipt path still works."""
    import select

    focused_cli = command[0] if command else "arm"
    live_action = "hermes_live" if focused_cli == "hermes" else "agent_arm_live"
    session = uuid.uuid4().hex[:12]
    start = time.monotonic()
    _append_arm_live_row(
        text=f"◆ {focused_cli} starting (cortex may need to cold-load) — session {session}",
        action="agent_arm_live_start",
        focused_cli=focused_cli,
        payload={"session": session, "command": command},
    )
    proc = subprocess.Popen(
        command,
        cwd=str(_REPO),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    out_lines: list[str] = []
    last_hb = start
    try:
        while True:
            now = time.monotonic()
            if now - start > timeout_s:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                raise subprocess.TimeoutExpired(command, timeout_s, output="\n".join(out_lines))
            rlist = []
            if proc.stdout is not None:
                rlist, _, _ = select.select([proc.stdout], [], [], 1.0)
            if rlist:
                line = proc.stdout.readline()
                if line == "":  # EOF
                    break
                line = line.rstrip("\n")
                if line.strip():
                    out_lines.append(line)
                    _append_arm_live_row(
                        text=line,
                        action=live_action,
                        focused_cli=focused_cli,
                        payload={"session": session},
                    )
                    last_hb = now
            else:
                if proc.poll() is not None:
                    break
                if now - last_hb >= 4.0:
                    last_hb = now
                    _append_arm_live_row(
                        text=f"◆ {focused_cli} working — {int(now - start)}s elapsed (loading/generating, not frozen)",
                        action="agent_arm_heartbeat",
                        focused_cli=focused_cli,
                        payload={"session": session, "elapsed_s": int(now - start)},
                    )
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
    try:
        rest = proc.stdout.read() if proc.stdout else ""
        for ln in (rest or "").splitlines():
            if ln.strip():
                out_lines.append(ln)
                _append_arm_live_row(text=ln, action=live_action, focused_cli=focused_cli, payload={"session": session})
    except Exception:
        pass
    try:
        rc = proc.wait(timeout=5)
    except Exception:
        rc = proc.poll()
    _append_arm_live_row(
        text=f"◆ {focused_cli} finished rc={rc} — {int(time.monotonic() - start)}s total",
        action="agent_arm_live_done",
        focused_cli=focused_cli,
        payload={"session": session, "returncode": rc},
    )
    return subprocess.CompletedProcess(command, rc if rc is not None else 0, "\n".join(out_lines), "")


def _run_internal_arm(arm: AgentArmSpec, prompt: str, timeout_s: int) -> tuple[int, str, str, dict[str, Any]]:
    """Run a native Python organ arm without spawning a wrapper CLI."""
    if arm.arm_id != "corvid_scout":
        raise ValueError(f"Unknown internal arm: {arm.arm_id}")
    from System.swarm_corvid_apprentice import SwarmCorvidApprentice

    corvid = SwarmCorvidApprentice(
        timeout_s=max(1.0, min(float(timeout_s), 30.0)),
        max_tokens=384,
    )
    result = corvid.evidence(prompt)
    return (
        0 if result.success else 1,
        result.response,
        result.error or "",
        {
            "internal_runner": "SwarmCorvidApprentice.evidence",
            "task": result.task.value,
            "model": result.model,
            "latency_s": round(float(result.latency_s), 4),
            "latency_ms": round(float(result.latency_s) * 1000.0, 2),
            "tokens_per_sec": round(float(result.tokens_per_sec), 6),
            "used_mtp": bool(result.used_mtp),
            "corvid_ledger": "corvid_apprentice_trace.jsonl",
        },
    )


def ask_agent_arm(
    arm_id: str,
    prompt: str,
    *,
    state_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    timeout_s: int = 60,
    require_exact: str | None = None,
    evidence_mode: bool = False,
) -> AgentArmResult:
    """Run one bounded arm query with before/after receipts.

    Exact/test execution is blocked unless the registry env flag is set.
    Evidence mode is Alice's native read-only arm path: it always writes
    receipts and captures messy output as evidence instead of rejecting UI text.
    ``require_exact`` lets callers reject wrapper text before Alice can treat
    the output as clean evidence.
    """

    arm = get_agent_arm(arm_id)
    env_map = env or os.environ
    receipt_id = str(uuid.uuid4())
    receipt_path = _arm_receipt_path(state_dir)
    prompt = (prompt or "").strip()
    if not prompt:
        return AgentArmResult(False, receipt_id, arm.arm_id, "EMPTY_PROMPT")

    command = _build_command(arm, prompt)
    start_row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "truth_label": "AGENT_ARM_LAUNCH_ATTEMPT",
        "arm_id": arm.arm_id,
        "display_name": arm.display_name,
        "model": arm.model,
        "provider_base_url": arm.provider_base_url,
        "enabled": arm.enabled,
        "live_env_var": arm.live_env_var,
        "live_env_enabled": arm.live_enabled(env_map),
        "mode": "evidence" if evidence_mode else "exact",
        "evidence_mode": evidence_mode,
        "prompt_sha256": _sha256_text(prompt),
        "require_exact_sha256": _sha256_text(require_exact) if require_exact else None,
        "command": command,
    }
    _append_jsonl(receipt_path, start_row)
    _kernel_arm_heartbeat(
        arm,
        state_dir=state_dir,
        receipt_id=receipt_id,
        current_job="launch_attempt",
        status="ATTEMPT",
        ok=None,
        evidence_mode=evidence_mode,
    )

    if not evidence_mode and not arm.live_enabled(env_map):
        end_row = {
            **start_row,
            "ts": time.time(),
            "truth_label": "AGENT_ARM_LAUNCH_BLOCKED",
            "ok": False,
            "status": "DISABLED_ENV_GATE",
            "truth_note": f"Set {arm.live_env_var}=1 to allow one guarded live arm call.",
        }
        _append_jsonl(receipt_path, end_row)
        _kernel_arm_heartbeat(
            arm,
            state_dir=state_dir,
            receipt_id=receipt_id,
            current_job="blocked_env_gate",
            status="DISABLED_ENV_GATE",
            ok=False,
            evidence_mode=evidence_mode,
        )
        return AgentArmResult(
            False,
            receipt_id,
            arm.arm_id,
            "DISABLED_ENV_GATE",
            mode="exact",
            artifact_path=str(receipt_path),
        )

    # Hermes + Grok + Claude + Codex stream live into the thinking panel (visibility); others buffer.
    if runner is None:
        runner = _streaming_runner if arm.arm_id in {"hermes_agent", "grok_agent", "claude_agent", "codex_agent"} else _default_runner
    t0 = time.time()
    try:
        internal_meta: dict[str, Any] = {}
        if arm.arm_id == "corvid_scout":
            returncode, stdout, stderr, internal_meta = _run_internal_arm(arm, prompt, timeout_s)
        else:
            completed = runner(command, timeout_s)
            returncode = int(getattr(completed, "returncode", 0))
            stdout = str(getattr(completed, "stdout", "") or "")
            stderr = str(getattr(completed, "stderr", "") or "")
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        internal_meta = {}
        returncode = None
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        timed_out = True
    except Exception as exc:
        internal_meta = {}
        returncode = None
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"
        timed_out = False

    output = stdout.strip()
    exact_ok = True
    if require_exact is not None and not evidence_mode:
        exact_ok = output == require_exact
    ok = returncode == 0 and not timed_out and exact_ok
    if timed_out:
        status = "TIMEOUT"
    elif returncode != 0:
        status = "COMMAND_FAILED"
    elif evidence_mode:
        status = "EVIDENCE_CAPTURED"
    elif not exact_ok:
        status = "EXACTNESS_FAILED"
    else:
        status = "OK"

    end_row = {
        **start_row,
        "ts": time.time(),
        "truth_label": "AGENT_ARM_LAUNCH_RESULT",
        "ok": ok,
        "status": status,
        "duration_s": round(time.time() - t0, 3),
        "returncode": returncode,
        "timed_out": timed_out,
        "evidence_mode": evidence_mode,
        "output_sha256": _sha256_text(output),
        "stderr_sha256": _sha256_text(stderr),
        "output_tail": output[-2000:],
        "stderr_tail": stderr[-2000:],
        "internal_arm": internal_meta,
    }
    _append_jsonl(receipt_path, end_row)
    cortex_metrics = {
        "tokens_per_sec": float(internal_meta.get("tokens_per_sec") or 0.0),
        "latency_ms": float(internal_meta.get("latency_ms") or 0.0),
        "used_mtp": bool(internal_meta.get("used_mtp")),
    }
    _kernel_arm_heartbeat(
        arm,
        state_dir=state_dir,
        receipt_id=receipt_id,
        current_job=f"launch_result:{status}",
        status=status,
        ok=ok,
        evidence_mode=evidence_mode,
        cortex_metrics=cortex_metrics,
    )
    try:
        from System.swarm_arm_outcome_learner import learn_from_receipts

        learn_from_receipts(state_dir=Path(state_dir) if state_dir is not None else None, max_rows=80)
    except Exception:
        pass
    # claude-opus-4-7 2026-05-25 — close the return leg (owner gate: "commit only
    # if alice learns"). learn_from_receipts above already refreshes routing
    # weights from the final receipt (item 3). Here we add the two missing
    # self-integration steps so each run actually changes Alice, not just the log:
    #   (4) update the arm's REPUTATION in the canonical root .sifta_reputation/
    #       (NOT Kernel/.sifta_reputation — that sidecar is read by nobody), and
    #   (5) write a diary/briefing row so the run is remembered, not only receipted.
    # Best-effort: a learning failure must never break the actual tool call.
    try:
        _rep_event = (
            "FAILURE" if (timed_out or returncode != 0)
            else "FALSE_SIGNAL" if status == "EXACTNESS_FAILED"
            else "SUCCESS"
        )
        _agent_id = (arm.arm_id or "").replace("_agent", "").upper() or "UNKNOWN_ARM"
        try:
            from Kernel import reputation_engine as _rep_engine
            # Pin to the canonical root reputation dir the swarm actually reads.
            _rep_engine.REP_DIR = _REPO / ".sifta_reputation"
            _rep_engine.REP_DIR.mkdir(exist_ok=True)
            _rep_engine.update_reputation(_agent_id, _rep_event)
        except Exception:
            pass
        # (5) diary / briefing row — append-only, same .sifta_state as receipts.
        try:
            _briefing = {
                "ts": time.time(),
                "briefing_id": str(uuid.uuid4()),
                "truth_label": "ALICE_AGENT_ARM_BRIEFING",
                "from_doctor": "agent_arm_launcher",
                "arm_id": arm.arm_id,
                "display_name": arm.display_name,
                "status": status,
                "ok": ok,
                "evidence_mode": evidence_mode,
                "receipt_id": receipt_id,
                "duration_s": round(time.time() - t0, 3),
                "reputation_event": _rep_event,
                "reputation_agent": _agent_id,
                "note": (
                    f"{arm.display_name} run finished status={status}; "
                    f"reputation {_rep_event}; routing weights refreshed."
                ),
            }
            _append_jsonl(receipt_path.parent / "alice_agent_arm_briefings.jsonl", _briefing)
        except Exception:
            pass
    except Exception:
        pass
    return AgentArmResult(
        ok,
        receipt_id,
        arm.arm_id,
        status,
        mode="evidence" if evidence_mode else "exact",
        output=output,
        stderr=stderr,
        returncode=returncode,
        artifact_path=str(receipt_path),
    )


def ask_hermes(
    prompt: str,
    *,
    state_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    timeout_s: int = 60,
    require_exact: str | None = None,
    evidence_mode: bool = False,
) -> AgentArmResult:
    return ask_agent_arm(
        "hermes_agent",
        prompt,
        state_dir=state_dir,
        env=env,
        runner=runner,
        timeout_s=timeout_s,
        require_exact=require_exact,
        evidence_mode=evidence_mode,
    )


def ask_hermes_evidence(
    prompt: str,
    *,
    state_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    timeout_s: int = 60,
) -> AgentArmResult:
    """Alice-owned evidence call: no exactness gate, receipts always written."""

    return ask_hermes(
        prompt,
        state_dir=state_dir,
        env=env,
        runner=runner,
        timeout_s=timeout_s,
        evidence_mode=True,
    )


def ask_codex_evidence(
    prompt: str,
    *,
    state_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    timeout_s: int = 60,
) -> AgentArmResult:
    """Alice-owned Codex evidence call: read-only sandbox, receipts written."""

    return ask_agent_arm(
        "codex_agent",
        prompt,
        state_dir=state_dir,
        env=env,
        runner=runner,
        timeout_s=timeout_s,
        evidence_mode=True,
    )
