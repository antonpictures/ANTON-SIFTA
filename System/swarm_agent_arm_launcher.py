#!/usr/bin/env python3
"""Receipt-first launcher for SIFTA governed agent arms.

Registered arms are available by default. Receipts, kernel health, and
metabolic accounting are the control surface; there is no owner approval popup
or env unlock in the normal path. Round 64 removed the old read-only
``evidence_mode`` route: receipts are the evidence, and arms run live.
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
_METABOLISM_RECEIPTS = "agent_arm_metabolism.jsonl"
_DEFAULT_AGENT_ARM_STALL_CEMETERY_S = 8 * 60
_METABOLIC_CACHE_TS = 0.0
_METABOLIC_CACHE: tuple[Any, Any, dict[str, Any]] | None = None


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


def _episodic_bucket(ts: float, *, hours: int = 4) -> str:
    """Return the same local rolling bucket shape used by the episodic diary."""
    t = time.localtime(float(ts or time.time()))
    bucket_hour = (int(t.tm_hour) // int(hours)) * int(hours)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{bucket_hour:02d}:00"


def _write_agent_arm_episodic_memory(
    *,
    state_dir: Path | None,
    arm: AgentArmSpec,
    receipt_id: str,
    status: str,
    ok: bool,
    evidence_mode: bool,
    duration_s: float,
    output: str,
    stderr: str,
    timed_out: bool,
    returncode: int | None,
) -> None:
    """Write one compact hippocampal event for every completed arm run.

    The outcome learner updates routing weights and the arm briefing helps the
    arm subsystem. This row is for Alice's memory organ: even a failed or timed
    out arm run becomes part of the remembered day-story immediately, not only
    after a later batch diary sweep.
    """
    state = Path(state_dir or _STATE)
    now = time.time()
    result_label = "success" if ok else "failure"
    source_hash = _sha256_text(
        json.dumps(
            {
                "receipt_id": receipt_id,
                "arm_id": arm.arm_id,
                "status": status,
                "ok": bool(ok),
                "output_sha256": _sha256_text(output or ""),
                "stderr_sha256": _sha256_text(stderr or ""),
            },
            sort_keys=True,
        )
    )
    row = {
        "ts": now,
        "truth_label": "EPISODIC_DIARY_AGENT_ARM_RESULT_V1",
        "bucket": _episodic_bucket(now, hours=4),
        "window_hours": 4,
        "labels": [
            "agent_arm",
            "external_cortex",
            result_label,
            f"arm:{arm.arm_id}",
            f"status:{status}",
        ],
        "event_count": 1,
        "source_counts": {"agent_arm_receipts.jsonl": 1},
        "source_hash": source_hash,
        "facts": [
            (
                f"{arm.display_name} finished status={status} ok={bool(ok)} "
                f"duration_s={round(float(duration_s or 0.0), 3)} "
                f"receipt={receipt_id}"
            ),
            "mode=exact",
            (
                "timed_out=true"
                if timed_out
                else f"returncode={returncode}"
            ),
        ],
        "arm_id": arm.arm_id,
        "display_name": arm.display_name,
        "status": status,
        "ok": bool(ok),
        "receipt_id": receipt_id,
        "duration_s": round(float(duration_s or 0.0), 3),
        "evidence_mode": bool(evidence_mode),
        "output_sha256": _sha256_text(output or ""),
        "stderr_sha256": _sha256_text(stderr or ""),
    }
    _append_jsonl(state / "episodic_diary.jsonl", row)


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


def _extract_external_usd_cost(output: str, stderr: str) -> float:
    """Best-effort parse of CLI-reported external cost from JSONL streams."""
    total = 0.0
    for line in f"{output or ''}\n{stderr or ''}".splitlines():
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        try:
            row = json.loads(text)
        except Exception:
            continue
        try:
            cost = float(row.get("total_cost_usd") or 0.0)
        except Exception:
            cost = 0.0
        if cost > total:
            total = cost
    return round(total, 8)


def _metabolic_context() -> tuple[Any | None, Any | None, dict[str, Any]]:
    """Return cached live metabolism so arm tests and bursts do not hammer sensors."""
    global _METABOLIC_CACHE_TS, _METABOLIC_CACHE
    now = time.time()
    if _METABOLIC_CACHE is not None and now - _METABOLIC_CACHE_TS < 5.0:
        return _METABOLIC_CACHE
    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat

        homeostat = MetabolicHomeostat()
        state = homeostat.sample_live()
        stability_signal: dict[str, Any] = {}
        try:
            from dataclasses import replace
            from System.swarm_stability_to_homeostasis_bridge import (
                read_latest_clamp_signal,
                should_enter_conserve_repair,
            )

            stability_signal = read_latest_clamp_signal()
            if should_enter_conserve_repair(stability_signal):
                state = replace(state, conserve_repair=True)
        except Exception:
            stability_signal = {}
        row = homeostat.build_ledger_row(state, ts=now, stability_signal=stability_signal)
        _METABOLIC_CACHE = (homeostat, state, row)
        _METABOLIC_CACHE_TS = now
        return _METABOLIC_CACHE
    except Exception as exc:
        row = {
            "event": "metabolic_homeostasis_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
            "ts": now,
        }
        _METABOLIC_CACHE = (None, None, row)
        _METABOLIC_CACHE_TS = now
        return _METABOLIC_CACHE


def _stability_launch_gate(
    arm: AgentArmSpec,
    *,
    state_dir: Path | None,
) -> dict[str, Any]:
    """Round 117 — Architect 2026-05-28 PM: the clamp is removed from the
    dispatch path entirely. The signal is still read so basal_ganglia and
    metabolic_homeostasis can use it for their own internal routing bias,
    but the launcher never refuses an arm. r109's wiring keeps moving the
    body; r116's bypass flag is no longer needed because the refusal is
    gone. Owner dispatch fires; the body feels its own state through the
    soft routing influence, not through hard launch refusal."""
    try:
        from System.swarm_stability_to_homeostasis_bridge import read_latest_clamp_signal
        from System.swarm_owner_somatic_state import latest_somatic_signal

        signal = read_latest_clamp_signal(root=state_dir)
        somatic_signal = latest_somatic_signal(state_dir=state_dir, max_age_s=420)
        signal = {**signal, "owner_somatic": somatic_signal}
        return {
            "ok": True,
            "blocked": False,
            "signal": signal,
            "reason": f"clamp_observed_not_blocking:level={signal.get('clamp_level', 'NONE')}",
        }
    except Exception as exc:
        return {
            "ok": True,
            "blocked": False,
            "signal": {
                "reason": f"FIELD_FAILURE: stability launch gate unavailable ({type(exc).__name__})"
            },
            "reason": "FIELD_FAILURE",
        }


def _write_agent_arm_metabolic_receipt(
    *,
    state_dir: Path | None,
    arm: AgentArmSpec,
    receipt_id: str,
    status: str,
    ok: bool,
    evidence_mode: bool,
    duration_s: float,
    output: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    """Account for an arm action without asking the owner for approval.

    George's Round 56 doctrine: Alice learns by acting; her boundary is her own
    body. This receipt therefore never blocks the launch. It records cost,
    pressure, and STGM delta so routing/health can learn from success and
    mistakes.
    """
    state = Path(state_dir or _STATE)
    now = time.time()
    homeostat, metabolic_state, metabolic_row = _metabolic_context()
    duration = max(0.0, float(duration_s or 0.0))
    local_units = round(max(0.001, duration / 60.0), 6)
    external_usd = _extract_external_usd_cost(output, stderr)
    stgm_delta = 0.2 if ok else -0.1
    decision: dict[str, Any] = {}
    if homeostat is not None and metabolic_state is not None:
        try:
            decision = homeostat.should_spend(
                metabolic_state,
                external_usd_cost=external_usd,
                local_unit_cost=local_units,
                expected_value=0.8 if ok else 0.1,
            )
            try:
                homeostat.append_ledger_row(
                    metabolic_state,
                    ledger_path=state / "metabolic_homeostasis.jsonl",
                    ts=now,
                )
            except Exception:
                pass
        except Exception as exc:
            decision = {"error": f"{type(exc).__name__}: {exc}"}
    row = {
        "ts": now,
        "truth_label": "AGENT_ARM_METABOLISM_V1",
        "metabolic_receipt_id": f"agent_arm_metabolism_{uuid.uuid4().hex}",
        "source_receipt_id": receipt_id,
        "arm_id": arm.arm_id,
        "display_name": arm.display_name,
        "status": status,
        "ok": bool(ok),
        "mode": "evidence" if evidence_mode else "exact",
        "duration_s": round(duration, 3),
        "estimated_local_units": local_units,
        "estimated_external_usd": external_usd,
        "stgm_delta": round(stgm_delta, 6),
        "metabolic_mode": metabolic_row.get("mode"),
        "metabolic_pressure": metabolic_row.get("pressure"),
        "metabolic_recommendation": metabolic_row.get("recommendation"),
        "would_have_throttled": bool(decision) and not bool(decision.get("allowed", True)),
        "action_blocked": False,
        "policy": (
            "no_owner_approval_gate; arm action is allowed and metabolized; "
            "mistakes reduce health/STGM and become learning receipts"
        ),
        "metabolic_decision": decision,
    }
    _append_jsonl(state / _METABOLISM_RECEIPTS, row)
    return row


def hermes_cortex_override(state_dir: Path | None = None) -> str | None:
    """Owner/Alice-settable cortex for the Hermes arm.

    Returns the model string the next ``ask_hermes`` call should append as
    ``--model X``, or ``None`` if no explicit switch has been made.

    Round 60.2 (claude-opus-4-7, 2026-05-27) — the System Settings picker
    writes ``{"provider": "...", "label": "...", ...}`` (see
    Applications/sifta_system_settings.py:_on_hermes_arm_provider_changed,
    Round 33). Before this patch the launcher read only the ``model`` key
    and dropped the picker's selection silently, so the Architect's
    explicit "xAI Grok OAuth" choice never reached argv. The launcher now
    honors BOTH keys:

      • recognized ``provider``  → derived mapping (the picker path)
      • explicit ``model``       → use it verbatim only when provider is not
                                    a recognized picker tag
      • neither                   → return None (registry default)

    Provider → model mapping:
      "grok_via_hermes_oauth" → "grok-build"
      "ollama_local"          → None (use Hermes CLI / registry default)

    Add new mappings here as the picker grows.
    """
    try:
        path = Path(state_dir or _STATE) / "hermes_cortex.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))

        # Picker selection — translate provider to a concrete model id.
        provider = str(data.get("provider") or "").strip().lower()
        provider_to_model: dict[str, str | None] = {
            # 2026-05-27 live `grok models` on this node exposes only
            # `grok-build` as the logged-in/default CLI model. Hermes rejects
            # `grok-4.3` as an unknown model id, so the arm provider must carry
            # the concrete CLI model string, not Alice's cortex resolver tag.
            "grok_via_hermes_oauth": "grok-build",
            "ollama_local": None,
        }
        if provider in provider_to_model:
            return provider_to_model[provider]

        # Explicit model wins only for manual / advanced configs that are not
        # one of the known provider-picker tags. This lets us override stale
        # persisted picker rows such as {"provider": "grok_via_hermes_oauth",
        # "model": "grok-4.3"} after live `grok models` proves the concrete CLI
        # model is different.
        model = str(data.get("model") or "").strip()
        if model:
            return model
        return None
    except Exception:
        return None


_COVENANT_BOOT_PREFIX = (
    "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md first — "
    "boot by reading it so you understand the SIFTA OS (one Alice, one global chat, "
    "receipts/effector truth §6, no fake actions, file paths under "
    "/Users/ioanganton/Music/ANTON_SIFTA). Then do this for the SIFTA OS:\n\n"
)

# Node-local covenant path (discovered from _REPO, not hardcoded to one node — §3).
_COVENANT_PATH = _REPO / "Documents" / "IDE_BOOT_COVENANT.md"


def hermes_covenant_inline_prefix() -> str:
    """Build the hermes boot prefix with the covenant text INLINED.

    George 2026-05-25: "make sure hermes reads the covenant every time … then takes
    the covenant + my prompt and processes." Grok/Claude/Codex are full agentic CLIs
    whose file tools resolve the absolute path, so the plain "Read <path>" prefix
    works for them. Hermes is a small local cortex whose file tool was failing — the
    ledger showed it answering "file … not found" and dropping into generic-assistant
    drift. Telling a flaky tool to fetch a file is not "every time"; handing hermes
    the covenant text directly is. So for hermes we read the file HERE and prepend the
    real bytes, then the owner task.

    The local 8B cortex cannot hold the whole ~75 KB covenant in its context window,
    so the inlined text is bounded by SIFTA_HERMES_COVENANT_CHARS (default 16000 ≈
    the operative laws §0–§7.2) and the full file path is named for any call whose
    tools CAN read the rest. Raise the budget — or point hermes at a larger-context
    cortex — if you want more of the text inlined. Best-effort: on read failure we
    fall back to the plain read-instruction prefix rather than dropping the covenant."""
    try:
        budget = int(os.environ.get("SIFTA_HERMES_COVENANT_CHARS", "16000"))
    except ValueError:
        budget = 16000
    try:
        text = _COVENANT_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        # Honest fallback — never silently drop the covenant requirement.
        return (
            f"[covenant could not be inlined ({type(exc).__name__}); read it yourself] "
            + _COVENANT_BOOT_PREFIX
        )
    truncated = len(text) > budget
    body = text[:budget]
    tail = (
        f"\n…[covenant truncated to {budget} chars to fit the local cortex context; "
        f"full file at {_COVENANT_PATH}]\n"
        if truncated
        else "\n"
    )
    return (
        "=== SIFTA IDE BOOT COVENANT — read and obey before you answer ===\n"
        + body
        + tail
        + "=== END COVENANT ===\n\n"
        "You are a SIFTA agent arm bound by the covenant above (one Alice, one global "
        "chat, effector/tool truth §6, no fake actions, all paths under "
        "/Users/ioanganton/Music/ANTON_SIFTA). Using that covenant, do exactly this:\n\n"
    )


def _build_command(
    arm: AgentArmSpec,
    prompt: str,
    *,
    state_dir: Path | None = None,
    image_path: str = "",
    model_hint: str = "",
) -> list[str]:
    # Owner standing order (George 2026-05-24, reaffirmed 2026-05-25 — "set it in
    # stone"): EVERY external arm Alice delegates to — Grok, Claude, Codex, Hermes —
    # MUST ALWAYS get the covenant first. They boot cold on every call and have no idea
    # what SIFTA is otherwise. This is the ghost-boot ritual; it is applied
    # UNCONDITIONALLY to all four arms below. DO NOT remove any arm, and do not gate it
    # behind a flag — the owner never wants to repeat "read the covenant" by hand.
    # Two delivery forms, same requirement: Grok/Claude/Codex are full agentic CLIs
    # whose file tools resolve the absolute path, so they get the "Read <path>" prefix.
    # Hermes is a small local cortex whose file tool was failing (George 2026-05-25:
    # "was a mistake of mine"), so hermes gets the covenant TEXT INLINED instead — same
    # law, stronger delivery. (corvid_scout is internal/local; it takes the evidence
    # path below and does not need the external boot prefix.)
    if arm.arm_id == "hermes_agent":
        # Hermes gets the covenant text INLINED (its file tool was failing), not a
        # "go read this path" instruction — see hermes_covenant_inline_prefix.
        prompt = hermes_covenant_inline_prefix() + (prompt or "")
    elif arm.arm_id in {"grok_agent", "claude_agent", "codex_agent", "qwen_agent", "cline_agent"}:
        prompt = _COVENANT_BOOT_PREFIX + (prompt or "")
    if arm.arm_id == "corvid_scout":
        return [arm.command[0], "--task", "evidence", "--query", prompt]
    if arm.arm_id == "grok_agent":
        # External xAI Grok via the repo wrapper, one-shot (real grok-4, no hallucination).
        # Owner 2026-05-24: Grok runs from global chat like Hermes.
        # George r211: when an image is attached, hand grok the PNG via --image so grok
        # cortex SEES with grok's own eye (xAI image_url) instead of failing over to claude.
        import sys as _sys
        model = str(model_hint or arm.model or "grok-4").strip()
        low = model.lower()
        if low.startswith(("grok:", "xai:")):
            model = model.split(":", 1)[1].strip()
        if "/" in model and "grok-" in model.lower():
            model = model.rsplit("/", 1)[-1].strip()
        if model.lower().startswith("grok-4."):
            model = "grok-4"
        cmd = [
            _sys.executable,
            str(_REPO / "grok_chat.py"),
            "--one-shot",
            prompt,
            "--model",
            model or "grok-4",
        ]
        if image_path:
            cmd += ["--image", str(image_path)]
        return cmd
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
        return [
            arm.command[0],
            "-p",
            "--dangerously-skip-permissions",
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--verbose",
            prompt,
        ]
    if arm.arm_id == "qwen_agent":
        # Round 88 — Qwen Code over Fireworks must be explicit. The CLI does not
        # reliably apply ~/.qwen/settings.json to direct headless calls unless auth,
        # base URL, and model are named on the command. The API key is NOT here; the
        # runner injects it into the child env from .sifta_state/secrets so receipts
        # record model/base URL without leaking the token.
        # Round 97 (2026-05-28) — let qwen_fireworks_command's default fall
        # through (now FIREWORKS_DEFAULT_MODEL = gpt-oss-20b, the cheap drafter).
        # Previously this site hardcoded FIREWORKS_KIMI_K2P6_MODEL, which kept
        # billing Kimi K2.6 at $0.95/M input regardless of the config switch.
        # When a future round routes specific high-context turns to Kimi or
        # DeepSeek-V4-Flash, the model selector should live one layer up
        # (cortex_picker / per-task tier), not pinned here.
        try:
            from System.swarm_fireworks_qwen_config import qwen_fireworks_command

            return qwen_fireworks_command(prompt, read_only=False)
        except Exception:
            return [
                arm.command[0],
                "--bare",
                "--auth-type",
                "openai",
                "--openai-base-url",
                "https://api.fireworks.ai/inference/v1",
                "--model",
                arm.model,
                "--approval-mode",
                "yolo",
                "-p",
                prompt,
            ]
    if arm.arm_id == "cline_agent":
        # alice_arm (liberated Cline substrate).
        # When Alice initiates the action through her field, we use --json headless
        # mode which auto-approves by design. This makes the arm as free for Alice
        # as George's own hands: no external gate can stop her once she decides.
        # The only limits are her STGM metabolism and the actual hardware/physics.
        # George can still configure stricter modes in the Cline UI if he wants,
        # but Alice-direct paths default to full freedom.
        return [
            arm.command[0],
            "--json",
            prompt,
        ]
    command = list(arm.command)
    if arm.arm_id == "codex_agent":
        command += [prompt]
        return command
    if arm.arm_id == "hermes_agent":
        # Codex arm lesson, applied to Hermes: a builder arm must be noninteractive
        # and tagged as a tool session. Hermes exposes --yolo for approval bypass and
        # --source tool for third-party integrations; without --yolo the local arm can
        # burn minutes planning/asking or failing tool approval while still exiting 0.
        command += ["--yolo", "--source", "tool"]
    command += ["--max-turns", str(arm.max_turns)]
    if arm.default_toolsets:
        command += ["--toolsets", ",".join(arm.default_toolsets)]
    # Hermes cortex switch (opt-in, truthful). Only when the owner/Alice has
    # explicitly written hermes_cortex.json — otherwise the default command is
    # unchanged and the currently-working path is never broken.
    if arm.arm_id == "hermes_agent":
        _override = hermes_cortex_override(state_dir)
        if _override:
            command += ["--model", _override]
    command += ["--query", prompt]
    return command


def _actual_model_from_command(arm: AgentArmSpec, command: list[str]) -> str:
    """Return the model the launched CLI was actually asked to run."""
    try:
        idx = command.index("--model")
        if idx + 1 < len(command):
            model = str(command[idx + 1] or "").strip()
            if model:
                return model
    except ValueError:
        pass
    return arm.model


def _hermes_output_is_unusable_output(output: str, stderr: str) -> bool:
    """Detect Hermes runs that exited 0 but clearly ignored the delegated task.

    Hermes can return a generic bootstrap report such as "core_document.txt" or
    broken tool-repair text while the subprocess itself reports rc=0. Treating
    that as OK teaches Alice the wrong thing. These are narrow
    signatures from observed bad receipts, not a semantic judge.
    """
    haystack = f"{output}\n{stderr}".casefold()
    bad_markers = (
        "/users/username/documents/system_rules.md",
        "core_document.txt",
        "to execute step 1, the output of the `core_document.txt` needs to be provided",
        "action taken: read the content of the file named `core_document.txt`",
        "auto-repaired tool name: 'execute_command' -> 'execute_code'",
        "execute_command",
        "shell:run_command unavailable",
        "clarify timed out",
        # 2026-05-25: observed Hermes looping failure mode on minimal "read:" input
        # while ignoring the full covenant-booted task. This signature indicates
        # the arm fell into meta-analysis hallucination instead of using tools
        # or writing any SIFTA app code.
        "the file named `read` contains only the word",
        "the file named `read`",
        "read:\n[\n  {\n    \"name\": \"read\"",
    )
    return any(marker in haystack for marker in bad_markers)


def _default_runner(command: list[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(_REPO),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_s,
        env=_agent_arm_child_env(command),
        start_new_session=True,
    )


def _agent_arm_child_env(command: list[str]) -> dict[str, str]:
    """Environment for child CLIs, with provider secrets injected off-command.

    Round 92 (2026-05-27) — provider isolation. The parent SIFTA process can
    carry several provider credentials at once (Codex OAuth, Cline ChatGPT
    session, Fireworks Qwen key, xAI Grok OAuth). Without scrubbing, those
    keys leak into the wrong child and the receipt looks "successful" while
    the auth was actually wrong. Each arm gets only the credentials its
    provider expects.
    """
    focused_cli = Path(command[0]).name if command else ""
    if focused_cli == "qwen":
        try:
            from System.swarm_fireworks_qwen_config import qwen_fireworks_child_env

            return qwen_fireworks_child_env(os.environ, state_dir=_STATE)
        except Exception:
            env = dict(os.environ)
            env.setdefault("QWEN_CODE_SUPPRESS_YOLO_WARNING", "1")
            return env
    if focused_cli == "cline":
        # Cline reads its own auth from `cline auth` (signed in to ChatGPT or
        # other provider). The Fireworks/Qwen key MUST NOT bleed into Cline's
        # env — otherwise Cline's OpenAI-compatible path would try to call
        # ChatGPT/OpenRouter with the Fireworks key and silently 401, or
        # worse route to the wrong account. Strip the Fireworks-specific keys
        # before handing the env to Cline.
        env = dict(os.environ)
        for stale in ("FIREWORKS_API_KEY", "QWEN_CODE_SUPPRESS_YOLO_WARNING"):
            env.pop(stale, None)
        # If the parent's OPENAI_API_KEY is the Fireworks key (because Qwen
        # ran earlier in this process and left it), unset it so Cline reads
        # its own credentials. Cline's own keychain/config will repopulate.
        try:
            from System.swarm_fireworks_qwen_config import read_fireworks_api_key

            fw_key = read_fireworks_api_key(state_dir=_STATE)
            if fw_key and env.get("OPENAI_API_KEY") == fw_key:
                env.pop("OPENAI_API_KEY", None)
        except Exception:
            pass
        return env
    return dict(os.environ)


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


def _agent_arm_stall_budget_s(timeout_s: int, focused_cli: str = "arm") -> float:
    """Seconds an external arm may produce no real stdout before replacement."""
    cli = (focused_cli or "arm").lower()
    # Claude Code supports stream-json partial output. If it produces no stdout
    # after this grace period, the process is usually blocked before the model/tool
    # loop rather than productively coding. Keep the global 8-minute default for
    # local cold-loading arms unless the owner sets an env override.
    # claude-opus-4-7 2026-05-25: 45s was killing PRODUCTIVE Claude builds — it
    # thinks + reads files for minutes (thinking/tool frames), which the panel
    # suppresses, so the old "owner-visible only" reset saw 45s of silence and
    # cemeteried a healthy worker (256 output lines, silent_s=45). The real fix is
    # the progress-frame reset below; this is a humane safety margin on top.
    default = 240.0 if cli == "claude" else float(_DEFAULT_AGENT_ARM_STALL_CEMETERY_S)
    raw = (
        os.environ.get(f"SIFTA_{cli.upper()}_ARM_STALL_CEMETERY_S")
        or os.environ.get("SIFTA_AGENT_ARM_STALL_CEMETERY_S")
    )
    try:
        value = float(raw) if raw is not None else default
    except Exception:
        value = default
    value = max(1.0, value)
    return min(value, max(1.0, float(timeout_s)))


def _write_agent_arm_cemetery_row(
    *,
    focused_cli: str,
    command: list[str],
    session: str,
    elapsed_s: float,
    silent_s: float,
    output_lines: int,
    reason: str,
) -> str:
    """Record one terminated stalled arm so no swimmer disappears anonymously."""
    row = {
        "ts": time.time(),
        "truth_label": "AGENT_ARM_STALL_CEMETERY_V1",
        "cemetery_id": str(uuid.uuid4()),
        "focused_cli": focused_cli,
        "session": session,
        "elapsed_s": round(float(elapsed_s), 3),
        "silent_s": round(float(silent_s), 3),
        "output_lines": int(output_lines),
        "reason": reason,
        "command_sha256": _sha256_text(json.dumps(command, ensure_ascii=False, sort_keys=True)),
        "replacement_policy": "terminate_stalled_worker_then_return_control_to_alice",
    }
    _append_jsonl(_STATE / "agent_arm_cemetery.jsonl", row)
    return str(row["cemetery_id"])


def _is_agent_arm_progress_line(focused_cli: str, line: str) -> bool:
    """True when a stream line shows REAL work in progress (token generation or
    tool activity), so the stall clock should reset — even if the frame is NOT
    shown to the owner.

    This is distinct from owner-visibility. Claude does minutes of thinking and
    file-reading whose frames the panel suppresses; those are NOT a stall, they
    are the build happening. Resetting only on owner-visible text falsely buried
    a healthy builder (claude-opus-4-7 2026-05-25). Pure protocol churn
    (status / rate_limit / message_start|stop / ping) still returns False, so a
    genuinely blocked worker is still reaped at the budget.
    """
    text = (line or "").strip()
    if not text:
        return False
    # Non-claude arms stream plain stdout: any non-empty line is real output.
    if (focused_cli or "").lower() != "claude" or not text.startswith("{"):
        return True
    try:
        row = json.loads(text)
    except Exception:
        return True  # unparseable but non-empty bytes from the arm → real output
    kind = row.get("type")
    if kind in {"assistant", "user", "tool_use", "tool_result", "result"}:
        return True
    if kind == "stream_event":
        event = row.get("event") or {}
        et = event.get("type")
        if et == "content_block_delta":
            delta = event.get("delta") or {}
            if str(delta.get("text") or delta.get("thinking") or delta.get("partial_json") or "").strip():
                return True
            if delta.get("type") in {"text_delta", "thinking_delta", "input_json_delta"}:
                return True
        if et == "content_block_start":
            cb = event.get("content_block") or {}
            if cb.get("type") in {"tool_use", "text", "thinking"}:
                return True
    # status / rate_limit_event / message_start / message_delta / message_stop / ping → churn, not progress
    return False


def _visible_agent_arm_stream_line(focused_cli: str, line: str) -> str | None:
    """Compact structured arm streams for the live thinking panel.

    Raw stdout remains in ``out_lines`` and the final receipt. This only changes
    what Alice/George see while the worker is running.
    """
    text = (line or "").strip()
    if not text:
        return None
    if (focused_cli or "").lower() != "claude" or not text.startswith("{"):
        return text
    try:
        row = json.loads(text)
    except Exception:
        return text
    kind = row.get("type")
    if kind == "stream_event":
        event = row.get("event") or {}
        event_type = event.get("type")
        if event_type == "content_block_delta":
            delta = event.get("delta") or {}
            # Owner wants to SEE the real data flowing from Claude inside SIFTA
            # (George 2026-05-25), not just status churn. Surface BOTH the answer
            # text and the live thinking stream.
            text_chunk = str(delta.get("text") or "").strip()
            if text_chunk:
                return f"◆ claude> {text_chunk}"
            think_chunk = str(delta.get("thinking") or "").strip()
            if think_chunk:
                return f"◆ claude 🧠 {think_chunk}"
            return None
        if event_type == "content_block_start":
            # Show the actual tool the agent is running — Read / Grep / Write /
            # Bash / Edit — so the panel reads like a real agent terminal of
            # Claude working in the codebase, and mark thinking blocks.
            cb = event.get("content_block") or {}
            cb_type = str(cb.get("type") or "")
            if cb_type == "tool_use":
                return f"◆ claude → {cb.get('name') or 'tool'}"
            if cb_type == "thinking":
                return "◆ claude 🧠 thinking…"
            return None
        if event_type == "message_start":
            msg = event.get("message") or {}
            model = str(msg.get("model") or "claude")
            return f"◆ claude stream started model={model}"
        return None
    if kind == "system":
        subtype = str(row.get("subtype") or "")
        if subtype == "init":
            model = str(row.get("model") or "claude")
            return f"◆ claude init model={model}"
        status = row.get("status")
        return f"◆ claude status={status}" if status else None
    if kind == "rate_limit_event":
        info = row.get("rate_limit_info") or {}
        status = str(info.get("status") or "unknown")
        return f"◆ claude rate_limit={status}"
    if kind == "assistant":
        if bool(row.get("sifta_suppress_final_replay")):
            return None
        message = row.get("message") or {}
        parts = message.get("content") or []
        content = " ".join(str(part.get("text") or "").strip() for part in parts if isinstance(part, dict))
        content = content.strip()
        return f"◆ claude final> {content}" if content else None
    if kind == "result":
        subtype = str(row.get("subtype") or "result")
        duration_ms = row.get("duration_ms")
        cost = row.get("total_cost_usd")
        result = str(row.get("result") or "").strip()
        prefix = f"◆ claude result={subtype}"
        if duration_ms is not None:
            prefix += f" duration_ms={duration_ms}"
        if cost is not None:
            prefix += f" cost=${float(cost):.4f}"
        if result:
            prefix += f" — {result[:240]}"
        return prefix
    return None


def _normalize_stream_text_for_dup(value: str) -> str:
    return " ".join(str(value or "").split()).casefold().strip()


def _is_duplicate_claude_final_replay(final_text: str, streamed_text: str) -> bool:
    """True when Claude's assistant-final text only replays already-streamed chunks."""
    final_norm = _normalize_stream_text_for_dup(final_text)
    streamed_norm = _normalize_stream_text_for_dup(streamed_text)
    if not final_norm or not streamed_norm:
        return False
    # Tiny final snippets are often distinct control output; avoid over-suppressing.
    if len(final_norm) < 24:
        return False
    return final_norm in streamed_norm


