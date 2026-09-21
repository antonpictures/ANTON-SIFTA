"""Durable action journal (D3b) -- append-only outbox with write-before-submit.

The loop's weakest moment is the instant between "I am about to move" and "I know
whether it moved". If the body dies there, a naive design either forgets the
action entirely (and the rover is somewhere unknown) or re-sends it (and the
rover moves twice). This module removes the first failure and makes the second
one impossible by construction:

* **Write before submit.** The intent row is fsynced to disk *before* the
  adapter is asked to act. There is no window in which an action exists in the
  world but not in the journal.
* **A chain, not a list.** Each row carries ``prev_hash`` and ``row_hash``, so a
  replayed journal can be checked for tampering or reordering rather than
  trusted because it parsed.
* **A torn tail is reported, never guessed.** A crash mid-append leaves a
  partial line. Replay counts it, refuses to invent a row from it, and keeps
  every complete row before it usable. Repair is explicit.
* **Attempted is not succeeded.** An intent whose submit never returned is
  ``unknown``: reconciliation territory (D3c), never a licence to resend.

Portability law: stdlib only, no Qt/AppKit, importable on a headless rover.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

try:  # package import (normal) with a direct-module fallback
    from System.swarm_adaptive_goal_loop import Clock, SystemClock
except ImportError:  # pragma: no cover - bare System/ path
    from swarm_adaptive_goal_loop import Clock, SystemClock  # type: ignore

__all__ = [
    "JOURNAL_SCHEMA_VERSION",
    "JOURNAL_FILENAME",
    "GENESIS_HASH",
    "JournalError",
    "JournalRow",
    "ReplayReport",
    "ActionJournal",
]

JOURNAL_SCHEMA_VERSION = "1.0.0"
JOURNAL_FILENAME = "adaptive_action_journal.jsonl"
GENESIS_HASH = "genesis"

# Row kinds. 'intent' is the commit point; everything else is a later observation.
KIND_INTENT = "intent"
KIND_SUBMIT = "submit"
KIND_STATUS = "status"
KIND_RESULT = "result"
KIND_VERIFICATION = "verification"
KIND_NOTE = "note"
# D3d: the one event a reader must never have to infer from a result row.
KIND_COMPLETION = "completion"
# D3e: an owner stop, and a bounded revision of a goal that did not work out.
# Both are journalled so a restart inherits the decision instead of re-deriving
# it -- a stop that only lived in memory would be re-attempted by the next boot.
KIND_STOP = "stop"
KIND_REVISION = "revision"
# Kinds are additive. A reader must ignore a kind it does not know rather than
# treat the row as malformed: the wire shape of a row never changes, only the
# vocabulary of what may appear in it.
JOURNAL_KINDS = (
    KIND_INTENT,
    KIND_SUBMIT,
    KIND_STATUS,
    KIND_RESULT,
    KIND_VERIFICATION,
    KIND_NOTE,
    KIND_COMPLETION,
    KIND_STOP,
    KIND_REVISION,
)

# States an intent can be in, from the journal's point of view alone.
SUBMIT_UNATTEMPTED = "unattempted"
SUBMIT_ATTEMPTED = "attempted"
SUBMIT_REJECTED = "rejected"
SUBMIT_ACCEPTED = "accepted"


class JournalError(RuntimeError):
    """The journal cannot be read or written safely."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JournalRow:
    """One durable row. ``row_hash`` covers every declared field plus the chain."""

    seq: int
    at_utc: str
    kind: str
    action_id: str
    goal_id: Optional[str]
    payload: dict
    prev_hash: str
    row_hash: str
    schema_version: str = JOURNAL_SCHEMA_VERSION

    def _hash_input(self) -> dict:
        return {
            "seq": self.seq,
            "at_utc": self.at_utc,
            "kind": self.kind,
            "action_id": self.action_id,
            "goal_id": self.goal_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "schema_version": self.schema_version,
        }

    def compute_hash(self) -> str:
        return _digest(self._hash_input())

    def to_dict(self) -> dict:
        out = dict(self._hash_input())
        out["row_hash"] = self.row_hash
        return out

    @classmethod
    def build(
        cls,
        *,
        seq: int,
        at_utc: str,
        kind: str,
        action_id: str,
        goal_id: Optional[str],
        payload: Mapping[str, Any],
        prev_hash: str,
    ) -> "JournalRow":
        if kind not in JOURNAL_KINDS:
            raise JournalError("UNKNOWN_KIND", f"{kind!r} is not a journal row kind")
        if not str(action_id or "").strip():
            raise JournalError("MISSING_ACTION_ID", "every journal row names the action it concerns")
        draft = cls(
            seq=int(seq),
            at_utc=str(at_utc),
            kind=str(kind),
            action_id=str(action_id),
            goal_id=None if goal_id is None else str(goal_id),
            payload=dict(payload or {}),
            prev_hash=str(prev_hash),
            row_hash="",
        )
        return cls(
            seq=draft.seq,
            at_utc=draft.at_utc,
            kind=draft.kind,
            action_id=draft.action_id,
            goal_id=draft.goal_id,
            payload=draft.payload,
            prev_hash=draft.prev_hash,
            row_hash=draft.compute_hash(),
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "JournalRow":
        required = ("seq", "at_utc", "kind", "action_id", "prev_hash", "row_hash")
        for field in required:
            if field not in raw:
                raise JournalError("MALFORMED_ROW", f"journal row is missing {field!r}")
        row = cls(
            seq=int(raw["seq"]),
            at_utc=str(raw["at_utc"]),
            kind=str(raw["kind"]),
            action_id=str(raw["action_id"]),
            goal_id=None if raw.get("goal_id") is None else str(raw["goal_id"]),
            payload=dict(raw.get("payload") or {}),
            prev_hash=str(raw["prev_hash"]),
            row_hash=str(raw["row_hash"]),
            schema_version=str(raw.get("schema_version") or JOURNAL_SCHEMA_VERSION),
        )
        if row.compute_hash() != row.row_hash:
            raise JournalError("ROW_HASH_MISMATCH", f"journal row {row.seq} does not match its own hash")
        return row


@dataclass(frozen=True)
class ReplayReport:
    """What a replay found, including what it refused to believe.

    ``torn_lines`` are a crash (an incomplete write). ``tampered_lines`` are a
    claim that contradicts its own hash. The two are never conflated: a torn tail
    may be repaired by truncation, a tampered row may not.
    """

    rows: tuple
    torn_lines: int
    chain_ok: bool
    first_bad_seq: Optional[int]
    detail: Optional[str]
    tampered_lines: int = 0

    def to_dict(self) -> dict:
        return {
            "rows": [row.to_dict() for row in self.rows],
            "torn_lines": int(self.torn_lines),
            "tampered_lines": int(self.tampered_lines),
            "chain_ok": bool(self.chain_ok),
            "first_bad_seq": self.first_bad_seq,
            "detail": self.detail,
        }


class ActionJournal:
    """Append-only, hash-chained, fsynced action outbox.

    ``state_dir`` is injected; nothing here writes outside it. The journal is
    opened lazily on first append, and its existing contents are replayed when
    the object is constructed so a restarted body sees what the dead one did.
    """

    def __init__(
        self,
        state_dir: Any,
        *,
        clock: Optional[Clock] = None,
        filename: str = JOURNAL_FILENAME,
        tolerate_chain_break: bool = False,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.clock = clock if clock is not None else SystemClock()
        self.filename = str(filename)
        self.tolerate_chain_break = bool(tolerate_chain_break)
        self._rows: list = []
        self._torn_lines = 0
        self._tampered_lines = 0
        self._chain_ok = True
        self._first_bad_seq: Optional[int] = None
        self._detail: Optional[str] = None
        self._next_seq = 1
        self._loaded = False

    # -- paths ---------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self.state_dir / self.filename

    # -- replay --------------------------------------------------------------

    def replay(self) -> ReplayReport:
        """Read every complete row; report the tail this file could not trust."""
        rows: list = []
        torn = 0
        tampered = 0
        chain_ok = True
        first_bad: Optional[int] = None
        detail: Optional[str] = None
        prev = GENESIS_HASH

        if self.path.exists():
            raw_bytes = self.path.read_bytes()
            if raw_bytes:
                complete, tail = _split_complete_lines(raw_bytes)
                # A line that never received its newline is not a promise that it
                # landed whole, so it is counted and never believed.
                if tail.strip():
                    torn += 1
                text = complete.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        torn += 1
                        continue
                    try:
                        row = JournalRow.from_dict(parsed)
                    except JournalError as exc:
                        # The row parses but contradicts its own hash: that is a
                        # lie, not a crash, and it is counted separately.
                        if exc.code == "ROW_HASH_MISMATCH":
                            tampered += 1
                            continue
                        torn += 1
                        detail = f"{exc.code}: {exc.detail}"
                        continue
                    if row.prev_hash != prev:
                        chain_ok = False
                        if first_bad is None:
                            first_bad = row.seq
                            detail = f"row {row.seq} does not chain onto seq {len(rows)}"
                    prev = row.row_hash
                    rows.append(row)

        self._rows = rows
        self._torn_lines = torn
        self._tampered_lines = tampered
        self._chain_ok = chain_ok
        self._first_bad_seq = first_bad
        self._detail = detail
        self._next_seq = (rows[-1].seq + 1) if rows else 1
        self._loaded = True

        if tampered and not self.tolerate_chain_break:
            raise JournalError(
                "ROW_TAMPERED",
                f"journal {self.path} holds {tampered} row(s) that contradict their own hash",
            )
        if not chain_ok and not self.tolerate_chain_break:
            raise JournalError(
                "CHAIN_BROKEN",
                f"journal {self.path} is not a valid chain at seq {first_bad}: {detail}",
            )
        return ReplayReport(
            rows=tuple(rows),
            torn_lines=torn,
            tampered_lines=tampered,
            chain_ok=chain_ok,
            first_bad_seq=first_bad,
            detail=detail,
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.replay()

    # -- append --------------------------------------------------------------

    def append(
        self,
        kind: str,
        action_id: str,
        *,
        goal_id: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> JournalRow:
        """Durably append one row. Returns only once the row is on disk."""
        self._ensure_loaded()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        prev = self._rows[-1].row_hash if self._rows else GENESIS_HASH
        row = JournalRow.build(
            seq=self._next_seq,
            at_utc=str(self.clock.now_utc()),
            kind=kind,
            action_id=action_id,
            goal_id=goal_id,
            payload=dict(payload or {}),
            prev_hash=prev,
        )
        line = (_canonical(row.to_dict()) + "\n").encode("utf-8")
        try:
            fd = os.open(str(self.path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        except OSError as exc:
            raise JournalError("OPEN_FAILED", f"cannot open journal {self.path}: {exc}") from exc
        try:
            written = os.write(fd, line)
            if written != len(line):
                raise JournalError(
                    "SHORT_WRITE",
                    f"journal {self.path} accepted {written} of {len(line)} bytes; row is not durable",
                )
            os.fsync(fd)
        finally:
            os.close(fd)

        self._rows.append(row)
        self._next_seq += 1
        self._torn_lines = 0
        self._detail = None
        return row

    # -- queries -------------------------------------------------------------

    @property
    def rows(self) -> tuple:
        self._ensure_loaded()
        return tuple(self._rows)

    @property
    def torn_lines(self) -> int:
        self._ensure_loaded()
        return self._torn_lines

    @property
    def tampered_lines(self) -> int:
        self._ensure_loaded()
        return self._tampered_lines

    def history(self, action_id: str) -> tuple:
        return tuple(row for row in self.rows if row.action_id == str(action_id))

    def latest(self, action_id: str, kind: Optional[str] = None) -> Optional[JournalRow]:
        for row in reversed(self.history(action_id)):
            if kind is None or row.kind == kind:
                return row
        return None

    def intents(self) -> tuple:
        return tuple(row for row in self.rows if row.kind == KIND_INTENT)

    def intent(self, action_id: str) -> Optional[JournalRow]:
        return self.latest(action_id, KIND_INTENT)

    def submit_state(self, action_id: str) -> Optional[str]:
        """How far the submit of this action got, as the journal alone knows it."""
        intent = self.intent(action_id)
        if intent is None:
            return None
        submit = self.latest(action_id, KIND_SUBMIT)
        if submit is None:
            return SUBMIT_UNATTEMPTED
        status = submit.payload.get("outcome")
        if status == "rejected":
            return SUBMIT_REJECTED
        if status == "accepted":
            return SUBMIT_ACCEPTED
        return SUBMIT_ATTEMPTED

    def in_flight(self) -> tuple:
        """Intents whose submit was attempted and whose outcome is not known.

        These are exactly the actions a restart must *reconcile*, never resend.
        """
        out = []
        for intent in self.intents():
            action_id = intent.action_id
            state = self.submit_state(action_id)
            if state in (SUBMIT_ATTEMPTED, SUBMIT_ACCEPTED):
                if self.latest(action_id, KIND_RESULT) is None:
                    out.append(intent)
        return tuple(out)

    def unattempted(self) -> tuple:
        """Intents durably recorded but never handed to an adapter."""
        return tuple(
            row
            for row in self.intents()
            if self.submit_state(row.action_id) == SUBMIT_UNATTEMPTED
        )

    def resend_forbidden(self) -> tuple:
        """Action ids that may not be submitted again without reconciliation."""
        return tuple(row.action_id for row in self.in_flight())

    # -- repair --------------------------------------------------------------

    def repair_torn_tail(self) -> int:
        """Explicitly drop an incomplete final line. Returns bytes discarded.

        Only ever truncates an *incomplete* write. A row that parses but fails
        its own hash is evidence of tampering and is never silently dropped.
        """
        if not self.path.exists():
            return 0
        if self._tampered_lines:
            raise JournalError(
                "NOT_TORN",
                f"journal {self.path} holds tampered rows; truncation would destroy evidence",
            )
        raw = self.path.read_bytes()
        complete, tail = _split_complete_lines(raw)
        if not tail and raw.endswith(b"\n"):
            return 0
        truncated = raw[: len(raw) - len(tail)]
        tmp = self.path.with_suffix(self.path.suffix + ".repair")
        tmp.write_bytes(truncated)
        os.replace(str(tmp), str(self.path))
        self.replay()
        return len(tail)

    def summary(self) -> dict:
        """A small owned dict; never the live rows themselves."""
        self._ensure_loaded()
        return {
            "path": str(self.path),
            "rows": len(self._rows),
            "torn_lines": self._torn_lines,
            "tampered_lines": self._tampered_lines,
            "chain_ok": self._chain_ok,
            "first_bad_seq": self._first_bad_seq,
            "intents": len(self.intents()),
            "in_flight": len(self.in_flight()),
            "unattempted": len(self.unattempted()),
            "schema_version": JOURNAL_SCHEMA_VERSION,
        }


def _split_complete_lines(raw: bytes) -> tuple:
    """Split bytes into (complete-lines, incomplete-tail) at the last newline."""
    if not raw:
        return b"", b""
    cut = raw.rfind(b"\n")
    if cut == -1:
        return b"", raw
    return raw[: cut + 1], raw[cut + 1 :]
