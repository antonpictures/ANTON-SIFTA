#!/usr/bin/env python3
"""Phase-1 terminal swimmer forge core.

This module implements the non-UI foundation from
Documents/ALICE_YIN_YANG_TERMINAL_SWIMMER_IMPLEMENTATION_PLAN.md.
It adapts the TerminalWorld-style loop to SIFTA without adding a widget:
ingest a terminal recording, filter it through covenant-safe gates, run a
deterministic seed task, and admit it only when the three-trial validation
bar is met:

* AllPassing: the reference script succeeds and leaves a valid receipt.
* Nop: an empty run fails the state checks.
* Partial: a truncated run fails at least one state check.

Every trial appends a compact flux row. The final decision appends a work
receipt. No external effect is claimed unless the sandbox produced the row
that proves it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]


MODULE_VERSION = "swarm_terminal_swimmer_forge.v1"
FLUX_LEDGER_NAME = "swimmer_forge_flux.jsonl"
WORK_RECEIPTS_NAME = "work_receipts.jsonl"
FLUX_SCHEMA = "SIFTA_TERMINAL_SWIMMER_FORGE_FLUX_V1"
WORK_RECEIPT_SCHEMA = "SIFTA_TERMINAL_SWIMMER_FORGE_WORK_RECEIPT_V1"
COMMAND_WRAPPER_SCHEMA = "SIFTA_TERMINAL_SWIMMER_COMMAND_WRAPPER_V1"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = _REPO_ROOT / ".sifta_state"

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "token_assignment",
        re.compile(r"(?i)\b[a-z0-9_]*(api[_-]?key|secret|token|password)\s*=\s*['\"]?[^'\"\s]{8,}"),
    ),
    ("bearer_token", re.compile(r"(?i)\bauthorization:\s*bearer\s+[a-z0-9._~+/=-]{16,}")),
)

_TUI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("alternate_screen", re.compile(r"\x1b\[\?1049[hl]")),
    ("full_screen_cli", re.compile(r"(?i)(^|\s)(vim|nvim|emacs|htop|top|less|more|tmux|screen)(\s|$)")),
)


def _json_dumps(row: Mapping[str, Any]) -> str:
    return json.dumps(dict(row), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    line = _json_dumps(row) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _sha256_16(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json_dumps(row).encode("utf-8")).hexdigest()[:16]


def _safe_relpath(path: str) -> str:
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe relative path: {path!r}")
    return rel.as_posix()


def _tail(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def transition_entropy_nats(payload: bytes) -> float:
    """Return Shannon entropy in nats for a byte payload."""
    if not payload:
        return 0.0
    counts = Counter(payload)
    total = len(payload)
    return round(-sum((count / total) * math.log(count / total) for count in counts.values()), 6)


@dataclass(frozen=True)
class SwimmerRecording:
    text: str
    source: str
    info: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
    bytes_seen: int = 0
    line_count: int = 0
    command_count: int = 0


@dataclass(frozen=True)
class FilterVerdict:
    ok: bool
    reasons: tuple[str, ...]
    labels: tuple[str, ...]


@dataclass(frozen=True)
class SwimmerTask:
    task_id: str
    instruction: str
    trace_id: str
    expected_files: dict[str, str]
    receipt_ledger: str
    solve_script: str
    partial_script: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrialResult:
    name: str
    ok: bool
    process_ok: bool
    validation_ok: bool
    returncode: int | None
    duration_ms: int
    status: str
    errors: tuple[str, ...]
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass(frozen=True)
class ThreeTrialResult:
    task_id: str
    trace_id: str
    admitted: bool
    all_passing_ok: bool
    nop_failed: bool
    partial_failed: bool
    trials: tuple[TrialResult, ...]
    receipt_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "admitted": self.admitted,
            "all_passing_ok": self.all_passing_ok,
            "nop_failed": self.nop_failed,
            "partial_failed": self.partial_failed,
            "trials": [asdict(trial) for trial in self.trials],
            "receipt_id": self.receipt_id,
        }


class TerminalSwimmerForge:
    """Core adapter for receipt-backed terminal swimmer validation."""

    def __init__(
        self,
        *,
        state_dir: Path | str | None = None,
        run_root: Path | str | None = None,
        default_timeout_s: float = 10.0,
        terminal_runner: Callable[[str, str | None, int], Mapping[str, Any]] | None = None,
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir is not None else _DEFAULT_STATE_DIR
        self.run_root = Path(run_root) if run_root is not None else self.state_dir / "terminal_swimmer_runs"
        self.default_timeout_s = float(default_timeout_s)
        self.terminal_runner = terminal_runner
        self.flux_ledger = self.state_dir / FLUX_LEDGER_NAME
        self.work_receipts = self.state_dir / WORK_RECEIPTS_NAME
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.run_root.mkdir(parents=True, exist_ok=True)

    def ingest_recording(
        self,
        text: str,
        *,
        source: str = "local_pty",
        info: Mapping[str, Any] | None = None,
    ) -> SwimmerRecording:
        """Build a compact recording object from terminal text plus metadata."""
        metadata = dict(info or {})
        duration = metadata.get("duration_s", metadata.get("duration", 0.0))
        try:
            duration_s = float(duration or 0.0)
        except (TypeError, ValueError):
            duration_s = 0.0
        lines = text.splitlines()
        command_count = sum(1 for line in lines if line.lstrip().startswith(("$", "%", ">")))
        return SwimmerRecording(
            text=text,
            source=str(source),
            info=metadata,
            duration_s=max(0.0, duration_s),
            bytes_seen=len(text.encode("utf-8", errors="replace")),
            line_count=len(lines),
            command_count=command_count,
        )

    def filter_recording(
        self,
        recording: SwimmerRecording,
        *,
        owner_consent: bool = False,
        min_duration_s: float = 0.0,
    ) -> FilterVerdict:
        """Apply Phase-1 covenant filters before synthesis or replay."""
        reasons: list[str] = []
        labels: list[str] = ["CLI_TEXT_ONLY", "PHASE1_LOCAL_FILTER"]
        text = recording.text

        if not text.strip():
            reasons.append("empty_recording")
        if recording.duration_s < min_duration_s:
            reasons.append(f"duration_below_min:{recording.duration_s:.3f}<{min_duration_s:.3f}")
        if recording.source == "local_pty" and not owner_consent:
            reasons.append("owner_consent_required_for_local_pty_ingest")
        for name, pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                reasons.append(f"pii_or_secret:{name}")
        for name, pattern in _TUI_PATTERNS:
            if pattern.search(text):
                reasons.append(f"tui_or_fullscreen:{name}")

        if not reasons:
            labels.append("FILTER_PASS")
        else:
            labels.append("FILTER_BLOCK")
        return FilterVerdict(ok=not reasons, reasons=tuple(reasons), labels=tuple(labels))

    def run_alice_global_chat_command(
        self,
        command: str,
        *,
        owner_consent: bool,
        trace_id: str | None = None,
        cwd: str | None = None,
        timeout_s: int | None = None,
        expected_stdout_contains: str | None = None,
    ) -> dict[str, Any]:
        """Run a narrow Phase-2 command through the Alice global-chat terminal path.

        This is not an admission shortcut. New swimmer tasks still need the
        three-trial gate before they become tournament work. The wrapper only
        gives local terminal swimmer commands one safe execution throat:
        owner consent + recording filters + alice_global_chat_terminal receipt.
        """
        clean_command = str(command or "").strip()
        trace = trace_id or str(uuid.uuid4())
        errors: list[str] = []

        recording = self.ingest_recording(
            f"$ {clean_command}\n",
            source="local_pty",
            info={"duration_s": 1.0, "phase": 2, "surface": "alice_global_chat_terminal"},
        )
        verdict = self.filter_recording(recording, owner_consent=owner_consent, min_duration_s=0.0)
        errors.extend(verdict.reasons)
        if not clean_command:
            errors.append("empty_command")
        if "\n" in clean_command or "\r" in clean_command:
            errors.append("multi_line_command_refused")

        if errors:
            return self._write_command_wrapper_receipt(
                trace_id=trace,
                command=clean_command,
                status="REFUSED",
                ok=False,
                errors=errors,
                filter_labels=verdict.labels,
                terminal_receipt={},
                expected_stdout_contains=expected_stdout_contains,
            )

        timeout = int(timeout_s if timeout_s is not None else self.default_timeout_s)
        terminal_receipt = self._run_alice_global_chat_terminal(clean_command, cwd, timeout)
        stdout = str(terminal_receipt.get("stdout") or "")
        runner_ok = (
            terminal_receipt.get("type") == "TERMINAL_EXECUTION"
            and int(terminal_receipt.get("exit_code", 1)) == 0
        )
        expected_ok = True
        if expected_stdout_contains is not None:
            expected_ok = expected_stdout_contains in stdout
            if not expected_ok:
                errors.append("expected_stdout_missing")

        return self._write_command_wrapper_receipt(
            trace_id=trace,
            command=clean_command,
            status="EXECUTED" if runner_ok and expected_ok else "FAILED",
            ok=bool(runner_ok and expected_ok),
            errors=errors,
            filter_labels=verdict.labels,
            terminal_receipt=terminal_receipt,
            expected_stdout_contains=expected_stdout_contains,
        )

    def seed_receipt_task(
        self,
        *,
        task_id: str = "seed_receipt_task",
        trace_id: str | None = None,
        expected_text: str = "SIFTA terminal swimmer forge alive",
    ) -> SwimmerTask:
        """Return a deterministic toy task that proves the three-trial engine."""
        trace = trace_id or str(uuid.uuid4())
        expected_payload = expected_text.rstrip("\n") + "\n"
        instruction = (
            "Write result.txt with the expected payload and append one JSONL "
            "receipt containing the provided trace_id, ok=true, status=DONE, "
            "and a truth_note. The receipt is the action proof."
        )
        solve_script = r"""set -euo pipefail
