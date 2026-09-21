"""D3f — bind the adaptive goal loop into the body's real routing.

`swarm_adaptive_goal_loop.py` had no caller: it was a correct loop nothing could
reach. This module is the invocation path, and it deliberately owns no scheduler,
no queue and no second verifier. There is one movement owner per body, and it is
still the `GoalLoop`; everything here either asks that loop a question or hands it
one bounded step.

Three things this binding refuses to let happen:

1. **Planning on a stale body.** The corrected D1/R1 planning view is consumed
   before every dependent action, not once at startup. `capability_availability_gate`
   was reachable only from `capability_field_summary` -- a status dashboard readout --
   so a lost organ could stay "planned" for as long as nobody looked at the dashboard.
   Here, an action whose precondition is lost, or which was *never reported by this
   body at all*, does not run: it comes back blocked with the reason the capability
   was lost, and unreported preconditions additionally owe a discovery.

2. **Waiting forever on a body.** A step polls at most `max_polls` times. The default
   is one poll and zero waiting, so the ordinary path is nonblocking; a caller that
   asks for more waits only inside the declared budget. The bound covers the wait
   *schedule*: it cannot interrupt a single adapter call that never returns, so a
   hung adapter is reported as `unknown` rather than pretended away.

3. **A stop that queues behind the step.** `request_stop` goes straight to
   `GoalLoop.owner_stop` at the moment it is asked, and the poll loop notices the
   flag at its next boundary. The stop never waits for a poll to finish first.

An outcome is `completed` only when the loop's own verifier confirmed it. A refusal,
an absence of evidence and a loss of contact are three different answers, and each
one is written to the shared ledgers in those terms.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

try:  # package-style import when System is on the path
    from System.swarm_adaptive_goal_loop import (
        GoalLoop,
        REASON_BLOCKED,
        REASON_STOP_REQUESTED,
    )
except ImportError:  # pragma: no cover - direct sibling import
    from swarm_adaptive_goal_loop import (
        GoalLoop,
        REASON_BLOCKED,
        REASON_STOP_REQUESTED,
    )

try:
    from System.swarm_boot_identity import planning_view
except ImportError:  # pragma: no cover
    from swarm_boot_identity import planning_view


__all__ = [
    "LEDGER_SOURCE",
    "OUTCOME_BLOCKED",
    "OUTCOME_COMPLETED",
    "OUTCOME_REFUSED",
    "OUTCOME_STOPPED",
    "OUTCOME_UNKNOWN",
    "REASON_OUTCOME_UNKNOWN",
    "AdaptiveStepBinding",
    "load_step_request",
    "lookup_adaptive_body",
    "lookup_adaptive_verifier",
    "planning_gate",
    "register_adaptive_body",
    "register_adaptive_verifier",
    "registered_adaptive_bodies",
    "registered_adaptive_verifiers",
    "run_goal_step",
]

LEDGER_SOURCE = "swarm_adaptive_step_binding"

# The goal loop has no "unknown outcome" reason of its own: an unknown outcome is
# not one of its decisions, it is the absence of one. This name is the V1 verifier
# refusal code, used here so the two layers speak the same word for the same fact.
REASON_OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"

# Which organ moves, and who can confirm it moved, are facts only the body knows.
# Nothing here invents either one: an organ registers itself, exactly as the
# browser and app surfaces register themselves with the tool router.
_BODIES: dict[str, dict[str, Any]] = {}
_VERIFIERS: dict[str, Any] = {}


def register_adaptive_body(
    adapter_id: str,
    adapter: Any,
    *,
    capability_revision: str = "",
) -> None:
    """Let the organ that actually moves register itself as a body."""
    _BODIES[str(adapter_id)] = {
        "adapter": adapter,
        "capability_revision": str(capability_revision),
    }


def register_adaptive_verifier(verifier_id: str, verifier: Any) -> None:
    """Let the organ that can confirm a postcondition register its verifier."""
    _VERIFIERS[str(verifier_id)] = verifier


def registered_adaptive_bodies() -> tuple:
    return tuple(sorted(_BODIES))


def registered_adaptive_verifiers() -> tuple:
    return tuple(sorted(_VERIFIERS))


def lookup_adaptive_body(adapter_id: str) -> Optional[dict[str, Any]]:
    """Return the registered body record for an adapter, or None if no organ claimed it."""
    entry = _BODIES.get(str(adapter_id))
    return dict(entry) if entry is not None else None


def lookup_adaptive_verifier(verifier_id: str) -> Any:
    return _VERIFIERS.get(str(verifier_id))

OUTCOME_COMPLETED = "completed"
OUTCOME_BLOCKED = "blocked"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_STOPPED = "stopped"
OUTCOME_REFUSED = "refused"


def planning_gate(
    action: Mapping[str, Any],
    *,
    state_root: Optional[Path | str] = None,
    readings: Optional[Mapping[str, Any]] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Ask the corrected D1/R1 planning view about exactly one action.

    Returns ``{"allowed", "reason_code", "detail", "blocked_by", "discovery_required",
    "checked_at_utc"}``. The view is asked *now*, not remembered: freshness is the
    whole point of R1, so a cached answer would reintroduce the fault this repairs.
    """
    view = planning_view([dict(action)], state_root=state_root, readings=readings, now=now)
    blocked = list(view.get("unavailable") or [])
    if not blocked:
        return {
            "allowed": True,
            "reason_code": None,
            "detail": "",
            "blocked_by": [],
            "discovery_required": list(view.get("discovery_required") or []),
            "checked_at_utc": view.get("checked_at_utc"),
            "topology_id": view.get("topology_id"),
        }
    first = dict(blocked[0])
    return {
        "allowed": False,
        "reason_code": first.get("reason_code") or REASON_BLOCKED,
        "detail": first.get("detail") or "unmet precondition",
        "blocked_by": list(first.get("blocked_by") or []),
        "discovery_required": list(view.get("discovery_required") or []),
        "checked_at_utc": view.get("checked_at_utc"),
        "topology_id": view.get("topology_id"),
    }


