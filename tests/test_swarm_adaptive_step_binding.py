"""D3f: the invocation path — a real action reaches the loop, once, bounded.

What this file is trying to falsify, clause by clause, from the audit:

* the corrected D1/R1 planning view must be consumed **before a dependent action
  acts**, not once at startup and not only by a status dashboard -- a body whose
  organ is gone must not be handed an action that needs that organ, and an organ
  the body has *never reported* must block the action too;
* a step must be bounded: the default path does not wait at all, an explicit poll
  budget terminates with ``unknown`` instead of waiting forever, and the bound is
  visible in the report rather than implied;
* an owner stop must not queue behind the step -- it reaches the body at the next
  poll boundary and can be issued from outside the step entirely;
* completion must be the loop's verification, never an adapter's report: with no
  verifier able to answer, the step ends ``unknown`` and says so;
* failure, recovery and completion must reach the shared ledgers, and a ledger that
  is down must not turn a real outcome into a failed step.

Nothing here builds its own scheduler or its own loop: the loop is always passed in.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "System") not in sys.path:
    sys.path.insert(0, str(ROOT / "System"))

from swarm_action_journal import ActionJournal  # noqa: E402
from swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalLoop,
    ManualClock,
)
from swarm_adaptive_step_binding import (  # noqa: E402
    OUTCOME_BLOCKED,
    OUTCOME_COMPLETED,
    OUTCOME_STOPPED,
    OUTCOME_UNKNOWN,
    REASON_OUTCOME_UNKNOWN,
    AdaptiveStepBinding,
    load_step_request,
    planning_gate,
    run_goal_step,
)

SHA = "sha256:2d1d055c42d2c8b9d8493bd0839c0169b3191b60ddbcc9891956b219eaa96769"
NOW = "2026-01-01T12:00:00Z"

AID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3f.action.dock"))
GID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3f.goal.root"))

CAP = "locomotion"


# --- fixtures shaped exactly like the frozen contracts ------------------------


def _goal(goal_id=GID):
    return {
        "schema_version": "1.0.0",
        "goal_id": goal_id,
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


def _proposal(action_id=AID):
    return {
        "schema_version": "1.0.0",
        "action_id": action_id,
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


def _action(action_id=AID, *, preconditions=(CAP,)):
    """The shape `planning_view` reads: a name and its preconditions."""
    return {
        "name": "navigate_to_pose",
        "preconditions": list(preconditions),
        "action_id": action_id,
    }


class _Body:
    """A body that answers status however the test asks it to."""

    def __init__(self, *, status="succeeded"):
        self.calls: list = []
        self.status_answer = status

    def probe(self):
        self.calls.append("probe")
        return {"adapter_id": "dock_body", "ready": True}

    def observe(self, action_id):
        self.calls.append(("observe", action_id))
        return []

    def submit(self, proposal):
        self.calls.append(("submit", proposal["action_id"]))
        return {"receipt_id": "r-1", "status": "accepted", "at_utc": NOW}

    def status(self, action_id):
        self.calls.append(("status", action_id))
        return {"status": self.status_answer, "at_utc": NOW}

    def cancel(self, action_id):
        self.calls.append(("cancel", action_id))
        return True

    def recover(self, action_id):
        self.calls.append(("recover", action_id))
        return {"status": "unknown"}

    def submitted(self) -> int:
        return sum(1 for c in self.calls if isinstance(c, tuple) and c[0] == "submit")


class _Verifier:
    """A V1-shaped completion verifier: named evidence, or a refusal."""

    verifier_id = "dock_verifier.v1"

    def __init__(self, *, verified=True):
        self.verified = verified
        self.requests: list = []

    def verify(self, request):
        self.requests.append(dict(request))
        if self.verified:
            return {
                "verified": True,
                "method": "adapter.at_pose",
                "detail": "pose within tolerance of the dock",
                "observation_ids": list(request["required_observation_ids"]),
                "verifier": self.verifier_id,
            }
        return {
            "verified": False,
            "method": "adapter.at_pose",
            "detail": "no pose evidence",
            "observation_ids": [],
            "verifier": self.verifier_id,
        }


def _loop(tmp_path, *, body=None, verifier=None):
    body = body if body is not None else _Body()
    return (
        GoalLoop(
            graph=[_goal()],
            adapter=AdapterBinding.bind("dock_body", body, capability_revision=SHA),
            verifier=verifier,
            clock=ManualClock(utc=NOW),
            journal=ActionJournal(tmp_path / "state"),
        ),
        body,
    )


# --- the planning gate: consumed now, not remembered -------------------------


def test_a_live_organ_allows_the_action(tmp_path):
    gate = planning_gate(
        _action(), state_root=tmp_path, readings={CAP: True}, now=1_767_268_800.0
    )
    assert gate["allowed"] is True
    assert gate["reason_code"] is None
    assert gate["blocked_by"] == []


def test_a_lost_organ_blocks_the_action_with_the_reason(tmp_path):
    gate = planning_gate(
        _action(), state_root=tmp_path, readings={CAP: False}, now=1_767_268_800.0
    )
    assert gate["allowed"] is False
    assert gate["reason_code"]  # the reason the capability was lost, never a blank
    assert gate["blocked_by"] == [CAP]
    assert CAP in gate["detail"]


def test_an_organ_never_reported_by_this_body_blocks_and_owes_a_discovery(tmp_path):
    """On an unfamiliar body the planner must not assume the organ exists."""
    gate = planning_gate(_action(), state_root=tmp_path, readings={}, now=1_767_268_800.0)
    assert gate["allowed"] is False
    assert gate["blocked_by"] == [CAP]
    assert [d["capability"] for d in gate["discovery_required"]] == [CAP]
    assert gate["discovery_required"][0]["state"] == "unreported"


def test_an_unmeasurable_organ_is_unknown_rather_than_failed(tmp_path):
    gate = planning_gate(
        _action(), state_root=tmp_path, readings={CAP: None}, now=1_767_268_800.0
    )
    assert gate["allowed"] is False
    assert [d["state"] for d in gate["discovery_required"]] == ["unknown"]


def test_an_action_with_no_preconditions_is_allowed_on_an_empty_body(tmp_path):
    gate = planning_gate(_action(preconditions=()), state_root=tmp_path, readings={})
    assert gate["allowed"] is True


def test_the_gate_is_asked_every_time_not_answered_from_memory(tmp_path):
    """R1 exists because freshness is the whole point: a cached answer would undo it."""
    first = planning_gate(_action(), state_root=tmp_path, readings={CAP: True})
    second = planning_gate(_action(), state_root=tmp_path, readings={CAP: False})
    assert first["allowed"] is True
    assert second["allowed"] is False


# --- the one invocation path -------------------------------------------------


def test_a_blocked_precondition_never_reaches_the_body(tmp_path):
    loop, body = _loop(tmp_path)
    binding = AdaptiveStepBinding(loop, readings={CAP: False}, state_root=tmp_path)
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_BLOCKED
    assert report["planning"]["allowed"] is False
    assert body.submitted() == 0, "the body was asked to move on a lost organ"
    assert ("status", AID) not in body.calls


def test_a_never_reported_precondition_also_stops_the_action(tmp_path):
    loop, body = _loop(tmp_path)
    binding = AdaptiveStepBinding(loop, readings={}, state_root=tmp_path)
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_BLOCKED
    assert report["planning"]["discovery_required"][0]["state"] == "unreported"
    assert body.submitted() == 0


def test_a_verified_completion_is_reported_as_completed(tmp_path):
    loop, body = _loop(tmp_path, verifier=_Verifier())
    binding = AdaptiveStepBinding(loop, readings={CAP: True}, state_root=tmp_path)
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_COMPLETED
    assert report["actual_observation_ids"] == ["obs-1"]
    assert report["verification"]["completed"] is True
    assert body.submitted() == 1, "one step means one attempt, not two"


def test_an_adapters_success_is_not_a_completion(tmp_path):
    """The adapter says it succeeded; no verifier can confirm it. That is `unknown`."""
    loop, body = _loop(tmp_path, body=_Body(status="succeeded"), verifier=_Verifier(verified=False))
    binding = AdaptiveStepBinding(loop, readings={CAP: True}, state_root=tmp_path)
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_UNKNOWN
    assert report["outcome"] != OUTCOME_COMPLETED
    assert report["reason_code"] == REASON_OUTCOME_UNKNOWN


# --- the bound ---------------------------------------------------------------


def test_the_default_step_does_not_wait_at_all(tmp_path):
    loop, body = _loop(tmp_path, verifier=_Verifier())
    binding = AdaptiveStepBinding(loop, readings={CAP: True}, state_root=tmp_path)
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["max_polls"] == 1
    assert report["interval_s"] == 0.0
    assert report["scheduled_wait_s"] == 0.0
    assert report["polls"] == 1


def test_polling_is_bounded_and_the_bound_is_reported(tmp_path):
    """A body that never answers must not be polled forever."""
    body = _Body(status="running")
    loop, _ = _loop(tmp_path, body=body)
    waits: list = []
    binding = AdaptiveStepBinding(
        loop,
        readings={CAP: True},
        state_root=tmp_path,
        sleep=waits.append,
        max_polls=3,
        interval_s=5.0,
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_UNKNOWN
    assert report["reason_code"] == REASON_OUTCOME_UNKNOWN
    assert report["polls"] == 3, "the poll budget was not honoured"
    assert waits == [5.0, 5.0], "three polls owe at most two bounded waits"
    assert report["scheduled_wait_s"] == 10.0
    assert sum(1 for c in body.calls if isinstance(c, tuple) and c[0] == "status") == 3


def test_a_stop_reaches_the_body_at_the_first_boundary(tmp_path):
    """A stop must not queue behind a slow body: it is issued, not scheduled."""
    body = _Body(status="running")
    loop, _ = _loop(tmp_path, body=body)
    binding: AdaptiveStepBinding

    def stop_now(_seconds):
        binding.request_stop(AID)

    binding = AdaptiveStepBinding(
        loop,
        readings={CAP: True},
        state_root=tmp_path,
        sleep=stop_now,
        max_polls=5,
        interval_s=1.0,
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_STOPPED
    assert report["stop_requested"] is True
    assert ("cancel", AID) in body.calls, "the stop never reached the body"
    assert report["polls"] < 5, "the stop waited for the poll budget to run out"


def test_a_stop_can_be_issued_from_outside_the_step(tmp_path):
    loop, body = _loop(tmp_path)
    binding = AdaptiveStepBinding(loop, readings={CAP: True}, state_root=tmp_path)
    binding.run_step(GID, _proposal(), preconditions=(CAP,))  # the action is now in flight

    report = binding.request_stop(AID)

    assert binding.stop_requested() is True
    assert ("cancel", AID) in body.calls
    assert report["reason_code"]
    assert report["physical_rest"]["confirmed"] in (True, False)


def test_a_second_step_does_not_resend_an_action_already_handed_over(tmp_path):
    """Bounded steps still obey D3b: an attempt is spent once."""
    loop, body = _loop(tmp_path, verifier=_Verifier())
    binding = AdaptiveStepBinding(loop, readings={CAP: True}, state_root=tmp_path)
    first = binding.run_step(GID, _proposal(), preconditions=(CAP,))
    second = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert first["outcome"] == OUTCOME_COMPLETED
    assert body.submitted() == 1, "the body was asked to act twice for one action"
    assert second["outcome"] is not None


# --- the shared ledgers ------------------------------------------------------


def _ledger_text(root: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(root.rglob("*.jsonl"))
    )


def test_a_completion_reaches_the_shared_ledger(tmp_path):
    ledger = tmp_path / "lived"
    loop, _ = _loop(tmp_path, verifier=_Verifier())
    binding = AdaptiveStepBinding(
        loop, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=ledger
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_COMPLETED
    assert report["ledger_error"] is None
    text = _ledger_text(ledger)
    assert "adaptive_step_completed" in text
    assert AID in text


def test_an_unknown_outcome_is_recorded_as_unknown_not_as_failure(tmp_path):
    ledger = tmp_path / "lived"
    loop, _ = _loop(tmp_path, verifier=_Verifier(verified=False))
    binding = AdaptiveStepBinding(
        loop, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=ledger
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_UNKNOWN
    text = _ledger_text(ledger)
    assert "adaptive_step_unknown" in text
    assert '"UNKNOWN"' in text


def test_a_blocked_action_reaches_the_shared_ledger(tmp_path):
    ledger = tmp_path / "lived"
    loop, _ = _loop(tmp_path)
    binding = AdaptiveStepBinding(
        loop, readings={CAP: False}, state_root=tmp_path, ledger_state_dir=ledger
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_BLOCKED
    assert "adaptive_step_blocked" in _ledger_text(ledger)


def test_a_ledger_that_is_down_does_not_turn_a_completion_into_a_failure(tmp_path):
    """The journal already holds the fact; a ledger fault is reported, not fatal."""
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("this is a file, not a state dir\n", encoding="utf-8")
    loop, _ = _loop(tmp_path, verifier=_Verifier())
    binding = AdaptiveStepBinding(
        loop, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=blocker / "sub"
    )
    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_COMPLETED
    assert report["ledger_error"], "the ledger fault was swallowed instead of reported"


# --- the step request, which is the whole storage story ----------------------


def test_a_step_request_round_trips_from_a_file(tmp_path):
    path = tmp_path / "step.json"
    path.write_text(
        json.dumps({"goal": _goal(), "action": _proposal(), "preconditions": [CAP]}),
        encoding="utf-8",
    )
    goal, action, preconditions = load_step_request(path)
    assert goal["goal_id"] == GID
    assert action["action_id"] == AID
    assert preconditions == [CAP]


def test_a_step_request_missing_its_action_is_refused(tmp_path):
    path = tmp_path / "step.json"
    path.write_text(json.dumps({"goal": _goal()}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_step_request(path)


def test_the_convenience_path_refuses_unknown_keywords(tmp_path):
    loop, _ = _loop(tmp_path)
    with pytest.raises(TypeError):
        run_goal_step(
            loop, GID, _proposal(), readings={CAP: True}, not_a_real_option=1
        )


def test_the_convenience_path_runs_one_gated_step(tmp_path):
    loop, body = _loop(tmp_path, verifier=_Verifier())
    report = run_goal_step(
        loop,
        GID,
        _proposal(),
        readings={CAP: True},
        state_root=tmp_path,
        preconditions=(CAP,),
    )
    assert report["outcome"] == OUTCOME_COMPLETED
    assert body.submitted() == 1
