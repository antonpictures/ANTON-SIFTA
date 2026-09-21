"""V1: evidence, not claims, decides. Wrong, stale and forged evidence must fail.

The audit's P2 finding was that C0 ``ActionResult.from_dict`` accepts two records
that pass its cross-checks while meaning nothing. Shape validation is therefore
not outcome verification, and this suite pins the difference: an observation ID
that resolves to no record, a record from another action or goal, a record older
than the configured window, a record with no readable time, and a postcondition
with no evaluator all fail to confirm. A submitter's own ``verified=true`` is
never an input.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalLoop,
    ManualClock,
)
from System.swarm_action_journal import ActionJournal  # noqa: E402
from System.swarm_outcome_verifier import (  # noqa: E402
    EVIDENCE_ID_UNKNOWN,
    EVIDENCE_INCOMPLETE,
    EVIDENCE_MISASSOCIATED,
    EVIDENCE_STALE,
    EVIDENCE_TIME_UNKNOWN,
    OUTCOME_UNKNOWN,
    PREDICATE_FALSE,
    PREDICATE_UNKNOWN,
    OutcomeVerifier,
)

SHA = "sha256:" + "e" * 64
NOW = "2026-01-01T12:00:00Z"

AID = str(uuid.uuid5(uuid.NAMESPACE_URL, "v1.action.act"))
GID = str(uuid.uuid5(uuid.NAMESPACE_URL, "v1.goal.root"))
OTHER_AID = str(uuid.uuid5(uuid.NAMESPACE_URL, "v1.action.other"))
OTHER_GID = str(uuid.uuid5(uuid.NAMESPACE_URL, "v1.goal.other"))


def _observation(oid: str, *, at: str = NOW, action_id: str = AID, goal_id: str = GID, pose=None) -> dict:
    return {
        "observation_id": oid,
        "action_id": action_id,
        "goal_id": goal_id,
        "observed_at_utc": at,
        "pose": {"x": 1.0, "y": 2.0} if pose is None else pose,
    }


def _request(**over) -> dict:
    request = {
        "action_id": AID,
        "goal_id": GID,
        "action_kind": "navigate_to_dock",
        "predicted_postcondition": "at_pose",
        "required_observation_ids": ["obs-1"],
    }
    request.update(over)
    return request


def _at_pose(records, request):  # noqa: ANN001, ARG001 - injected evaluator
    for record in records:
        pose = record.get("pose") or {}
        if abs(float(pose.get("x", 0.0)) - 1.0) > 0.05:
            return {"holds": False, "detail": f"x={pose.get('x')} is not the dock"}
    return {"holds": True, "detail": "pose within tolerance"}


def _verifier(rows, *, max_age_s=900.0, predicates=None) -> OutcomeVerifier:
    return OutcomeVerifier(
        evidence={AID: rows},
        clock=ManualClock(utc=NOW),
        predicates={"at_pose": _at_pose} if predicates is None else predicates,
        max_age_s=max_age_s,
    )


# -- the confirming case ----------------------------------------------------


def test_fresh_associated_evidence_satisfying_the_predicate_confirms() -> None:
    answer = _verifier([_observation("obs-1")]).verify(_request())

    assert answer["verified"] is True
    assert answer["method"] == "at_pose"
    assert answer["verifier"] == "outcome_verifier.v1"
    assert answer["observation_ids"] == ["obs-1"]
    assert answer["detail"] == "pose within tolerance"


# -- wrong evidence ---------------------------------------------------------


def test_an_id_that_resolves_to_no_record_cannot_confirm() -> None:
    answer = _verifier([_observation("obs-9")]).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_ID_UNKNOWN in answer["detail"]
    assert "obs-1" in answer["detail"]
    assert answer["observation_ids"] == []


def test_a_record_from_another_action_cannot_confirm() -> None:
    rows = [_observation("obs-1", action_id=OTHER_AID)]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_MISASSOCIATED in answer["detail"]
    assert OTHER_AID in answer["detail"]


def test_a_record_from_another_goal_cannot_confirm() -> None:
    rows = [_observation("obs-1", goal_id=OTHER_GID)]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_MISASSOCIATED in answer["detail"]
    assert OTHER_GID in answer["detail"]


def test_required_evidence_the_claim_did_not_name_cannot_confirm() -> None:
    request = _request(claimed_observation_ids=["obs-1"], required_observation_ids=["obs-1", "obs-2"])

    answer = _verifier([_observation("obs-1")]).verify(request)

    assert answer["verified"] is False
    assert EVIDENCE_INCOMPLETE in answer["detail"]
    assert "obs-2" in answer["detail"]


def test_no_named_evidence_at_all_cannot_confirm() -> None:
    request = _request(required_observation_ids=[])

    answer = _verifier([_observation("obs-1")]).verify(request)

    assert answer["verified"] is False
    assert EVIDENCE_INCOMPLETE in answer["detail"]


# -- stale / undated evidence ----------------------------------------------


def test_evidence_older_than_the_window_cannot_confirm() -> None:
    rows = [_observation("obs-1", at="2026-01-01T11:00:00Z")]  # exactly 3600s old

    answer = _verifier(rows, max_age_s=900.0).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_STALE in answer["detail"]
    assert "3600.000s" in answer["detail"]


def test_the_same_record_confirms_when_the_window_admits_it() -> None:
    rows = [_observation("obs-1", at="2026-01-01T11:00:00Z")]

    assert _verifier(rows, max_age_s=7200.0).verify(_request())["verified"] is True


def test_evidence_dated_ahead_of_the_clock_cannot_confirm() -> None:
    rows = [_observation("obs-1", at="2026-01-01T13:00:00Z")]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_STALE in answer["detail"]
    assert "future" in answer["detail"]


def test_evidence_with_no_readable_time_cannot_confirm() -> None:
    rows = [_observation("obs-1", at="not-a-time")]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_TIME_UNKNOWN in answer["detail"]


def test_evidence_with_no_time_field_cannot_confirm() -> None:
    rows = [{"observation_id": "obs-1", "action_id": AID, "goal_id": GID}]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert EVIDENCE_TIME_UNKNOWN in answer["detail"]


# -- forged success ---------------------------------------------------------


def test_a_submitters_own_verified_flag_is_not_an_input() -> None:
    """An adapter-shaped record that asserts its own success changes nothing."""
    rows = [
        {
            "observation_id": "ghost",
            "action_id": AID,
            "goal_id": GID,
            "observed_at_utc": NOW,
            "verified": True,
            "actual_observation_ids": ["ghost"],
        }
    ]
    request = _request(
        claimed_observation_ids=["ghost"],
        required_observation_ids=["ghost"],
        claimed_verified=True,
        verifier_result={"verified": True, "observation_ids": []},
    )

    answer = _verifier(rows).verify(request)

    # 'ghost' resolves and the submitter declares it verified, but no path here
    # reads that declaration: the postcondition is judged on the record itself,
    # and this record does not show the dock pose.
    assert answer["verified"] is False
    assert PREDICATE_FALSE in answer["detail"]


def test_a_forged_success_naming_an_unresolvable_id_cannot_confirm() -> None:
    request = _request(claimed_observation_ids=["ghost"], claimed_verified=True)

    answer = _verifier([_observation("obs-1")]).verify(request)

    assert answer["verified"] is False
    assert EVIDENCE_ID_UNKNOWN in answer["detail"]


# -- unknown postconditions -------------------------------------------------


def test_a_postcondition_with_no_evaluator_cannot_confirm() -> None:
    answer = _verifier([_observation("obs-1")], predicates={}).verify(_request())

    assert answer["verified"] is False
    assert PREDICATE_UNKNOWN in answer["detail"]
    assert "at_pose" in answer["detail"]


def test_an_action_naming_no_postcondition_is_unknown() -> None:
    request = _request(predicted_postcondition=None)

    answer = _verifier([_observation("obs-1")]).verify(request)

    assert answer["verified"] is False
    assert OUTCOME_UNKNOWN in answer["detail"]


def test_an_evaluator_that_cannot_tell_is_unknown_not_a_quiet_no() -> None:
    def cannot_tell(records, request):  # noqa: ANN001, ARG001
        return None

    answer = _verifier([_observation("obs-1")], predicates={"at_pose": cannot_tell}).verify(_request())

    assert answer["verified"] is False
    assert OUTCOME_UNKNOWN in answer["detail"]


def test_an_evaluator_refusing_the_evidence_carries_its_reason() -> None:
    rows = [_observation("obs-1", pose={"x": 9.0, "y": 2.0})]

    answer = _verifier(rows).verify(_request())

    assert answer["verified"] is False
    assert PREDICATE_FALSE in answer["detail"]
    assert "x=9.0" in answer["detail"]


# -- the loop end to end ----------------------------------------------------


class _Adapter:
    adapter_id = "dock_body"

    def __init__(self) -> None:
        self.submitted = 0

    def probe(self):
        return {}

    def observe(self, cursor):  # noqa: ANN001, ARG002
        return {}

    def submit(self, proposal):  # noqa: ANN001, ARG002
        self.submitted += 1
        return "receipt-v1"

    def status(self, action_id):  # noqa: ANN001, ARG002
        return {"status": "succeeded"}

    def cancel(self, action_id):  # noqa: ANN001, ARG002
        return True

    def recover(self, checkpoint):  # noqa: ANN001, ARG002
        return True


def _goal() -> dict:
    return {
        "schema_version": "1.0.0",
        "goal_id": GID,
        "owner_provenance": {"source": "owner", "owner_authorized": True, "task_id": "t1"},
        "task_family": "nav",
        "desired_observable": "at_dock",
        "predicate": "at_pose",
        "deadline_utc": None,
        "budget": None,
        "dependency_ids": [],
        "active_subgoal": None,
        "progress_condition": "progress",
        "failure_condition": "failure",
        "checkpoint_ref": None,
        "revision_history": [{"revision": 0, "at_utc": NOW, "change": "created"}],
        "created_at_utc": NOW,
    }


def _proposal() -> dict:
    return {
        "schema_version": "1.0.0",
        "action_id": AID,
        "goal_id": GID,
        "adapter_id": "dock_body",
        "capability_revision": SHA,
        "action_kind": "navigate_to_pose",
        "args": {"x_m": 1.0},
        "required_observation_ids": ["obs-1"],
        "predicted_postcondition": "at_pose",
        "predicted_uncertainty": 0.1,
        "predicted_cost": [],
        "cancellation_behavior": "stop",
        "recovery_behavior": "replan",
        "created_at_utc": NOW,
    }


def _loop(tmp_path: Path, verifier) -> GoalLoop:  # noqa: ANN001
    loop = GoalLoop(
        graph=[_goal()],
        adapter=AdapterBinding.bind("dock_body", _Adapter(), capability_revision=SHA),
        verifier=verifier,
        clock=ManualClock(utc=NOW),
        journal=ActionJournal(tmp_path),
    )
    loop.propose(_proposal())
    loop.submit(AID)
    loop.reconcile(AID)  # the adapter now claims success; it is only a claim
    return loop


def test_a_stale_observation_cannot_complete_a_goal(tmp_path: Path) -> None:
    rows = [_observation("obs-1", at="2026-01-01T11:30:00Z")]  # 1800s old
    loop = _loop(tmp_path, _verifier(rows, max_age_s=900.0))

    report = loop.confirm(AID)

    assert report["completed"] is False
    assert EVIDENCE_STALE in report["detail"]
    assert loop.completed == ()
    assert loop.unverified_successes() == (AID,)


def test_a_wrong_id_cannot_complete_a_goal(tmp_path: Path) -> None:
    loop = _loop(tmp_path, _verifier([_observation("obs-7")]))

    report = loop.confirm(AID)

    assert report["completed"] is False
    assert EVIDENCE_ID_UNKNOWN in report["detail"]
    assert loop.completed == ()


def test_fresh_evidence_completes_the_goal_once(tmp_path: Path) -> None:
    loop = _loop(tmp_path, _verifier([_observation("obs-1")]))

    first = loop.confirm(AID)
    second = loop.confirm(AID)

    assert first["completed"] is True
    assert first["result"]["verifier_result"]["verified"] is True
    assert first["result"]["actual_observation_ids"] == ["obs-1"]
    assert loop.completed == (GID,)
    assert loop.unverified_successes() == ()
    # The second call reports the same completion from the journal rather than
    # performing a second one.
    assert second["already_completed"] is True
    assert second["result"]["action_id"] == first["result"]["action_id"]
    assert second["result"]["verifier_result"] == first["result"]["verifier_result"]


def test_the_refusal_is_journalled_as_a_verification_that_did_not_confirm(tmp_path: Path) -> None:
    rows = [_observation("obs-1", at="2026-01-01T00:00:00Z")]
    loop = _loop(tmp_path, _verifier(rows, max_age_s=900.0))

    loop.confirm(AID)

    rows_written = [r for r in loop.journal.rows if r.kind == "verification"]
    assert len(rows_written) == 1
    assert rows_written[0].payload["verified"] is False
    assert rows_written[0].payload["outcome"] == "not_confirmed"
    assert EVIDENCE_STALE in rows_written[0].payload["detail"]
