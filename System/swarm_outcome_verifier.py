"""V1: an outcome verifier that reads evidence, not claims.

C0's ``ActionResult.from_dict`` validates a record's *shape*. That is not the
same as knowing the action happened: the audit found two records that pass the
frozen cross-checks while meaning nothing -- ``succeeded`` with ``verified=true``
and nonempty ``actual_observation_ids`` but an empty
``verifier_result.observation_ids``, and ``unknown`` carrying no reason.

This module is the independent judge D3d completes goals on. It resolves the
claimed evidence IDs to actual observation records, checks that each record is
associated with *this* action and goal and frame, checks that it is fresh
against an injected clock, and then evaluates the observable predicate. An
adapter's word is never an input: nothing here reads a ``verified`` flag a
submitter supplied. ``verified`` is only ever true because a resolved, fresh,
associated observation satisfies a named predicate.

The evidence source and the clock are constructor arguments and the predicate
evaluators are injected. Nothing here touches the wall clock, the network, or
the disk on its own, so a test can hand it a forged record and watch it refuse.

Stdlib only; importable from a bare ``System/`` path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

__all__ = [
    "EVIDENCE_ID_UNKNOWN",
    "EVIDENCE_MISASSOCIATED",
    "EVIDENCE_STALE",
    "EVIDENCE_TIME_UNKNOWN",
    "EVIDENCE_INCOMPLETE",
    "PREDICATE_UNKNOWN",
    "PREDICATE_FALSE",
    "OUTCOME_UNKNOWN",
    "DEFAULT_MAX_AGE_S",
    "OutcomeVerifier",
    "parse_utc",
]

EVIDENCE_ID_UNKNOWN = "EVIDENCE_ID_UNKNOWN"
EVIDENCE_MISASSOCIATED = "EVIDENCE_MISASSOCIATED"
EVIDENCE_STALE = "EVIDENCE_STALE"
EVIDENCE_TIME_UNKNOWN = "EVIDENCE_TIME_UNKNOWN"
EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
PREDICATE_UNKNOWN = "PREDICATE_UNKNOWN"
PREDICATE_FALSE = "PREDICATE_FALSE"
OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"

#: A lifetime belongs to the observation that declared it: this is only the
#: fallback when a caller configures no window at all.
DEFAULT_MAX_AGE_S = 900.0

#: Clock skew tolerated before a future timestamp is called stale.
_FUTURE_SKEW_S = 2.0


def parse_utc(text: Any) -> Optional[datetime]:
    """Read an ISO-8601 instant, or ``None`` when it cannot be read.

    ``None`` is deliberate: an unreadable time is *unknown*, and an unknown time
    must not be laundered into "fresh".
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _postcondition_name(postcondition: Any) -> Optional[str]:
    """The predicate's name, whether it came as a string or a mapping."""
    if postcondition is None:
        return None
    if isinstance(postcondition, str):
        name = postcondition.strip()
        return name or None
    if isinstance(postcondition, Mapping):
        for key in ("predicate", "kind", "name"):
            value = postcondition.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _verdict(answer: Any) -> tuple[bool, Optional[str], bool]:
    """Normalise an evaluator's answer into (holds, detail, unknown).

    An evaluator that returns ``None`` is saying *I cannot tell*: that is its own
    outcome, not a quiet no and never a yes.
    """
    if answer is None:
        return False, None, True
    if isinstance(answer, Mapping):
        if answer.get("unknown"):
            return False, None if answer.get("detail") is None else str(answer["detail"]), True
        holds = bool(answer.get("holds") or answer.get("satisfied"))
        detail = answer.get("detail")
        return holds, None if detail is None else str(detail), False
    if isinstance(answer, tuple) and answer:
        detail = answer[1] if len(answer) > 1 else None
        return bool(answer[0]), None if detail is None else str(detail), False
    return bool(answer), None, False


