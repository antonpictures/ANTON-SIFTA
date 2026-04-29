#!/usr/bin/env python3
"""
swarm_effector_runtime.py — Safe effector execution law (filesystem v1)
══════════════════════════════════════════════════════════════════════

Lifecycle (GoEX-aligned): PROPOSE → SANDBOX → PREVIEW → COMMIT / UNDO → RECEIPT → REPLAY

- All world touches stay under ``root`` (path traversal rejected).
- Filesystem only in v1 — no shell, WhatsApp, or raw network.
- Append-only JSONL receipts with deterministic integrity hash per row.
- COMMIT / UNDO rows may embed ``content_b64`` / ``prior_b64`` (bounded size)
  so ``replay_from_ledger`` can reconstruct state without extra stores.

See: Documents/IDE_BOOT_COVENANT.md §6–§7.2 (tool truth, effector ledger).
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

SCHEMA_V1 = "SIFTA_EFFECTOR_RECEIPT_V1"
KIND_FS_WRITE = "fs_write"
PHASE_COMMIT = "COMMIT"
PHASE_UNDO = "UNDO"
PHASE_BROKEN = "BROKEN"
_MAX_B64_PAYLOAD = 65_536  # bytes before base64; keeps JSONL bounded for v1
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


def _safe_rel_path(root: Path, rel: str) -> Path:
    rel = (rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise ValueError("empty_rel_path")
    if ".." in rel.split("/"):
        raise ValueError("path_escape")
    target = (root / rel).resolve()
    root_r = root.resolve()
    if target != root_r and root_r not in target.parents:
        raise ValueError("path_escape")
    return target


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64_decode(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"), validate=True)


@dataclass
class ProposedAction:
    action_id: str
    kind: str
    rel_path: str
    content: str
    mode: str
    caller_id: str


class EffectorRuntime:
    """Filesystem-bound effector: propose → commit → undo → receipt → replay."""

    def __init__(
        self,
        root: Path,
        *,
        receipt_path: Path,
        undo_dir: Path,
        registration_trace_path: Optional[Path] = None,
        default_caller_id: Optional[str] = None,
        require_registered_caller: bool = True,
    ) -> None:
        self.root = root.resolve()
        self.receipt_path = receipt_path
        self.undo_dir = undo_dir
        self.registration_trace_path = registration_trace_path or _DEFAULT_REGISTRATION_TRACE
        self.default_caller_id = default_caller_id
        self.require_registered_caller = require_registered_caller
        self._pending: Dict[str, ProposedAction] = {}
        self.root.mkdir(parents=True, exist_ok=True)
        self.undo_dir.mkdir(parents=True, exist_ok=True)
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
                if not verify_receipt_row(row) or row.get("kind") != KIND_FS_WRITE:
                    continue
                aid = str(row.get("action_id") or "")
                if not aid:
                    continue
                if row.get("phase") == PHASE_COMMIT and row.get("ok") is True:
                    committed.add(aid)
                elif row.get("phase") == PHASE_UNDO and row.get("ok") is True:
                    committed.discard(aid)
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

    def _validate_caller_id(self, caller_id: Optional[str]) -> str:
        caller_id = str(caller_id or "").strip()
        if caller_id.lower() in _ANONYMOUS_CALLERS:
            raise ValueError("anonymous_caller_refused")
        if self.require_registered_caller and caller_id not in self._registered_caller_tokens():
            raise ValueError("unregistered_caller_refused")
        return caller_id

    def _resolve_caller_id(self, action: Dict[str, Any]) -> str:
        return self._validate_caller_id(action.get("caller_id") or self.default_caller_id)

    def _resolve_method_caller_id(self, caller_id: Optional[str]) -> str:
        return self._validate_caller_id(caller_id or self.default_caller_id)

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
                row["truth_note"] = f"{phase} recorded by deterministic filesystem effector runtime."
            else:
                row["truth_note"] = f"{phase} recorded failure before or during deterministic filesystem effector runtime."
        row["integrity"] = receipt_integrity(row)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(self.receipt_path, json.dumps(row, separators=(",", ":")) + "\n")
        return row

    def propose(self, action: Dict[str, Any]) -> ProposedAction:
        caller_id = self._resolve_caller_id(action)
        if action.get("kind") != KIND_FS_WRITE:
            raise ValueError(f"unsupported_kind:{action.get('kind')}")
        rel = str(action.get("rel_path", ""))
        _safe_rel_path(self.root, rel)
        mode = str(action.get("mode", "create"))
        if mode not in ("create", "replace"):
            raise ValueError("invalid_mode")
        content = "" if action.get("content") is None else str(action.get("content"))
        aid = str(action.get("action_id") or uuid.uuid4())
        if aid in self._committed_ids:
            raise ValueError("action_id_already_committed")
        p = ProposedAction(
            action_id=aid,
            kind=KIND_FS_WRITE,
            rel_path=rel,
            content=content,
            mode=mode,
            caller_id=caller_id,
        )
        self._pending[aid] = p
        return p

    def sandbox(self, action_id: str) -> Dict[str, Any]:
        p = self._pending.get(action_id)
        if not p:
            return {"ok": False, "reason": "unknown_action_id"}
        try:
            path = _safe_rel_path(self.root, p.rel_path)
        except ValueError:
            return {"ok": False, "reason": "path_escape"}
        exists = path.is_file()
        if p.mode == "create" and exists:
            return {"ok": False, "reason": "create_conflict_exists"}
        if p.mode == "replace" and not exists:
            return {"ok": False, "reason": "replace_missing_file"}
        return {"ok": True, "resolved": str(path.relative_to(self.root))}

    def preview(self, action_id: str) -> str:
        p = self._pending.get(action_id)
        if not p:
            raise KeyError("unknown_action_id")
        n = len(p.content.encode("utf-8"))
        return f"{p.kind} {p.mode} {p.rel_path!r} ({n} bytes)"

    def commit(self, action_id: str) -> Dict[str, Any]:
        if action_id in self._committed_ids:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "ts": time.time(),
                    "ok": False,
                    "error": "double_commit",
                    "caller_id": self._caller_for_action(action_id),
                    "status": "rejected",
                    "truth_note": "Rejected duplicate COMMIT for an action already committed in this runtime or receipt ledger.",
                }
            )
            return {"ok": False, "error": "double_commit", "action_id": action_id}

        p = self._pending.get(action_id)
        if not p:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "ts": time.time(),
                    "ok": False,
                    "error": "unknown_or_expired_action",
                    "caller_id": self._caller_for_action(action_id),
                    "status": "rejected",
                    "truth_note": "Rejected COMMIT because no pending proposed action exists for this action_id.",
                }
            )
            return {"ok": False, "error": "unknown_or_expired_action", "action_id": action_id}

        try:
            path = _safe_rel_path(self.root, p.rel_path)
        except ValueError as e:
            del self._pending[action_id]
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "rel_path": p.rel_path,
                    "ts": time.time(),
                    "ok": False,
                    "error": str(e),
                    "caller_id": p.caller_id,
                    "status": "rejected",
                    "truth_note": "Rejected COMMIT because the target path escaped the effector root.",
                }
            )
            return {"ok": False, "error": str(e), "action_id": action_id}

        sb = self.sandbox(action_id)
        if not sb.get("ok"):
            err = sb.get("reason", "sandbox_failed")
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "rel_path": p.rel_path,
                    "mode": p.mode,
                    "ts": time.time(),
                    "ok": False,
                    "error": err,
                    "caller_id": p.caller_id,
                    "status": "rejected",
                    "truth_note": f"Rejected COMMIT in sandbox before filesystem mutation: {err}.",
                }
            )
            return {"ok": False, "error": err, "action_id": action_id}

        raw = p.content.encode("utf-8")
        if len(raw) > _MAX_B64_PAYLOAD:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "rel_path": p.rel_path,
                    "ts": time.time(),
                    "ok": False,
                    "error": "payload_too_large_for_receipt_v1",
                    "caller_id": p.caller_id,
                    "status": "rejected",
                    "truth_note": "Rejected COMMIT because v1 receipt would exceed bounded payload size.",
                }
            )
            return {"ok": False, "error": "payload_too_large_for_receipt_v1", "action_id": action_id}

        prior_exists = path.is_file()
        prior_bytes = path.read_bytes() if prior_exists else b""
        meta_path = self.undo_dir / f"{action_id}.undo.json"
        prior_path = self.undo_dir / f"{action_id}.prior.bin"

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        except OSError as e:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "rel_path": p.rel_path,
                    "ts": time.time(),
                    "ok": False,
                    "error": f"os_error:{e}",
                    "caller_id": p.caller_id,
                    "status": "error",
                    "truth_note": "Filesystem mutation failed with an OS error; BROKEN receipt records the failure.",
                }
            )
            return {"ok": False, "error": str(e), "action_id": action_id}

        meta = {"rel_path": p.rel_path, "created": not prior_exists}
        prior_path.write_bytes(prior_bytes)
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        del self._pending[action_id]
        self._committed_ids.add(action_id)

        self._append_receipt(
            {
                "phase": PHASE_COMMIT,
                "action_id": action_id,
                "kind": KIND_FS_WRITE,
                "rel_path": p.rel_path,
                "mode": p.mode,
                "ts": time.time(),
                "ok": True,
                "caller_id": p.caller_id,
                "status": "committed",
                "truth_note": "Filesystem write committed after registered-caller validation and sandbox check.",
                "content_b64": _b64(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        return {"ok": True, "action_id": action_id, "path": str(path)}

    def undo(self, action_id: str, *, caller_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            undo_caller_id = self._resolve_method_caller_id(caller_id)
        except ValueError as e:
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "ts": time.time(),
                    "ok": False,
                    "error": str(e),
                    "caller_id": caller_id or self.default_caller_id,
                    "status": "rejected",
                    "truth_note": "Rejected UNDO because the calling agent is not present in the registration trace.",
                }
            )
            return {"ok": False, "error": str(e), "action_id": action_id}

        meta_path = self.undo_dir / f"{action_id}.undo.json"
        prior_path = self.undo_dir / f"{action_id}.prior.bin"
        if not meta_path.is_file() or not prior_path.is_file():
            self._append_receipt(
                {
                    "phase": PHASE_BROKEN,
                    "action_id": action_id,
                    "kind": KIND_FS_WRITE,
                    "ts": time.time(),
                    "ok": False,
                    "error": "no_undo_snapshot",
                    "caller_id": self._caller_for_action(action_id),
                    "status": "rejected",
                    "truth_note": "Rejected UNDO because no local undo snapshot exists for this action_id.",
                }
            )
            return {"ok": False, "error": "no_undo_snapshot", "action_id": action_id}

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rel_path = str(meta.get("rel_path", ""))
        created = bool(meta.get("created"))
        path = _safe_rel_path(self.root, rel_path)
        prior_bytes = prior_path.read_bytes()

        if created:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(prior_bytes)

        self._committed_ids.discard(action_id)
        meta_path.unlink(missing_ok=True)
        prior_path.unlink(missing_ok=True)

        undo_row: Dict[str, Any] = {
            "phase": PHASE_UNDO,
            "action_id": action_id,
            "kind": KIND_FS_WRITE,
            "rel_path": rel_path,
            "ts": time.time(),
            "ok": True,
            "caller_id": undo_caller_id,
            "original_caller_id": self._caller_for_action(action_id),
            "status": "undone",
            "truth_note": "Filesystem write undone from deterministic undo snapshot.",
            "restored_created": created,
        }
        if not created:
            undo_row["prior_b64"] = _b64(prior_bytes)
        self._append_receipt(undo_row)
        return {"ok": True, "action_id": action_id}

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


def replay_from_ledger(root: Path, receipt_path: Path) -> Dict[str, Any]:
    """
    Apply COMMIT / UNDO rows in file order; skip rows with bad integrity.

    Requires COMMIT rows to carry ``content_b64`` (v1 runtime always sets it
    for payloads ≤ ``_MAX_B64_PAYLOAD``).
    """
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    skipped: List[str] = []
    warnings: List[str] = []

    if not receipt_path.is_file():
        return {"ok": True, "skipped": skipped, "warnings": warnings}

    for line in receipt_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped.append("json_error")
            continue
        if not verify_receipt_row(row):
            skipped.append("tampered")
            warnings.append("integrity_fail")
            continue
        if row.get("kind") != KIND_FS_WRITE:
            continue
        phase = row.get("phase")
        rel_path = str(row.get("rel_path", ""))
        if not rel_path:
            continue
        try:
            path = _safe_rel_path(root, rel_path)
        except ValueError:
            skipped.append("path_escape")
            continue

        if phase == PHASE_COMMIT and row.get("ok") is True:
            b64 = row.get("content_b64")
            if not b64:
                skipped.append("no_content_b64")
                continue
            try:
                data = _b64_decode(str(b64))
            except Exception:
                skipped.append("b64_fail")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        elif phase == PHASE_UNDO and row.get("ok") is True:
            created = row.get("restored_created")
            if created is True:
                if path.exists():
                    path.unlink()
            else:
                pb = row.get("prior_b64")
                if not pb:
                    skipped.append("undo_missing_prior_b64")
                    continue
                try:
                    data = _b64_decode(str(pb))
                except Exception:
                    skipped.append("undo_b64_fail")
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

    return {"ok": True, "skipped": skipped, "warnings": warnings}
