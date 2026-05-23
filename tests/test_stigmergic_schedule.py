import json
from datetime import datetime, timedelta

from System.stigmergic_schedule import (
    add_from_alice_text,
    add_task,
    answer_query_for_alice,
    parse_schedule_write,
    pending_tasks,
    reschedule_first_matching,
    summary_for_alice,
)


def test_schedule_summary_surfaces_pending_tasks(tmp_path):
    schedule = tmp_path / "schedule.jsonl"
    due = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    add_task(
        "learn a new history lesson",
        due_ts=due.timestamp(),
        due="tomorrow at 10:00",
        repeat="daily for 10 days",
        priority=2,
        path=schedule,
    )

    summary = summary_for_alice(path=schedule)

    assert "STIGMERGIC SCHEDULE:" in summary
    assert "history lesson" in summary
    assert "repeat=daily for 10 days" in summary
    assert "not a guess" in summary


def test_pending_tasks_dedupes_same_text_and_due(tmp_path):
    schedule = tmp_path / "schedule.jsonl"
    due = datetime.now().timestamp() + 3600
    add_task("stretch", due_ts=due, path=schedule)
    add_task("stretch", due_ts=due, path=schedule)

    tasks = pending_tasks(path=schedule)

    assert len(tasks) == 1
    assert tasks[0]["text"] == "stretch"


def test_schedule_query_answers_stt_model_mishearing(tmp_path):
    schedule = tmp_path / "schedule.jsonl"
    due = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    add_task(
        "learn a new history lesson with George",
        due_ts=due.timestamp(),
        due="tomorrow at 10:00",
        repeat="daily for 10 days",
        priority=2,
        path=schedule,
    )

    reply = answer_query_for_alice("What do I have to model at 10am?", path=schedule)

    assert "10:00am" in reply
    assert "history lesson with George" in reply
    assert "daily for 10 days" in reply


def test_schedule_query_returns_empty_for_non_schedule_send():
    assert answer_query_for_alice("send a message to Carlton and say hello") == ""


def test_schedule_capability_reply_names_local_ledger(tmp_path):
    schedule = tmp_path / "schedule.jsonl"

    reply = answer_query_for_alice(
        "Do you have a schedule document where you can write what I have?",
        path=schedule,
    )

    assert ".sifta_state/stigmergic_schedule.jsonl" in reply
    assert "write to it with receipts" in reply
    assert "remind me to call Jeff" in reply


def test_plain_life_schedule_write_without_time(tmp_path):
    schedule = tmp_path / "schedule.jsonl"

    reply, row = add_from_alice_text(
        "Alice, add buy groceries to my schedule",
        path=schedule,
    )

    assert row is not None
    assert row["text"] == "buy groceries"
    assert row["source"] == "alice_schedule_protocol"
    assert "schedule_id" in row
    assert "Added to my schedule: buy groceries." == reply
    assert pending_tasks(path=schedule)[0]["text"] == "buy groceries"


def test_plain_life_schedule_write_with_due_time(tmp_path):
    schedule = tmp_path / "schedule.jsonl"

    reply, row = add_from_alice_text(
        "remind me to call Jeff tomorrow at 10am",
        priority=2,
        source="voice_test",
        path=schedule,
    )

    assert row is not None
    assert row["text"] == "call Jeff"
    assert row["priority"] == 2
    assert row["source"] == "voice_test"
    assert row["due"].startswith("tomorrow at 10")
    assert "Added to my schedule: call Jeff for tomorrow at 10" in reply


def test_schedule_meta_question_is_not_misparsed_as_write():
    item, due_ts, due = parse_schedule_write(
        "Do you have a schedule document where you can write in a schedule what I have?"
    )

    assert item == ""
    assert due_ts is None
    assert due == ""


def test_natural_phrasing_how_is_my_schedule_hits_deterministic_path(tmp_path):
    """Architect transcript 2026-05-08: 'How is my schedule looks like?' fell
    through to the LLM and produced ungrounded narration. The Decide regex must
    catch this shape so the deterministic loop runs."""
    schedule = tmp_path / "schedule.jsonl"

    reply_empty = answer_query_for_alice("How is my schedule looks like?", path=schedule)

    assert reply_empty
    assert "schedule ledger" in reply_empty
    assert "I do not see" in reply_empty


