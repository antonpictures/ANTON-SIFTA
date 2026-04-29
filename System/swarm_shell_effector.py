#!/usr/bin/env python3
"""
swarm_shell_effector.py — Safe shell effector execution law
══════════════════════════════════════════════════════════════════════

Lifecycle: PROPOSE → SANDBOX → COMMIT → RECEIPT

- Starts with a strict whitelist of read-only or safe ephemeral commands:
  (git diff, git status, py_compile, pytest).
- No irreversible actions allowed yet.
- Subprocess execution without shell=True to avoid injection.

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

# Reuse the exact same schema version to unify ledgers if needed
SCHEMA_V1 = "SIFTA_EFFECTOR_RECEIPT_V1"
KIND_SHELL_EXEC = "shell_exec"
PHASE_COMMIT = "COMMIT"
PHASE_BROKEN = "BROKEN"
_DEFAULT_REGISTRATION_TRACE = Path(__file__).resolve().parents[1] / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_ANONYMOUS_CALLERS = {"", "anonymous", "unknown", "none", "null"}


def _canonical_dumps(obj: Dict[str, Any]) -> str:
    body = {k: v for k, v in sorted(obj.items()) if k != "integrity"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def receipt_integrity(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_dumps(payload).encode("utf-8")).hexdigest()


def verify_receipt_row(row: Dict[str, Any]) -> bool:
    if row.get("schema") != SCHEMA_V1:
        return False
    got = row.get("integrity")
    if not got or not isinstance(got, str):
        return False
    expect = receipt_integrity({k: v for k, v in row.items() if k != "integrity"})
    return got == expect


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def is_command_whitelisted(command: List[str]) -> tuple[bool, Optional[str]]:
    """Returns (is_whitelisted, target_rel_path_to_check)"""
    if not command:
        return False, None
    cmd0 = command[0]

    # whitelist: git diff, git status
    if cmd0 == "git" and len(command) >= 2:
        if command[1] in ("diff", "status"):
            # Block potentially dangerous git flags
            if any(arg.startswith("--ext-diff") for arg in command):
                return False, None
            # read-only git commands don't specify a single strictly-bound file we must jail,
            # but we can enforce no path traversal visually if we wanted. 
            # For now, git is scoped to cwd=root by subprocess.run.
            return True, None

    # whitelist: pytest <file>
    if cmd0 == "pytest" and len(command) == 2:
        # Disallow flags starting with '-' to prevent flag injection
        if command[1].startswith("-"):
            return False, None
        return True, command[1]

    # whitelist: python3 -m pytest <file>, python3 -m py_compile <file>
    if cmd0 == "python3" and len(command) == 4:
        if command[1] == "-m" and command[2] in ("pytest", "py_compile"):
            if command[3].startswith("-"):
                return False, None
            return True, command[3]

    return False, None


@dataclass
class ProposedShellAction:
    action_id: str
    kind: str
    command: List[str]
    caller_id: str


class ShellEffectorRuntime:
    """
    Shell-bound effector: propose → sandbox (dry run) → commit → receipt.
    No undo because currently allowed actions are non-mutating or safe.
    """

    def __init__(
        self,
        root: Path,
        *,
        receipt_path: Path,
        registration_trace_path: Optional[Path] = None,
        default_caller_id: Optional[str] = None,
        require_registered_caller: bool = True,
    ) -> None:
        self.root = root.resolve()
        self.receipt_path = receipt_path
        self.registration_trace_path = registration_trace_path or _DEFAULT_REGISTRATION_TRACE
        self.default_caller_id = default_caller_id
        self.require_registered_caller = require_registered_caller
        self._pending: Dict[str, ProposedShellAction] = {}
        self.root.mkdir(parents=True, exist_ok=True)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self._committed_ids: set[str] = self._load_committed_ids()

    def _load_committed_ids(self) -> set[str]:
        committed: set[str] = set()
        if not self.receipt_path.is_file():
            return committed
        with open(self.receipt_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not verify_receipt_row(row) or row.get("kind") != KIND_SHELL_EXEC:
                    continue
                aid = str(row.get("action_id") or "")
                if not aid:
                    continue
                if row.get("phase") == PHASE_COMMIT and row.get("ok") is True:
                    committed.add(aid)
        return committed

    def _registered_caller_tokens(self) -> set[str]:
        tokens: set[str] = set()
        if not self.registration_trace_path.is_file():
            return tokens
        with open(self.registration_trace_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for key in ("doctor", "trace_id", "agent_id", "caller_id"):
                    value = row.get(key)
                    if value is not None:
                        tokens.add(str(value).strip())
        return tokens

    def _resolve_caller_id(self, action: Dict[str, Any]) -> str:
        caller_id = str(action.get("caller_id") or self.default_caller_id or "").strip()
        if caller_id.lower() in _ANONYMOUS_CALLERS:
            raise ValueError("anonymous_caller_refused")
        if self.require_registered_caller and caller_id not in self._registered_caller_tokens():
            raise ValueError("unregistered_caller_refused")
        return caller_id

    def _caller_for_action(self, action_id: str) -> Optional[str]:
        p = self._pending.get(action_id)
        if p:
            return p.caller_id
        row = self.receipt(action_id)
        if row and row.get("caller_id"):
            return str(row.get("caller_id"))
        return self.default_caller_id

    def _append_receipt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row.setdefault("schema", SCHEMA_V1)
        row.setdefault("status", "ok" if row.get("ok") is True else "error")
        if "truth_note" not in row:
            phase = row.get("phase", "UNKNOWN")
            if row.get("ok") is True:
                row["truth_note"] = f"{phase} recorded by deterministic shell effector runtime."
            else:
                row["truth_note"] = f"{phase} recorded failure before or during deterministic shell effector runtime."
        row["integrity"] = receipt_integrity(row)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(self.receipt_path, json.dumps(row, separators=(",", ":")) + "\n")
        return row

    def propose(self, action: Dict[str, Any]) -> ProposedShellAction:
        caller_id = self._resolve_caller_id(action)
        if action.get("kind") != KIND_SHELL_EXEC:
            raise ValueError(f"unsupported_kind:{action.get('kind')}")
        
        command = action.get("command")
        if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            raise ValueError("command_must_be_list_of_strings")

        is_wl, target_path = is_command_whitelisted(command)
        if not is_wl:
            raise ValueError("command_not_whitelisted")
            
        if target_path:
            from System.swarm_effector_runtime import _safe_rel_path
            _safe_rel_path(self.root, target_path)

        aid = str(action.get("action_id") or uuid.uuid4())
        if aid in self._committed_ids:
            raise ValueError("action_id_already_committed")

        p = ProposedShellAction(
            action_id=aid,
            kind=KIND_SHELL_EXEC,
            command=command,
            caller_id=caller_id,
        )
        self._pending[aid] = p
        return p

    def sandbox(self, action_id: str) -> Dict[str, Any]:
        """Dry-run checks for shell commands."""
        p = self._pending.get(action_id)
        if not p:
            return {"ok": False, "reason": "unknown_action_id"}
        
        is_wl, target_path = is_command_whitelisted(p.command)
        if not is_wl:
            return {"ok": False, "reason": "command_not_whitelisted"}
            
        if target_path:
            from System.swarm_effector_runtime import _safe_rel_path
            try:
                _safe_rel_path(self.root, target_path)
            except ValueError:
                return {"ok": False, "reason": "path_escape"}

        return {"ok": True, "resolved_command": " ".join(p.command)}

    def preview(self, action_id: str) -> str:
        p = self._pending.get(action_id)
        if not p:
            raise KeyError("unknown_action_id")
        return f"{p.kind}: " + " ".join(p.command)

    def commit(self, action_id: str) -> Dict[str, Any]:
        if action_id in self._committed_ids:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_SHELL_EXEC,
                    "ts": time.time(),
                    "ok": False,
                    "error": "double_commit",
                    "caller_id": self._caller_for_action(action_id),
                    "status": "rejected",
                    "truth_note": "Rejected duplicate COMMIT for an action already committed.",
                }
            )
            return {"ok": False, "error": "double_commit", "action_id": action_id}

        p = self._pending.get(action_id)
        if not p:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_SHELL_EXEC,
                    "ts": time.time(),
                    "ok": False,
                    "error": "unknown_or_expired_action",
                    "caller_id": self._caller_for_action(action_id),
                    "status": "rejected",
                    "truth_note": "Rejected COMMIT because no pending proposed action exists.",
                }
            )
            return {"ok": False, "error": "unknown_or_expired_action", "action_id": action_id}

        sb = self.sandbox(action_id)
        if not sb.get("ok"):
            err = sb.get("reason", "sandbox_failed")
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_SHELL_EXEC,
                    "command": p.command,
                    "ts": time.time(),
                    "ok": False,
                    "error": err,
                    "caller_id": p.caller_id,
                    "status": "rejected",
                    "truth_note": f"Rejected COMMIT in sandbox phase: {err}.",
                }
            )
            del self._pending[action_id]
            return {"ok": False, "error": err, "action_id": action_id}

        try:
            # Execute without shell=True for injection safety
            result = subprocess.run(
                p.command,
                cwd=self.root,
                capture_output=True,
                text=False,
                timeout=60,
            )
        except Exception as e:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_SHELL_EXEC,
                    "command": p.command,
                    "ts": time.time(),
                    "ok": False,
                    "error": f"exec_error:{e}",
                    "caller_id": p.caller_id,
                    "status": "error",
                    "truth_note": "Shell execution failed to launch.",
                }
            )
            del self._pending[action_id]
            return {"ok": False, "error": str(e), "action_id": action_id}

        del self._pending[action_id]
        self._committed_ids.add(action_id)

        stdout_b64 = _b64(result.stdout) if result.stdout else ""
        stderr_b64 = _b64(result.stderr) if result.stderr else ""

        self._append_receipt(
            {
                "phase": PHASE_COMMIT,
                "action_id": action_id,
                "kind": KIND_SHELL_EXEC,
                "command": p.command,
                "exit_code": result.returncode,
                "ts": time.time(),
                "ok": True,
                "caller_id": p.caller_id,
                "status": "committed",
                "truth_note": f"Shell exec committed. Exit code: {result.returncode}",
                "stdout_b64": stdout_b64,
                "stderr_b64": stderr_b64,
            }
        )
        return {
            "ok": True, 
            "action_id": action_id, 
            "exit_code": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace"),
            "stderr": result.stderr.decode("utf-8", errors="replace"),
        }

    def undo(self, action_id: str) -> Dict[str, Any]:
        """Shell execution on whitelisted safe commands doesn't require explicit undo."""
        self._append_receipt(
            {
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_SHELL_EXEC,
                "ts": time.time(),
                "ok": False,
                "error": "shell_exec_not_undoable",
                "caller_id": self._caller_for_action(action_id),
                "status": "rejected",
                "truth_note": "Shell execution does not currently support UNDO operations.",
            }
        )
        return {"ok": False, "error": "shell_exec_not_undoable", "action_id": action_id}

    def receipt(self, action_id: str) -> Optional[Dict[str, Any]]:
        if not self.receipt_path.is_file():
            return None
        last: Optional[Dict[str, Any]] = None
        with open(self.receipt_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("action_id") == action_id:
                    last = row
        return last