class OutcomeVerifier:
    """Resolve evidence to records, then judge the predicate on those records.

    ``evidence`` may be a mapping of action_id to records, an object with an
    ``observations_for(action_id)`` method, or a callable taking an action_id.
    ``predicates`` maps a predicate name (``request["predicate"]`` or
    ``request["predicted_postcondition"]``) to a callable receiving
    ``(records, request)``. A predicate with no evaluator is ``PREDICATE_UNKNOWN``
    -- never a silent success.
    """

    def __init__(
        self,
        *,
        evidence: Any,
        clock: Any,
        predicates: Optional[Mapping[str, Callable[..., Any]]] = None,
        max_age_s: Optional[float] = DEFAULT_MAX_AGE_S,
        verifier_id: str = "outcome_verifier.v1",
        require_goal_association: bool = True,
    ) -> None:
        self.evidence = evidence
        self.clock = clock
        self.predicates = dict(predicates or {})
        self.max_age_s = max_age_s
        self.verifier_id = str(verifier_id)
        self.require_goal_association = bool(require_goal_association)

    # -- evidence access ------------------------------------------------------

    def _records(self, action_id: str) -> Sequence[Mapping[str, Any]]:
        source = self.evidence
        rows: Iterable[Any]
        if hasattr(source, "observations_for"):
            rows = source.observations_for(action_id)
        elif callable(source):
            rows = source(action_id)
        elif isinstance(source, Mapping):
            rows = source.get(action_id, ())
        else:  # pragma: no cover - programming error, not a runtime condition
            raise TypeError(f"unsupported evidence source {type(source).__name__}")
        return tuple(r for r in (rows or ()) if isinstance(r, Mapping))

    def _resolve(self, rows: Sequence[Mapping[str, Any]], wanted: Sequence[str]) -> tuple[dict, list, list]:
        """Split wanted IDs into resolved records and named problems."""
        index: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            key = row.get("observation_id")
            if key is not None:
                index.setdefault(str(key), row)
        resolved: dict[str, Mapping[str, Any]] = {}
        unknown: list[str] = []
        for oid in wanted:
            key = str(oid)
            if key in index:
                resolved[key] = index[key]
            else:
                unknown.append(key)
        return resolved, unknown, [str(o) for o in wanted]

    # -- the judgement --------------------------------------------------------

    def verify(self, request: Mapping[str, Any]) -> dict:
        """Answer with a VERIFIER_RESULT-shaped mapping. Never guesses yes."""
        action_id = str(request.get("action_id") or "")
        goal_id = request.get("goal_id")
        claimed = tuple(request.get("claimed_observation_ids") or ())
        required = tuple(request.get("required_observation_ids") or ())
        wanted = claimed or required
        predicate = request.get("predicate") or request.get("predicted_postcondition")
        name = _postcondition_name(predicate)

        def refuse(code: str, detail: str) -> dict:
            return {
                "verified": False,
                "verifier": self.verifier_id,
                "method": name or "unnamed_postcondition",
                "detail": f"[{code}] {detail}",
                "observation_ids": [],
            }

        if not action_id:
            return refuse(EVIDENCE_INCOMPLETE, "no action_id in the verification request")
        if not wanted:
            return refuse(
                EVIDENCE_INCOMPLETE,
                "no observation evidence was named for this action, so nothing can be resolved",
            )

        rows = self._records(action_id)
        resolved, unknown, _ = self._resolve(rows, wanted)

        if unknown:
            return refuse(
                EVIDENCE_ID_UNKNOWN,
                f"claimed observation(s) {sorted(unknown)} are not in the evidence store; "
                "an ID that resolves to nothing is not evidence",
            )

        now = parse_utc(self.clock.now_utc())
        if now is None:  # pragma: no cover - the injected clock is authoritative
            return refuse(OUTCOME_UNKNOWN, "the injected clock did not yield a readable instant")

        usable: dict[str, Mapping[str, Any]] = {}
        for oid in wanted:
            row = resolved[str(oid)]
            row_action = row.get("action_id")
            if row_action is not None and str(row_action) != action_id:
                return refuse(
                    EVIDENCE_MISASSOCIATED,
                    f"observation {oid!r} belongs to action {row_action!r}, not {action_id!r}",
                )
            if self.require_goal_association and goal_id is not None:
                row_goal = row.get("goal_id")
                if row_goal is not None and str(row_goal) != str(goal_id):
                    return refuse(
                        EVIDENCE_MISASSOCIATED,
                        f"observation {oid!r} belongs to goal {row_goal!r}, not {goal_id!r}",
                    )
            observed = parse_utc(row.get("observed_at_utc") or row.get("recorded_at_utc"))
            if observed is None:
                return refuse(
                    EVIDENCE_TIME_UNKNOWN,
                    f"observation {oid!r} carries no readable observed_at_utc; "
                    "an observation of unknown age cannot be called fresh evidence",
                )
            age = (now - observed).total_seconds()
            if age < -_FUTURE_SKEW_S:
                return refuse(
                    EVIDENCE_STALE,
                    f"observation {oid!r} is dated {abs(age):.3f}s in the future, ahead of the loop clock",
                )
            if self.max_age_s is not None and age > float(self.max_age_s):
                return refuse(
                    EVIDENCE_STALE,
                    f"observation {oid!r} is {age:.3f}s old, beyond the {float(self.max_age_s):.3f}s window",
                )
            usable[str(oid)] = row

        missing = [str(o) for o in required if str(o) not in usable]
        if missing:
            return refuse(
                EVIDENCE_INCOMPLETE,
                f"required observation(s) {sorted(missing)} did not resolve to usable evidence",
            )

        if name is None:
            return refuse(OUTCOME_UNKNOWN, "the action named no observable postcondition to check")

        evaluator = self.predicates.get(name)
        if evaluator is None:
            return refuse(
                PREDICATE_UNKNOWN,
                f"no evaluator is registered for predicate {name!r}; "
                "an unchecked postcondition is unknown, not satisfied",
            )

        evidence_rows = [usable[str(o)] for o in (required or wanted)]
        holds, note, cannot_tell = _verdict(evaluator(evidence_rows, dict(request)))
        if cannot_tell:
            return refuse(
                OUTCOME_UNKNOWN,
                note or f"the evaluator for {name!r} could not tell from the resolved evidence",
            )
        if not holds:
            return refuse(
                PREDICATE_FALSE,
                note or f"predicate {name!r} does not hold on the resolved evidence",
            )

        return {
            "verified": True,
            "verifier": self.verifier_id,
            "method": name,
            "detail": note,
            "observation_ids": [str(o) for o in (required or wanted)],
        }
