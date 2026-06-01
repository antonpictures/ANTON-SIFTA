#!/usr/bin/env python3
"""r274: body stabilization queue is the unified process field, not a silent fallback."""

from __future__ import annotations

import json

from System import swarm_alice_schedule_diary_awareness as awareness
from System import swarm_body_stabilization_queue as bodyq
from System import swarm_execution_queue as execq
from System import swarm_memory_card as memory_card


def test_body_queue_accepts_state_dir_and_folds_execution_queue(tmp_path):
    state = tmp_path / ".sifta_state"

    bodyq.add_queue_item(
        description="owner will buy asada fries because mom said eat well",
        kind="owner_carbon_plan",
        owner_plan=True,
        priority=0.8,
        state_dir=state,
    )
    execq.enqueue("code Alice alive", state_dir=state)

    snap = bodyq.get_current_queue(state_dir=state, include_processes=False)

    assert snap["truth_label"] == bodyq.TRUTH_LABEL
    assert snap["health"]["owner_plans"] == 1
    assert snap["execution_queue"]["snapshot"]["counts"]["queued"] == 1
    assert snap["execution_queue"]["next_task"]["task"] == "code Alice alive"
    assert "Execution queue" in snap["summary"]


def test_schedule_diary_awareness_loads_body_queue_not_fallback(tmp_path):
    state = tmp_path / ".sifta_state"
    bodyq.add_queue_item(
        description="stabilize after owner's store run",
        status="active",
        state_dir=state,
    )

    view = awareness.get_my_schedule_and_diary(state_dir=state)
    queue = view["body_stabilization_queue"]

    assert queue["truth_label"] == bodyq.TRUTH_LABEL
    assert queue["health"]["active_items"] == 1
    assert "not yet loaded" not in json.dumps(queue)


def test_pending_schedule_items_join_same_field(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    with (state / "stigmergic_schedule.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({
            "text": "George future talk",
            "priority": 0.7,
            "source": "provider_schedule",
            "done": False,
            "schedule_id": "s1",
        }) + "\n")

    snap = bodyq.get_current_queue(state_dir=state, include_processes=False)

    assert snap["pending_schedule_items"]
    assert snap["pending_schedule_items"][0]["text"] == "George future talk"


def test_missing_time_gap_writes_to_requested_state_dir(tmp_path):
    state = tmp_path / ".sifta_state"
    bodyq.incorporate_missing_time_gap(
        300,
        "I was dark and came back.",
        state_dir=state,
    )

    ledger = state / "body_stabilization_queue.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["kind"] == "power_cycle_recovery"
    assert rows[-1]["status"] == "active"


def test_owner_future_body_plan_is_captured_and_deduped(tmp_path):
    state = tmp_path / ".sifta_state"
    text = "I will stop typing and go to the store to buy asada fries because mom told me to eat well"

    first = bodyq.maybe_capture_owner_plan_from_text(text, state_dir=state, now=123.0)
    second = bodyq.maybe_capture_owner_plan_from_text(text, state_dir=state, now=124.0)

    assert first is not None
    assert first["kind"] == "owner_carbon_plan"
    assert first["owner_plan"] is True
    assert first["priority"] > 0.8
    assert second is not None
    assert second["status"] == "duplicate_recent"

    snap = bodyq.get_current_queue(state_dir=state, include_processes=False)
    assert snap["health"]["owner_plans"] == 1
    assert "Swimmer happiness" in snap["summary"]


def test_owner_alice_body_task_is_captured(tmp_path):
    state = tmp_path / ".sifta_state"
    row = bodyq.maybe_capture_owner_plan_from_text(
        "I have a task telling you to code Alice alive and optimize the queue",
        state_dir=state,
        now=125.0,
    )

    assert row is not None
    assert row["kind"] == "self_stabilization"
    assert row["owner_plan"] is False


def test_non_future_chatter_not_captured(tmp_path):
    state = tmp_path / ".sifta_state"
    row = bodyq.maybe_capture_owner_plan_from_text(
        "that movie was funny",
        state_dir=state,
    )

    assert row is None


def test_memory_card_surfaces_body_stabilization_queue(tmp_path):
    state = tmp_path / ".sifta_state"
    bodyq.add_queue_item(
        description="owner future body plan: eat well",
        kind="owner_carbon_plan",
        owner_plan=True,
        state_dir=state,
    )

    card = memory_card.compose_memory_card(state, token_budget=1200)
    prompt = memory_card.format_for_prompt(card)

    assert "BODY STABILIZATION QUEUE" in prompt
    assert "Swimmer happiness" in prompt
    assert "eat well" in prompt