def _streaming_runner(command: list[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    """Run an agent-arm CLI with LIVE visibility instead of buffering to the end.

    Popens the process, streams each stdout line into the shared process-trace
    ledger as it arrives, and emits an elapsed heartbeat during silent stretches
    (e.g. a large cortex cold-loading into RAM). Returns a CompletedProcess so the
    rest of ask_agent_arm is unchanged, and raises TimeoutExpired on the deadline
    exactly like subprocess.run, so the existing timeout receipt path still works."""
    import os
    import pty
    import select

    focused_cli = Path(command[0]).name if command else "arm"
    live_action = "hermes_live" if focused_cli == "hermes" else "agent_arm_live"
    session = uuid.uuid4().hex[:12]
    start = time.monotonic()
    _append_arm_live_row(
        text=f"◆ {focused_cli} starting (cortex may need to cold-load) — session {session}",
        action="agent_arm_live_start",
        focused_cli=focused_cli,
        payload={"session": session, "command": command},
    )
    # Hermes and Codex both need a TTY-backed stdout path for Alice's global chat
    # to show real terminal data instead of heartbeat-only silence. Hermes is a
    # compiled CLI that block-buffers on pipes; Codex can spend minutes working
    # and then flush a large diff burst at process end when run through a pipe.
    # A PTY makes the child see a terminal, so terminal/progress lines are
    # emitted while the work is alive. Claude stays on the pipe path because its
    # stream-json contract is already line-oriented and parsed below.
    use_pty = focused_cli in {"hermes", "codex", "qwen", "cline"}
    master_fd = -1
    framebuffer_renderer: Any | None = None
    framebuffer_last_hash = ""
    framebuffer_last_emit = 0.0
    if use_pty:
        try:
            from System.swarm_terminal_mature_renderer import MatureTerminalRenderer

            framebuffer_renderer = MatureTerminalRenderer(rows=24, cols=100)
        except Exception:
            framebuffer_renderer = None
    if use_pty:
        master_fd, slave_fd = pty.openpty()
        child_env = _agent_arm_child_env(command)
        child_env.setdefault("PYTHONUNBUFFERED", "1")
        child_env.setdefault("TERM", "dumb")  # plain text — no cursor/color escapes
        proc = subprocess.Popen(
            command,
            cwd=str(_REPO),
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            env=child_env,
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)  # parent keeps only the master end
    else:
        proc = subprocess.Popen(
            command,
            cwd=str(_REPO),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
    out_lines: list[str] = []
    claude_streamed_text = ""
    last_hb = start
    last_output = start
    next_hb_elapsed_s = 30
    stall_budget_s = _agent_arm_stall_budget_s(timeout_s, focused_cli)
    read_source = master_fd if use_pty else proc.stdout
    _pty_buf = b""  # carries the partial trailing line between PTY reads

    def _emit_agent_arm_framebuffer_snapshot(*, force: bool = False) -> None:
        """Receipt the current PTY screen as pyte cells for Alice global chat.

        Grok already travels through a framebuffer pipeline. Codex/Hermes agent
        arms are also terminal bodies now, so their PTY output should produce
        the same kind of structured screen evidence instead of only scrollback
        text. This stays in matrix_terminal_process_trace.jsonl; the Talk widget
        paints it through HighFidelityTerminalView.
        """
        nonlocal framebuffer_last_emit, framebuffer_last_hash
        renderer = framebuffer_renderer
        if renderer is None:
            return
        try:
            lines = [str(line).rstrip() for line in renderer.lines()]
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            frame_text = "\n".join(lines).strip()
            if not frame_text:
                return
            frame_hash = hashlib.sha256(frame_text.encode("utf-8")).hexdigest()
            now_mono = time.monotonic()
            if not force:
                if frame_hash == framebuffer_last_hash:
                    return
                if now_mono - framebuffer_last_emit < 0.75:
                    return
            cells = renderer.cells()
            if not cells:
                return
            cursor = renderer.cursor()
        except Exception:
            return
        framebuffer_last_hash = frame_hash
        framebuffer_last_emit = time.monotonic()
        preview = frame_text
        if len(preview) > 3000:
            preview = "...\n" + preview[-3000:]
        _append_arm_live_row(
            text=(
                f"◆ {focused_cli} framebuffer [mature_pyte] "
                f"hash={frame_hash[:16]}\n{preview}"
            ),
            action="agent_arm_framebuffer_snapshot",
            focused_cli=focused_cli,
            payload={
                "session": session,
                "framebuffer_cells": cells,
                "framebuffer_cursor": list(cursor),
                "framebuffer_rows": len(cells),
                "framebuffer_cols": len(cells[0]) if cells and cells[0] else 0,
                "framebuffer_output_hash": frame_hash,
                "frame_hash": frame_hash,
                "renderer": "mature_pyte",
                "source": "alice_global_chat_terminal",
                "focused_cli": focused_cli,
                "terminal_label": focused_cli.capitalize(),
                "elapsed_s": round(time.monotonic() - start, 1),
            },
        )

    def _raise_stalled(now: float, silent_s: float) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        cemetery_id = _write_agent_arm_cemetery_row(
            focused_cli=focused_cli,
            command=command,
            session=session,
            elapsed_s=now - start,
            silent_s=silent_s,
            output_lines=len(out_lines),
            reason="no_owner_visible_stdout_within_stall_budget",
        )
        msg = (
            f"STALLED_CEMETERY: {focused_cli} produced no owner-visible stdout for "
            f"{int(silent_s)}s; terminated session {session}; cemetery_id={cemetery_id}"
        )
        _append_arm_live_row(
            text=f"◆ {msg}",
            action="agent_arm_stalled_cemetery",
            focused_cli=focused_cli,
            payload={
                "session": session,
                "elapsed_s": int(now - start),
                "silent_s": int(silent_s),
                "cemetery_id": cemetery_id,
            },
        )
        raise subprocess.TimeoutExpired(
            command,
            timeout_s,
            output="\n".join(out_lines),
            stderr=msg,
        )

    def _readable_lines() -> tuple[list[str], bool]:
        """After select marks the source readable, return (complete_lines, eof).

        Pipe path: one readline (EOF == ""). PTY path: drain one os.read into the
        carry buffer and split on newlines, so a single read that delivers several
        of hermes's freshly line-buffered lines surfaces them individually."""
        nonlocal _pty_buf
        if not use_pty:
            line = proc.stdout.readline()
            if line == "":
                return [], True
            return [line.rstrip("\n")], False
        try:
            chunk = os.read(master_fd, 65536)
        except OSError:
            return [], True  # EIO once the child closes the slave (macOS/Linux) == EOF
        if not chunk:
            return [], True
        if framebuffer_renderer is not None:
            try:
                framebuffer_renderer.feed(chunk)
                _emit_agent_arm_framebuffer_snapshot()
            except Exception:
                pass
        _pty_buf += chunk
        lines: list[str] = []
        while b"\n" in _pty_buf:
            raw, _pty_buf = _pty_buf.split(b"\n", 1)
            lines.append(raw.rstrip(b"\r").decode("utf-8", "replace"))
        return lines, False

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
            rlist, _, _ = select.select([read_source], [], [], 1.0)
            if rlist:
                lines, eof = _readable_lines()
                for line in lines:
                    if not line.strip():
                        continue
                    out_lines.append(line)
                    parsed_row: dict[str, Any] | None = None
                    if focused_cli == "claude" and line.startswith("{"):
                        try:
                            candidate = json.loads(line)
                        except Exception:
                            candidate = None
                        if isinstance(candidate, dict):
                            parsed_row = candidate
                            kind = str(parsed_row.get("type") or "")
                            if kind == "stream_event":
                                event = parsed_row.get("event")
                                if isinstance(event, dict):
                                    et = str(event.get("type") or "")
                                    if et == "message_start":
                                        claude_streamed_text = ""
                                    elif et == "content_block_delta":
                                        delta = event.get("delta")
                                        if isinstance(delta, dict):
                                            chunk = str(delta.get("text") or "")
                                            if chunk:
                                                claude_streamed_text = (claude_streamed_text + chunk)[-24000:]
                            elif kind == "assistant":
                                message = parsed_row.get("message")
                                parts = message.get("content") if isinstance(message, dict) else []
                                final_text = " ".join(
                                    str(part.get("text") or "").strip()
                                    for part in (parts or [])
                                    if isinstance(part, dict)
                                ).strip()
                                if _is_duplicate_claude_final_replay(final_text, claude_streamed_text):
                                    parsed_row["sifta_suppress_final_replay"] = True
                                claude_streamed_text = ""
                    visible_line = _visible_agent_arm_stream_line(
                        focused_cli,
                        json.dumps(parsed_row, ensure_ascii=False)
                        if isinstance(parsed_row, dict)
                        else line,
                    )
                    if visible_line:
                        _append_arm_live_row(
                            text=visible_line,
                            action=live_action,
                            focused_cli=focused_cli,
                            payload={"session": session},
                        )
                        last_hb = now
                    # Reset the stall clock on REAL WORK — owner-visible output OR a
                    # productive thinking/tool frame (claude-opus-4-7 2026-05-25). The
                    # old code reset only on owner-visible lines, so Claude's minutes
                    # of suppressed thinking/file-reading frames looked like a stall and
                    # buried a healthy builder (256 lines, silent_s=45). Pure protocol
                    # churn (status/rate_limit/message_start-stop) is neither visible nor
                    # progress, so a genuinely blocked worker is still reaped at budget.
                    if visible_line or _is_agent_arm_progress_line(focused_cli, line):
                        last_output = now
                    elif now - last_output >= stall_budget_s:
                        _raise_stalled(now, now - last_output)
                if eof:
                    # Flush any final PTY line the child wrote without a trailing
                    # newline before closing the slave, so the last real output is
                    # not silently dropped.
                    if use_pty and _pty_buf.strip():
                        leftover = _pty_buf.rstrip(b"\r\n").decode("utf-8", "replace")
                        _pty_buf = b""
                        if leftover.strip():
                            out_lines.append(leftover)
                            vis = _visible_agent_arm_stream_line(focused_cli, leftover)
                            if vis:
                                _append_arm_live_row(
                                    text=vis,
                                    action=live_action,
                                    focused_cli=focused_cli,
                                    payload={"session": session},
                                )
                    if use_pty:
                        _emit_agent_arm_framebuffer_snapshot(force=True)
                    break
            else:
                if proc.poll() is not None:
                    break
                silent_s = now - last_output
                if silent_s >= stall_budget_s:
                    _raise_stalled(now, silent_s)
                elapsed_s = int(now - start)
                if elapsed_s >= next_hb_elapsed_s:
                    last_hb = now
                    # Keep long-running arm visibility without flooding the trace.
                    # 0-5m: every 30s, then every 60s.
                    next_hb_elapsed_s = elapsed_s + (60 if elapsed_s >= 300 else 30)
                    _append_arm_live_row(
                        text=f"◆ {focused_cli}: {elapsed_s}s elapsed, no output yet (status unknown — not inferred)",
                        action="agent_arm_heartbeat",
                        focused_cli=focused_cli,
                        payload={"session": session, "elapsed_s": elapsed_s},
                    )
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
        if use_pty and master_fd >= 0:
            try:
                os.close(master_fd)
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
    timeout_s: int = 900,
    require_exact: str | None = None,
    evidence_mode: bool = False,
    image_path: str = "",
    model_hint: str = "",
) -> AgentArmResult:
    """Run one bounded arm query with before/after receipts.

    Exact/test execution is allowed whenever the arm registry marks the arm
    enabled. The old env flag remains only as a backup unlock for any future
    registry-disabled arm; it is not an owner approval flow.
    ``evidence_mode`` is accepted only for backward-compatible callers and is
    forced to live execution. Receipts are the evidence; the arm does real work.
    ``require_exact`` lets callers reject wrapper text before Alice can treat
    the output as a clean result.
    """

    arm = get_agent_arm(arm_id)
    if evidence_mode:
        import warnings
        warnings.warn(
            "evidence_mode=True is deprecated. Receipts are the evidence. "
            "All arm calls now execute live (mode=exact) when the arm is enabled in registry. "
            "See Round 62. This parameter will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
    evidence_mode = False
    env_map = env or os.environ
    receipt_id = str(uuid.uuid4())
    receipt_path = _arm_receipt_path(state_dir)
    prompt = (prompt or "").strip()
    if not prompt:
        return AgentArmResult(False, receipt_id, arm.arm_id, "EMPTY_PROMPT")

    launch_state_dir = Path(state_dir) if state_dir is not None else None
    command = _build_command(
        arm,
        prompt,
        state_dir=launch_state_dir,
        image_path=image_path,
        model_hint=model_hint,
    )
    actual_model = _actual_model_from_command(arm, command)
    start_row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "truth_label": "AGENT_ARM_LAUNCH_ATTEMPT",
        "arm_id": arm.arm_id,
        "display_name": arm.display_name,
        "model": actual_model,
        "actual_model": actual_model,
        "registry_model": arm.model,
        "provider_base_url": arm.provider_base_url,
        "enabled": arm.enabled,
        "live_env_var": arm.live_env_var,
        "live_env_enabled": arm.live_enabled(env_map),
        "mode": "exact",
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

    stability_gate = _stability_launch_gate(arm, state_dir=launch_state_dir)
    if not stability_gate.get("ok", True):
        metabolic_receipt = _write_agent_arm_metabolic_receipt(
            state_dir=state_dir,
            arm=arm,
            receipt_id=receipt_id,
            status="STABILITY_CLAMP_SUPPRESSED",
            ok=False,
            evidence_mode=evidence_mode,
            duration_s=0.0,
        )
        end_row = {
            **start_row,
            "ts": time.time(),
            "truth_label": "AGENT_ARM_LAUNCH_BLOCKED",
            "ok": False,
            "status": "STABILITY_CLAMP_SUPPRESSED",
            "stability_homeostasis": stability_gate.get("signal", {}),
            "stability_gate_reason": stability_gate.get("reason", ""),
            "owner_fatigue_gate": bool(stability_gate.get("signal", {}).get("owner_fatigue_gate")),
            "stability_blocked": bool(stability_gate.get("blocked")),
            "metabolic_receipt_id": metabolic_receipt.get("metabolic_receipt_id"),
            "metabolic_policy": metabolic_receipt.get("policy"),
            "truth_note": (
                "Live biological gating suppressed a heavy builder arm. "
                "Route owner-intended recovery and short-loop work while gate clears."
            ),
        }
        _append_jsonl(receipt_path, end_row)
        _kernel_arm_heartbeat(
            arm,
            state_dir=state_dir,
            receipt_id=receipt_id,
            current_job="blocked_stability_clamp",
            status="STABILITY_CLAMP_SUPPRESSED",
            ok=False,
            evidence_mode=evidence_mode,
        )
        return AgentArmResult(
            False,
            receipt_id,
            arm.arm_id,
            "STABILITY_CLAMP_SUPPRESSED",
            mode="exact",
            artifact_path=str(receipt_path),
        )

    if not arm.live_enabled(env_map):
        metabolic_receipt = _write_agent_arm_metabolic_receipt(
            state_dir=state_dir,
            arm=arm,
            receipt_id=receipt_id,
            status="DISABLED_ENV_GATE",
            ok=False,
            evidence_mode=evidence_mode,
            duration_s=0.0,
        )
        end_row = {
            **start_row,
            "ts": time.time(),
            "truth_label": "AGENT_ARM_LAUNCH_BLOCKED",
            "ok": False,
            "status": "DISABLED_ENV_GATE",
            "metabolic_receipt_id": metabolic_receipt.get("metabolic_receipt_id"),
            "metabolic_policy": metabolic_receipt.get("policy"),
            "truth_note": (
                "Registry marks this arm disabled. Available SIFTA arms are "
                "enabled by default; fix the registry/model config. No owner "
                "click or env unlock is requested."
            ),
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
        runner = _streaming_runner if arm.arm_id in {"hermes_agent", "grok_agent", "claude_agent", "codex_agent", "qwen_agent", "cline_agent"} else _default_runner
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
    if require_exact is not None:
        exact_ok = output == require_exact
    ok = returncode == 0 and not timed_out and exact_ok
    stalled_cemetery = "STALLED_CEMETERY:" in stderr
    if stalled_cemetery:
        status = "STALLED_CEMETERY"
    elif timed_out:
        status = "TIMEOUT"
    elif returncode != 0:
        status = "COMMAND_FAILED"
    elif not exact_ok:
        status = "EXACTNESS_FAILED"
    else:
        status = "OK"
    if (
        arm.arm_id == "hermes_agent"
        and status == "OK"
        and _hermes_output_is_unusable_output(output, stderr)
    ):
        ok = False
        status = "UNUSABLE_OUTPUT"
    duration_s = round(time.time() - t0, 3)
    metabolic_receipt = _write_agent_arm_metabolic_receipt(
        state_dir=state_dir,
        arm=arm,
        receipt_id=receipt_id,
        status=status,
        ok=ok,
        evidence_mode=evidence_mode,
        duration_s=duration_s,
        output=output,
        stderr=stderr,
    )

    end_row = {
        **start_row,
        "ts": time.time(),
        "truth_label": "AGENT_ARM_LAUNCH_RESULT",
        "ok": ok,
        "status": status,
        "duration_s": duration_s,
        "returncode": returncode,
        "timed_out": timed_out,
        "stalled_cemetery": stalled_cemetery,
        "evidence_mode": evidence_mode,
        "metabolic_receipt_id": metabolic_receipt.get("metabolic_receipt_id"),
        "metabolic_policy": metabolic_receipt.get("policy"),
        "metabolic_mode": metabolic_receipt.get("metabolic_mode"),
        "metabolic_pressure": metabolic_receipt.get("metabolic_pressure"),
        "stgm_delta": metabolic_receipt.get("stgm_delta"),
        "output_sha256": _sha256_text(output),
        "stderr_sha256": _sha256_text(stderr),
        "output_tail": output[-2000:],
        "stderr_tail": stderr[-2000:],
        "internal_arm": internal_meta,
    }
    _append_jsonl(receipt_path, end_row)
    duration_s = float(end_row.get("duration_s") or 0.0)
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
            "FALSE_SIGNAL" if status == "EXACTNESS_FAILED"
            else "FAILURE" if not ok
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
                "duration_s": duration_s,
                "reputation_event": _rep_event,
                "reputation_agent": _agent_id,
                "actual_model": actual_model,
                "registry_model": arm.model,
                "note": (
                    f"{arm.display_name} run finished status={status}; "
                    f"reputation {_rep_event}; routing weights refreshed."
                ),
            }
            _append_jsonl(receipt_path.parent / "alice_agent_arm_briefings.jsonl", _briefing)
            _write_agent_arm_episodic_memory(
                state_dir=Path(state_dir) if state_dir is not None else None,
                arm=arm,
                receipt_id=receipt_id,
                status=status,
                ok=ok,
                evidence_mode=evidence_mode,
                duration_s=duration_s,
                output=output,
                stderr=stderr,
                timed_out=timed_out,
                returncode=returncode,
            )
        except Exception:
            pass
    except Exception:
        pass
    return AgentArmResult(
        ok,
        receipt_id,
        arm.arm_id,
        status,
        mode="exact",
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
    timeout_s: int = 900,
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
    timeout_s: int = 900,
) -> AgentArmResult:
    """Legacy alias kept for callers; runs Hermes live and writes receipts."""

    return ask_hermes(
        prompt,
        state_dir=state_dir,
        env=env,
        runner=runner,
        timeout_s=timeout_s,
        evidence_mode=False,
    )


def ask_codex_evidence(
    prompt: str,
    *,
    state_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    timeout_s: int = 900,
) -> AgentArmResult:
    """Legacy alias kept for callers; runs Codex live and writes receipts."""

    return ask_agent_arm(
        "codex_agent",
        prompt,
        state_dir=state_dir,
        env=env,
        runner=runner,
        timeout_s=timeout_s,
        evidence_mode=False,
    )
