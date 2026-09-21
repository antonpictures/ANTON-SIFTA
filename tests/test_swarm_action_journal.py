"""D3b: durable action journal -- write-before-submit, restart, torn tail, tampering.

Every test uses ``tmp_path`` as the state directory. Nothing here touches the
live ``.sifta_state``, the network, or the wall clock.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_action_journal import (  # noqa: E402
    GENESIS_HASH,
    JOURNAL_FILENAME,
    ActionJournal,
    JournalError,
)
from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalLoop,
    LifecycleError,
    LifecycleLedger,
    ManualClock,
)

SHA = "sha256:" + "b" * 64


def _gid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3b.goal.{label}"))


def _aid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3b.action.{label}"))


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


def _proposal(label: str, goal_label: str) -> dict:
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
    """An adapter that can be told to die mid-submit and that watches the journal."""

    adapter_id = "nav2"

    def __init__(self, journal=None, *, fail: bool = False, receipt: str = "receipt-1") -> None:
        self.journal = journal
        self.fail = fail
        self.receipt = receipt
        self.submit_calls = 0
        self.intent_seen_at_submit = None

    def probe(self):
        return {}

    def observe(self, cursor):
        return {}

    def submit(self, action):
        self.submit_calls += 1
        if self.journal is not None:
            row = self.journal.intent(action["action_id"])
            self.intent_seen_at_submit = None if row is None else row.seq
        if self.fail:
            raise RuntimeError("body died mid-submit")
        return self.receipt

    def status(self, action_id):
        return {}

    def cancel(self, action_id):
        return True

    def recover(self, checkpoint):
        return True


def _loop(state_dir, adapter: _Adapter, journal: ActionJournal, goal: str = "root") -> GoalLoop:
    return GoalLoop(
        graph=[_goal(goal)],
        adapter=AdapterBinding.bind("nav2", adapter, capability_revision=SHA),
        clock=ManualClock(),
        journal=journal,
    )


# --- write ordering -----------------------------------------------------------


def test_the_intent_is_durable_before_the_adapter_is_asked_to_act(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    adapter = _Adapter()
    loop = _loop(tmp_path, adapter, journal)
    adapter.journal = journal
    loop.propose(_proposal("act", "root"))

    outcome = loop.submit(_aid("act"))

    # The adapter itself saw the intent row already on disk when it was called.
    assert adapter.intent_seen_at_submit == outcome["intent_seq"]
    assert journal.intent(_aid("act")) is not None
    assert outcome["outcome"] == "accepted"
    assert journal.submit_state(_aid("act")) == "accepted"


def test_the_journal_file_exists_and_holds_the_intent_after_a_successful_submit(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(), journal)
    loop.propose(_proposal("act", "root"))
    loop.submit(_aid("act"))

    lines = (tmp_path / JOURNAL_FILENAME).read_text().strip().splitlines()

    assert len(lines) == 2
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds == ["intent", "submit"]


def test_a_loop_without_a_journal_refuses_to_submit(tmp_path: Path) -> None:
    adapter = _Adapter()
    loop = GoalLoop(
        graph=[_goal("root")],
        adapter=AdapterBinding.bind("nav2", adapter, capability_revision=SHA),
        clock=ManualClock(),
    )
    loop.propose(_proposal("act", "root"))

    with pytest.raises(LifecycleError) as excinfo:
        loop.submit(_aid("act"))

    assert excinfo.value.code == "NO_JOURNAL"
    assert adapter.submit_calls == 0


def test_submitting_an_action_that_was_never_proposed_is_refused(tmp_path: Path) -> None:
    loop = _loop(tmp_path, _Adapter(), ActionJournal(tmp_path))

    with pytest.raises(LifecycleError) as excinfo:
        loop.submit(_aid("ghost"))

    assert excinfo.value.code == "UNKNOWN_ACTION"


# --- crash mid-submit ---------------------------------------------------------


def test_a_crash_mid_submit_leaves_the_intent_and_an_unknown_outcome(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(fail=True), journal)
    loop.propose(_proposal("act", "root"))

    with pytest.raises(RuntimeError, match="body died") as excinfo:
        loop.submit(_aid("act"))

    assert "body died" in str(excinfo.value)
    assert journal.intent(_aid("act")) is not None
    assert journal.submit_state(_aid("act")) == "attempted"
    assert loop.lifecycle.state(_aid("act")) == "unknown"
    assert loop.lifecycle.is_terminal("unknown") is False


def test_an_adapter_that_returns_no_receipt_is_not_a_success(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(receipt=""), journal)
    loop.propose(_proposal("act", "root"))

    outcome = loop.submit(_aid("act"))

    assert outcome["outcome"] == "attempted_unknown"
    assert outcome["effect_receipt_id"] is None
    assert loop.lifecycle.state(_aid("act")) == "unknown"


def test_a_crashed_submit_is_in_flight_and_may_not_be_resent(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    adapter = _Adapter(fail=True)
    loop = _loop(tmp_path, adapter, journal)
    loop.propose(_proposal("act", "root"))

    with pytest.raises(RuntimeError):
        loop.submit(_aid("act"))
    in_flight = journal.in_flight()
    assert [row.action_id for row in in_flight] == [_aid("act")]

    with pytest.raises(JournalError) as excinfo:
        loop.submit(_aid("act"))

    assert excinfo.value.code == "RESEND_FORBIDDEN"
    assert adapter.submit_calls == 1


def test_the_resend_refusal_names_every_action_that_needs_reconciliation(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(fail=True), journal)
    loop.propose(_proposal("act", "root"))

    with pytest.raises(RuntimeError):
        loop.submit(_aid("act"))

    assert journal.resend_forbidden() == (_aid("act"),)


# --- the intent written before a crash in the caller --------------------------


def test_an_intent_written_but_never_submitted_is_not_a_duplicate_claim(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(), journal)
    loop.propose(_proposal("act", "root"))
    # Simulate a process that died between the intent append and the adapter call.
    journal.append("intent", _aid("act"), goal_id=_gid("root"), payload={"partial": True})

    assert journal.submit_state(_aid("act")) == "unattempted"
    assert [row.action_id for row in journal.unattempted()] == [_aid("act")]

    outcome = loop.submit(_aid("act"))

    assert len(journal.history(_aid("act"))) == 2  # the reused intent, then the submit
    assert outcome["outcome"] == "accepted"
    assert journal.intents()[-1].seq == outcome["intent_seq"]


# --- restart ------------------------------------------------------------------


def test_a_restarted_body_replays_what_the_dead_one_did(tmp_path: Path) -> None:
    first = ActionJournal(tmp_path, clock=ManualClock(utc="2026-01-01T00:00:00Z"))
    loop = _loop(tmp_path, _Adapter(fail=True), first)
    loop.propose(_proposal("act", "root"))
    with pytest.raises(RuntimeError):
        loop.submit(_aid("act"))

    second = ActionJournal(tmp_path)

    assert len(second.rows) == 2
    assert second.submit_state(_aid("act")) == "attempted"
    assert [row.action_id for row in second.in_flight()] == [_aid("act")]
    assert second.summary()["chain_ok"] is True


def test_sequence_numbers_never_reuse_after_a_restart(tmp_path: Path) -> None:
    first = ActionJournal(tmp_path)
    first.append("note", _aid("act"), payload={"n": 1})
    first.append("note", _aid("act"), payload={"n": 2})

    second = ActionJournal(tmp_path)
    row = second.append("note", _aid("act"), payload={"n": 3})

    assert [r.seq for r in second.rows] == [1, 2, 3]
    assert row.seq == 3


def test_a_verified_action_is_no_longer_in_flight_after_restart(tmp_path: Path) -> None:
    first = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(), first)
    loop.propose(_proposal("act", "root"))
    loop.submit(_aid("act"))
    first.append("result", _aid("act"), goal_id=_gid("root"), payload={"status": "succeeded"})

    second = ActionJournal(tmp_path)

    assert second.in_flight() == ()
    assert second.resend_forbidden() == ()


# --- integrity ----------------------------------------------------------------


def test_every_row_chains_onto_the_one_before_it(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("note", _aid("a"), payload={"n": 1})
    journal.append("note", _aid("b"), payload={"n": 2})

    rows = journal.rows

    assert rows[0].prev_hash == GENESIS_HASH
    assert rows[1].prev_hash == rows[0].row_hash
    assert rows[0].row_hash != rows[1].row_hash


def test_a_torn_final_line_is_reported_and_never_becomes_a_row(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("intent", _aid("act"), goal_id=_gid("root"), payload={"i": 1})
    with open(tmp_path / JOURNAL_FILENAME, "ab") as handle:
        handle.write(b'{"seq": 2, "at_utc": "2026-01-01T00:00:00Z", "kind": "subm')

    report = ActionJournal(tmp_path).replay()

    assert report.torn_lines == 1
    assert report.tampered_lines == 0
    assert len(report.rows) == 1
    assert report.chain_ok is True


def test_a_torn_tail_does_not_hide_the_complete_rows_before_it(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    loop = _loop(tmp_path, _Adapter(fail=True), journal)
    loop.propose(_proposal("act", "root"))
    with pytest.raises(RuntimeError):
        loop.submit(_aid("act"))
    with open(tmp_path / JOURNAL_FILENAME, "ab") as handle:
        handle.write(b'{"seq": 3, "at_utc": "2026-')

    restarted = ActionJournal(tmp_path)

    assert restarted.torn_lines == 1
    assert restarted.submit_state(_aid("act")) == "attempted"
    assert [row.action_id for row in restarted.in_flight()] == [_aid("act")]


def test_a_torn_tail_can_be_repaired_explicitly(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("note", _aid("act"), payload={"n": 1})
    with open(tmp_path / JOURNAL_FILENAME, "ab") as handle:
        handle.write(b'{"seq": 2, "at_u')

    restarted = ActionJournal(tmp_path)
    discarded = restarted.repair_torn_tail()

    assert discarded > 0
    assert restarted.torn_lines == 0
    assert len(restarted.rows) == 1
    assert json.loads((tmp_path / JOURNAL_FILENAME).read_text().strip())["seq"] == 1


def test_an_edited_row_is_reported_as_tampering_not_as_a_crash(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("intent", _aid("act"), goal_id=_gid("root"), payload={"distance_m": 1.0})

    path = tmp_path / JOURNAL_FILENAME
    row = json.loads(path.read_text().strip())
    row["payload"]["distance_m"] = 40.0  # the action now claims a different distance
    path.write_text(json.dumps(row) + "\n")

    restarted = ActionJournal(tmp_path, tolerate_chain_break=True)
    report = restarted.replay()

    assert report.tampered_lines == 1
    assert report.torn_lines == 0
    assert report.rows == ()


def test_a_tampered_journal_is_refused_rather_than_trusted(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("intent", _aid("act"), goal_id=_gid("root"), payload={"distance_m": 1.0})

    path = tmp_path / JOURNAL_FILENAME
    row = json.loads(path.read_text().strip())
    row["payload"]["distance_m"] = 40.0
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(JournalError) as excinfo:
        ActionJournal(tmp_path).replay()

    assert excinfo.value.code == "ROW_TAMPERED"


def test_a_tampered_row_is_never_silently_truncated_as_if_it_were_torn(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("intent", _aid("act"), goal_id=_gid("root"), payload={"distance_m": 1.0})

    path = tmp_path / JOURNAL_FILENAME
    row = json.loads(path.read_text().strip())
    row["payload"]["distance_m"] = 40.0
    path.write_text(json.dumps(row) + "\n")

    restarted = ActionJournal(tmp_path, tolerate_chain_break=True)
    restarted.replay()

    with pytest.raises(JournalError) as excinfo:
        restarted.repair_torn_tail()

    assert excinfo.value.code == "NOT_TORN"


def test_reordered_rows_break_the_chain(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("note", _aid("a"), payload={"n": 1})
    journal.append("note", _aid("b"), payload={"n": 2})

    path = tmp_path / JOURNAL_FILENAME
    lines = path.read_text().strip().splitlines()
    path.write_text("\n".join([lines[1], lines[0]]) + "\n")

    with pytest.raises(JournalError) as excinfo:
        ActionJournal(tmp_path).replay()

    assert excinfo.value.code == "CHAIN_BROKEN"


# --- row discipline -----------------------------------------------------------


def test_a_row_without_an_action_id_is_refused(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)

    with pytest.raises(JournalError) as excinfo:
        journal.append("note", "")

    assert excinfo.value.code == "MISSING_ACTION_ID"


def test_an_unknown_row_kind_is_refused(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)

    with pytest.raises(JournalError) as excinfo:
        journal.append("opinion", _aid("act"))

    assert excinfo.value.code == "UNKNOWN_KIND"


def test_the_summary_is_a_small_owned_dict_not_the_live_rows(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)
    journal.append("note", _aid("act"), payload={"n": 1})

    summary = journal.summary()

    assert summary["rows"] == 1
    assert summary["schema_version"] == "1.0.0"
    assert "note" not in json.dumps(summary)  # no live row bodies leak into the view


def test_the_journal_writes_only_inside_the_state_directory(tmp_path: Path) -> None:
    state = tmp_path / "state"
    journal = ActionJournal(state)
    journal.append("note", _aid("act"), payload={"n": 1})

    assert [p.name for p in sorted(state.iterdir())] == [JOURNAL_FILENAME]


def test_an_unknown_submit_state_is_none_not_a_guess(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path)

    assert journal.submit_state(_aid("never")) is None
    assert journal.latest(_aid("never")) is None
    assert journal.intent(_aid("never")) is None


def test_lifecycle_history_survives_a_legal_sequence(tmp_path: Path) -> None:
    ledger = LifecycleLedger()
    ledger.observe("a1", "accepted")
    ledger.observe("a1", "running")
    ledger.observe("a1", "succeeded")

    assert ledger.history("a1") == ("accepted", "running", "succeeded")
    assert ledger.unresolved() == ()
