"""Owner-authenticated ``/stigmergicode`` command bus.

The public web chat is intentionally zero-authority.  This module is the small
bridge between an explicitly paired owner surface and the local Alice Browser
coding tab. Pairing secrets and public receipts stay hashed; optional task text
is retained only in the owner-state queue with restrictive permissions so the
coding surface can receive the exact bounded request.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows is not a supported SIFTA host.
    fcntl = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = ROOT / ".sifta_state"
COMMAND_RE = re.compile(r"^/stigmergicode(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
MAX_TASK_CHARS = 4000
PAIR_TTL_S = 300.0
SESSION_TTL_S = 12 * 60 * 60


def parse_command(text: str) -> Optional[str]:
    """Return the optional coding task, or ``None`` for a non-command.

    ``//stigmergicode`` remains the existing literal-slash escape and is not
    interpreted as an owner command.
    """
    clean = str(text or "").strip()
    match = COMMAND_RE.fullmatch(clean)
    if not match or clean.startswith("//"):
        return None
    task = str(match.group(1) or "").strip()
    if len(task) > MAX_TASK_CHARS:
        raise ValueError(f"Coding task exceeds {MAX_TASK_CHARS} characters")
    return task


def _paths(state_dir: Path | str) -> tuple[Path, Path, Path]:
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    owner_path = root / "stigmergicode_owner.json"
    tasks_path = root / "stigmergicode_tasks.jsonl"
    lock_path = root / "stigmergicode.lock"
    if tasks_path.exists():
        tasks_path.chmod(0o600)
    return owner_path, tasks_path, lock_path


def _digest(secret: str) -> str:
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()


def _locked(lock_path: Path):
    class _Lock:
        def __enter__(self):
            self.handle = lock_path.open("a+")
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            return self

        def __exit__(self, *_args):
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()

    return _Lock()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _append(path: Path, row: dict[str, Any]) -> None:
    from System.jsonl_file_lock import append_line_locked

    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if path.name == "stigmergicode_tasks.jsonl":
        path.chmod(0o600)


def _task_states(path: Path) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return states
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("task_id"):
            states[str(row["task_id"])] = row
    return states


def issue_pairing_ticket(*, state_dir: Path | str = DEFAULT_STATE_DIR, now: Optional[float] = None) -> str:
    """Create a short-lived ticket for the owner to enter on the phone page."""
    owner_path, _, lock_path = _paths(state_dir)
    ticket = secrets.token_urlsafe(32)
    stamp = time.time() if now is None else float(now)
    with _locked(lock_path):
        current = _read_json(owner_path)
        current.update({
            "ticket_hash": _digest(ticket),
            "ticket_expires_at": stamp + PAIR_TTL_S,
            "session_hash": "",
            "session_expires_at": 0.0,
            "schema_version": "stigmergicode.owner.v1",
        })
        owner_path.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
        owner_path.chmod(0o600)
    return ticket


def pair_ticket(ticket: str, *, state_dir: Path | str = DEFAULT_STATE_DIR, now: Optional[float] = None) -> str:
    """Consume a one-use ticket and return a bearer session token."""
    owner_path, _, lock_path = _paths(state_dir)
    stamp = time.time() if now is None else float(now)
    session = secrets.token_urlsafe(40)
    with _locked(lock_path):
        current = _read_json(owner_path)
        if (
            not ticket
            or not current.get("ticket_hash")
            or stamp >= float(current.get("ticket_expires_at") or 0.0)
            or not hmac.compare_digest(_digest(ticket), str(current.get("ticket_hash")))
        ):
            raise PermissionError("Pairing ticket expired or already used")
        current.update({
            "ticket_hash": "",
            "ticket_expires_at": 0.0,
            "session_hash": _digest(session),
            "session_expires_at": stamp + SESSION_TTL_S,
        })
        sessions = {key: expiry for key, expiry in current.get("sessions", {}).items() if float(expiry) > stamp}
        sessions[_digest(session)] = stamp + SESSION_TTL_S
        current["sessions"] = dict(list(sessions.items())[-16:])
        owner_path.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
        owner_path.chmod(0o600)
    return session


def authenticate(token: str, *, state_dir: Path | str = DEFAULT_STATE_DIR, now: Optional[float] = None) -> bool:
    owner_path, _, _ = _paths(state_dir)
    current = _read_json(owner_path)
    stamp = time.time() if now is None else float(now)
    return bool(
        token
        and (
            (current.get("session_hash")
             and stamp < float(current.get("session_expires_at") or 0.0)
             and hmac.compare_digest(_digest(token), str(current.get("session_hash"))))
            or any(stamp < float(expiry) and hmac.compare_digest(_digest(token), key)
                   for key, expiry in current.get("sessions", {}).items())
        )
    )


def revoke(*, state_dir: Path | str = DEFAULT_STATE_DIR) -> None:
    owner_path, _, lock_path = _paths(state_dir)
    with _locked(lock_path):
        current = _read_json(owner_path)
        current.update({"ticket_hash": "", "ticket_expires_at": 0.0, "session_hash": "", "session_expires_at": 0.0, "sessions": {}})
        owner_path.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
        owner_path.chmod(0o600)


def _append_receipt(row: dict[str, Any], *, state_dir: Path) -> None:
    try:
        from System.ledger_append import append_ledger_line
        from System.swarm_stigmergic_boot_memory import append_linked_record

        memory_row = append_linked_record(
            "owner_command",
            state_dir=state_dir,
            payload={"task_id": row.get("task_id"), "command_hash": row.get("command_hash")},
        )

        receipt = {
            "trace_id": str(uuid.uuid4()),
            "truth_label": "IDE_DOCTOR_OPERATIONAL_TRACE",
            "status": row.get("status", "QUEUED"),
            "action": "stigmergicode_command",
            "source": "owner_authenticated_command_bus",
            "task_id": row.get("task_id"),
            "command_hash": row.get("command_hash"),
            "source_ids": [memory_row["record_id"], memory_row["boot_record_id"]],
            "owner_authority": True,
            "no_stgm_claim": True,
            "clock_source": "os_time",
        }
        append_ledger_line(state_dir / "ide_stigmergic_trace.jsonl", receipt)
        append_ledger_line(state_dir / "work_receipts.jsonl", receipt)
    except Exception:
        # The task queue remains authoritative if a coordination ledger is unavailable.
        pass


def enqueue_task(task: str = "", *, source: str = "owner", state_dir: Path | str = DEFAULT_STATE_DIR, now: Optional[float] = None) -> dict[str, Any]:
    """Append one idempotent owner request to the private coding queue."""
    clean = str(task or "").strip()
    if len(clean) > MAX_TASK_CHARS:
        raise ValueError(f"Coding task exceeds {MAX_TASK_CHARS} characters")
    root = Path(state_dir)
    _, tasks_path, lock_path = _paths(root)
    stamp = time.time() if now is None else float(now)
    command_hash = _digest(clean or "(open-coding-tab)")
    request_id = _digest(f"{source}:{command_hash}")[:32]
    with _locked(lock_path):
        states = _task_states(tasks_path)
        for row in reversed(list(states.values())):
            if row.get("request_id") == request_id:
                return row
        row = {
            "schema_version": "stigmergicode.task.v1",
            "task_id": uuid.uuid4().hex,
            "request_id": request_id,
            "command_hash": command_hash,
            "task": clean,
            "task_present": bool(clean),
            "source": str(source)[:80],
            "status": "PENDING",
            "created_at": stamp,
            "updated_at": stamp,
            "owner_authority": True,
            "browser_target": "http://127.0.0.1:3080",
        }
        _append(tasks_path, row)
    _append_receipt(row, state_dir=root)
    return row


def claim_next_task(*, state_dir: Path | str = DEFAULT_STATE_DIR, now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Claim one pending tab request, including its private owner task text."""
    root = Path(state_dir)
    _, tasks_path, lock_path = _paths(root)
    stamp = time.time() if now is None else float(now)
    with _locked(lock_path):
        states = _task_states(tasks_path)
        eligible = []
        for row in states.values():
            status = str(row.get("status") or "")
            age = stamp - float(row.get("updated_at") or row.get("created_at") or stamp)
            if status == "PENDING" or (status == "CLAIMED" and age > 60.0):
                eligible.append(row)
        pending = sorted(eligible, key=lambda row: float(row.get("created_at") or 0.0))
        if not pending:
            return None
        row = dict(pending[0])
        row.update({"status": "CLAIMED", "updated_at": stamp, "claimed_at": stamp, "claimed_by": "alice_browser"})
        _append(tasks_path, row)
    _append_receipt(row, state_dir=root)
    return row


