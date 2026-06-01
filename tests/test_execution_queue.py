#!/usr/bin/env python3
"""r272: Alice's execution queue — done/running/next, her self-stabilization process diary."""
from System import swarm_execution_queue as q


def test_three_tense_queue(tmp_path):
    sifta = tmp_path / ".sifta_state"
    a = q.enqueue("buy asada fries", state_dir=sifta)
    q.enqueue("code Alice alive", state_dir=sifta)
    q.start(a["task_id"], state_dir=sifta)
    q.complete(a["task_id"], result="bought", state_dir=sifta)
    snap = q.queue_snapshot(state_dir=sifta)
    assert snap["counts"]["done"] == 1
    assert snap["counts"]["queued"] == 1
    assert snap["done"][0]["task"] == "buy asada fries"
    nxt = q.next_task(state_dir=sifta)
    assert nxt and nxt["task"] == "code Alice alive"
    blk = q.stabilize_block(state_dir=sifta)
    assert "EXECUTION QUEUE" in blk and "Next up" in blk


def test_running_then_next(tmp_path):
    sifta = tmp_path / ".sifta_state"
    a = q.enqueue("one", state_dir=sifta)
    q.enqueue("two", state_dir=sifta)
    q.start(a["task_id"], state_dir=sifta)
    snap = q.queue_snapshot(state_dir=sifta)
    assert snap["counts"]["running"] == 1 and snap["counts"]["queued"] == 1
    assert q.next_task(state_dir=sifta)["task"] == "two"  # queued head, not the running one


def test_fail_is_honest(tmp_path):
    sifta = tmp_path / ".sifta_state"
    t = q.enqueue("risky", state_dir=sifta)
    q.start(t["task_id"], state_dir=sifta)
    q.fail(t["task_id"], reason="boom", state_dir=sifta)
    snap = q.queue_snapshot(state_dir=sifta)
    assert snap["counts"]["failed"] == 1
    assert snap["failed"][0]["reason"] == "boom"


def test_empty_queue_block(tmp_path):
    assert q.stabilize_block(state_dir=tmp_path / ".sifta_state") == ""
