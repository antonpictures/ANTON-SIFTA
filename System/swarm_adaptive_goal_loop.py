"""Adaptive goal loop (D3a) -- injection seams, goal DAG, lifecycle discipline.

This module is the skeleton the rest of D3 hangs from. It deliberately owns no
durable state yet (D3b adds the journal); what it establishes is the set of
*seams* and *refusals* that make the later halves testable and honest:

* **Injection.** The adapter, the verifier, and the clock are constructor
  arguments. Nothing here reads the wall clock, the network, or the disk on its
  own, so a test can drive the whole loop deterministically.
* **Frozen records only.** Goals, action proposals and action results are
  validated with the C0 contract classes. This module never invents a record
  shape, and a malformed record is refused at the boundary rather than
  half-consumed.
* **A goal graph is a DAG.** Unknown dependencies, duplicate ids and cycles are
  refused by name. A goal whose dependency is not satisfied is not "ready", and
  the loop will not run ahead of its own dependencies.
* **Lifecycle discipline.** Action states move only along the contract's own
  transition table. ``unknown`` is explicitly *not* terminal: it means the body
  does not know, and a caller must reconcile rather than assume.

Portability law: stdlib only, no Qt/AppKit, safe to import on a headless Linux
rover.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, runtime_checkable

try:  # package import (normal) with a direct-module fallback for bare sys.path use
    from System.swarm_adaptive_contracts import (
        LIFECYCLE_STATES,
        LIFECYCLE_TRANSITIONS,
        RECORDS_SCHEMA_VERSION,
        TERMINAL_STATES,
        ActionProposal,
        ActionResult,
        ContractError,
        Goal,
        assert_adapter,
    )
except ImportError:  # pragma: no cover - exercised only under a bare System/ path
    from swarm_adaptive_contracts import (  # type: ignore
        LIFECYCLE_STATES,
        LIFECYCLE_TRANSITIONS,
        RECORDS_SCHEMA_VERSION,
        TERMINAL_STATES,
        ActionProposal,
        ActionResult,
        ContractError,
        Goal,
        assert_adapter,
    )

__all__ = [
    "Clock",
    "SystemClock",
    "ManualClock",
    "GoalGraphError",
    "VerificationIntegrityError",
    "LifecycleError",
    "GoalNode",
    "GoalGraph",
    "VerifierResult",
    "Verifier",
    "NullVerifier",
    "AdapterBinding",
    "LifecycleLedger",
    "CompletionRefused",
    "GoalLoop",
]

UNRESOLVED_STATE = "unknown"


def _journal_module():
    """Import the journal either way, so ``System/`` runs from its own directory."""
    try:
        from System import swarm_action_journal as journal_module
    except ImportError:  # pragma: no cover - bare System/ path
        import swarm_action_journal as journal_module  # type: ignore

    return journal_module


# --- Clock seam ---------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """Time is injected so the loop is deterministic under test."""

    def now_utc(self) -> str: ...

    def monotonic_s(self) -> float: ...


class SystemClock:
    """The real clock. The only place in this module that reads wall time."""

    def now_utc(self) -> str:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def monotonic_s(self) -> float:
        import time as _time

        return _time.monotonic()


class ManualClock:
    """A clock a test owns. Never advances on its own."""

    def __init__(self, *, utc: str = "2026-01-01T00:00:00Z", monotonic_s: float = 0.0) -> None:
        self._utc = utc
        self._monotonic = float(monotonic_s)

    def now_utc(self) -> str:
        return self._utc

    def monotonic_s(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> "ManualClock":
        self._monotonic += float(seconds)
        base = _dt.datetime.strptime(self._utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc
        )
        self._utc = (base + _dt.timedelta(seconds=float(seconds))).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self


# --- Refusals -----------------------------------------------------------------


class GoalGraphError(ValueError):
    """A goal set that cannot be executed as a DAG. Carries a machine code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


class VerificationIntegrityError(ValueError):
    """A verifier claim that cannot be true, refused before it is believed."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


class LifecycleError(ValueError):
    """An action state change the contract does not permit."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


class CompletionRefused(LifecycleError):
    """D3d: a goal was not allowed to be called done.

    Raised by the strict completion path so that "the verifier did not confirm
    it" can never be mistaken for "it is done". The non-strict :meth:`GoalLoop.confirm`
    reports the same refusal as data; this type exists for callers that must not
    proceed on an unconfirmed success.
    """


