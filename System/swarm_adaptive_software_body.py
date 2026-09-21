"""D3H-1 — a body that really moves, and a witness that really looks.

The D3f step path was a real invocation path with no real body behind it. Nothing
in Alice's ordinary startup ever called ``register_adaptive_body``, so in production
every step would have been refused for want of an adapter, and the only "bodies" in
existence were test doubles. A path that only a test can walk is not an organ.

This module is one honest software body plus its witness:

* :class:`SoftwareFileAdapter` performs **exactly one reversible effect** — it writes
  bytes to a file inside a workspace this body owns — and records what it did, on
  disk, before it says anything about it. It never claims a verification. It reports
  its own delivery, no more.
* :class:`SoftwareFileVerifier` is a **separately observing** witness. It reads the
  persisted record and then hashes the bytes *currently on disk* by itself. It never
  reads the adapter's word for what happened. If the file changed after the effect,
  the witness refuses — which is the entire reason it is a separate organ.
* :func:`install_software_body` is the real registration path, called from Alice's
  boot (``System/swarm_boot.py``) through the canonical ``System.`` import.

Three laws this file is written to keep:

1. **An effect is real or it is absent.** The bytes reach the filesystem through an
   atomic replace inside a path proven to be inside the workspace. A path that tries
   to escape the workspace is refused rather than followed.
2. **Status is persisted, so a restart reconciles instead of guessing.** Records live
   in a JSON file under ``state_dir``; every read goes to disk. A second process that
   never saw the first one's memory can still say what the body did — and if it cannot
   find a record it says ``unknown``, never ``succeeded``.
3. **A repeat is not a second effect.** An action id that is submitted again with the
   same proposal is answered from the record without touching the file; the same id
   with *different* content is refused as ``ID_CONFLICT``.

Honest limits, named rather than hidden: this body owns no control channel yet, so
``cancel`` on an already-applied action reports that it cannot un-happen and points at
``recover``; bounded adapter I/O, reachable owner stop and concurrent-writer
arbitration are D3H-3's jobs and are not claimed here. ``recover`` reverses the
postcondition *this body* created, not arbitrary side effects of a larger plan.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

try:  # package import (normal, and what boot uses)
    from System.swarm_adaptive_step_binding import (
        lookup_adaptive_body,
        register_adaptive_body,
        register_adaptive_verifier,
    )
except ImportError:  # pragma: no cover - bare System/ on sys.path
    from swarm_adaptive_step_binding import (  # type: ignore
        lookup_adaptive_body,
        register_adaptive_body,
        register_adaptive_verifier,
    )

try:  # the frozen contracts: used to prove the interface, not to re-declare it
    from System.swarm_adaptive_contracts import ADAPTER_METHODS, adapter_report, assert_adapter
except ImportError:  # pragma: no cover - bare System/ on sys.path
    from swarm_adaptive_contracts import (  # type: ignore
        ADAPTER_METHODS,
        adapter_report,
        assert_adapter,
    )

__all__ = [
    "ADAPTER_ID",
    "CAPABILITY_REVISION",
    "POSTCONDITION",
    "STATE_FILENAME",
    "VERIFIER_ID",
    "SoftwareFileAdapter",
    "SoftwareFileVerifier",
    "SoftwareBodyError",
    "capability_declaration",
    "capability_revision",
    "install_software_body",
    "registration_report",
    "require_software_body",
]

LEDGER_SOURCE = "swarm_adaptive_software_body"

ADAPTER_ID = "software_file_body"
VERIFIER_ID = "software_file_verifier.v1"

# The one postcondition this body can witness. A verifier that accepted any string
# would be a rubber stamp, so the name is fixed here and checked by the witness.
POSTCONDITION = "file_bytes_at_path"

STATE_FILENAME = "adaptive_software_body.json"
PREIMAGE_DIRNAME = "adaptive_software_body_preimages"
STATE_SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = _REPO_ROOT / ".sifta_state"
_DEFAULT_WORKSPACE = _DEFAULT_STATE_DIR / "adaptive_software_workspace"


def capability_declaration() -> dict[str, Any]:
    """What this body claims it can do, in a form that can be hashed.

    Kept separate from the hash so the claim is readable: an operator can see the
    capability and check the revision that names it.
    """
    return {
        "adapter_id": ADAPTER_ID,
        "verifier_id": VERIFIER_ID,
        "effects": ["write_file"],
        "postconditions": [POSTCONDITION],
        "reversible": True,
        "physical": False,
        "workspace_scoped": True,
        "methods": sorted(ADAPTER_METHODS),
    }


def capability_revision() -> str:
    """A content-addressed revision of the declaration above.

    The frozen ``ActionProposal`` requires ``capability_revision`` to be a real
    SHA256 -- a human label is refused by the contract. Content addressing is also the
    property a stale revision needs: if this body's declared capability changes, the
    revision changes with it, and an action that quoted the old one can be recognised
    as quoting a capability that no longer exists.
    """
    canonical = json.dumps(capability_declaration(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


CAPABILITY_REVISION = capability_revision()


class SoftwareBodyError(RuntimeError):
    """A refusal this body can explain, carrying a stable ``code``."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = str(code)
        self.detail = str(detail)


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _observation_id(sha: str) -> str:
    """An observation id that encodes its own evidence and can be re-checked.

    The id is not a name for a memory: it carries the digest of the bytes that were
    actually read, so :meth:`SoftwareFileAdapter.verify_observation` can re-hash the
    file later and say whether the id still describes reality.
    """
    return "obs:" + str(sha).removeprefix("sha256:")[:16]


