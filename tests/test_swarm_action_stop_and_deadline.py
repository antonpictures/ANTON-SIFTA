"""D3e: owner stop, deadlines, and bounded revision.

What this file is trying to falsify, clause by clause, from the audit:

* a stop must not queue behind a sick organ -- a probe that hangs or raises
  cannot delay it, because a stop never calls probe or observe at all;
* a journal failure must not lose the stop -- the body stops first, the record
  is written second, and a write failure is reported rather than fatal;
* a restart must not reset the deadline or the spend -- both are read back from
  the frozen record and the journal, never from this process's memory;
* exhausted revisions must stop retrying -- a refusal, not a silent extra try;
* an acknowledged cancellation is not physical rest -- ``physical_rest`` stays
  false, with the frozen ``STOP_UNVERIFIED`` code, unless a separate verifier
  confirms named evidence.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "System") not in sys.path:
    sys.path.insert(0, str(ROOT / "System"))

from swarm_action_journal import (  # noqa: E402
    KIND_REVISION,
    KIND_STOP,
    ActionJournal,
)
from swarm_adaptive_goal_loop import (  # noqa: E402
    DEFAULT_MAX_REVISIONS,
    AdapterBinding,
    GoalLoop,
    ManualClock,
    NoAttemptsRemain,
    REASON_BUDGET_EXHAUSTED,
    REASON_EXPIRED,
    REASON_STOPPED_VERIFIED,
    REASON_STOP_REQUESTED,
    REASON_STOP_UNVERIFIED,
    REASON_TIMEOUT,
)

SHA = "sha256:2d1d055c42d2c8b9d8493bd0839c0169b3191b60ddbcc9891956b219eaa96769"
NOW = "2026-01-01T12:00:00Z"

AID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3e.action.dock"))
AID2 = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3e.action.second"))
GID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3e.goal.root"))
GID2 = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3e.goal.child"))


# --- fixtures shaped exactly like the frozen contracts ------------------------


def _goal(goal_id=GID, *, deadline_utc=None, budget=None, deps=()):
    return {
        "schema_version": "1.0.0",
        "goal_id": goal_id,
        "owner_provenance": {"source": "owner", "owner_authorized": True, "task_id": "t1"},
        "task_family": "nav",
        "desired_observable": "at_dock",
        "predicate": "at_pose",
        "deadline_utc": deadline_utc,
        "budget": budget,
        "dependency_ids": list(deps),
        "active_subgoal": None,
        "progress_condition": "progress",
        "failure_condition": "failure",
        "checkpoint_ref": None,
        "revision_history": [{"revision": 0, "at_utc": NOW, "change": "created"}],
        "created_at_utc": NOW,
    }


def _proposal(goal_id=GID, action_id=AID):
    return {
        "schema_version": "1.0.0",
        "action_id": action_id,
        "goal_id": goal_id,
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


class _Adapter:
    """A body that records what was asked of it, and can be made sick on demand."""

    def __init__(self, *, probe_mode="ok", cancel_answer=True):
        self.calls: list = []
        self.probe_mode = probe_mode
        self.cancel_answer = cancel_answer

    def probe(self):
        self.calls.append("probe")
        if self.probe_mode == "raise":
            raise RuntimeError("probe exploded")
        if self.probe_mode == "hang":
            raise AssertionError("a hung probe was invoked during a stop")
        return {"adapter_id": "dock_body", "ready": True}

    def observe(self, action_id):
        self.calls.append(("observe", action_id))
        return []

    def submit(self, proposal):
        self.calls.append(("submit", proposal["action_id"]))
        return {"receipt_id": "r-1", "status": "accepted", "at_utc": NOW}

    def status(self, action_id):
        self.calls.append(("status", action_id))
        return {"status": "succeeded", "at_utc": NOW}

    def cancel(self, action_id):
        self.calls.append(("cancel", action_id))
        if isinstance(self.cancel_answer, Exception):
            raise self.cancel_answer
        return self.cancel_answer

    def recover(self, action_id):
        self.calls.append(("recover", action_id))
        return {"status": "unknown"}


class _RestVerifier:
    """A V1-shaped verifier that either confirms named rest evidence or refuses."""

    verifier_id = "rest_verifier.v1"

    def __init__(self, *, verified=True):
        self.verified = verified
        self.requests: list = []

    def verify(self, request):
        self.requests.append(dict(request))
        if self.verified:
            return {
                "verified": True,
                "method": "adapter.posture_is_stopped",
                "detail": "wheel encoders report zero",
                "observation_ids": list(request["required_observation_ids"]),
                "verifier": self.verifier_id,
            }
        return {
            "verified": False,
            "method": "adapter.posture_is_stopped",
            "detail": "encoders still turning",
            "observation_ids": [],
            "verifier": self.verifier_id,
        }


def _loop(tmp_path, *, adap=None, clock=None, journal=True, rest_verifier=None, goals=None):
    body = adap if adap is not None else _Adapter()
    return GoalLoop(
        graph=goals if goals is not None else [_goal()],
        adapter=AdapterBinding.bind("dock_body", body, capability_revision=SHA),
        clock=clock if clock is not None else ManualClock(utc=NOW),
        journal=ActionJournal(tmp_path) if journal else None,
        rest_verifier=rest_verifier,
    ), body


def _running(tmp_path, **kw):
    """A loop with one action accepted and running -- the state a stop interrupts."""
    loop, body = _loop(tmp_path, **kw)
    loop.propose(_proposal())
    body.cancel_answer = kw.get("cancel_answer", True)
    loop.submit(AID)
    return loop, body


# --- deadline: a property of the record, not of this process ------------------


def test_goal_without_deadline_never_expires(tmp_path):
    loop, _ = _loop(tmp_path)
    status = loop.deadline_status(GID)
    assert status["expired"] is False
    assert status["deadline_utc"] is None
    assert status["reason_code"] is None


def test_future_deadline_is_open_and_past_deadline_is_expired(tmp_path):
    clock = ManualClock(utc=NOW)
    loop, _ = _loop(tmp_path, clock=clock, goals=[_goal(deadline_utc="2026-01-01T13:00:00Z")])
    assert loop.deadline_status(GID)["expired"] is False
    clock.advance(7200)
    status = loop.deadline_status(GID)
    assert status["expired"] is True
    assert status["reason_code"] == REASON_EXPIRED
    assert loop.expired_goals() == (GID,)


def test_restart_does_not_reset_the_deadline(tmp_path):
    clock = ManualClock(utc=NOW)
    goals = [_goal(deadline_utc="2026-01-01T13:00:00Z")]
    first, _ = _loop(tmp_path, clock=clock, goals=goals)
    assert first.deadline_status(GID)["expired"] is False
    # A fresh process, a fresh clock reading well past the same frozen deadline.
    later = ManualClock(utc="2026-01-01T14:00:00Z")
    second, _ = _loop(tmp_path, clock=later, goals=goals)
    assert second.deadline_status(GID)["expired"] is True
    assert second.blocked_state(GID)["blocked"] is False  # nothing spent yet


# --- revisions: bounded, journalled, and spend inherited across a restart -----


def test_revisions_are_bounded_by_the_default_and_then_block(tmp_path):
    loop, _ = _loop(tmp_path)
    loop.propose(_proposal())
    seen = []
    for _ in range(DEFAULT_MAX_REVISIONS):
        answer = loop.revise(AID, change="replan")
        assert answer["revised"] is True
        seen.append(answer["revision"])
    assert seen == [1, 2, 3]

    refused = loop.revise(AID, change="replan again")
    assert refused["revised"] is False
    assert refused["blocked"] is True
    assert refused["reason_code"] == REASON_BUDGET_EXHAUSTED
    assert refused["remaining"] == 0


def test_blocked_goal_is_idempotent_and_spends_nothing_further(tmp_path):
    loop, _ = _loop(tmp_path)
    loop.propose(_proposal())
    for _ in range(DEFAULT_MAX_REVISIONS):
        loop.revise(AID, change="replan")
    first = loop.revise(AID, change="one more")
    rows_after_first = len(loop.journal.rows)
    second = loop.revise(AID, change="and another")
    assert first["blocked"] is True and second["blocked"] is True
    assert second["idempotent"] is True
    assert second["reason_code"] == first["reason_code"] == REASON_BUDGET_EXHAUSTED
    assert len(loop.journal.rows) == rows_after_first  # no endless rows
    assert loop.revision_count(GID) == DEFAULT_MAX_REVISIONS


def test_goal_budget_names_its_own_revision_allowance(tmp_path):
    goals = [_goal(budget={"resource": "revisions", "amount": 1, "unit": "count"})]
    loop, _ = _loop(tmp_path, goals=goals)
    loop.propose(_proposal())
    assert loop.max_revisions(GID) == 1
    assert loop.revise(AID, change="replan")["revised"] is True
    refused = loop.revise(AID, change="replan")
    assert refused["reason_code"] == REASON_BUDGET_EXHAUSTED
    assert "1 of 1" in refused["detail"]


def test_unrelated_budget_resource_does_not_bound_revisions(tmp_path):
    goals = [_goal(budget={"resource": "joules", "amount": 1, "unit": "J"})]
    loop, _ = _loop(tmp_path, goals=goals)
    loop.propose(_proposal())
    assert loop.max_revisions(GID) == DEFAULT_MAX_REVISIONS


def test_restart_does_not_reset_spent_revisions(tmp_path):
    goals = [_goal(budget={"resource": "revisions", "amount": 2, "unit": "count"})]
    first, _ = _loop(tmp_path, goals=goals)
    first.propose(_proposal())
    assert first.revise(AID, change="replan")["revised"] is True

    second, _ = _loop(tmp_path, goals=goals)
    assert second.revision_count(GID) == 1  # inherited from the journal
    assert second.revise(AID, change="replan")["revised"] is True
    refused = second.revise(AID, change="replan")
    assert refused["reason_code"] == REASON_BUDGET_EXHAUSTED


def test_a_deadline_is_closed_only_once_it_is_passed(tmp_path):
    """The frozen law is `now > deadline`: the deadline second is still open."""
    clock = ManualClock(utc=NOW)
    goals = [_goal(deadline_utc="2026-01-01T13:00:00Z")]
    loop, _ = _loop(tmp_path, clock=clock, goals=goals)
    clock.advance(3600)
    assert loop.deadline_status(GID)["now_utc"] == "2026-01-01T13:00:00Z"
    assert loop.deadline_status(GID)["expired"] is False
    clock.advance(1)
    assert loop.deadline_status(GID)["expired"] is True


def test_expired_deadline_blocks_with_expired_not_budget(tmp_path):
    clock = ManualClock(utc=NOW)
    goals = [_goal(deadline_utc="2026-01-01T13:00:00Z")]
    loop, _ = _loop(tmp_path, clock=clock, goals=goals)
    loop.propose(_proposal())
    clock.advance(3601)
    answer = loop.revise(AID, change="replan")
    assert answer["revised"] is False
    assert answer["reason_code"] == REASON_EXPIRED
    assert "deadline" in answer["detail"]


def test_revision_row_is_journalled_and_block_survives_restart(tmp_path):
    goals = [_goal(budget={"resource": "revisions", "amount": 1, "unit": "count"})]
    loop, _ = _loop(tmp_path, goals=goals)
    loop.propose(_proposal())
    loop.revise(AID, change="replan")
    loop.revise(AID, change="replan")

    kinds = [row.kind for row in loop.journal.rows]
    assert kinds.count(KIND_REVISION) == 2
    blocked_rows = [r for r in loop.journal.rows if r.kind == KIND_REVISION and r.payload.get("blocked")]
    assert len(blocked_rows) == 1
    assert blocked_rows[0].payload["reason_code"] == REASON_BUDGET_EXHAUSTED
    assert blocked_rows[0].goal_id == GID

    restarted, _ = _loop(tmp_path, goals=goals)
    state = restarted.blocked_state(GID)
    assert state["blocked"] is True
    assert state["source"] == "journal"
    assert state["reason_code"] == REASON_BUDGET_EXHAUSTED


def test_require_attemptable_refuses_a_blocked_goal(tmp_path):
    goals = [_goal(budget={"resource": "revisions", "amount": 1, "unit": "count"})]
    loop, _ = _loop(tmp_path, goals=goals)
    loop.propose(_proposal())
    loop.revise(AID, change="replan")
    loop.revise(AID, change="replan")
    with pytest.raises(NoAttemptsRemain) as caught:
        loop.require_attemptable(GID)
    assert caught.value.code == REASON_BUDGET_EXHAUSTED
    assert caught.value.blocked["blocked"] is True


def test_require_attemptable_refuses_an_expired_goal_that_never_spent(tmp_path):
    clock = ManualClock(utc=NOW)
    goals = [_goal(deadline_utc="2026-01-01T13:00:00Z")]
    loop, _ = _loop(tmp_path, clock=clock, goals=goals)
    clock.advance(3601)
    with pytest.raises(NoAttemptsRemain) as caught:
        loop.require_attemptable(GID)
    assert caught.value.code == REASON_EXPIRED


def test_require_attemptable_allows_a_healthy_goal(tmp_path):
    loop, _ = _loop(tmp_path)
    assert loop.require_attemptable(GID)["blocked"] is False


def test_timeout_code_is_used_when_the_world_still_has_time(tmp_path):
    loop, _ = _loop(tmp_path)
    loop.propose(_proposal())
    assert loop.revise(AID, change="replan")["reason_code"] == REASON_TIMEOUT


# --- the owner stop -----------------------------------------------------------


def test_stop_calls_only_cancel_never_probe_or_observe(tmp_path):
    loop, body = _running(tmp_path)
    before = len(body.calls)

    report = loop.owner_stop(AID)

    after = body.calls[before:]
    assert [c for c in after if c == "cancel" or c[0] == "cancel"] == [("cancel", AID)]
    assert "probe" not in [c if isinstance(c, str) else c[0] for c in after]
    assert all(not (isinstance(c, tuple) and c[0] in ("observe", "status", "recover", "submit")) for c in after)
    assert report["probe_called"] is False
    assert body.probe_mode == "ok"  # the adapter was never even asked to be ready


def test_a_hanging_probe_cannot_delay_a_stop(tmp_path):
    """The probe would raise if it were called; the stop must not call it."""
    loop, body = _running(tmp_path, adap=_Adapter(probe_mode="hang"))
    body.probe_mode = "hang"
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is True
    assert "probe" not in [c if isinstance(c, str) else c[0] for c in body.calls]


def test_a_raising_probe_cannot_delay_a_stop(tmp_path):
    loop, body = _running(tmp_path, adap=_Adapter(probe_mode="raise"))
    body.probe_mode = "raise"
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is True
    assert report["stop_requested"] is True


def test_cancellation_acknowledgment_is_not_physical_rest(tmp_path):
    loop, _ = _running(tmp_path)
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is True
    assert report["physical_rest"]["confirmed"] is False
    assert report["physical_rest"]["reason_code"] == REASON_STOP_UNVERIFIED
    assert report["ledger_state"] == "cancelled"
    # An ack is not allowed to smuggle in a success claim.
    assert report["reason_code"] == REASON_STOP_REQUESTED


def test_physical_rest_requires_named_evidence_and_a_verifier(tmp_path):
    rest = _RestVerifier(verified=True)
    loop, _ = _running(tmp_path, rest_verifier=rest)
    report = loop.owner_stop(AID, rest_observation_ids=["obs-1", "obs-2"])
    assert report["physical_rest"]["confirmed"] is True
    assert report["physical_rest"]["reason_code"] == REASON_STOPPED_VERIFIED
    assert rest.requests[0]["predicted_postcondition"] == "stopped"
    assert rest.requests[0]["required_observation_ids"] == ["obs-1", "obs-2"]
    assert rest.requests[0]["action_id"] == AID


def test_a_verifier_that_refuses_leaves_rest_unconfirmed(tmp_path):
    rest = _RestVerifier(verified=False)
    loop, _ = _running(tmp_path, rest_verifier=rest)
    report = loop.owner_stop(AID, rest_observation_ids=["obs-1"])
    assert report["physical_rest"]["confirmed"] is False
    assert report["physical_rest"]["reason_code"] == REASON_STOP_UNVERIFIED
    assert "encoders still turning" in report["physical_rest"]["detail"]


def test_evidence_without_a_verifier_is_still_unverified(tmp_path):
    """Naming evidence is not the same as having it judged."""
    loop, _ = _running(tmp_path)
    report = loop.owner_stop(AID, rest_observation_ids=["obs-1"])
    assert report["physical_rest"]["confirmed"] is False
    assert report["physical_rest"]["reason_code"] == REASON_STOP_UNVERIFIED


def test_cancel_that_declines_leaves_state_unknown_not_cancelled(tmp_path):
    loop, body = _running(tmp_path)
    body.cancel_answer = False
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is False
    assert report["ledger_state"] == "unknown"
    assert report["physical_rest"]["confirmed"] is False
    assert report["cancel_error"]


def test_cancel_that_raises_still_records_the_stop(tmp_path):
    loop, body = _running(tmp_path)
    body.cancel_answer = RuntimeError("motor bus dropped")
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is False
    assert "motor bus dropped" in report["cancel_error"]
    assert report["ledger_state"] == "unknown"
    assert report["physical_rest"]["reason_code"] == REASON_STOP_UNVERIFIED


def test_stop_survives_a_journal_failure(tmp_path, monkeypatch):
    loop, body = _running(tmp_path)
    calls_at_stop = list(body.calls)

    def explode(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(loop.journal, "append", explode)
    report = loop.owner_stop(AID)

    assert ("cancel", AID) in body.calls[len(calls_at_stop) - 1 :] or ("cancel", AID) in body.calls
    assert report["acknowledged"] is True           # the stop happened
    assert report["ledger_state"] == "cancelled"
    assert "disk gone" in report["journal_error"]   # and the missing record is reported
    assert loop.last_stop(AID)["action_id"] == AID


def test_stop_is_journalled_with_its_truthful_rest_verdict(tmp_path):
    loop, _ = _running(tmp_path)
    loop.owner_stop(AID)
    rows = [r for r in loop.journal.rows if r.kind == KIND_STOP]
    assert len(rows) == 1
    assert rows[0].payload["acknowledged"] is True
    assert rows[0].payload["physical_rest"] is False
    assert rows[0].payload["physical_rest_code"] == REASON_STOP_UNVERIFIED
    assert rows[0].action_id == AID
    assert rows[0].goal_id == GID


def test_stop_works_without_a_journal_at_all(tmp_path):
    loop, _ = _loop(tmp_path, journal=False)
    loop.propose(_proposal())
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is True
    assert report["journal_error"] is None
    assert report["physical_rest"]["confirmed"] is False


def test_stop_of_a_never_submitted_action_is_honest(tmp_path):
    loop, _ = _loop(tmp_path)
    loop.propose(_proposal())
    report = loop.owner_stop(AID)
    assert report["acknowledged"] is True
    assert report["ledger_state"] == "cancelled"
    assert report["physical_rest"]["confirmed"] is False


def test_stop_of_a_finished_action_does_not_rewrite_its_ending(tmp_path):
    loop, body = _loop(tmp_path)
    loop.propose(_proposal())
    loop.submit(AID)
    loop.lifecycle.observe(AID, "succeeded", first=False)
    report = loop.owner_stop(AID)
    assert report["already_terminal"] is True
    assert report["ledger_state"] == "succeeded"
    assert report["acknowledged"] is True
    assert report["physical_rest"]["confirmed"] is False


def test_stop_does_not_claim_completion(tmp_path):
    loop, _ = _running(tmp_path)
    loop.owner_stop(AID)
    assert loop.completed == ()
    assert loop.unverified_successes() == ()
    assert loop.confirm(AID)["already_completed"] is False


def test_second_stop_is_reported_not_hidden(tmp_path):
    loop, body = _running(tmp_path)
    first = loop.owner_stop(AID)
    second = loop.owner_stop(AID)
    assert first["acknowledged"] is True and second["acknowledged"] is True
    assert body.calls.count(("cancel", AID)) == 2
    assert sum(1 for r in loop.journal.rows if r.kind == KIND_STOP) == 2


def test_stop_falls_back_to_the_journal_to_find_its_goal(tmp_path):
    loop, _ = _running(tmp_path)
    loop._proposals.clear()  # a restarted process has no in-memory proposal
    assert loop._goal_for_action(AID) == GID


def test_unknown_action_cannot_be_stopped_or_revised(tmp_path):
    loop, _ = _loop(tmp_path)
    with pytest.raises(Exception):
        loop.owner_stop("nobody-knows-this-action")
    with pytest.raises(Exception):
        loop.revise("nobody-knows-this-action", change="replan")
