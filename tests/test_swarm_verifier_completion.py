"""D3d: verifier-driven completion -- check first, then call it done.

The law under test: an adapter saying "succeeded" never completes anything. A
goal becomes complete only when a verifier that is not the submitting component
answers with named observation evidence, and the frozen ActionResult that
records that evidence is on disk before the goal is marked done.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_action_journal import ActionJournal  # noqa: E402
from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    CompletionRefused,
    GoalLoop,
    ManualClock,
    VerificationIntegrityError,
)

SHA = "sha256:" + "d" * 64


def _gid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3d.goal.{label}"))


def _aid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3d.action.{label}"))


def _goal(label: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "goal_id": _gid(label),
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
        "revision_history": [{"revision": 0, "at_utc": "2026-01-01T00:00:00Z", "change": "created"}],
        "created_at_utc": "2026-01-01T00:00:00Z",
    }


def _proposal(label: str, goal_label: str = "root") -> dict:
    return {
        "schema_version": "1.0.0",
        "action_id": _aid(label),
        "goal_id": _gid(goal_label),
        "adapter_id": "nav2",
        "capability_revision": SHA,
        "action_kind": "navigate_to_pose",
        "args": {"x_m": 1.0},
        "required_observation_ids": ["obs-1"],
        "predicted_postcondition": "at_pose",
        "predicted_uncertainty": 0.1,
        "predicted_cost": [],
        "cancellation_behavior": "stop",
        "recovery_behavior": "replan",
        "created_at_utc": "2026-01-01T00:00:00Z",
    }


class _Adapter:
    adapter_id = "nav2"

    def __init__(self, *, receipt: str = "receipt-9") -> None:
        self.receipt = receipt
        self.submit_calls = 0

    def probe(self):
        return {}

    def observe(self, cursor):
        return {}

    def submit(self, action):
        self.submit_calls += 1
        return self.receipt

    def status(self, action_id):
        return {"status": "succeeded"}

    def cancel(self, action_id):
        return True

    def recover(self, checkpoint):
        return True


class _Verifier:
    """A verifier whose answer a test owns. Never the component that submitted."""

    def __init__(self, answer) -> None:
        self.answer = answer
        self.requests: list = []

    def verify(self, request):
        self.requests.append(dict(request))
        if isinstance(self.answer, Exception):
            raise self.answer
        if callable(self.answer):
            return self.answer(request)
        return self.answer


_CONFIRMED = {
    "verified": True,
    "verifier": "camera_postcondition",
    "method": "april_tag_at_dock",
    "detail": "tag 7 seen in the dock frame",
    "observation_ids": ["obs-1", "obs-2"],
}


def _loop(tmp_path: Path, *, verifier, adapter=None, journal=None) -> GoalLoop:
    return GoalLoop(
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", adapter or _Adapter(), capability_revision=SHA),
        clock=ManualClock(),
        verifier=verifier,
        journal=journal if journal is not None else ActionJournal(tmp_path),
    )


def _submitted(tmp_path: Path, *, verifier, adapter=None) -> GoalLoop:
    """A loop with one action durably submitted, the adapter claiming success.

    The claim arrives the way a real one does -- through reconciliation -- and
    it is emphatically *not* an ActionResult: the frozen C0 contract refuses a
    `succeeded` ActionResult carrying no verified result, so the adapter's word
    waits in the claim slot until a verifier supplies evidence.
    """
    loop = _loop(tmp_path, verifier=verifier, adapter=adapter)
    loop.propose(_proposal("act"))
    loop.submit(_aid("act"))
    loop.reconcile(_aid("act"))
    return loop


# --- the core law -------------------------------------------------------------


def test_an_adapters_success_claim_alone_does_not_complete_the_goal(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))

    assert loop.completed == ()
    assert loop.unverified_successes() == (_aid("act"),)


def test_a_confirmed_postcondition_completes_the_goal(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))

    report = loop.require_confirmed(_aid("act"))

    assert report["verified"] is True
    assert report["completed"] is True
    assert loop.completed == (_gid("root"),)
    assert loop.unverified_successes() == ()


def test_the_verifier_is_asked_about_this_action_and_its_evidence(tmp_path: Path) -> None:
    verifier = _Verifier(_CONFIRMED)
    loop = _submitted(tmp_path, verifier=verifier)

    loop.confirm(_aid("act"))

    assert verifier.requests[0]["action_id"] == _aid("act")
    assert verifier.requests[0]["goal_id"] == _gid("root")
    assert verifier.requests[0]["predicted_postcondition"] == "at_pose"
    assert verifier.requests[0]["required_observation_ids"] == ["obs-1"]


def test_an_unconfirmed_verdict_leaves_the_goal_incomplete(tmp_path: Path) -> None:
    answer = {
        "verified": False,
        "verifier": "camera_postcondition",
        "method": "april_tag_at_dock",
        "detail": "tag not visible",
        "observation_ids": [],
    }
    loop = _submitted(tmp_path, verifier=_Verifier(answer))

    report = loop.confirm(_aid("act"))

    assert report["completed"] is False
    assert report["verified"] is False
    assert report["detail"] == "tag not visible"
    assert loop.completed == ()
    assert loop.unverified_successes() == (_aid("act"),)


def test_the_strict_path_raises_instead_of_returning_an_incomplete_goal(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier({"verified": False, "verifier": "v", "method": "m", "detail": None, "observation_ids": []}))

    with pytest.raises(CompletionRefused) as excinfo:
        loop.require_confirmed(_aid("act"))

    assert excinfo.value.code == "UNVERIFIED_SUCCESS"
    assert loop.completed == ()


def test_the_null_verifier_never_completes_anything(tmp_path: Path) -> None:
    """An unwired loop degrades into 'unverified', not into 'assumed fine'."""
    loop = GoalLoop(  # no verifier injected at all
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", _Adapter(), capability_revision=SHA),
        clock=ManualClock(),
        journal=ActionJournal(tmp_path),
    )
    loop.propose(_proposal("act"))
    loop.submit(_aid("act"))

    report = loop.confirm(_aid("act"))

    assert report["verified"] is False
    assert report["completed"] is False
    assert loop.completed == ()


# --- the evidence is durable --------------------------------------------------


def test_the_frozen_result_row_is_written_before_the_completion(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))

    loop.require_confirmed(_aid("act"))

    kinds = [row.kind for row in loop.journal.history(_aid("act"))]
    assert kinds.index("result") < kinds.index("completion")
    assert loop.journal.summary()["chain_ok"] is True


def test_the_completion_row_names_the_verifier_and_the_observations(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))

    loop.require_confirmed(_aid("act"))

    row = loop.journal.latest(_aid("act"), "completion")
    assert row.goal_id == _gid("root")
    assert row.payload["verifier"] == "camera_postcondition"
    assert row.payload["method"] == "april_tag_at_dock"
    assert row.payload["observation_ids"] == ["obs-1", "obs-2"]
    assert row.payload["verified"] is True


def test_a_confirmed_result_is_a_contract_valid_result_not_an_ad_hoc_dict(tmp_path: Path) -> None:
    from System.swarm_adaptive_contracts import ActionResult

    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))

    report = loop.require_confirmed(_aid("act"))
    frozen = report["result"]

    assert ActionResult.from_dict(frozen).to_dict() == frozen
    assert frozen["status"] == "succeeded"
    assert frozen["actual_observation_ids"] == ["obs-1", "obs-2"]
    assert frozen["verifier_result"]["verified"] is True
    assert frozen["effect_receipt_id"] == "receipt-9"
    assert frozen["cost"] is None  # an unreported cost is unknown, not zero


def test_a_result_with_no_observation_behind_it_cannot_be_recorded_as_verified(tmp_path: Path) -> None:
    forged = {
        "verified": True,
        "verifier": "self_report",
        "method": "trust_me",
        "detail": "I am sure",
        "observation_ids": [],
    }
    loop = _submitted(tmp_path, verifier=_Verifier(forged))

    with pytest.raises(VerificationIntegrityError) as excinfo:
        loop.confirm(_aid("act"))

    assert excinfo.value.code == "UNEVIDENCED_SUCCESS"
    assert loop.completed == ()
    assert loop.journal.latest(_aid("act"), "verification").payload["outcome"] == "refused"


def test_the_refused_forgery_attempt_is_visible_on_disk(tmp_path: Path) -> None:
    forged = {"verified": True, "verifier": "self_report", "method": "trust_me", "detail": None, "observation_ids": []}
    loop = _submitted(tmp_path, verifier=_Verifier(forged))
    with pytest.raises(VerificationIntegrityError):
        loop.confirm(_aid("act"))

    restarted = ActionJournal(tmp_path)

    assert restarted.summary()["chain_ok"] is True
    assert restarted.latest(_aid("act"), "verification").payload["verified"] is None
    assert "UNEVIDENCED_SUCCESS" in restarted.latest(_aid("act"), "verification").payload["detail"]


def test_a_verifier_verdict_is_recorded_even_when_it_refuses(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier({"verified": False, "verifier": "v", "method": "m", "detail": "no", "observation_ids": []}))

    loop.confirm(_aid("act"))

    assert loop.journal.latest(_aid("act"), "verification").payload["outcome"] == "not_confirmed"


# --- restart, duplication, and refusal boundaries -----------------------------


def test_a_completion_survives_a_restart_as_a_fact(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))
    loop.require_confirmed(_aid("act"))

    fresh = GoalLoop(
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", _Adapter(), capability_revision=SHA),
        clock=ManualClock(),
        verifier=_Verifier(_CONFIRMED),
        journal=ActionJournal(tmp_path),
    )

    assert fresh.completed == ()  # memory is gone
    assert fresh.confirmed_actions() == (_aid("act"),)  # the fact is not


def test_completing_twice_does_not_write_a_second_completion(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(_CONFIRMED))
    loop.require_confirmed(_aid("act"))

    second = loop.require_confirmed(_aid("act"))

    assert second["already_completed"] is True
    rows = [row for row in loop.journal.history(_aid("act")) if row.kind == "completion"]
    assert len(rows) == 1


def test_completion_without_a_journal_is_refused(tmp_path: Path) -> None:
    loop = GoalLoop(
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", _Adapter(), capability_revision=SHA),
        clock=ManualClock(),
        verifier=_Verifier(_CONFIRMED),
    )
    loop.propose(_proposal("act"))

    with pytest.raises(CompletionRefused) as excinfo:
        loop.confirm(_aid("act"))

    assert excinfo.value.code == "NO_JOURNAL"
    assert loop.completed == ()


def test_an_action_that_was_never_submitted_has_nothing_to_confirm(tmp_path: Path) -> None:
    loop = _loop(tmp_path, verifier=_Verifier(_CONFIRMED))
    loop.propose(_proposal("act"))

    with pytest.raises(CompletionRefused) as excinfo:
        loop.confirm(_aid("act"))

    assert excinfo.value.code == "UNJOURNALLED_ACTION"


def test_an_unknown_action_is_refused(tmp_path: Path) -> None:
    loop = _loop(tmp_path, verifier=_Verifier(_CONFIRMED))

    with pytest.raises(CompletionRefused) as excinfo:
        loop.confirm(_aid("ghost"))

    assert excinfo.value.code == "UNKNOWN_ACTION"


def test_a_verifier_that_raises_does_not_complete_the_goal(tmp_path: Path) -> None:
    loop = _submitted(tmp_path, verifier=_Verifier(RuntimeError("camera driver died")))

    with pytest.raises(RuntimeError):
        loop.confirm(_aid("act"))

    assert loop.completed == ()
    assert loop.unverified_successes() == (_aid("act"),)


def test_completion_uses_the_verified_observations_not_the_predicted_ones(tmp_path: Path) -> None:
    verified_elsewhere = {
        "verified": True,
        "verifier": "camera_postcondition",
        "method": "april_tag_at_dock",
        "detail": "tag 7",
        "observation_ids": ["obs-99"],
    }
    loop = _submitted(tmp_path, verifier=_Verifier(verified_elsewhere))

    report = loop.require_confirmed(_aid("act"))

    assert report["result"]["actual_observation_ids"] == ["obs-99"]
    assert report["result"]["verifier_result"]["observation_ids"] == ["obs-99"]