class SoftwareFileAdapter:
    """A real, reversible software body: one file, written once, recorded first.

    The adapter implements the frozen adapter interface
    (``probe/observe/submit/status/cancel/recover``). It is not physical, so it does
    not claim ``stop``.
    """

    def __init__(
        self,
        *,
        workspace: Optional[Path | str] = None,
        state_dir: Optional[Path | str] = None,
        adapter_id: str = ADAPTER_ID,
        capability_revision: str = CAPABILITY_REVISION,
    ) -> None:
        self.workspace = Path(workspace) if workspace is not None else _DEFAULT_WORKSPACE
        self.state_dir = Path(state_dir) if state_dir is not None else _DEFAULT_STATE_DIR
        self.adapter_id = str(adapter_id)
        self.capability_revision = str(capability_revision)

    # --- persistence -------------------------------------------------------

    @property
    def record_path(self) -> Path:
        return self.state_dir / STATE_FILENAME

    @property
    def preimage_dir(self) -> Path:
        return self.state_dir / PREIMAGE_DIRNAME

    def _load(self) -> dict[str, Any]:
        """Read the record file from disk. Never a cached copy: a restart must see truth."""
        try:
            raw = self.record_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"schema_version": STATE_SCHEMA_VERSION, "records": {}}
        except OSError:
            return {"schema_version": STATE_SCHEMA_VERSION, "records": {}}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # An unreadable record file is not an empty history: it is an unknown one.
            return {"schema_version": STATE_SCHEMA_VERSION, "records": {}, "unreadable": True}
        if not isinstance(data, dict):
            return {"schema_version": STATE_SCHEMA_VERSION, "records": {}, "unreadable": True}
        data.setdefault("records", {})
        if not isinstance(data["records"], dict):
            data["records"] = {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        """Atomically replace the record file. A torn record file must never exist."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        data = dict(data)
        data["schema_version"] = STATE_SCHEMA_VERSION
        data["adapter_id"] = self.adapter_id
        data["capability_revision"] = self.capability_revision
        data["updated_at_utc"] = _now_utc()
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
        fd, tmp_name = tempfile.mkstemp(dir=str(self.state_dir), prefix=".adaptive_body_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.record_path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _record(self, action_id: str) -> Optional[dict[str, Any]]:
        entry = self._load().get("records", {}).get(str(action_id))
        return dict(entry) if isinstance(entry, dict) else None

    # --- workspace discipline ---------------------------------------------

    def _resolve_target(self, proposal: Mapping[str, Any]) -> Path:
        """Resolve the target inside the workspace, or refuse to move at all."""
        args = proposal.get("args") or {}
        raw = str(args.get("path") or f"{proposal.get('action_id')}.txt")
        candidate = Path(raw)
        target = (candidate if candidate.is_absolute() else self.workspace / candidate).resolve()
        root = self.workspace.resolve()
        if target != root and root not in target.parents:
            raise SoftwareBodyError(
                "PATH_OUTSIDE_WORKSPACE",
                f"{raw!r} resolves to {target}, which is outside this body's workspace {root}",
            )
        return target

    @staticmethod
    def _content_for(proposal: Mapping[str, Any]) -> str:
        args = proposal.get("args") or {}
        if "content" in args:
            return str(args["content"])
        if "text" in args:
            return str(args["text"])
        return ""

    @staticmethod
    def _proposal_hash(proposal: Mapping[str, Any]) -> str:
        canonical = json.dumps(dict(proposal), sort_keys=True, separators=(",", ":"), default=str)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # --- the frozen adapter interface --------------------------------------

    def probe(self) -> dict[str, Any]:
        """Report readiness from a live look at the filesystem, not from hope."""
        probe_dir = self.workspace
        while not probe_dir.exists() and probe_dir != probe_dir.parent:
            probe_dir = probe_dir.parent
        writable = os.access(probe_dir, os.W_OK) if probe_dir.exists() else False
        return {
            "adapter_id": self.adapter_id,
            "ready": bool(writable),
            "capability_revision": self.capability_revision,
            "workspace": str(self.workspace),
            "workspace_writable": bool(writable),
            "reversible": True,
            "at_utc": _now_utc(),
        }

    def observe(self, cursor: Optional[str] = None) -> list[dict[str, Any]]:
        """Report observations of the bytes as they are *now*, re-hashed on the spot."""
        records = self._load().get("records", {})
        wanted = [str(cursor)] if cursor else sorted(records)
        out: list[dict[str, Any]] = []
        for action_id in wanted:
            record = records.get(action_id)
            if not isinstance(record, dict):
                continue
            target = Path(str(record.get("absolute_path") or ""))
            try:
                data = target.read_bytes()
            except OSError:
                continue
            sha = _sha256_bytes(data)
            out.append(
                {
                    "observation_id": _observation_id(sha),
                    "action_id": action_id,
                    "path": str(record.get("path") or ""),
                    "sha256": sha,
                    "size": len(data),
                    "at_utc": _now_utc(),
                }
            )
        return out

    def submit(self, proposal: Mapping[str, Any]) -> dict[str, Any]:
        """Apply the effect once, or answer from the record if it already happened.

        Returns the receipt the loop expects: ``{"receipt_id", "status", "at_utc"}``.
        The status is ``accepted`` because that is what this call is — the acceptance
        of a command whose delivery :meth:`status` then reports from disk.
        """
        proposal = dict(proposal or {})
        action_id = str(proposal.get("action_id") or "")
        if not action_id:
            raise SoftwareBodyError("INVALID_ARGUMENT", "a proposal without an action_id cannot be applied")
        proposal_hash = self._proposal_hash(proposal)

        existing = self._record(action_id)
        if existing is not None:
            if str(existing.get("proposal_hash")) != proposal_hash:
                raise SoftwareBodyError(
                    "ID_CONFLICT",
                    f"action {action_id!r} was already applied with different content "
                    f"({existing.get('proposal_hash')} != {proposal_hash}); a renamed action is a "
                    "new attempt, a reused id with new content is a conflict",
                )
            # Same id, same content: the effect is already on disk. Do not repeat it.
            return {
                "receipt_id": str(existing.get("receipt_id") or ""),
                "status": "accepted",
                "at_utc": _now_utc(),
                "repeated": True,
                "detail": "already applied; the recorded effect was not repeated",
            }

        target = self._resolve_target(proposal)
        data = self._content_for(proposal).encode("utf-8")

        preimage_existed = target.exists()
        preimage_path: Optional[Path] = None
        if preimage_existed:
            try:
                preimage_bytes = target.read_bytes()
            except OSError as exc:
                raise SoftwareBodyError(
                    "PREIMAGE_UNREADABLE",
                    f"cannot read {target} before replacing it ({exc}); refusing to move without a way back",
                ) from exc
            self.preimage_dir.mkdir(parents=True, exist_ok=True)
            preimage_path = self.preimage_dir / f"{action_id}.bin"
            preimage_path.write_bytes(preimage_bytes)

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".adaptive_fx_", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        sha = _sha256_bytes(data)
        record = {
            "action_id": action_id,
            "goal_id": str(proposal.get("goal_id") or ""),
            "proposal_hash": proposal_hash,
            "path": str(target.relative_to(self.workspace.resolve())) if target != self.workspace.resolve() else target.name,
            "absolute_path": str(target),
            "sha256": sha,
            "size": len(data),
            "state": "succeeded",
            "receipt_id": str(uuid.uuid4()),
            "applied_at_utc": _now_utc(),
            "postcondition": POSTCONDITION,
            "observation_ids": [_observation_id(sha)],
            "preimage_existed": bool(preimage_existed),
            "preimage_path": str(preimage_path) if preimage_path is not None else "",
            "reversed": False,
            "capability_revision": self.capability_revision,
        }
        data_root = self._load()
        data_root.setdefault("records", {})[action_id] = record
        self._save(data_root)
        return {
            "receipt_id": record["receipt_id"],
            "status": "accepted",
            "at_utc": _now_utc(),
            "observation_ids": list(record["observation_ids"]),
        }

    def status(self, action_id: str) -> dict[str, Any]:
        """Report what is recorded, from disk. No record is ``unknown``, never ``succeeded``."""
        record = self._record(str(action_id))
        if record is None:
            return {
                "status": "unknown",
                "at_utc": _now_utc(),
                "detail": f"this body has no record of action {action_id!r}",
            }
        return {
            "status": str(record.get("state") or "unknown"),
            "at_utc": _now_utc(),
            "applied_at_utc": record.get("applied_at_utc"),
            "path": record.get("path"),
            "sha256": record.get("sha256"),
            "size": record.get("size"),
            "receipt_id": record.get("receipt_id"),
            "observation_ids": list(record.get("observation_ids") or []),
            "reversed": bool(record.get("reversed")),
        }

    def cancel(self, action_id: str) -> bool:
        """A software effect that already happened cannot be cancelled — say so.

        Reversal is :meth:`recover`. Returning ``True`` here would claim a control this
        body does not have.
        """
        record = self._record(str(action_id))
        return record is None

    def recover(self, action_id: str) -> dict[str, Any]:
        """Reverse the postcondition this body created, and re-read the result."""
        action_id = str(action_id)
        record = self._record(action_id)
        if record is None:
            return {
                "status": "unknown",
                "reversed": False,
                "at_utc": _now_utc(),
                "detail": f"nothing to reverse: no record of action {action_id!r}",
            }
        if record.get("reversed"):
            return {
                "status": "succeeded",
                "reversed": True,
                "at_utc": _now_utc(),
                "detail": "already reversed; the reversal was not repeated",
            }
        target = Path(str(record.get("absolute_path") or ""))
        preimage_existed = bool(record.get("preimage_existed"))
        preimage_path = Path(str(record.get("preimage_path") or "")) if record.get("preimage_path") else None
        if preimage_existed:
            if preimage_path is None or not preimage_path.exists():
                return {
                    "status": "unknown",
                    "reversed": False,
                    "at_utc": _now_utc(),
                    "detail": f"the pre-image for {action_id!r} is gone; the previous bytes cannot be restored",
                }
            restored = preimage_path.read_bytes()
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".adaptive_rv_", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(restored)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, target)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                return {
                    "status": "unknown",
                    "reversed": False,
                    "at_utc": _now_utc(),
                    "detail": f"could not remove {target}: {exc}",
                }

        try:
            observed = target.read_bytes()
            sha_now: Optional[str] = _sha256_bytes(observed)
        except OSError:
            sha_now = None

        data_root = self._load()
        record = dict(data_root.get("records", {}).get(action_id) or record)
        record.update(
            state="cancelled",
            reversed=True,
            reversed_at_utc=_now_utc(),
            sha256_after_reverse=sha_now,
            observation_ids=[],
        )
        data_root.setdefault("records", {})[action_id] = record
        self._save(data_root)
        return {
            "status": "succeeded",
            "reversed": True,
            "at_utc": _now_utc(),
            "path": str(record.get("path") or ""),
            "sha256_now": sha_now,
            "detail": "pre-image restored" if preimage_existed else "created file removed",
        }

    # --- reconciliation helpers (used by tests, operators and the witness) ---

    def action_identity(self, action_id: str) -> dict[str, Any]:
        """Everything this body knows about one action, straight from disk."""
        record = self._record(str(action_id))
        if record is None:
            return {"action_id": str(action_id), "known": False, "record": None}
        return {
            "action_id": str(action_id),
            "known": True,
            "proposal_hash": record.get("proposal_hash"),
            "capability_revision": record.get("capability_revision"),
            "receipt_id": record.get("receipt_id"),
            "record": record,
        }

    def known_actions(self) -> tuple:
        return tuple(sorted(self._load().get("records", {})))

    def verify_observation(self, observation_id: str) -> dict[str, Any]:
        """Re-hash reality and say whether an observation id still describes it."""
        wanted = str(observation_id)
        for row in self.observe():
            if row["observation_id"] == wanted:
                return {"valid": True, "observation_id": wanted, "sha256": row["sha256"], "path": row["path"]}
        return {
            "valid": False,
            "observation_id": wanted,
            "detail": "no bytes currently on disk hash to this observation id",
        }

    @classmethod
    def from_state(
        cls,
        *,
        workspace: Optional[Path | str] = None,
        state_dir: Optional[Path | str] = None,
        **kwargs: Any,
    ) -> "SoftwareFileAdapter":
        """Reattach to a body that ran in a previous process, by reading its records."""
        return cls(workspace=workspace, state_dir=state_dir, **kwargs)


class SoftwareFileVerifier:
    """A witness that reads the record and then hashes the bytes for itself.

    It shares no memory with the adapter: given only the state directory and the
    workspace it can confirm or refuse. It answers with ``observation_ids`` minted
    from the bytes it read, so a later check can re-hash them.
    """

    verifier_id = VERIFIER_ID

    def __init__(
        self,
        *,
        workspace: Optional[Path | str] = None,
        state_dir: Optional[Path | str] = None,
        adapter_id: str = ADAPTER_ID,
    ) -> None:
        self.workspace = Path(workspace) if workspace is not None else _DEFAULT_WORKSPACE
        self.state_dir = Path(state_dir) if state_dir is not None else _DEFAULT_STATE_DIR
        self.adapter_id = str(adapter_id)

    def _records(self) -> dict[str, Any]:
        path = self.state_dir / STATE_FILENAME
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        records = data.get("records") if isinstance(data, dict) else None
        return records if isinstance(records, dict) else {}

    def verify(self, request: Mapping[str, Any]) -> dict[str, Any]:
        action_id = str((request or {}).get("action_id") or "")
        predicted = str((request or {}).get("predicted_postcondition") or "")
        refusal = {
            "verified": False,
            "method": "independent_byte_read",
            "observation_ids": [],
            "verifier": self.verifier_id,
        }
        if predicted and predicted != POSTCONDITION:
            return {
                **refusal,
                "detail": (
                    f"this body witnesses {POSTCONDITION!r}, not {predicted!r}; "
                    "a postcondition no organ here can observe is not confirmed"
                ),
            }
        record = self._records().get(action_id)
        if not isinstance(record, dict):
            return {**refusal, "detail": f"no record for action {action_id!r}; nothing was observed"}
        if record.get("reversed"):
            return {**refusal, "detail": f"action {action_id!r} was reversed; the postcondition is gone"}
        target = Path(str(record.get("absolute_path") or ""))
        try:
            observed = target.read_bytes()
        except OSError as exc:
            return {**refusal, "detail": f"the bytes at {target} could not be read: {exc}"}
        observed_sha = _sha256_bytes(observed)
        expected_sha = str(record.get("sha256") or "")
        if observed_sha != expected_sha:
            return {
                **refusal,
                "detail": (
                    f"the bytes on disk hash to {observed_sha}, but the action claimed "
                    f"{expected_sha}; the body's claim is not confirmed"
                ),
            }
        return {
            "verified": True,
            "method": "independent_byte_read",
            "detail": f"read {len(observed)} byte(s) at {record.get('path')} and hashed them: {observed_sha}",
            "observation_ids": [_observation_id(observed_sha)],
            "verifier": self.verifier_id,
        }


def install_software_body(
    *,
    workspace: Optional[Path | str] = None,
    state_dir: Optional[Path | str] = None,
    adapter_id: str = ADAPTER_ID,
    verifier_id: str = VERIFIER_ID,
    capability_revision: str = CAPABILITY_REVISION,
) -> dict[str, Any]:
    """Register this body and its witness with the runtime. Called from boot.

    Never raises: a boot that dies because a body is missing would take the whole
    organism down over one absent arm. The returned report says plainly whether the
    registration happened and, if it did not, exactly why.
    """
    try:
        already = lookup_adaptive_body(adapter_id) is not None
        adapter = SoftwareFileAdapter(
            workspace=workspace,
            state_dir=state_dir,
            adapter_id=adapter_id,
            capability_revision=capability_revision,
        )
        # Prove the interface against the frozen contract before claiming to be a body.
        assert_adapter(adapter)
        verifier = SoftwareFileVerifier(
            workspace=workspace, state_dir=state_dir, adapter_id=adapter_id
        )
        register_adaptive_body(adapter_id, adapter, capability_revision=capability_revision)
        register_adaptive_verifier(verifier_id, verifier)
        return {
            "registered": True,
            "already_registered": bool(already),
            "adapter_id": str(adapter_id),
            "verifier_id": str(verifier_id),
            "capability_revision": str(capability_revision),
            "workspace": str(adapter.workspace),
            "state_dir": str(adapter.state_dir),
            "required_methods": adapter_report(adapter)["present"],
            "reason_code": None,
            "detail": "",
        }
    except Exception as exc:  # never fracture the heartbeat for an absent arm
        return {
            "registered": False,
            "already_registered": False,
            "adapter_id": str(adapter_id),
            "verifier_id": str(verifier_id),
            "capability_revision": str(capability_revision),
            "workspace": str(workspace) if workspace is not None else str(_DEFAULT_WORKSPACE),
            "state_dir": str(state_dir) if state_dir is not None else str(_DEFAULT_STATE_DIR),
            "reason_code": str(getattr(exc, "code", None) or "REGISTRATION_FAILED"),
            "detail": f"{type(exc).__name__}: {exc}",
        }


def require_software_body(adapter_id: str = ADAPTER_ID) -> dict[str, Any]:
    """Say precisely whether a body is registered, and what to do when it is not."""
    entry = lookup_adaptive_body(adapter_id)
    if entry is None:
        return {
            "registered": False,
            "adapter_id": str(adapter_id),
            "reason_code": "ADAPTER_NOT_REGISTERED",
            "adapter": None,
            "detail": (
                f"no organ has registered adapter {adapter_id!r}, so the adaptive step path has "
                "nothing to move. Register it with "
                "`from System.swarm_adaptive_software_body import install_software_body; "
                "install_software_body()` — Alice's boot (System/swarm_boot.py) does this at startup."
            ),
        }
    return {
        "registered": True,
        "adapter_id": str(adapter_id),
        "reason_code": None,
        "adapter": entry.get("adapter"),
        "capability_revision": entry.get("capability_revision"),
        "detail": "",
    }


def registration_report() -> dict[str, Any]:
    """The state of this arm, for the body census and for anyone asking what is wired."""
    report = require_software_body()
    adapter = report.get("adapter")
    return {
        "adapter_id": ADAPTER_ID,
        "verifier_id": VERIFIER_ID,
        "registered": report["registered"],
        "reason_code": report["reason_code"],
        "detail": report["detail"],
        "capability_revision": report.get("capability_revision"),
        "workspace": str(getattr(adapter, "workspace", _DEFAULT_WORKSPACE)),
        "state_dir": str(getattr(adapter, "state_dir", _DEFAULT_STATE_DIR)),
        "probe": adapter.probe() if adapter is not None else None,
        "known_actions": list(adapter.known_actions()) if adapter is not None else [],
    }