def test_natural_phrasing_what_does_my_schedule_look_like_hits_deterministic_path(tmp_path):
    schedule = tmp_path / "schedule.jsonl"
    due = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
    add_task(
        "review proposal with Daniel",
        due_ts=due.timestamp(),
        due="tomorrow at 2pm",
        priority=1,
        path=schedule,
    )

    reply = answer_query_for_alice("what does my schedule look like today", path=schedule)

    assert "review proposal with Daniel" in reply


def test_capability_query_do_you_have_access_to_my_schedule(tmp_path):
    """Architect transcript 2026-05-08: 'Do you have access to my schedule?'
    must be answered by the local capability path, not by an LLM that invents
    'Yes I have access to your schedule data.'"""
    schedule = tmp_path / "schedule.jsonl"

    reply = answer_query_for_alice("Do you have access to my schedule?", path=schedule)

    assert ".sifta_state/stigmergic_schedule.jsonl" in reply
    assert "0 pending items" in reply


def test_capability_query_can_you_see_my_calendar(tmp_path):
    schedule = tmp_path / "schedule.jsonl"

    reply = answer_query_for_alice("Can you see my calendar?", path=schedule)

    assert ".sifta_state/stigmergic_schedule.jsonl" in reply


def test_query_writes_read_receipt_to_receipts_ledger(tmp_path, monkeypatch):
    """Decide → Execute → Receipt: a successful read must leave a receipt row
    so Alice's reply is auditable, not just spoken."""
    import System.stigmergic_schedule as schedule_mod

    schedule = tmp_path / "schedule.jsonl"
    receipts = tmp_path / "schedule_receipts.jsonl"
    monkeypatch.setattr(schedule_mod, "_SCHEDULE_RECEIPTS", receipts)

    reply = answer_query_for_alice("how is my schedule", path=schedule)
    assert reply

    assert receipts.exists(), "expected schedule read to leave a receipt row"
    rows = [json.loads(line) for line in receipts.read_text("utf-8").splitlines() if line.strip()]
    assert rows, "expected at least one receipt row written"
    last = rows[-1]
    assert last["operation"] == "query"
    assert last["ok"] is True
    assert last["status"] == "NO_MATCH"
    assert last["kind"] == "lookup"
    assert last["matched_count"] == 0
    assert "schedule effector read receipt" in last["truth_note"]
    assert last["query_excerpt"].startswith("how is my schedule")
    assert "receipt_hash" in last


def test_capability_query_writes_read_receipt(tmp_path, monkeypatch):
    import System.stigmergic_schedule as schedule_mod

    schedule = tmp_path / "schedule.jsonl"
    receipts = tmp_path / "schedule_receipts.jsonl"
    monkeypatch.setattr(schedule_mod, "_SCHEDULE_RECEIPTS", receipts)

    reply = answer_query_for_alice("Do you have access to my schedule?", path=schedule)
    assert reply

    rows = [json.loads(line) for line in receipts.read_text("utf-8").splitlines() if line.strip()]
    assert rows
    assert rows[-1]["status"] == "CAPABILITY_REPLY"
    assert rows[-1]["kind"] == "capability"


def test_reschedule_first_matching_replaces_pending_entry(tmp_path):
    schedule = tmp_path / "schedule.jsonl"
    old_due = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    new_due = old_due + timedelta(days=1)
    add_task(
        "Colombia history class focusing on Simon Bolivar",
        due_ts=old_due.timestamp(),
        due="tomorrow at 10 am",
        priority=2,
        path=schedule,
    )

    row = reschedule_first_matching(
        ("history", "class", "Colombia"),
        due_ts=new_due.timestamp(),
        due="Tuesday at 10 am",
        path=schedule,
    )

    tasks = pending_tasks(path=schedule)
    assert row["text"] == "Colombia history class focusing on Simon Bolivar"
    assert len(tasks) == 1
    assert tasks[0]["due"] == "Tuesday at 10 am"
    assert "tomorrow at 10 am" not in summary_for_alice(path=schedule)
