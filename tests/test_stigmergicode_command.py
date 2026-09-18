from __future__ import annotations

from System.swarm_stigmergicode_command import (
    authenticate,
    claim_next_task,
    complete_task,
    enqueue_task,
    issue_pairing_ticket,
    pair_ticket,
    parse_command,
    release_task,
    write_task_handoff,
)


def test_command_parser_distinguishes_escape_and_bounded_task():
    assert parse_command("/stigmergicode") == ""
    assert parse_command("/STIGMERGICODE  fix the harness tests") == "fix the harness tests"
    assert parse_command("//stigmergicode literal") is None
    assert parse_command("hello /stigmergicode") is None


def test_pairing_is_one_use_and_session_is_hashed(tmp_path):
    ticket = issue_pairing_ticket(state_dir=tmp_path, now=10)
    session = pair_ticket(ticket, state_dir=tmp_path, now=11)
    assert authenticate(session, state_dir=tmp_path, now=12)
    assert not authenticate(ticket, state_dir=tmp_path, now=12)
    try:
        pair_ticket(ticket, state_dir=tmp_path, now=12)
    except PermissionError:
        pass
    else:
        raise AssertionError("pairing tickets must be one-use")


def test_task_queue_is_claimed_and_can_be_requeued(tmp_path):
    row = enqueue_task("run the bounded harness smoke test", source="test", state_dir=tmp_path, now=20)
    claimed = claim_next_task(state_dir=tmp_path, now=21)
    assert claimed and claimed["task_id"] == row["task_id"]
    released = release_task(claimed["task_id"], state_dir=tmp_path, reason="harness_boot_in_progress")
    assert released["status"] == "PENDING"
    claimed_again = claim_next_task(state_dir=tmp_path, now=22)
    opened = complete_task(claimed_again["task_id"], state_dir=tmp_path)
    assert opened["status"] == "OPENED"
    assert claim_next_task(state_dir=tmp_path, now=23) is None


def test_repeated_owner_delivery_is_idempotent_and_handoff_is_private(tmp_path):
    first = enqueue_task("inspect the camera adapter", source="talk_owner", state_dir=tmp_path, now=20)
    repeated = enqueue_task("inspect the camera adapter", source="talk_owner", state_dir=tmp_path, now=99)
    assert repeated["task_id"] == first["task_id"]
    claimed = claim_next_task(state_dir=tmp_path, now=21)
    assert claimed["task"] == "inspect the camera adapter"
    handoff = write_task_handoff(claimed, state_dir=tmp_path)
    assert handoff.stat().st_mode & 0o777 == 0o600
    payload = handoff.read_text(encoding="utf-8")
    assert "inspect the camera adapter" in payload