python3 - <<'PY'
import json
import os
import time
from pathlib import Path

Path(os.environ["SIFTA_SWIMMER_RESULT"]).write_text(
    os.environ["SIFTA_SWIMMER_EXPECTED_TEXT"] + "\n",
    encoding="utf-8",
)
row = {
    "ts": time.time(),
    "event": "terminal_swimmer_seed_task",
    "trace_id": os.environ["SIFTA_SWIMMER_TRACE_ID"],
    "ok": True,
    "status": "DONE",
    "truth_note": "seed task wrote result.txt from the sandbox solve script",
}
with open(os.environ["SIFTA_SWIMMER_RECEIPT_LEDGER"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(row, sort_keys=True) + "\n")
PY
"""
        partial_script = r"""set -euo pipefail
python3 - <<'PY'
import os
from pathlib import Path

Path(os.environ["SIFTA_SWIMMER_RESULT"]).write_text(
    os.environ["SIFTA_SWIMMER_EXPECTED_TEXT"] + "\n",
    encoding="utf-8",
)
PY
"""
        return SwimmerTask(
            task_id=task_id,
            instruction=instruction,
            trace_id=trace,
            expected_files={"result.txt": expected_payload},
            receipt_ledger="work_receipts.jsonl",
            solve_script=solve_script,
            partial_script=partial_script,
            metadata={"task_kind": "deterministic_seed", "phase": 1},
        )

    def run_three_trial(self, task: SwimmerTask) -> ThreeTrialResult:
        """Run AllPassing/Nop/Partial and append a final work receipt."""
        run_id = uuid.uuid4().hex[:12]
        all_passing = self._run_trial(
            task=task,
            trial_name="all_passing",
            script=task.solve_script,
            run_id=run_id,
        )
        nop = self._run_trial(
            task=task,
            trial_name="nop",
            script=":",
            run_id=run_id,
        )
        partial = self._run_trial(
            task=task,
            trial_name="partial",
            script=task.partial_script,
            run_id=run_id,
        )
        admitted = all_passing.ok and not nop.ok and not partial.ok
        trials = (all_passing, nop, partial)
        receipt_id = self._write_work_receipt(task=task, trials=trials, admitted=admitted)
        return ThreeTrialResult(
            task_id=task.task_id,
            trace_id=task.trace_id,
            admitted=admitted,
            all_passing_ok=all_passing.ok,
            nop_failed=not nop.ok,
            partial_failed=not partial.ok,
            trials=trials,
            receipt_id=receipt_id,
        )

    def _run_trial(
        self,
        *,
        task: SwimmerTask,
        trial_name: str,
        script: str,
        run_id: str,
    ) -> TrialResult:
        sandbox = self.run_root / task.task_id / run_id / trial_name
        if sandbox.exists():
            shutil.rmtree(sandbox)
        sandbox.mkdir(parents=True, exist_ok=True)
        script_path = sandbox / "swimmer_trial.sh"
        script_path.write_text(script, encoding="utf-8")
        script_path.chmod(0o700)

        env = dict(os.environ)
        env.update(
            {
                "SIFTA_SWIMMER_SANDBOX": str(sandbox),
                "SIFTA_SWIMMER_TRACE_ID": task.trace_id,
                "SIFTA_SWIMMER_EXPECTED_TEXT": next(iter(task.expected_files.values())).rstrip("\n"),
                "SIFTA_SWIMMER_RESULT": str(sandbox / "result.txt"),
                "SIFTA_SWIMMER_RECEIPT_LEDGER": str(sandbox / task.receipt_ledger),
            }
        )

        started = time.monotonic()
        stdout = ""
        stderr = ""
        returncode: int | None = None
        status = "RUN"
        try:
            proc = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=sandbox,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.default_timeout_s,
                check=False,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            returncode = proc.returncode
            process_ok = proc.returncode == 0
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            process_ok = False
            status = "TIMEOUT"
        duration_ms = int((time.monotonic() - started) * 1000)

        validation_ok, errors = self._validate_task_artifacts(task, sandbox)
        ok = process_ok and validation_ok
        if status != "TIMEOUT":
            status = "PASS" if ok else "FAIL"
        result = TrialResult(
            name=trial_name,
            ok=ok,
            process_ok=process_ok,
            validation_ok=validation_ok,
            returncode=returncode,
            duration_ms=duration_ms,
            status=status,
            errors=tuple(errors),
            stdout_tail=_tail(stdout),
            stderr_tail=_tail(stderr),
        )

        # Real electricity measurement for the yin body layer (Landauer/Prigogine)
        power_sample = self._sample_powermetrics_joules(
            duration_s=max(0.05, duration_ms / 1000.0)
        )

        self._append_flux_row(
            task=task,
            trial=result,
            script=script,
            stdout=stdout,
            stderr=stderr,
            power_sample=power_sample,
        )
        return result

    def _validate_task_artifacts(self, task: SwimmerTask, sandbox: Path) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for relpath, expected in task.expected_files.items():
            safe_rel = _safe_relpath(relpath)
            path = sandbox / safe_rel
            if not path.exists():
                errors.append(f"missing_file:{safe_rel}")
                continue
            actual = path.read_text(encoding="utf-8", errors="replace")
            if actual != expected:
                errors.append(f"content_mismatch:{safe_rel}")

        receipt_path = sandbox / _safe_relpath(task.receipt_ledger)
        matching_receipts = []
        if not receipt_path.exists():
            errors.append(f"missing_receipt_ledger:{task.receipt_ledger}")
        else:
            for line_number, line in enumerate(receipt_path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"invalid_receipt_json:{line_number}")
                    continue
                if row.get("trace_id") == task.trace_id:
                    matching_receipts.append(row)
            if not any(
                row.get("ok") is True and row.get("status") == "DONE" and row.get("truth_note")
                for row in matching_receipts
            ):
                errors.append("receipt_missing_truth_row")

        return not errors, errors

    def _append_flux_row(
        self,
        *,
        task: SwimmerTask,
        trial: TrialResult,
        script: str,
        stdout: str,
        stderr: str,
        power_sample: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        in_bytes = script.encode("utf-8", errors="replace")
        out_bytes = (stdout + stderr).encode("utf-8", errors="replace")
        proxy_j = self._joules_proxy(trial.duration_ms, len(in_bytes), len(out_bytes))

        power_sample = power_sample or {"joules": 0.0, "note": "no_sample"}
        real_j = power_sample.get("joules", 0.0) or 0.0
        joules_used = real_j if real_j > 0.0 else proxy_j

        row: dict[str, Any] = {
            "ts": time.time(),
            "event": "terminal_swimmer_forge_trial",
            "schema": FLUX_SCHEMA,
            "module_version": MODULE_VERSION,
            "truth_label": "OPERATIONAL",
            "trace_id": task.trace_id,
            "task_id": task.task_id,
            "trial": trial.name,
            "ok": trial.ok,
            "status": trial.status,
            "process_ok": trial.process_ok,
            "validation_ok": trial.validation_ok,
            "returncode": trial.returncode,
            "duration_ms": trial.duration_ms,
            "bytes_in": len(in_bytes),
            "bytes_out": len(out_bytes),
            "transition_entropy_nats": transition_entropy_nats(in_bytes + out_bytes),
            "joules": round(joules_used, 6),
            "joules_proxy": proxy_j,
            "joules_real": real_j,
            "power_note": power_sample.get("note", ""),
            "package_power_w": power_sample.get("package_power_w", 0.0),
            "errors": list(trial.errors),
        }
        row["row_sha256_16"] = _sha256_16(row)
        _append_jsonl(self.flux_ledger, row)
        return row

    def _write_work_receipt(
        self,
        *,
        task: SwimmerTask,
        trials: Sequence[TrialResult],
        admitted: bool,
    ) -> str:
        receipt_id = str(uuid.uuid4())
        row: dict[str, Any] = {
            "ts": time.time(),
            "trace_id": receipt_id,
            "event": "WORK_RECEIPT",
            "schema": WORK_RECEIPT_SCHEMA,
            "source": "swarm_terminal_swimmer_forge",
            "module_version": MODULE_VERSION,
            "receipt": "terminal_swimmer_forge_phase1_three_trial",
            "task_id": task.task_id,
            "swimmer_trace_id": task.trace_id,
            "ok": admitted,
            "status": "ADMITTED" if admitted else "REJECTED",
            "truth_note": (
                "AllPassing passed and both Nop/Partial failed state checks"
                if admitted
                else "three-trial admission failed; inspect trial_results"
            ),
            "trial_results": [
                {
                    "name": trial.name,
                    "ok": trial.ok,
                    "process_ok": trial.process_ok,
                    "validation_ok": trial.validation_ok,
                    "status": trial.status,
                    "errors": list(trial.errors),
                }
                for trial in trials
            ],
        }
        row["row_sha256_16"] = _sha256_16(row)
        _append_jsonl(self.work_receipts, row)
        return receipt_id

    def _run_alice_global_chat_terminal(
        self,
        command: str,
        cwd: str | None,
        timeout_s: int,
    ) -> dict[str, Any]:
        if self.terminal_runner is not None:
            return dict(self.terminal_runner(command, cwd, timeout_s))
        try:
            from System.swarm_terminal_organ import run_terminal
        except Exception as exc:
            return {
                "type": "TERMINAL_ERROR",
                "source": "alice_global_chat_terminal",
                "command": command,
                "error": f"terminal_organ_import_failed:{type(exc).__name__}",
                "exit_code": 1,
            }
        receipt = run_terminal(command, cwd=cwd, timeout_s=timeout_s)
        return dict(receipt or {})

    def _write_command_wrapper_receipt(
        self,
        *,
        trace_id: str,
        command: str,
        status: str,
        ok: bool,
        errors: Sequence[str],
        filter_labels: Sequence[str],
        terminal_receipt: Mapping[str, Any],
        expected_stdout_contains: str | None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "ts": time.time(),
            "trace_id": trace_id,
            "event": "TERMINAL_SWIMMER_COMMAND_WRAPPER",
            "schema": COMMAND_WRAPPER_SCHEMA,
            "source": "alice_global_chat_terminal",
            "module_version": MODULE_VERSION,
            "command": command,
            "ok": bool(ok),
            "status": status,
            "errors": list(errors),
            "filter_labels": list(filter_labels),
            "expected_stdout_contains": expected_stdout_contains or "",
            "terminal_receipt_type": str(terminal_receipt.get("type") or ""),
            "terminal_receipt_hash": str(terminal_receipt.get("hash") or terminal_receipt.get("receipt_hash") or ""),
            "terminal_exit_code": terminal_receipt.get("exit_code"),
            "stdout_tail": _tail(str(terminal_receipt.get("stdout") or ""), limit=500),
            "stderr_tail": _tail(str(terminal_receipt.get("stderr") or ""), limit=500),
            "truth_note": "Phase-2 wrapper; three-trial gate remains mandatory for swimmer admission.",
        }
        row["row_sha256_16"] = _sha256_16(row)
        _append_jsonl(self.work_receipts, row)
        return row

    @staticmethod
    def _sample_powermetrics_joules(duration_s: float = 0.4) -> dict[str, Any]:
        """Best-effort real power sample on macOS via powermetrics.

        Returns dict with 'joules', 'cpu_time_ms', 'package_power_w', 'note'.
        Falls back to proxy values + note when powermetrics is unavailable,
        not permitted, or the sample fails. Never raises.
        """
        result = {
            "joules": 0.0,
            "cpu_time_ms": 0,
            "package_power_w": 0.0,
            "note": "powermetrics_unavailable_or_denied",
        }
        if not sys.platform == "darwin":
            result["note"] = "not_macos"
            return result

        try:
            # Short non-interactive sample. CPU + package power are often readable
            # without sudo for short intervals; full power may require it.
            cmd = [
                "powermetrics",
                "-i", str(int(duration_s * 1000)),
                "-n", "1",
                "-s", "cpu_power,package_power",
                "--format", "plist",
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(2.0, duration_s + 1.5),
            )
            if proc.returncode != 0:
                result["note"] = f"powermetrics_exit_{proc.returncode}"
                return result

            # Extremely lightweight plist parse for the fields we care about.
            # We do not want plistlib dependency in the core forge for phase-1.
            out = proc.stdout
            # Look for CPU time and package power numbers in the plist-ish output.
            import re as _re
            cpu_match = _re.search(r"<key>cpu_time</key>\s*<real>([0-9.]+)</real>", out)
            pkg_match = _re.search(r"<key>combined_package_power</key>\s*<real>([0-9.]+)</real>", out)
            if cpu_match:
                result["cpu_time_ms"] = int(float(cpu_match.group(1)) * 1000)
            if pkg_match:
                pkg_w = float(pkg_match.group(1))
                result["package_power_w"] = pkg_w
                result["joules"] = round(pkg_w * max(0.001, duration_s), 6)
                result["note"] = "powermetrics_sampled"
            else:
                result["note"] = "powermetrics_sampled_no_package_power"
        except Exception as exc:  # pragma: no cover - hardware/tool variance
            result["note"] = f"powermetrics_exception:{type(exc).__name__}"

        return result

    @staticmethod
    def _joules_proxy(duration_ms: int, bytes_in: int, bytes_out: int) -> float:
        byte_factor = max(1.0, (bytes_in + bytes_out) / 1024.0)
        second_factor = max(0.001, duration_ms / 1000.0)
        return round(byte_factor * second_factor, 6)


def run_seed_smoke(
    *,
    state_dir: Path | str | None = None,
    run_root: Path | str | None = None,
    trace_id: str | None = None,
) -> ThreeTrialResult:
    forge = TerminalSwimmerForge(state_dir=state_dir, run_root=run_root)
    task = forge.seed_receipt_task(trace_id=trace_id)
    return forge.run_three_trial(task)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIFTA terminal swimmer forge phase-1 core")
    parser.add_argument("--state-dir", default=None, help="state directory for flux/work receipt ledgers")
    parser.add_argument("--run-root", default=None, help="sandbox run directory")
    parser.add_argument("--trace-id", default=None, help="trace id for the seed smoke task")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_seed_smoke(
        state_dir=args.state_dir,
        run_root=args.run_root,
        trace_id=args.trace_id,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.admitted else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
