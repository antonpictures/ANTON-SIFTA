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