# --- Goal graph ---------------------------------------------------------------


@dataclass(frozen=True)
class GoalNode:
    """One validated goal record plus the dependency view the loop needs."""

    goal_id: str
    record: dict
    dependencies: tuple
    task_family: str
    deadline_utc: Optional[str]

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "GoalNode":
        validated = Goal.from_dict(dict(record))
        payload = validated.to_dict()
        return cls(
            goal_id=payload["goal_id"],
            record=payload,
            dependencies=tuple(payload["dependency_ids"]),
            task_family=payload["task_family"],
            deadline_utc=payload.get("deadline_utc"),
        )


class GoalGraph:
    """A validated set of goals.

    Construction is the validation: after ``GoalGraph(records)`` returns, every
    dependency resolves to a known goal, no goal depends on itself, no two goals
    share an id, and the dependency relation is acyclic. Callers get an
    execution order they can trust rather than one they must re-check.
    """

    def __init__(self, records: Iterable[Mapping[str, Any]]) -> None:
        nodes: dict[str, GoalNode] = {}
        order: list[str] = []
        for record in records:
            node = GoalNode.from_record(record)
            if node.goal_id in nodes:
                raise GoalGraphError("DUPLICATE_GOAL_ID", f"goal {node.goal_id!r} appears twice")
            if node.goal_id in node.dependencies:
                # Unreachable while the C0 contract enforces its own
                # self-dependency rule (it raises first, inside from_record).
                # Kept so the loop's refusal survives a relaxation of that rule.
                raise GoalGraphError("SELF_DEPENDENCY", f"goal {node.goal_id!r} depends on itself")
            nodes[node.goal_id] = node
            order.append(node.goal_id)

        for node in nodes.values():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise GoalGraphError(
                        "MISSING_DEPENDENCY",
                        f"goal {node.goal_id!r} depends on unknown goal {dep!r}",
                    )

        self._nodes = nodes
        self._order = order
        self._topological = self._topological_order()

    def _topological_order(self) -> tuple:
        """Kahn's algorithm; a leftover node is a cycle, reported by its members."""
        indegree = {gid: 0 for gid in self._order}
        dependents: dict[str, list] = {gid: [] for gid in self._order}
        for node in self._nodes.values():
            indegree[node.goal_id] += len(node.dependencies)
            for dep in node.dependencies:
                dependents[dep].append(node.goal_id)

        ready = [gid for gid in self._order if indegree[gid] == 0]
        resolved: list[str] = []
        while ready:
            gid = ready.pop(0)
            resolved.append(gid)
            for child in dependents[gid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)

        if len(resolved) != len(self._order):
            stuck = sorted(gid for gid in self._order if gid not in set(resolved))
            raise GoalGraphError("CYCLE", f"dependency cycle among goals {stuck}")
        return tuple(resolved)

    @property
    def goal_ids(self) -> tuple:
        return tuple(self._order)

    @property
    def execution_order(self) -> tuple:
        """Topological order: every goal after the goals it depends on."""
        return self._topological

    def node(self, goal_id: str) -> GoalNode:
        try:
            return self._nodes[goal_id]
        except KeyError as exc:
            raise GoalGraphError("UNKNOWN_GOAL", f"no goal {goal_id!r} in this graph") from exc

    def roots(self) -> tuple:
        return tuple(gid for gid in self._topological if not self._nodes[gid].dependencies)

    def ready(self, completed: Iterable[str]) -> tuple:
        """Goals whose dependencies are all complete and which are not complete.

        A dependency that is merely *known* does not make a goal ready; only a
        satisfied dependency does. This is the boundary that stops the loop from
        running ahead of its own preconditions.
        """
        done = set(completed)
        for gid in done:
            if gid not in self._nodes:
                raise GoalGraphError("UNKNOWN_GOAL", f"completed goal {gid!r} is not in this graph")
        return tuple(
            gid
            for gid in self._topological
            if gid not in done and all(dep in done for dep in self._nodes[gid].dependencies)
        )

    def blocked(self, completed: Iterable[str]) -> tuple:
        """Goals that cannot yet run, with the exact dependencies holding them."""
        done = set(completed)
        out = []
        for gid in self._topological:
            if gid in done:
                continue
            unmet = [dep for dep in self._nodes[gid].dependencies if dep not in done]
            if unmet:
                out.append({"goal_id": gid, "blocked_by": unmet})
        return tuple(out)

    def deadline_expired(self, goal_id: str, clock: Clock) -> bool:
        node = self.node(goal_id)
        if not node.deadline_utc:
            return False
        return str(clock.now_utc()) > str(node.deadline_utc)