def complete_task(task_id: str, *, status: str = "OPENED", state_dir: Path | str = DEFAULT_STATE_DIR, reason: str = "") -> dict[str, Any]:
    root = Path(state_dir)
    _, tasks_path, lock_path = _paths(root)
    with _locked(lock_path):
        states = _task_states(tasks_path)
        previous = states.get(str(task_id))
        if not previous:
            raise KeyError("Unknown stigmergicode task")
        row = dict(previous)
        row.update({"status": str(status).upper(), "updated_at": time.time()})
        if reason:
            row["reason"] = str(reason)[:240]
        _append(tasks_path, row)
    _append_receipt(row, state_dir=root)
    return row


def release_task(task_id: str, *, state_dir: Path | str = DEFAULT_STATE_DIR, reason: str = "") -> dict[str, Any]:
    """Return a claimed task to the queue when the browser is still booting."""
    return complete_task(task_id, status="PENDING", state_dir=state_dir, reason=reason)


def write_task_handoff(row: dict[str, Any], *, state_dir: Path | str = DEFAULT_STATE_DIR) -> Path:
    """Write the current owner task for the local coding surface, never public chat."""
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    path = root / "stigmergicode_active_task.json"
    payload = {
        "schema_version": "stigmergicode.handoff.v1",
        "task_id": str(row.get("task_id") or ""),
        "request_id": str(row.get("request_id") or ""),
        "task": str(row.get("task") or "") if row.get("task_present") else "",
        "task_present": bool(row.get("task_present")),
        "workspace": str(ROOT),
        "browser_target": str(row.get("browser_target") or "http://127.0.0.1:3080"),
        "acceptance": [
            "inspect the existing dirty worktree before editing",
            "make only the bounded requested change",
            "run focused tests and report the real exit status",
            "leave unrelated user changes untouched",
        ],
        "owner_authority": True,
        "created_at": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pair and queue the owner /stigmergicode command")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("pair", help="print a one-use pairing ticket")
    sub.add_parser("revoke", help="revoke the owner session")
    args = parser.parse_args()
    if args.action == "pair":
        print(issue_pairing_ticket())
    else:
        revoke()
        print("stigmergicode owner session revoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
