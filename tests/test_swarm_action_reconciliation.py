"""D3c: reconciliation -- ask the adapter what happened; never blindly resend.

The scenario under test is always the same shape: a body attempted an action and
died before learning the outcome. A restart must find out, not guess and not
repeat. Every test injects a temporary state directory and a scripted adapter.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_action_journal import ActionJournal, JournalError  # noqa: E402
from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalLoop,
    LifecycleError,
    ManualClock,
)

SHA = "sha256:" + "c" * 64


def _gid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3c.goal.{label}"))


def _aid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3c.action.{label}"))


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


class _ScriptedAdapter:
    """Adapter whose status answers are scripted per action id.

    ``answers`` maps an action id to a status payload, an Exception instance to
    raise, or None to answer with nothing at all.
    """

    adapter_id = "nav2"

    def __init__(self, *, answers=None, fail_submit: bool = False, receipt: str = "receipt-1") -> None:
        self.answers = dict(answers or {})
        self.fail_submit = fail_submit
        self.receipt = receipt
        self.submit_calls = 0
        self.status_calls: list = []

    def probe(self):
        return {}

    def observe(self, cursor):
        return {}

    def submit(self, action):
        self.submit_calls += 1
        if self.fail_submit:
            raise RuntimeError("body died mid-submit")
        return self.receipt

    def status(self, action_id):
        self.status_calls.append(action_id)
        answer = self.answers.get(action_id, None)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def cancel(self, action_id):
        return True

    def recover(self, checkpoint):
        return True


def _loop(state_dir, adapter, journal, goals=("root",)) -> GoalLoop:
    return GoalLoop(
        graph=[_goal(label) for label in goals],
        adapter=AdapterBinding.bind("nav2", adapter, capability_revision=SHA),
        clock=ManualClock(),
        journal=journal,
    )


def _attempted_after_crash(state_dir, labels=("act",)):
    """Leave the journal in the state a crash-between-submit-and-result creates."""
    journal = ActionJournal(state_dir)
    loop = _loop(state_dir, _ScriptedAdapter(fail_submit=True), journal)
    for label in labels:
        loop.propose(_proposal(label))
        with pytest.raises(RuntimeError):
            loop.submit(_aid(label))
    return journal


# --- the core law -------------------------------------------------------------


def test_a_restart_reconciles_an_attempted_action_by_asking_not_resending(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)

    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(answers={_aid("act"): {"status": "running"}})
    loop = _loop(tmp_path, adapter, journal)

    report = loop.reconcile()

    assert adapter.submit_calls == 0
    assert adapter.status_calls == [_aid("act")]
    assert report["reconciled"] == (
        {"action_id": _aid("act"), "status": "running", "resolved": False, "detail": None},
    )
    assert loop.lifecycle.state(_aid("act")) == "running"


def test_an_action_that_is_still_running_stays_unresendable_and_in_flight(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)

    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(answers={_aid("act"): {"status": "running"}})
    loop = _loop(tmp_path, adapter, journal)
    loop.reconcile()

    assert journal.in_flight()[0].action_id == _aid("act")
    assert journal.resend_forbidden() == (_aid("act"),)
    with pytest.raises(JournalError) as excinfo:
        loop.submit(_aid("act"))

    assert excinfo.value.code == "RESEND_FORBIDDEN"
    assert adapter.submit_calls == 0


def test_a_reconciled_terminal_result_closes_the_action(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)

    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "failed"}}), journal)

    report = loop.reconcile()

    assert report["reconciled"][0]["resolved"] is True
    assert report["still_in_flight"] == ()
    assert journal.in_flight() == ()
    assert loop.lifecycle.state(_aid("act")) == "failed"
    assert journal.latest(_aid("act"), "result").payload["via"] == "reconciliation"


def test_a_reconciled_terminal_action_is_never_resubmitted(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(answers={_aid("act"): {"status": "cancelled"}})
    loop = _loop(tmp_path, adapter, journal)
    loop.reconcile()

    with pytest.raises(JournalError) as excinfo:
        loop.submit(_aid("act"))

    assert excinfo.value.code == "RESEND_FORBIDDEN"
    assert adapter.submit_calls == 0


def test_reconciliation_never_calls_submit_across_a_whole_batch(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path, labels=("a", "b", "c"))
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter()
    loop = _loop(tmp_path, adapter, journal)

    report = loop.reconcile()

    assert adapter.submit_calls == 0
    assert len(adapter.status_calls) == 3
    assert len(report["reconciled"]) == 3


def test_reconcile_all_covers_every_in_flight_action(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path, labels=("a", "b"))
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(
        answers={_aid("a"): {"status": "failed"}, _aid("b"): {"status": "succeeded"}}
    )
    loop = _loop(tmp_path, adapter, journal)

    report = loop.reconcile()

    assert {entry["action_id"] for entry in report["reconciled"]} == {_aid("a"), _aid("b")}
    assert report["still_in_flight"] == ()


# --- refusing to guess --------------------------------------------------------


def test_a_missing_answer_is_unknown_not_success(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(), journal)  # status() answers nothing

    report = loop.reconcile()

    assert report["reconciled"][0]["status"] == "unknown"
    assert report["reconciled"][0]["resolved"] is False
    assert loop.lifecycle.state(_aid("act")) == "unknown"
    assert journal.in_flight()[0].action_id == _aid("act")


def test_an_invented_status_word_is_recorded_as_unknown_and_not_believed(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "totally_fine"}}), journal)

    report = loop.reconcile()

    entry = report["reconciled"][0]
    assert entry["status"] == "unknown"
    assert entry["resolved"] is False
    assert "totally_fine" in entry["detail"]
    row = journal.latest(_aid("act"), "status")
    assert row.payload["reported"] == "totally_fine"
    assert row.payload["outcome"] == "unknown"


def test_a_status_of_verified_is_not_a_lifecycle_state(tmp_path: Path) -> None:
    """'verified' is the verifier's word, not the adapter's."""
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "verified"}}), journal)

    report = loop.reconcile()

    assert report["reconciled"][0]["status"] == "unknown"
    assert loop.unverified_successes() == ()


def test_a_status_call_that_raises_leaves_the_action_unresolved_and_recorded(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(answers={_aid("act"): ConnectionError("no link")})
    loop = _loop(tmp_path, adapter, journal)

    report = loop.reconcile()

    entry = report["reconciled"][0]
    assert entry["resolved"] is False
    assert "status unavailable" in entry["detail"]
    assert "ConnectionError" in entry["detail"]
    assert journal.latest(_aid("act"), "status").payload["outcome"] == "status_unavailable"
    assert journal.in_flight()[0].action_id == _aid("act")


def test_reconciliation_without_a_journal_is_refused(tmp_path: Path) -> None:
    adapter = _ScriptedAdapter()
    loop = GoalLoop(
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", adapter, capability_revision=SHA),
        clock=ManualClock(),
    )

    with pytest.raises(LifecycleError) as excinfo:
        loop.reconcile()

    assert excinfo.value.code == "NO_JOURNAL"
    assert adapter.status_calls == []


def test_reconciling_an_action_with_no_intent_row_is_refused(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter()
    loop = _loop(tmp_path, adapter, journal)

    with pytest.raises(JournalError) as excinfo:
        loop.reconcile(_aid("ghost"))

    assert excinfo.value.code == "UNJOURNALLED_ACTION"
    assert adapter.status_calls == []


# --- provenance of a reconciled success ---------------------------------------


def test_a_reconciled_success_is_a_claim_that_the_verifier_has_not_confirmed(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "succeeded"}}), journal)

    report = loop.reconcile()

    assert report["reconciled"][0]["resolved"] is True
    assert loop.unverified_successes() == (_aid("act"),)
    assert loop.result(_aid("act"))["verified"] is False
    assert loop.result(_aid("act"))["via"] == "reconciliation"


def test_reconciliation_records_the_effect_receipt_when_the_adapter_supplies_one(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    answer = {"status": "succeeded", "effect_receipt_id": "eff-77"}
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): answer}), journal)

    loop.reconcile()

    assert journal.latest(_aid("act"), "status").payload["effect_receipt_id"] == "eff-77"


def test_a_partially_answered_batch_leaves_the_rest_in_flight(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path, labels=("a", "b"))
    journal = ActionJournal(tmp_path)
    adapter = _ScriptedAdapter(answers={_aid("a"): {"status": "failed"}, _aid("b"): None})
    loop = _loop(tmp_path, adapter, journal)

    report = loop.reconcile()

    assert report["reconciled"][0]["resolved"] is True
    assert report["reconciled"][1]["resolved"] is False
    assert report["still_in_flight"] == (_aid("b"),)


def test_reconciliation_survives_a_second_restart_as_a_durable_chain(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "failed"}}), journal)
    loop.reconcile()

    restarted = ActionJournal(tmp_path)  # replays and verifies the chain

    assert restarted.summary()["chain_ok"] is True
    assert restarted.torn_lines == 0
    assert restarted.tampered_lines == 0
    kinds = [row.kind for row in restarted.history(_aid("act"))]
    assert kinds == ["intent", "submit", "status", "result"]
    assert restarted.in_flight() == ()


def test_reconciling_twice_does_not_duplicate_a_result(tmp_path: Path) -> None:
    _attempted_after_crash(tmp_path)
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _ScriptedAdapter(answers={_aid("act"): {"status": "failed"}}), journal)

    loop.reconcile()
    second = loop.reconcile()

    assert second["reconciled"] == ()
    assert len([row for row in journal.history(_aid("act")) if row.kind == "result"]) == 1