class AdaptiveStepBinding:
    """One bounded invocation path into an existing `GoalLoop`.

    The loop is passed in, never constructed here: a binding that built its own loop
    would be the duplicate global coordinator the audit forbids.
    """

    def __init__(
        self,
        loop: GoalLoop,
        *,
        state_root: Optional[Path | str] = None,
        readings: Optional[Mapping[str, Any]] = None,
        ledger_state_dir: Optional[Path | str] = None,
        sleep: Optional[Callable[[float], Any]] = None,
        interval_s: float = 0.0,
        max_polls: int = 1,
        now_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.loop = loop
        self.state_root = state_root
        self.readings = readings
        self.ledger_state_dir = ledger_state_dir
        self.interval_s = max(0.0, float(interval_s))
        self.max_polls = max(1, int(max_polls))
        self._sleep = sleep
        self._now_fn = now_fn or time.time
        self._stop: dict[str, Any] = {"requested": False, "action_id": None, "report": None}

    # ── the stop, which never queues ─────────────────────────────────────────

    def request_stop(
        self,
        action_id: str,
        *,
        reason_code: str = REASON_STOP_REQUESTED,
        rest_observation_ids: Optional[Sequence[str]] = None,
    ) -> dict[str, Any]:
        """Stop now. The owner stop is issued on this call, not at the next poll."""
        report = self.loop.owner_stop(
            action_id, reason_code=reason_code, rest_observation_ids=rest_observation_ids
        )
        self._stop = {"requested": True, "action_id": str(action_id), "report": report}
        return report

    def stop_requested(self) -> bool:
        return bool(self._stop.get("requested"))

    # ── shared ledgers ───────────────────────────────────────────────────────

    def _record(
        self,
        text: str,
        *,
        event_label: str,
        epistemic_status: str,
        evidence_links: Sequence[str] = (),
    ) -> Optional[str]:
        """Write one semantic event into the lived-experience ledger.

        A ledger that is unavailable must not turn a real outcome into a failed step:
        the action journal already holds the fact, so the ledger error is *reported*
        rather than raised. Returns the error text, or None.
        """
        if self.ledger_state_dir is None:
            return None
        try:
            try:
                from System.swarm_lived_experience_bridge import record_lived_event
            except ImportError:  # pragma: no cover
                from swarm_lived_experience_bridge import record_lived_event

            record_lived_event(
                text,
                event_label=event_label,
                epistemic_status=epistemic_status,
                source=LEDGER_SOURCE,
                evidence_links=list(evidence_links),
                state_dir=self.ledger_state_dir,
            )
            return None
        except Exception as exc:  # a ledger fault is reported, never fatal
            return f"{type(exc).__name__}: {exc}"

    # ── the one invocation path ──────────────────────────────────────────────

    def run_step(
        self,
        goal_id: str,
        action: Mapping[str, Any],
        *,
        preconditions: Sequence[str] = (),
        confirm: bool = True,
        rest_observation_ids: Optional[Sequence[str]] = None,
    ) -> dict[str, Any]:
        """Gate, attempt once, poll a bounded number of times, then verify.

        Two views of one intent meet here and are deliberately kept apart: `action` is
        the frozen ``ActionProposal`` the loop submits, and `preconditions` names the
        capabilities that action depends on. They are separate arguments because they
        are separate questions -- "what will you do" and "what must still exist for it
        to be lawful" -- and merging them would mean inventing a field the frozen
        contract does not have. An action that declares no precondition is allowed by
        the gate; that is the truth, not an oversight.

        Returns a report that always names its outcome and reason. It never returns
        `completed` on the strength of an adapter report alone: completion is whatever
        `GoalLoop.confirm` says, which is the frozen V1 verification.
        """
        action = dict(action)
        action_id = str(action.get("action_id") or "")
        started = time.monotonic()
        report: dict[str, Any] = {
            "goal_id": str(goal_id),
            "action_id": action_id,
            "outcome": None,
            "reason_code": None,
            "detail": "",
            "polls": 0,
            "max_polls": self.max_polls,
            "interval_s": self.interval_s,
            "scheduled_wait_s": 0.0,
            "wall_wait_s": 0.0,
            "stop_requested": False,
            "planning": None,
            "preconditions": [str(p) for p in preconditions],
            "ledger_error": None,
            "journal_error": None,
        }

        # 1. the corrected planning view, consumed before the action acts.
        gate_subject = {
            "name": str(action.get("action_kind") or action.get("name") or "action"),
            "preconditions": [str(p) for p in preconditions],
        }
        gate = planning_gate(gate_subject, state_root=self.state_root, readings=self.readings)
        report["planning"] = gate
        if not gate["allowed"]:
            report.update(
                outcome=OUTCOME_BLOCKED,
                reason_code=gate["reason_code"],
                detail=gate["detail"],
            )
            report["ledger_error"] = self._record(
                f"adaptive step refused for goal {goal_id}: {gate['detail']}",
                event_label="adaptive_step_blocked",
                epistemic_status="INFERRED",
                evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
            )
            report["wall_wait_s"] = round(time.monotonic() - started, 6)
            return report

        # 2. attempt it exactly once. The loop owns write-before-submit and refuses
        #    to resend an action it already handed to the adapter.
        if self.loop.proposal(action_id) is None:
            try:
                self.loop.propose(action)
            except Exception as exc:
                report.update(
                    outcome=OUTCOME_REFUSED,
                    reason_code=getattr(exc, "code", None) or "REFUSED",
                    detail=str(exc),
                )
                report["wall_wait_s"] = round(time.monotonic() - started, 6)
                return report
        try:
            self.loop.submit(action_id)
        except Exception as exc:
            report.update(
                outcome=OUTCOME_REFUSED,
                reason_code=getattr(exc, "code", None) or "REFUSED",
                detail=str(exc),
            )
            report["ledger_error"] = self._record(
                f"adaptive step could not submit {action_id}: {exc}",
                event_label="adaptive_step_refused",
                epistemic_status="INFERRED",
                evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
            )
            report["wall_wait_s"] = round(time.monotonic() - started, 6)
            return report

        # 3. poll, bounded, and yield to a stop at every boundary.
        for _ in range(self.max_polls):
            if self._stop.get("requested"):
                report.update(
                    outcome=OUTCOME_STOPPED,
                    reason_code=str(
                        (self._stop.get("report") or {}).get("reason_code")
                        or REASON_STOP_REQUESTED
                    ),
                    detail="an owner stop was requested during the step",
                    stop_requested=True,
                )
                report["ledger_error"] = self._record(
                    f"adaptive step for {action_id} was stopped by the owner",
                    event_label="adaptive_step_stopped",
                    epistemic_status="DIRECT_OBSERVED",
                    evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
                )
                report["wall_wait_s"] = round(time.monotonic() - started, 6)
                return report

            report["polls"] += 1
            try:
                report["reconciliation"] = self.loop.reconcile(action_id)
            except Exception as exc:
                # A body that cannot answer has not failed the action -- it has
                # declined to tell us what happened, which is `unknown`, not `failed`.
                report.update(
                    outcome=OUTCOME_UNKNOWN,
                    reason_code=getattr(exc, "code", None) or REASON_OUTCOME_UNKNOWN,
                    detail=f"{type(exc).__name__}: {exc}",
                )
                break
            if self.loop.result(action_id) is not None or self.loop.claim(action_id) is not None:
                break
            if self.interval_s > 0 and report["polls"] < self.max_polls:
                self._wait(self.interval_s, report)

        report["scheduled_wait_s"] = round(self.interval_s * max(0, report["polls"] - 1), 6)

        if report["outcome"] is None and report["polls"] >= self.max_polls:
            if self.loop.result(action_id) is None and self.loop.claim(action_id) is None:
                report.update(
                    outcome=OUTCOME_UNKNOWN,
                    reason_code=REASON_OUTCOME_UNKNOWN,
                    detail=(
                        f"no answer after {report['polls']} bounded poll(s); the body was "
                        "not contacted further"
                    ),
                )

        # 4. completion is the loop's own verification, never an adapter's report.
        if confirm and report["outcome"] is None:
            try:
                verdict = self.loop.confirm(action_id)
            except Exception as exc:
                report.update(
                    outcome=OUTCOME_UNKNOWN,
                    reason_code=getattr(exc, "code", None) or REASON_OUTCOME_UNKNOWN,
                    detail=f"verification could not be performed: {exc}",
                )
            else:
                report["verification"] = verdict
                if verdict.get("completed"):
                    result = verdict.get("result") or {}
                    report.update(
                        outcome=OUTCOME_COMPLETED,
                        reason_code=None,
                        detail="verification confirmed the postcondition",
                        actual_observation_ids=list(
                            result.get("actual_observation_ids") or []
                        ),
                    )
                else:
                    report.update(
                        outcome=OUTCOME_UNKNOWN,
                        reason_code=REASON_OUTCOME_UNKNOWN,
                        detail=str(verdict.get("detail") or "not confirmed"),
                    )

        # 5. the shared ledger hears the answer in the terms it was actually known in.
        if report["outcome"] == OUTCOME_COMPLETED:
            report["ledger_error"] = self._record(
                f"goal {goal_id} completed and was verified through action {action_id}",
                event_label="adaptive_step_completed",
                epistemic_status="DIRECT_OBSERVED",
                evidence_links=[
                    f"goal:{goal_id}",
                    f"action:{action_id}",
                    *[str(o) for o in report.get("actual_observation_ids") or []],
                ],
            )
        elif report["outcome"] in (OUTCOME_UNKNOWN, OUTCOME_BLOCKED):
            report["ledger_error"] = self._record(
                f"goal {goal_id} step {action_id} ended without a known outcome: {report['detail']}",
                event_label="adaptive_step_unknown",
                epistemic_status="UNKNOWN",
                evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
            )
        elif report["outcome"] == OUTCOME_STOPPED:
            report["ledger_error"] = self._record(
                f"goal {goal_id} step {action_id} ended because the owner stopped it",
                event_label="adaptive_step_stopped",
                epistemic_status="DIRECT_OBSERVED",
                evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
            )
        elif report["outcome"] == OUTCOME_REFUSED:
            report["ledger_error"] = self._record(
                f"goal {goal_id} step {action_id} was refused: {report['detail']}",
                event_label="adaptive_step_refused",
                epistemic_status="INFERRED",
                evidence_links=[f"goal:{goal_id}", f"action:{action_id}"],
            )

        report["wall_wait_s"] = round(time.monotonic() - started, 6)
        return report

    def _wait(self, seconds: float, report: dict[str, Any]) -> None:
        """Wait between polls, but never past the owner's patience."""
        if self._sleep is not None:
            self._sleep(seconds)
            return
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop.get("requested"):
                return
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))


