import json
from pathlib import Path

from System.swarm_identity_life_grounding import (
    build_identity_life_packet,
    format_identity_life_grounding_for_prompt,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_empty_identity_life_grounding_does_not_crash(tmp_path):
    prompt = format_identity_life_grounding_for_prompt(state_dir=tmp_path)

    assert "LOCAL IDENTITY + LIFE GROUNDING" in prompt
    assert "Current owner/speaker:" in prompt
    assert "no recent owner day segments visible" in prompt
    assert "no recent Alice stigtime boundaries visible" in prompt


def test_identity_life_packet_separates_three_lanes(tmp_path):
    _write_jsonl(
        tmp_path / "architect_day_segments.jsonl",
        [
            {
                "label": "desk_work",
                "start_time": "9:00 AM",
                "end_time": "10:00 AM",
                "location": "desk",
                "context_note": "George typing at Alice keyboard",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "stigtime_log.jsonl",
        [
            {
                "kind": "STIGTIME_BOUNDARY",
                "ts": 1000.0,
                "stigtime_out": "idle",
                "stigtime_in": "thinking",
                "context": "cortex=alice-m5-cortex-8b-6.3gb",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "stigmergic_schedule.jsonl",
        [{"text": "learn Colombia history with George", "priority": 2, "done": False}],
    )

    packet = build_identity_life_packet(state_dir=tmp_path, now=1060.0)

    assert packet["truth_label"] == "IDENTITY_LIFE_GROUNDING_V1"
    assert any("desk_work" in item for item in packet["life_lanes"]["owner_life"])
    assert any("idle -> thinking" in item for item in packet["life_lanes"]["alice_life"])
    assert any("Colombia history" in item for item in packet["life_lanes"]["shared_agenda"])


def test_prompt_forbids_generic_owner_language(tmp_path):
    prompt = format_identity_life_grounding_for_prompt(state_dir=tmp_path)

    assert "prefer" in prompt and "direct second person" in prompt
    assert "stranger labels" in prompt
    assert "'an individual'" not in prompt
    assert "If asked 'who am I?', answer from owner genesis first" in prompt
    assert "do not invent a second human or unseen speaker" in prompt
    assert "ghost speaker" not in prompt
    assert "Two-body desk" in prompt
