"""r873/r874 P1-E stigmergic life-event reminders."""

import json
import time

from System.swarm_owner_life_event_inference import (
    due_life_reminders,
    mark_reminder_fired,
    process_owner_turn,
    reminder_speech_for_row,
)


def _state(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    return state


def test_pizza_in_oven_schedules_row(tmp_path):
    state = _state(tmp_path)
    now = time.time()
    out = process_owner_turn(
        "I am putting a pizza in the oven",
        typed_turn=True,
        state_dir=state,
        now=now,
    )
    assert out["action"] == "scheduled"
    row = out["row"]
    assert row["source"] == "stigmergic_inference"
    assert float(row["due_ts"]) >= now + 12 * 60
    body = (state / "owner_body_events.jsonl").read_text(encoding="utf-8")
    assert "life_event_inferred" in body
    diary = (state / "alice_first_person_journal.jsonl").read_text(encoding="utf-8")
    assert "Dear diary" in diary
    assert "bridget" in diary or '"source": "bridget"' in diary


def test_explicit_40_minutes(tmp_path):
    state = _state(tmp_path)
    now = time.time()
    out = process_owner_turn(
        "pizza in the oven, 40 minutes",
        typed_turn=True,
        state_dir=state,
        now=now,
    )
    assert out["action"] == "scheduled"
    assert abs(float(out["due_ts"]) - (now + 40 * 60)) < 2.0


def test_instruction_range_and_owen_typo_uses_later_bound(tmp_path):
    state = _state(tmp_path)
    now = time.time()
    out = process_owner_turn(
        "I just put a pizza in the owen. Instructions read 22-25 minutes.",
        typed_turn=True,
        state_dir=state,
        now=now,
    )
    assert out["action"] == "scheduled"
    assert abs(float(out["due_ts"]) - (now + 25 * 60)) < 2.0


def test_already_took_it_out_closes(tmp_path):
    state = _state(tmp_path)
    sched = state / "stigmergic_schedule.jsonl"
    sched.write_text(
        json.dumps(
            {
                "text": "pizza in the oven",
                "priority": 2,
                "created": time.time(),
                "done": False,
                "source": "stigmergic_inference",
                "due_ts": time.time() + 600,
                "schedule_id": "abc123",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = process_owner_turn("already took it out", typed_turn=True, state_dir=state)
    assert out["action"] == "closed"


def test_plain_chat_no_row(tmp_path):
    state = _state(tmp_path)
    out = process_owner_turn("how are you today", typed_turn=True, state_dir=state)
    assert out["action"] == "no_event_detected"
    sched = state / "stigmergic_schedule.jsonl"
    assert not sched.exists() or sched.read_text(encoding="utf-8").strip() == ""


def test_media_lane_skips(tmp_path):
    state = _state(tmp_path)
    out = process_owner_turn(
        "pizza in the oven",
        typed_turn=False,
        media_lane=True,
        state_dir=state,
    )
    assert out["action"] == "skipped_media_or_empty"


def test_fired_reminder_writes_receipt(tmp_path):
    state = _state(tmp_path)
    sched = state / "stigmergic_schedule.jsonl"
    row = {
        "text": "pizza in the oven",
        "priority": 2,
        "created": time.time() - 1000,
        "done": False,
        "source": "stigmergic_inference",
        "due_ts": time.time() - 5,
        "schedule_id": "sched-pizza-1",
        "event_class": "pizza",
    }
    sched.write_text(json.dumps(row) + "\n", encoding="utf-8")
    due = due_life_reminders(state_dir=state, now=time.time())
    assert len(due) == 1
    speech = reminder_speech_for_row(due[0])
    assert "pizza" in speech.lower()
    receipt = mark_reminder_fired("sched-pizza-1", speech=speech, state_dir=state)
    assert receipt is not None
    assert (state / "stigmergic_schedule_receipts.jsonl").exists()
    rows = [json.loads(line) for line in sched.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["fired"] is True
    assert due_life_reminders(state_dir=state, now=time.time()) == []


def test_fired_reminder_does_not_refire(tmp_path):
    """r875 regression (Fable verifier): the r874 copy-mutation bug left
    fired=False on disk, so the 30s poll repeated the same reminder forever.
    After mark_reminder_fired, due_life_reminders must return nothing."""
    state = _state(tmp_path)
    sched = state / "stigmergic_schedule.jsonl"
    row = {
        "text": "pizza in the oven",
        "priority": 2,
        "created": time.time() - 1000,
        "done": False,
        "source": "stigmergic_inference",
        "due_ts": time.time() - 5,
        "schedule_id": "sched-pizza-2",
        "event_class": "pizza",
    }
    sched.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert len(due_life_reminders(state_dir=state, now=time.time())) == 1
    mark_reminder_fired("sched-pizza-2", speech="test", state_dir=state)
    # The fired flag must be ON DISK, not on a lost copy.
    on_disk = [json.loads(l) for l in sched.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert any(r.get("fired") is True for r in on_disk)
    assert due_life_reminders(state_dir=state, now=time.time()) == []


def test_fired_reminder_writes_bridget_diary(tmp_path):
    state = _state(tmp_path)
    sched = state / "stigmergic_schedule.jsonl"
    row = {
        "text": "pizza in the oven",
        "priority": 2,
        "created": time.time() - 1000,
        "done": False,
        "source": "stigmergic_inference",
        "due_ts": time.time() - 5,
        "schedule_id": "sched-pizza-3",
        "event_class": "pizza",
    }
    sched.write_text(json.dumps(row) + "\n", encoding="utf-8")
    speech = reminder_speech_for_row(row)
    mark_reminder_fired("sched-pizza-3", speech=speech, state_dir=state)
    diary = (state / "alice_first_person_journal.jsonl").read_text(encoding="utf-8")
    assert "Dear diary" in diary
    assert "reminded George" in diary