def run_goal_step(
    loop: GoalLoop,
    goal_id: str,
    action: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience: one gated, bounded step against an existing loop.

    Only the binding options are accepted here; the loop itself is always passed in.
    """
    binding_keys = {
        "state_root",
        "readings",
        "ledger_state_dir",
        "sleep",
        "interval_s",
        "max_polls",
        "now_fn",
    }
    confirm = kwargs.pop("confirm", True)
    rest = kwargs.pop("rest_observation_ids", None)
    preconditions = tuple(kwargs.pop("preconditions", ()))
    binding_kwargs = {k: v for k, v in kwargs.items() if k in binding_keys}
    unknown = sorted(set(kwargs) - binding_keys)
    if unknown:
        raise TypeError(f"run_goal_step got unexpected keyword(s): {', '.join(unknown)}")
    binding = AdaptiveStepBinding(loop, **binding_kwargs)
    return binding.run_step(
        goal_id, action, preconditions=preconditions, confirm=confirm,
        rest_observation_ids=rest,
    )


def load_step_request(
    path: Path | str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Read one owner-provided step request.

    Shape: ``{"goal": {...}, "action": {...}, "preconditions": ["locomotion", ...]}``.
    The preconditions list is where the caller declares what the action depends on, so
    the planning gate has something true to check instead of an assumption.

    A file is the whole storage story on purpose: the binding keeps no goal store of
    its own, so a second coordinator cannot grow here by accident.
    """
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("a step request must be a JSON object")
    goal = payload.get("goal")
    action = payload.get("action")
    if not isinstance(goal, dict) or not isinstance(action, dict):
        raise ValueError("a step request needs both 'goal' and 'action' objects")
    declared = payload.get("preconditions") or []
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Sequence):
        raise ValueError("'preconditions' must be a list of capability names")
    preconditions = [str(p) for p in declared]
    return goal, action, preconditions
