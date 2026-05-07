import json
from datetime import datetime
from pathlib import Path

from System.stigmergic_prediction_engine import (
    SCHEMA,
    TRUTH_LABEL,
    build_prediction,
    format_prediction_for_alice,
    latest_prediction,
    write_prediction,
)
from System.swarm_unified_stigmergic_field import build_unified_field


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _local_ts(year: int, month: int, day: int, hour: int, minute: int) -> float:
    return datetime(year, month, day, hour, minute).timestamp()


def test_prediction_uses_day_segments_as_schedule_prior(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    rows = []
    for day, ts in enumerate(
        [
            _local_ts(2026, 5, 5, 8, 58),
            _local_ts(2026, 5, 6, 8, 59),
            _local_ts(2026, 5, 7, 8, 55),
        ]
    ):
        rows.append(
            {
                "ts": ts,
                "local_date": f"2026-05-0{5 + day}",
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 30,
                "end_minute_of_day": 10 * 60,
                "segment_id": f"meal-{day}",
                "context_note": "breakfast / meal pattern",
            }
        )
    rows.append(
        {
            "ts": _local_ts(2026, 5, 7, 8, 30),
            "label": "desk_work",
            "start_minute_of_day": 11 * 60,
            "segment_id": "work-1",
        }
    )
    _write_jsonl(state / "architect_day_segments.jsonl", rows)

    row = build_prediction(state_dir=state, now=now, write=False)

    assert row["schema"] == SCHEMA
    assert row["truth_label"] == TRUTH_LABEL
    assert row["next_likely_segment"] == "meal"
    assert row["expected_start_min"] == 30
    assert row["confidence"] > 0.5
    assert row["basis_event_count"] == 4
    assert "architect_day_segments.jsonl" in row["source_ledgers"]


def test_future_explicit_schedule_can_override_segment_prior(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 50,
                "segment_id": "meal-later",
            }
        ],
    )
    _write_jsonl(
        state / "stigmergic_schedule.jsonl",
        [
            {
                "created": now - 60,
                "due_ts": now + 20 * 60,
                "done": False,
                "text": "appointment with Carlton",
                "schedule_id": "appt-1",
            }
        ],
    )

    row = build_prediction(state_dir=state, now=now, write=False)

    assert row["next_likely_segment"] == "appointment"
    assert row["expected_start_min"] == 20
    assert row["candidate_segments"][0]["receipts"] == ["appt-1"]


def test_prediction_writes_latest_json_and_append_ledger(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "phone_call",
                "start_minute_of_day": 9 * 60 + 10,
                "segment_id": "phone-1",
                "context_note": "scheduled phone call pattern",
            }
        ],
    )

    row = write_prediction(state_dir=state, now=now)

    assert row["next_likely_segment"] == "phone_call"
    assert (state / "stigmergic_prediction.json").exists()
    assert (state / "stigmergic_prediction.jsonl").exists()
    assert latest_prediction(state_dir=state)["trace_id"] == row["trace_id"]


def test_prediction_prompt_is_compact_and_truth_labeled(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "shopping",
                "start_minute_of_day": 9 * 60 + 15,
                "segment_id": "shop-1",
                "location": "store",
            }
        ],
    )

    prompt = format_prediction_for_alice(state_dir=state, now=now, write=False)

    assert "STIGMERGIC PREDICTION" in prompt
    assert TRUTH_LABEL in prompt
    assert "shopping" in prompt
    assert "in ~15 min" in prompt
    assert "live voice overrides" in prompt


def test_prediction_becomes_unified_field_signal(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    row = {
        "ts": now,
        "truth_label": TRUTH_LABEL,
        "next_likely_segment": "meal",
        "confidence": 0.81,
        "expected_start_min": 23,
        "expected_start_time": "9:23 AM",
        "basis_days": 3,
        "basis_event_count": 12,
    }
    state.mkdir(parents=True, exist_ok=True)
    (state / "stigmergic_prediction.json").write_text(json.dumps(row), encoding="utf-8")

    field = build_unified_field(state_dir=state, now=now, write=False)

    assert field["schedule_prediction"]["next_likely_segment"] == "meal"
    assert field["schedule_prediction"]["confidence"] == 0.81
    assert field["signal_freshness"]["schedule_prediction"] > 0.8


def test_prompt_formatter_reuses_fresh_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    now = _local_ts(2026, 5, 7, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 20,
                "segment_id": "meal-1",
            }
        ],
    )

    assert "STIGMERGIC PREDICTION" in format_prediction_for_alice(state_dir=state, now=now, write=True)
    assert "STIGMERGIC PREDICTION" in format_prediction_for_alice(state_dir=state, now=now + 60, write=True)

    rows = (state / "stigmergic_prediction.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