# --- Verifier seam ------------------------------------------------------------


@dataclass(frozen=True)
class VerifierResult:
    """A contract-shaped VERIFIER_RESULT, or a refusal to claim one."""

    verified: bool
    verifier: str
    method: str
    detail: Optional[str]
    observation_ids: tuple

    def to_dict(self) -> dict:
        return {
            "verified": bool(self.verified),
            "verifier": str(self.verifier),
            "method": str(self.method),
            "detail": None if self.detail is None else str(self.detail),
            "observation_ids": [str(o) for o in self.observation_ids],
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "VerifierResult":
        """Read a verifier's answer without laundering it into a stronger claim.

        A success with no observation behind it is refused here, not accepted and
        questioned later: a claim of verified success that names no evidence is
        the exact shape a forged success takes.
        """
        if not isinstance(payload, Mapping):
            raise VerificationIntegrityError(
                "MALFORMED_VERIFIER_RESULT", f"verifier returned {type(payload).__name__}, not a mapping"
            )
        verified = bool(payload.get("verified"))
        observation_ids = tuple(str(o) for o in (payload.get("observation_ids") or ()))
        if verified and not observation_ids:
            raise VerificationIntegrityError(
                "UNEVIDENCED_SUCCESS",
                "a verifier cannot report verified=True without naming observation evidence",
            )
        return cls(
            verified=verified,
            verifier=str(payload.get("verifier") or ""),
            method=str(payload.get("method") or ""),
            detail=None if payload.get("detail") is None else str(payload["detail"]),
            observation_ids=observation_ids,
        )


@runtime_checkable
class Verifier(Protocol):
    """Judges whether an action's postcondition actually holds.

    A verifier is given the claim and the evidence it may use, and is never the
    component that submitted the action. It returns a mapping with at least
    ``verified``; see :meth:`VerifierResult.from_payload`.
    """

    def verify(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class NullVerifier:
    """The honest default: it never claims success.

    Used whenever no real verifier is injected, so an unwired loop degrades into
    "unverified" instead of into "assumed fine".
    """

    def verify(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "verified": False,
            "verifier": "null",
            "method": "none",
            "detail": "no verifier injected; success is not claimed",
            "observation_ids": [],
        }


# --- Adapter binding ----------------------------------------------------------


@dataclass(frozen=True)
class AdapterBinding:
    """An adapter that has been proved to satisfy the contract's interface."""

    adapter_id: str
    adapter: Any
    physical: bool
    capability_revision: str

    @classmethod
    def bind(
        cls, adapter_id: str, adapter: Any, *, physical: bool = False, capability_revision: str = ""
    ) -> "AdapterBinding":
        if not adapter_id or not str(adapter_id).strip():
            raise ContractError("INVALID_ARGUMENT", "adapter_id", "adapter_id must be non-empty")
        try:
            assert_adapter(adapter, physical=physical)
        except ContractError as exc:
            raise ContractError(exc.code, exc.path, f"adapter {adapter_id!r}: {exc.message}") from exc
        return cls(
            adapter_id=str(adapter_id),
            adapter=adapter,
            physical=bool(physical),
            capability_revision=str(capability_revision or ""),
        )


# --- Lifecycle ----------------------------------------------------------------


class LifecycleLedger:
    """Tracks action states and refuses transitions the contract forbids."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}
        self._history: dict[str, list] = {}

    def observe(self, action_id: str, status: str, *, first: bool = True) -> str:
        """Record a reported status, returning the state now believed."""
        action_id = str(action_id)
        status = str(status)
        if status not in LIFECYCLE_STATES:
            raise LifecycleError("UNKNOWN_STATE", f"{status!r} is not a lifecycle state")
        current = self._states.get(action_id)
        if current is None:
            self._states[action_id] = status
            self._history[action_id] = [status]
            return status
        if current == status:
            return status
        allowed = LIFECYCLE_TRANSITIONS.get(current, ())
        if status not in allowed:
            raise LifecycleError(
                "ILLEGAL_TRANSITION",
                f"action {action_id!r} cannot move {current!r} -> {status!r}; allowed {list(allowed)}",
            )
        self._states[action_id] = status
        self._history[action_id].append(status)
        return status

    def state(self, action_id: str) -> Optional[str]:
        return self._states.get(str(action_id))

    def history(self, action_id: str) -> tuple:
        return tuple(self._history.get(str(action_id), ()))

    @staticmethod
    def is_terminal(status: Optional[str]) -> bool:
        """``unknown`` is not terminal: it means reconcile, not conclude."""
        return status in TERMINAL_STATES

    def unresolved(self) -> tuple:
        """Actions whose outcome the body does not know."""
        return tuple(a for a, s in self._states.items() if s == UNRESOLVED_STATE)


# --- The loop -----------------------------------------------------------------


class GoalLoop:
    """D3a loop skeleton: injected adapter, verifier and clock over a goal DAG.

    What it already refuses to do is the point: it will not start a goal whose
    dependencies are unmet, will not believe a success with no evidence, and will
    not treat an unknown outcome as an ending.
    """

    def __init__(
        self,
        *,
        graph: Iterable[Mapping[str, Any]] = (),
        adapter: Optional[AdapterBinding] = None,
        verifier: Optional[Verifier] = None,
        clock: Optional[Clock] = None,
        journal: Any = None,
    ) -> None:
        self.graph = GoalGraph(graph) if graph else GoalGraph(())
        self.adapter = adapter
        self.verifier = verifier if verifier is not None else NullVerifier()
        self.clock = clock if clock is not None else SystemClock()
        self.lifecycle = LifecycleLedger()
        self.journal = journal
        self._completed: list[str] = []
        self._proposals: dict[str, dict] = {}
        self._claims: dict[str, dict] = {}
        self._results: dict[str, dict] = {}
        self._revisions: dict[str, int] = {}

    # -- goals ---------------------------------------------------------------

    def register_goal(self, record: Mapping[str, Any]) -> str:
        """Add one goal, re-validating the whole graph (a DAG claim is global)."""
        existing = [self.graph.node(gid).record for gid in self.graph.goal_ids]
        self.graph = GoalGraph(existing + [dict(record)])
        return GoalNode.from_record(record).goal_id

    def mark_complete(self, goal_id: str) -> None:
        self.graph.node(goal_id)  # refuse unknown ids before mutating anything
        if goal_id not in self._completed:
            self._completed.append(goal_id)

    @property
    def completed(self) -> tuple:
        return tuple(self._completed)

    def ready_goals(self) -> tuple:
        return self.graph.ready(self._completed)

    def blocked_goals(self) -> tuple:
        return self.graph.blocked(self._completed)

    # -- actions -------------------------------------------------------------

    def propose(self, proposal: Mapping[str, Any]) -> dict:
        """Validate and remember an action proposal against the frozen record."""
        validated = ActionProposal.from_dict(dict(proposal)).to_dict()
        action_id = validated["action_id"]
        goal_id = validated["goal_id"]
        self.graph.node(goal_id)  # a proposal for an unknown goal is refused
        if goal_id not in self.ready_goals():
            raise GoalGraphError(
                "GOAL_NOT_READY",
                f"cannot propose for goal {goal_id!r}; unmet dependencies "
                f"{[d for d in self.graph.node(goal_id).dependencies if d not in set(self._completed)]}",
            )
        self._proposals[action_id] = validated
        self._revisions[action_id] = self._revisions.get(action_id, 0)
        return validated

    def record_result(self, result: Mapping[str, Any]) -> dict:
        """Validate an action result and move its lifecycle state legally."""
        validated = ActionResult.from_dict(dict(result)).to_dict()
        action_id = validated["action_id"]
        if action_id not in self._proposals:
            raise LifecycleError(
                "UNKNOWN_ACTION", f"result for action {action_id!r} that was never proposed"
            )
        self.lifecycle.observe(action_id, validated["status"])
        self._results[action_id] = validated
        return validated

    def verify(self, action_id: str) -> VerifierResult:
        """Ask the injected verifier about a proposed action, without believing it."""
        if action_id not in self._proposals:
            raise LifecycleError("UNKNOWN_ACTION", f"no proposal {action_id!r} to verify")
        proposal = self._proposals[action_id]
        request = {
            "action_id": action_id,
            "goal_id": proposal["goal_id"],
            "action_kind": proposal["action_kind"],
            "predicted_postcondition": proposal["predicted_postcondition"],
            "required_observation_ids": list(proposal["required_observation_ids"]),
        }
        try:
            result = VerifierResult.from_payload(self.verifier.verify(request))
        except VerificationIntegrityError as exc:
            # A forged success is refused at the boundary -- and the attempt is
            # written down. A refusal that leaves no trace is indistinguishable
            # later from a verifier that was never asked.
            if self.journal is not None:
                self.journal.append(
                    _journal_module().KIND_VERIFICATION,
                    action_id,
                    goal_id=proposal["goal_id"],
                    payload={
                        "verified": None,
                        "outcome": "refused",
                        "verifier": type(self.verifier).__name__,
                        "detail": f"[{exc.code}] {exc}",
                    },
                )
            raise
        if self.journal is not None:
            self.journal.append(
                _journal_module().KIND_VERIFICATION,
                action_id,
                goal_id=proposal["goal_id"],
                payload={
                    **result.to_dict(),
                    "outcome": "confirmed" if result.verified else "not_confirmed",
                },
            )
        return result

    def proposal(self, action_id: str) -> Optional[dict]:
        return self._proposals.get(str(action_id))

    # -- durable submission (D3b) --------------------------------------------

    def attach_journal(self, journal: Any) -> None:
        """Give the loop a durable outbox. Without one it refuses to submit."""
        self.journal = journal

    def submit(self, action_id: str) -> dict:
        """Journal the intent durably, *then* ask the adapter to act.

        Ordering is the whole point: the row is fsynced before the adapter is
        called, so no action can exist in the world without existing on disk.
        If the adapter raises, the intent and an ``attempted_unknown`` marker stay
        behind, the action becomes ``unknown``, and a retry is refused -- the body
        must reconcile before it may act again.
        """
        action_id = str(action_id)
        if self.journal is None:
            raise LifecycleError(
                "NO_JOURNAL",
                "refusing to submit without a durable journal: an unjournalled action cannot be reconciled",
            )
        if self.adapter is None:
            raise LifecycleError("NO_ADAPTER", "no adapter bound to this loop")

        try:
            from System.swarm_action_journal import (
                KIND_INTENT,
                KIND_SUBMIT,
                SUBMIT_ACCEPTED,
                SUBMIT_ATTEMPTED,
                SUBMIT_UNATTEMPTED,
                JournalError,
            )
        except ImportError:  # pragma: no cover - bare System/ path
            from swarm_action_journal import (  # type: ignore
                KIND_INTENT,
                KIND_SUBMIT,
                SUBMIT_ACCEPTED,
                SUBMIT_ATTEMPTED,
                SUBMIT_UNATTEMPTED,
                JournalError,
            )

        # The journal is consulted before this process's own memory. A restarted
        # body holds no proposals, and that amnesia must never become permission
        # to resend an action the previous body already handed over.
        state = self.journal.submit_state(action_id)
        if state in (SUBMIT_ATTEMPTED, SUBMIT_ACCEPTED):
            raise JournalError(
                "RESEND_FORBIDDEN",
                f"action {action_id!r} was already handed to the adapter ({state}); "
                "reconcile its true status instead of resending it",
            )

        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise LifecycleError("UNKNOWN_ACTION", f"no proposal {action_id!r} to submit")
        if state == SUBMIT_UNATTEMPTED:
            # A previous process wrote the intent and died before submitting.
            # Reuse that row rather than inventing a second claim.
            intent_row = self.journal.intent(action_id)
        else:
            intent_row = self.journal.append(
                KIND_INTENT,
                action_id,
                goal_id=proposal["goal_id"],
                payload={
                    "goal_id": proposal["goal_id"],
                    "action_kind": proposal["action_kind"],
                    "adapter_id": proposal["adapter_id"],
                    "capability_revision": proposal["capability_revision"],
                    "predicted_postcondition": proposal["predicted_postcondition"],
                    "required_observation_ids": list(proposal["required_observation_ids"]),
                    "args": dict(proposal["args"]),
                },
            )

        try:
            receipt = self.adapter.adapter.submit(dict(proposal))
        except Exception as exc:  # the adapter's failure must not erase the intent
            self.journal.append(
                KIND_SUBMIT,
                action_id,
                goal_id=proposal["goal_id"],
                payload={
                    "outcome": "attempted_unknown",
                    "error": f"{type(exc).__name__}: {exc}",
                    "adapter_id": self.adapter.adapter_id,
                },
            )
            self.lifecycle.observe(action_id, UNRESOLVED_STATE)
            raise

        # An empty receipt id is no receipt id: the adapter did not tell us the
        # action was accepted, so the action stays unknown.
        receipt_id = None
        if receipt is not None:
            candidate = str(receipt).strip()
            receipt_id = candidate or None
        outcome = SUBMIT_ACCEPTED if receipt_id else "attempted_unknown"
        self.journal.append(
            KIND_SUBMIT,
            action_id,
            goal_id=proposal["goal_id"],
            payload={
                "outcome": outcome,
                "effect_receipt_id": receipt_id,
                "adapter_id": self.adapter.adapter_id,
            },
        )
        self.lifecycle.observe(action_id, "accepted" if receipt_id else UNRESOLVED_STATE)
        if receipt_id:
            # A receipted handover means the action is under way in the world, not
            # merely acknowledged. Walking the frozen ladder one rung (accepted ->
            # running) keeps the graph honest: nothing may be called succeeded
            # without having first been known to run.
            self.lifecycle.observe(action_id, "running")
        return {
            "action_id": action_id,
            "intent_seq": intent_row.seq,
            "outcome": outcome,
            "effect_receipt_id": receipt_id,
        }

    def result(self, action_id: str) -> Optional[dict]:
        """The frozen ActionResult for this action, if one exists.

        Only a contract-valid record lives here. An adapter's report that an
        action succeeded is not one: the frozen contract refuses a `succeeded`
        ActionResult that carries no verified result, so such reports wait in
        `claim()` until a verifier supplies the evidence.
        """
        return self._results.get(str(action_id))

    def claim(self, action_id: str) -> Optional[dict]:
        """What a body reported about an action, before verification."""
        return self._claims.get(str(action_id))

    # -- reconciliation (D3c) -------------------------------------------------

    def reconcile(self, action_id: Optional[str] = None) -> dict:
        """Ask the adapter what actually happened. Never resend, never guess.

        A restart finds actions whose submit was attempted and whose outcome was
        never learned. The only honest move is to ask, so this calls
        ``adapter.status`` and records whatever it says -- including "still
        running" and including "I do not know". A non-terminal or unrecognisable
        answer leaves the action unresolved and still un-resendable; only a
        terminal answer, evidenced by the journal, closes it.

        Statuses outside the frozen lifecycle are recorded as ``unknown`` rather
        than accepted as words: an adapter cannot invent a state.
        """
        if self.adapter is None:
            raise LifecycleError("NO_ADAPTER", "no adapter bound to this loop")
        if self.journal is None:
            raise LifecycleError(
                "NO_JOURNAL",
                "refusing to reconcile without a durable journal: there is no record of what was attempted",
            )
        try:
            from System.swarm_action_journal import KIND_NOTE, KIND_RESULT, KIND_STATUS, JournalError
        except ImportError:  # pragma: no cover - bare System/ path
            from swarm_action_journal import (  # type: ignore
                KIND_NOTE,
                KIND_RESULT,
                KIND_STATUS,
                JournalError,
            )

        if action_id is None:
            targets = [row.action_id for row in self.journal.in_flight()]
        else:
            action_id = str(action_id)
            if self.journal.intent(action_id) is None:
                raise JournalError(
                    "UNJOURNALLED_ACTION",
                    f"action {action_id!r} has no intent row; there is nothing trustworthy to reconcile",
                )
            targets = [action_id]

        outcomes: list = []
        for target in targets:
            goal_id = None
            intent = self.journal.intent(target)
            if intent is not None:
                goal_id = intent.goal_id
            try:
                reported = self.adapter.adapter.status(target)
            except Exception as exc:
                self.journal.append(
                    KIND_STATUS,
                    target,
                    goal_id=goal_id,
                    payload={
                        "reported": None,
                        "outcome": "status_unavailable",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                self.journal.append(
                    KIND_NOTE,
                    target,
                    goal_id=goal_id,
                    payload={"note": "reconciliation_incomplete", "for_action": target},
                )
                outcomes.append(
                    {
                        "action_id": target,
                        "status": UNRESOLVED_STATE,
                        "resolved": False,
                        "detail": f"status unavailable: {type(exc).__name__}: {exc}",
                    }
                )
                continue

            raw_status = None
            if isinstance(reported, Mapping):
                raw_status = reported.get("status")
            claimed = None if raw_status is None else str(raw_status)
            status = claimed if claimed in LIFECYCLE_STATES else UNRESOLVED_STATE
            detail = None
            if claimed is not None and claimed != status:
                detail = f"adapter reported {claimed!r}, which is not a frozen lifecycle state"

            self.journal.append(
                KIND_STATUS,
                target,
                goal_id=goal_id,
                payload={
                    "reported": claimed,
                    "outcome": status,
                    "detail": detail,
                    "effect_receipt_id": (
                        reported.get("effect_receipt_id") if isinstance(reported, Mapping) else None
                    ),
                },
            )

            current = self.lifecycle.state(target)
            try:
                self.lifecycle.observe(target, status)
            except LifecycleError:
                # The ledger refuses the jump; the journal keeps the report and
                # the action stays where it was rather than being forced forward.
                self.journal.append(
                    KIND_NOTE,
                    target,
                    goal_id=goal_id,
                    payload={"note": "lifecycle_refused", "from": current, "to": status},
                )

            resolved = status in TERMINAL_STATES
            if resolved:
                self.journal.append(
                    KIND_RESULT,
                    target,
                    goal_id=goal_id,
                    payload={
                        "status": status,
                        "via": "reconciliation",
                        "detail": detail,
                    },
                )
                self._claims[target] = {
                    "action_id": target,
                    "goal_id": goal_id,
                    "status": status,
                    "via": "reconciliation",
                    "verified": False,
                    "detail": detail,
                }
            outcomes.append(
                {
                    "action_id": target,
                    "status": status,
                    "resolved": resolved,
                    "detail": detail,
                }
            )

        return {
            "reconciled": tuple(outcomes),
            "still_in_flight": tuple(row.action_id for row in self.journal.in_flight()),
            "resend_forbidden": tuple(self.journal.resend_forbidden()),
        }

    def unverified_successes(self) -> tuple:
        """Actions a body claims succeeded that no verifier has confirmed."""
        return tuple(
            action_id
            for action_id, row in {**self._claims, **self._results}.items()
            if row.get("status") == "succeeded" and not row.get("verified")
        )

    # -- verifier-driven completion (D3d) ------------------------------------

    def confirmed_actions(self) -> tuple:
        """Actions on disk with a completion row. The journal is the authority.

        In-memory completion does not survive a restart; this does, so a body
        that comes back up cannot be talked into completing the same goal twice
        or forget that it already had the evidence.
        """
        if self.journal is None:
            return ()
        kinds = _journal_module().KIND_COMPLETION
        seen: list = []
        for row in self.journal.rows:
            if row.kind == kinds and row.action_id not in seen:
                seen.append(row.action_id)
        return tuple(seen)

    def _verified_result_on_disk(self, action_id: str) -> Optional[dict]:
        """The frozen result a verifier wrote, read back from the journal.

        After a restart the in-memory result map is empty, so an
        ``already_completed`` answer must be able to produce the evidence it is
        asserting rather than an empty shell.
        """
        if self.journal is None:
            return None
        j = _journal_module()
        for row in reversed(self.journal.rows):
            if row.action_id != str(action_id) or row.kind != j.KIND_RESULT:
                continue
            if row.payload.get("via") == "verification":
                return {k: v for k, v in row.payload.items() if k != "via"}
        return None

    def confirm(self, action_id: str) -> dict:
        """Ask the verifier, persist a frozen result, and complete only if confirmed.

        The order is the law: a goal is not completed and then checked, it is
        checked and then completed. An adapter's ``succeeded`` never reaches
        here -- only a named verifier answering with named observation evidence
        can, and the frozen ``ActionResult`` it produces is written to the
        journal before the goal is marked done.
        """
        action_id = str(action_id)
        if self.journal is None:
            raise CompletionRefused(
                "NO_JOURNAL",
                "refusing to complete a goal without a durable journal: an unrecorded "
                "completion is an unfalsifiable claim",
            )
        j = _journal_module()
        # The journal is consulted before memory, for the same reason it is
        # before a resend: a restart must not turn an already-completed action
        # into an unknown one, nor into a second completion.
        already = action_id in self.confirmed_actions()
        if already:
            completion = self.journal.latest(action_id, j.KIND_COMPLETION)
            on_disk = self._verified_result_on_disk(action_id)
            return {
                "action_id": action_id,
                "goal_id": completion.goal_id if completion is not None else None,
                "verified": True,
                "completed": True,
                "already_completed": True,
                "verifier_result": (self.result(action_id) or on_disk or {}).get("verifier_result"),
                "result": self.result(action_id) or on_disk,
                "detail": "this action already has a completion row on disk",
            }
        proposal = self._proposals.get(action_id)
        if proposal is None:
            raise CompletionRefused("UNKNOWN_ACTION", f"no proposal {action_id!r} to confirm")
        if self.journal.intent(action_id) is None:
            raise CompletionRefused(
                "UNJOURNALLED_ACTION",
                f"action {action_id!r} has no intent row; it was never submitted, so nothing "
                "can have been observed about it",
            )
        goal_id = proposal["goal_id"]

        result = self.verify(action_id)  # journals the verdict either way
        if not result.verified:
            return {
                "action_id": action_id,
                "goal_id": goal_id,
                "verified": False,
                "completed": False,
                "already_completed": False,
                "verifier_result": result.to_dict(),
                "result": None,
                "detail": result.detail or "the verifier did not confirm the postcondition",
            }

        submitted = self.journal.latest(action_id, j.KIND_SUBMIT)
        receipt_id = None
        if submitted is not None:
            receipt_id = submitted.payload.get("effect_receipt_id") or submitted.payload.get(
                "receipt_id"
            )
        latest_status = self.journal.latest(action_id, j.KIND_STATUS)
        if latest_status is not None and latest_status.payload.get("effect_receipt_id"):
            receipt_id = latest_status.payload["effect_receipt_id"]

        now = self.clock.now_utc()
        frozen = ActionResult.from_dict(
            {
                "schema_version": "1.0.0",
                "action_id": action_id,
                "status": "succeeded",
                "actual_observation_ids": list(result.observation_ids),
                "verifier_result": result.to_dict(),
                # A predicted cost is not an actual cost, and an unreported one is
                # unknown rather than zero.
                "cost": None,
                "error": None,
                "effect_receipt_id": receipt_id,
                "updated_at_utc": now,
            }
        ).to_dict()

        self.record_result(frozen)
        self._results[action_id] = {**frozen, "verified": True, "via": "verification"}
        # The claim is settled: keeping it would leave a confirmed action listed
        # as an unverified success forever.
        self._claims.pop(action_id, None)
        self.journal.append(
            j.KIND_RESULT, action_id, goal_id=goal_id, payload={**frozen, "via": "verification"}
        )
        self.mark_complete(goal_id)
        self.journal.append(
            j.KIND_COMPLETION,
            action_id,
            goal_id=goal_id,
            payload={
                "action_id": action_id,
                "goal_id": goal_id,
                "verified": True,
                "verifier": result.verifier,
                "method": result.method,
                "observation_ids": list(result.observation_ids),
                "effect_receipt_id": receipt_id,
                "verified_at_utc": now,
            },
        )
        return {
            "action_id": action_id,
            "goal_id": goal_id,
            "verified": True,
            "completed": True,
            "already_completed": False,
            "verifier_result": result.to_dict(),
            "result": frozen,
            "detail": result.detail,
        }

    def require_confirmed(self, action_id: str) -> dict:
        """Strict completion: anything short of a confirmed success raises."""
        report = self.confirm(action_id)
        if not report["completed"]:
            raise CompletionRefused(
                "UNVERIFIED_SUCCESS",
                f"goal {report['goal_id']!r} is not done: {report['detail']}",
            )
        return report

    def unresolved_actions(self) -> tuple:
        return self.lifecycle.unresolved()
